"""
Layer Decoder — décode les rasters COG uint8 vers leurs valeurs physiques originales.
Conventions d'encodage (définies dans l'ingestion, respectées ici) :

  NDVI / NDWI  (indices spectraux [-1, 1]) :
    encode : uint8 = (valeur + 1) / 2 * 254    (255 = nodata)
    decode : valeur = (uint8 / 254) * 2 - 1

  DTM  (élévation en mètres, range variable) :
    L'ingestion encode en uint8 via process_dtm.
    On lit les métadonnées VALUE_MIN / VALUE_MAX pour reconstruire.
    Si absentes : fallback sur la plage [0, 254] → [0, 254] (passthrough).

  LST  (température en Kelvin, float32 natif) :
    Pas de COG uint8 dans l'ingestion actuelle — lu directement.

  BuildingHeight (hauteur en mètres, float32 natif) :
    Pas de COG uint8 dans l'ingestion actuelle — lu directement.

"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
import rasterio

logger = logging.getLogger(__name__)


class LayerEncoding(Enum):
    """
    Convention d'encodage d'un raster.

    FLOAT32_NATIVE  : raster déjà en float32, aucun décodage nécessaire
    SPECTRAL_INDEX  : uint8, encode un index spectral [-1, 1]
                      formule : valeur = (pixel / 254) * 2 - 1
                      nodata  : pixel == 255
    ELEVATION_UINT8 : uint8, encode une élévation avec plage stockée en metadata
                      formule : valeur = pixel / 254 * (max - min) + min
                      nodata  : pixel == 255
                      fallback: passthrough si métadonnées absentes
    """
    FLOAT32_NATIVE = "float32_native"
    SPECTRAL_INDEX = "spectral_index"
    ELEVATION_UINT8 = "elevation_uint8"


@dataclass(frozen=True)
class LayerSpec:
    """
    Spécification de décodage pour un type de couche.

    """
    name: str
    encoding: LayerEncoding
    nodata_in: float = 255.0
    nodata_out: float = np.nan


# ── Registre des specs par nom de couche ─────────────────────────────────────
#
# Clés = noms utilisés dans le dict paths de UHIPreprocessor.
# Pour ajouter un nouveau type de couche : ajouter une entrée ici.
# Aucun autre code ne change.

LAYER_SPECS: dict[str, LayerSpec] = {
    "ndvi": LayerSpec(
        name="NDVI",
        encoding=LayerEncoding.SPECTRAL_INDEX,
    ),
    "ndwi": LayerSpec(
        name="NDWI",
        encoding=LayerEncoding.SPECTRAL_INDEX,
    ),
    "dtm": LayerSpec(
        name="DTM",
        encoding=LayerEncoding.ELEVATION_UINT8,
    ),
    "building_height": LayerSpec(
        name="BuildingHeight",
        encoding=LayerEncoding.FLOAT32_NATIVE,
        nodata_in=-9999.0,
        nodata_out=np.nan,
    ),
    "lst": LayerSpec(
        name="LST",
        encoding=LayerEncoding.FLOAT32_NATIVE,
        nodata_in=-9999.0,
        nodata_out=np.nan,
    ),
}


class LayerDecoder:
    """
    Décode un tableau numpy uint8 vers les valeurs physiques float32
    correspondant au type de couche demandé.

    Utilisé par UHIPreprocessor après chaque lecture de fenêtre raster,
    avant la construction de la matrice de features X.
    """

    def decode(
        self,
        raw: np.ndarray,
        layer_name: str,
        raster_path: Optional[str] = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Décode un tableau brut vers float32 + masque nodata.

        Parameters
        ----------
        raw          : tableau numpy tel que lu par rasterio (uint8 ou float32)
        layer_name   : clé dans LAYER_SPECS ('ndvi', 'dtm', 'lst', ...)
        raster_path  : chemin du fichier source (nécessaire pour lire les
                       métadonnées VALUE_MIN/VALUE_MAX du DTM)

        Returns
        -------
        (decoded, nodata_mask)
          decoded     : float32 avec valeurs physiques, NaN sur les pixels nodata
          nodata_mask : bool array, True = pixel nodata
        """
        spec = LAYER_SPECS.get(layer_name)
        if spec is None:
            logger.warning(
                f"No LayerSpec for '{layer_name}' — treating as FLOAT32_NATIVE"
            )
            return raw.astype(np.float32), np.zeros_like(raw, dtype=bool)

        if spec.encoding == LayerEncoding.FLOAT32_NATIVE:
            return self._decode_native(raw, spec)

        if spec.encoding == LayerEncoding.SPECTRAL_INDEX:
            return self._decode_spectral_index(raw, spec)

        if spec.encoding == LayerEncoding.ELEVATION_UINT8:
            return self._decode_elevation(raw, spec, raster_path)

        raise NotImplementedError(f"Unknown encoding: {spec.encoding}")

    # ── Décodeurs privés ──────────────────────────────────────────────

    @staticmethod
    def _decode_native(
        raw: np.ndarray,
        spec: LayerSpec,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Pas de transformation — le raster est déjà en float32.
        Applique uniquement le masque nodata.
        """
        data = raw.astype(np.float32)
        nodata_mask = (raw == spec.nodata_in) | ~np.isfinite(data)
        data[nodata_mask] = np.nan
        return data, nodata_mask

    @staticmethod
    def _decode_spectral_index(
        raw: np.ndarray,
        spec: LayerSpec,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Décode un index spectral encodé en uint8.

        Formule inverse de l'ingestion :
          encode : uint8 = (valeur + 1) / 2 * 254
          decode : valeur = (uint8 / 254) * 2 - 1

        Plage résultante : [-1.0, 1.0]
        """
        nodata_mask = raw == int(spec.nodata_in)
        decoded = (raw.astype(np.float32) / 254.0) * 2.0 - 1.0
        decoded[nodata_mask] = np.nan
        return decoded, nodata_mask

    @staticmethod
    def _decode_elevation(
        raw: np.ndarray,
        spec: LayerSpec,
        raster_path: Optional[str],
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Décode une élévation encodée en uint8.

        Si les métadonnées VALUE_MIN / VALUE_MAX sont présentes dans le fichier :
          decode : valeur = pixel / 254 * (VALUE_MAX - VALUE_MIN) + VALUE_MIN

        Sinon (fallback) :
          Le raster est lu en passthrough — on avertit et on retourne float32 brut.
          Cela évite un crash silencieux avec des valeurs incorrectes.

        Les métadonnées sont écrites par process_dtm() dans l'ingestion.
        """
        nodata_mask = raw == int(spec.nodata_in)

        value_min, value_max = LayerDecoder._read_elevation_range(raster_path)

        if value_min is not None and value_max is not None:
            decoded = (
                raw.astype(np.float32) / 254.0
                * (value_max - value_min)
                + value_min
            )
            logger.debug(
                f"DTM decoded: [{value_min:.1f}, {value_max:.1f}] m "
                f"from uint8 [{raw.min()}, {raw.max()}]"
            )
        else:
            logger.warning(
                "DTM raster has no MIN_ELEVATION/MAX_ELEVATION  metadata. "
                "Using raw uint8 values as elevation. "
                "Add metadata in process_dtm() to fix this."
            )
            decoded = raw.astype(np.float32)

        decoded[nodata_mask] = np.nan
        return decoded, nodata_mask

    @staticmethod
    def _read_elevation_range(
        raster_path: Optional[str],
    ) -> tuple[Optional[float], Optional[float]]:
        """
        Lit VALUE_MIN et VALUE_MAX depuis les métadonnées du fichier raster.

        Retourne (None, None) si le fichier est absent ou si les
        métadonnées ne sont pas présentes.
        """
        if raster_path is None:
            return None, None

        try:
            with rasterio.open(raster_path) as src:
                tags = src.tags()
                value_min = tags.get("MIN_ELEVATION")
                value_max = tags.get("MAX_ELEVATION")

            if value_min is not None and value_max is not None:
                return float(value_min), float(value_max)

        except Exception as exc:
            logger.warning(f"Could not read elevation metadata from '{raster_path}': {exc}")

        return None, None