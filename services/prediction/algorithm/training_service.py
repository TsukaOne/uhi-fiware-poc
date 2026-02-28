"""
UHI Training Service

Standalone service responsible for:
  - Resolving input layer paths from Orion-LD
  - Collecting training samples (windowed, memory-safe)
  - Training the XGBoost UHI model
  - Persisting model artifacts and reporting metrics back to Orion-LD

Architecture principle:
  - Completely decoupled from the prediction service
  - All input paths resolved from Orion at runtime (no hardcoded paths)
  - Training runs in a background thread to keep the API non-blocking
  - Training state is exposed via /training/status
"""

import os
import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import joblib
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.windows import Window
from sklearn.model_selection import train_test_split
import xgboost as xgb
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from algorithm.domain.layer_decoder import LayerDecoder,LAYER_SPECS

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# Training defaults (all overridable per-request)
DEFAULT_SAMPLE_RATE   = float(os.getenv("TRAINING_SAMPLE_RATE",  "0.005"))
DEFAULT_N_ESTIMATORS  = int(os.getenv("TRAINING_N_ESTIMATORS",   "500"))
DEFAULT_MAX_DEPTH     = int(os.getenv("TRAINING_MAX_DEPTH",       "8"))
DEFAULT_LEARNING_RATE = float(os.getenv("TRAINING_LEARNING_RATE", "0.05"))
DEFAULT_USE_GPU       = os.getenv("TRAINING_USE_GPU", "false").lower() == "true"

# Processing constants
NODATA_THRESHOLD = -1e10
CHUNK_ROWS       = 2048
CHUNK_COLS       = 2048
_NATIVE_LAYERS = {"ndvi", "ndwi"}


# ---------------------------------------------------------------------------
# Training state — thread-safe singleton
# ---------------------------------------------------------------------------
class TrainingState:
    """
    Thread-safe container for the current training job state.
    Single instance shared between the API router and the background thread.
    """

    def __init__(self):
        self._lock   = threading.Lock()
        self._status = "idle"       # idle | running | success | failed
        self._started_at: Optional[datetime] = None
        self._finished_at: Optional[datetime] = None
        self._metrics: dict  = {}
        self._error: Optional[str] = None
        self._config: dict   = {}
        

    # ── Setters (always under lock) ──────────────────────────────────

    def start(self, config: dict):
        with self._lock:
            self._status      = "running"
            self._started_at  = datetime.now(timezone.utc)
            self._finished_at = None
            self._metrics     = {}
            self._error       = None
            self._config      = config

    def succeed(self, metrics: dict):
        with self._lock:
            self._status      = "success"
            self._finished_at = datetime.now(timezone.utc)
            self._metrics     = metrics

    def fail(self, error: str):
        with self._lock:
            self._status      = "failed"
            self._finished_at = datetime.now(timezone.utc)
            self._error       = error

    # ── Snapshot (under lock, returns plain dict for JSON serialisation) ─

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "status":      self._status,
                "started_at":  self._started_at.isoformat() if self._started_at  else None,
                "finished_at": self._finished_at.isoformat() if self._finished_at else None,
                "duration_seconds": (
                    (self._finished_at - self._started_at).total_seconds()
                    if self._started_at and self._finished_at else None
                ),
                "config":  self._config,
                "metrics": self._metrics,
                "error":   self._error,
            }

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._status == "running"





# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class TrainingConfig(BaseModel):
    """
    Training hyperparameters and options.
    All fields have defaults but can be overridden per-request.
    """
    sample_rate:   float = Field(DEFAULT_SAMPLE_RATE,   gt=0, le=1,
                                 description="Fraction of valid pixels to sample (0–1)")
    n_estimators:  int   = Field(DEFAULT_N_ESTIMATORS,  gt=0,
                                 description="Number of XGBoost trees")
    max_depth:     int   = Field(DEFAULT_MAX_DEPTH,     gt=0, le=20,
                                 description="Max tree depth")
    learning_rate: float = Field(DEFAULT_LEARNING_RATE, gt=0,
                                 description="XGBoost learning rate (eta)")
    use_gpu:       bool  = Field(DEFAULT_USE_GPU,
                                 description="Use CUDA GPU for training")
    force_recache: bool  = Field(False,
                                 description="Ignore existing sample cache and resample")


