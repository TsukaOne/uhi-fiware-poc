"""
Training Orchestrator — coordinates the full training pipeline.

Responsibilities:
  - Launch training in a background daemon thread
  - Pass all required dependencies explicitly (no global variables)
  - Report progress via TrainingState
  - Register the trained model in Orion via asyncio bridge

"""
from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

from algorithm.config import Settings
from algorithm.infrastructure.orion_publisher import OrionPublisher
from algorithm.training_service import TrainingState, UHIPreprocessor, XGBoostUHIModel

logger = logging.getLogger(__name__)

NODATA_THRESHOLD = -1e10


class TrainingOrchestrator:
    """
    Manages the lifecycle of a training job.

    All dependencies are injected at construction — no global state.
    This makes it testable: pass mock publisher and state in tests.
    """

    def __init__(
        self,
        settings: Settings,
        publisher: OrionPublisher,
        training_state: TrainingState,
    ) -> None:
        self._settings = settings
        self._publisher = publisher
        self._state = training_state

    def launch(
        self,
        paths: dict[str, Path],
        config: dict,
        event_loop: asyncio.AbstractEventLoop,
    ) -> threading.Thread:
        """
        Start the training job in a daemon thread.

        The event_loop is passed explicitly so the thread can schedule
        async Orion calls back onto it via run_coroutine_threadsafe.

        Returns the started thread (for test inspection if needed).
        """
        thread = threading.Thread(
            target=self._run,
            kwargs=dict(paths=paths, config=config, loop=event_loop),
            daemon=True,
            name="uhi-training-job",
        )
        thread.start()
        logger.info(f"Training thread started: {thread.name}")
        return thread

    def _run(
        self,
        paths: dict[str, Path],
        config: dict,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """
        Full training pipeline — runs in a daemon thread.

        Steps:
          1. Compute LST rural reference value from the LST raster
          2. Load cached samples or resample from scratch
          3. Train XGBoost model
          4. Persist model artifact to disk
          5. Register model entity in Orion (async → sync bridge)
        """
        try:
            logger.info("=== Training job started ===")
            # 1. Compute LST rural reference value from the LST raster
            lst_rural = self._compute_lst_rural_reference(paths["lst"])

            # 2. Load cached samples or resample from scratch
            X, y = self._load_or_collect_samples(paths, lst_rural, config)
            logger.info(f"Dataset: {X.shape[0]:,} pixels × {X.shape[1]} features")

            # 3. Train XGBoost model
            model = XGBoostUHIModel(config=config)
            metrics = model.train(X, y)

            # 4. Persist model artifact to disk
            saved_path = model.save(self._settings.model_path)
            
            # 5. Register model entity in Orion 
            entity_id = self._register_model_in_orion(
                saved_path, metrics, config, loop
            )

            # 6. Update state
            metrics["model_entity_id"] = entity_id
            self._state.succeed(metrics)
            logger.info("=== Training job completed successfully ===")

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            # Raise exception to trigger a retry
            logger.exception("Training job failed")
            # Update state to failed with error message
            self._state.fail(error_msg)

    def _compute_lst_rural_reference(self, lst_path: Path) -> float:
        """
        Read a 20×20 pixel window around the rural reference point
        and return the median LST value as the baseline temperature.
        """
        row_ref, col_ref = self._settings.rural_point
        window = Window(
            col_off=col_ref - 10, row_off=row_ref - 10,
            width=20, height=20,
        )
        with rasterio.open(lst_path) as src:
            patch = src.read(1, window=window).astype(float)

        lst_rural = float(np.nanmedian(patch))
        logger.info(f"LST rural reference: {lst_rural:.2f} K")
        return lst_rural

    def _load_or_collect_samples(
        self,
        paths: dict[str, Path],
        lst_rural: float,
        config: dict,
    ) -> tuple:
        """
        Return (X, y) training samples, loading from cache if available.

        Cache is bypassed when force_recache=True in config.
        """
        cache_file = self._settings.cache_path / "training_samples.npz"
        use_cache = cache_file.exists() and not config.get("force_recache", False)

        if use_cache:
            logger.info(f"Loading cached samples: {cache_file}")
            data = np.load(cache_file)
            return data["X"], data["y"]

        logger.info("Collecting samples from rasters…")
        preprocessor = UHIPreprocessor(ref_path=paths["ndvi"])
        X, y = preprocessor.collect_samples(
            paths=paths,
            lst_rural=lst_rural,
            sample_rate=config["sample_rate"],
        )
        self._settings.cache_path.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache_file, X=X, y=y)
        logger.info(f"Samples cached: {cache_file}")
        return X, y

    def _register_model_in_orion(
        self,
        model_path: Path,
        metrics: dict,
        config: dict,
        loop: asyncio.AbstractEventLoop,
    ) -> str:
        """
        Bridge from sync thread to async Orion call.

        Uses asyncio.run_coroutine_threadsafe to safely call the async
        publisher from within a daemon thread.
        """
        input_ids = list(self._settings.all_layer_entity_ids.values())

        future = asyncio.run_coroutine_threadsafe(
            self._publisher.publish_trained_model(
                model_path=model_path,
                metrics=metrics,
                config=config,
                input_entity_ids=input_ids,
            ),
            loop,
        )
        entity_id = future.result(timeout=30)
        logger.info(f"Model entity registered in Orion: {entity_id}")
        return entity_id