class TrainingResponse(BaseModel):
    status:  str
    message: str
    job_id:  Optional[str] = None


class TrainingStatusResponse(BaseModel):
    status:           str
    started_at:       Optional[str]
    finished_at:      Optional[str]
    duration_seconds: Optional[float]
    config:           dict
    metrics:          dict
    error:            Optional[str]



# ---------------------------------------------------------------------------
# Preprocessor
# ---------------------------------------------------------------------------

class UHIPreprocessor:
    """
    Windowed raster reader and sample collector.
    Never loads a full raster into RAM — processes chunk by chunk.
    """

    def __init__(self, ref_path: Path):
        with rasterio.open(ref_path) as src:
            self.ref_transform = src.transform
            self.ref_crs       = src.crs
            self.ref_shape     = (src.height, src.width)
        self._decoder = LayerDecoder()
        logger.info(
            f"Reference grid : {self.ref_shape[0]}×{self.ref_shape[1]} pixels"
        )

    # ── Low-level readers ────────────────────────────────────────────

    def _read_native(self, path: Path, window: Window) -> np.ndarray:
        """Read a window from a raster already on the reference grid."""
        with rasterio.open(path) as src:
            return src.read(1, window=window, out_dtype=np.float32)

    def _read_reprojected(self, path: Path, window: Window) -> np.ndarray:
        """Read a window from a raster on a different grid and reproject it."""
        h, w      = window.height, window.width
        dst       = np.empty((h, w), dtype=np.float32)
        bounds    = rasterio.windows.bounds(window, self.ref_transform)
        dst_tf    = rasterio.transform.from_bounds(*bounds, width=w, height=h)

        with rasterio.open(path) as src:
            reproject(
                source       = rasterio.band(src, 1),
                destination  = dst,
                src_transform= src.transform,
                src_crs      = src.crs,
                dst_transform= dst_tf,
                dst_crs      = self.ref_crs,
                resampling   = Resampling.bilinear,
            )
        return dst
    
    def _read_and_decode_window(
        self,
        layer_name: str,
        path: Path,
        window: Window,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Read a window from the given layer and decode it to physical values.    
        """
        raw = (
            self._read_native(path, window)
            if layer_name in _NATIVE_LAYERS
            else self._read_reprojected(path, window)
        )
        decoded, nodata_mask = self._decoder.decode(
            raw=raw,
            layer_name=layer_name,
            raster_path=str(path),
        )
        return decoded, nodata_mask

    def _read_chunk_parallel(
        self,
        paths: dict[str, Path],
        window: Window
    ) -> dict[str, np.ndarray]:
        """
        Read all layers for one chunk in parallel (I/O-bound → ThreadPoolExecutor).
        native_layers : set of layer names already on the reference grid.
        """
        def _load(layer_name: str, path: Path):
            return layer_name, self._read_and_decode_window(layer_name, path, window)

        results: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        with ThreadPoolExecutor(max_workers=min(len(paths), 6)) as pool:
            futures = [pool.submit(_load, n, p) for n, p in paths.items()]
            for fut in futures:
                name, result = fut.result()
                results[name] = result

        return results

    # ── Sample collection ────────────────────────────────────────────

    def collect_samples(
        self,
        paths: dict[str, Path],
        lst_rural: float,
        sample_rate: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Walk the full raster extent chunk by chunk.
        Return (X, y) where y = LST_pixel - LST_rural (UHI in °C/K).

        Memory cost at any point in time = one chunk × n_layers × 4 bytes.
        For CHUNK_ROWS=2048, CHUNK_COLS=2048, 5 layers → ~80 MB.
        """
        total_rows, total_cols = self.ref_shape
        X_chunks, y_chunks = [], []
        rng = np.random.default_rng(42)

        n_total = (
            ((total_rows + CHUNK_ROWS - 1) // CHUNK_ROWS) *
            ((total_cols + CHUNK_COLS - 1) // CHUNK_COLS)
        )
        logger.info(f"Collecting samples: {n_total} chunks ({CHUNK_ROWS}×{CHUNK_COLS})")

        processed = 0
        for row0 in range(0, total_rows, CHUNK_ROWS):
            for col0 in range(0, total_cols, CHUNK_COLS):
                row1 = min(row0 + CHUNK_ROWS, total_rows)
                col1 = min(col0 + CHUNK_COLS, total_cols)
                h, w = row1 - row0, col1 - col0

                window = Window(col_off=col0, row_off=row0, width=w, height=h)
                decoded_layers = self._read_chunk_parallel(paths, window)

                valid = self._build_validity_mask(decoded_layers)

                n_valid = int(valid.sum())
                if n_valid == 0:
                    del decoded_layers
                    continue

                n_sample  = max(1, int(n_valid * sample_rate))
                valid_idx = np.flatnonzero(valid)
                chosen    = rng.choice(valid_idx, size=n_sample, replace=False)

                rr, cc       = np.unravel_index(chosen, (h, w))
                rr_g, cc_g   = rr + row0, cc + col0

                dist = np.sqrt(
                    (rr_g - total_rows / 2) ** 2 +
                    (cc_g - total_cols / 2) ** 2
                ).astype(np.float32)

                ndvi_data = decoded_layers["ndvi"][0]
                ndwi_data = decoded_layers["ndwi"][0]
                dtm_data = decoded_layers["dtm"][0]
                bh_data = decoded_layers["building_height"][0]
                lst_data = decoded_layers["lst"][0]

                X_chunk = np.column_stack([
                    ndvi_data.ravel()[chosen],
                    ndwi_data.ravel()[chosen],
                    dtm_data.ravel()[chosen],
                    bh_data.ravel()[chosen],
                    dist,
                ]).astype(np.float32)

                y_chunk = (lst_data.ravel()[chosen] - lst_rural).astype(np.float32)

                X_chunks.append(X_chunk)
                y_chunks.append(y_chunk)

                del decoded_layers, valid, X_chunk, y_chunk

                processed += 1
                if processed % 200 == 0:
                    logger.info(f"  {processed}/{n_total} chunks ({processed/n_total*100:.1f}%)")

        logger.info(f"Collection complete — {processed} chunks processed")
        return np.vstack(X_chunks), np.concatenate(y_chunks)

    @staticmethod
    def _build_validity_mask(
        decoded_layers: dict[str, tuple[np.ndarray, np.ndarray]],
    ) -> np.ndarray:
        """
        Combine nodata masks from all layers to build a final validity mask.
        A pixel is valid if it's valid in all layers and has a finite, positive LST
        """
        first_array = next(iter(decoded_layers.values()))[0]
        total_pixels = first_array.size

        valid = np.ones(first_array.shape, dtype=bool)

        logger.info(f"Total pixels: {total_pixels:,}")

        for layer_name, (decoded, nodata_mask) in decoded_layers.items():
            layer_valid_pixels = np.count_nonzero(~nodata_mask)
            layer_invalid_pixels = np.count_nonzero(nodata_mask)
            logger.info(
                f"[{layer_name.upper()}] "
                f"valid: {layer_valid_pixels:,} | "
                f"nodata: {layer_invalid_pixels:,} "
                f"({layer_invalid_pixels / total_pixels:.2%})"
            )
            valid &= ~nodata_mask

        
        after_nodata_valid = np.count_nonzero(valid)

        logger.info(
            f"After nodata intersection: "
            f"{after_nodata_valid:,} valid pixels "
            f"({after_nodata_valid / total_pixels:.2%})"
        )

        # Contrainte supplémentaire sur LST
        lst_data, _ = decoded_layers["lst"]
        valid &= np.isfinite(lst_data) & (lst_data > 0)

        return valid
# ---------------------------------------------------------------------------
# XGBoost model wrapper
# ---------------------------------------------------------------------------

FEATURE_NAMES = ["ndvi", "ndwi", "dtm", "building_height", "distance_to_center"]


class XGBoostUHIModel:
    """
    Thin wrapper around xgb.XGBRegressor with UHI-specific helpers.
    Keeps training logic out of the router.
    """

    def __init__(self, config: dict):
        self.config = config
        self.feature_names = FEATURE_NAMES
        self.avg_uhi: Optional[float] = None   # ← ajouter

        self.model = xgb.XGBRegressor(
            tree_method = "hist",
            device = "cuda" if config["use_gpu"] else "cpu",
            n_estimators = config["n_estimators"],
            max_depth  = config["max_depth"],
            learning_rate = config["learning_rate"],
            min_child_weight = 50,
            subsample = 0.8,
            colsample_bytree = 0.8,
            early_stopping_rounds = 50,
            eval_metric = "rmse",
            n_jobs = -1,
            random_state = 42,
            verbosity = 1,
        )

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> dict:
        """
        Split data, train with early stopping, return evaluation metrics.
        """
        self.avg_uhi = float(y.mean())
        self.uhi_min = float(y.min()) 
        self.uhi_max = float(y.max())

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        logger.info(
            f"Training XGBoost — {len(X_train):,} train / {len(X_test):,} test pixels"
        )

        self.model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=50,
        )

        train_r2   = float(self.model.score(X_train, y_train))
        test_r2    = float(self.model.score(X_test,  y_test))
        best_iter  = int(self.model.best_iteration)

        importance = pd.DataFrame({
            "feature":    self.feature_names,
            "importance": self.model.feature_importances_,
        }).sort_values("importance", ascending=False)

        metrics = {
            "train_r2":           round(train_r2,  4),
            "test_r2":            round(test_r2,   4),
            "best_iteration":     best_iter,
            "n_train_samples":    len(X_train),
            "n_test_samples":     len(X_test),
            "avg_uhi_celsius":    round(self.avg_uhi, 3),
            "uhi_min":            round(float(y.min()), 3),
            "uhi_max":            round(float(y.max()), 3),
            "feature_importance": importance.set_index("feature")["importance"]
                                            .round(4).to_dict(),
        }

        logger.info(f"Train R² : {train_r2:.4f} | Test R² : {test_r2:.4f}")
        return metrics

    def save(self, model_dir: Path) -> Path:
        """
        Persist the trained model as a single Joblib artifact.
        The file contains:
        - XGBoost model (sklearn wrapper)
        - feature names
        - training config
        - avg_uhi baseline
        - timestamp
        """

        if self.avg_uhi is None:
            raise RuntimeError("Model must be trained before saving.")

        model_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        model_path = model_dir / f"xgb_uhi_{timestamp}.joblib"

        artifact = {
            "model": self.model,
            "feature_names": self.feature_names,
            "avg_uhi": self.avg_uhi,
            "uhi_min":       self.uhi_min,
            "uhi_max":       self.uhi_max,   
            "config": self.config,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        joblib.dump(artifact, model_path, compress=3)

        # Maintain a symlink/alias to latest model
        latest_path = model_dir / "xgb_uhi_latest.joblib"
        joblib.dump(artifact, latest_path, compress=3)

        logger.info(f"Model saved → {model_path}")

        return model_path

    @staticmethod
    def load(model_dir: Path) -> "XGBoostUHIModel":
        """
        Load latest saved model from disk.
        """

        model_path = model_dir / "xgb_uhi_latest.joblib"

        if not model_path.exists():
            raise FileNotFoundError(f"No model found at {model_path}")

        artifact = joblib.load(model_path)

        instance = XGBoostUHIModel(config=artifact["config"])
        instance.model = artifact["model"]
        instance.feature_names = artifact["feature_names"]
        instance.avg_uhi = artifact["avg_uhi"]
        instance.uhi_min = artifact["uhi_min"]
        instance.uhi_max = artifact["uhi_max"]

        logger.info(f"Model loaded from {model_path}")

        return instance
        
    