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

  LST  (température en °C, uint8 normalisé) :
    Encodé comme DTM : uint8 [0,254] → [MIN_TEMPERATURE, MAX_TEMPERATURE]
    Tags : MIN_TEMPERATURE / MAX_TEMPERATURE

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
    RANGE_UINT8     : uint8, encode une valeur avec plage [min, max] stockée en metadata
                      formule : valeur = pixel / 254 * (max - min) + min
                      nodata  : pixel == 255
                      tags min/max configurables via LayerSpec.min_tag / max_tag
    """
    FLOAT32_NATIVE = "float32_native"
    SPECTRAL_INDEX = "spectral_index"
    RANGE_UINT8 = "range_uint8"


@dataclass(frozen=True)
class LayerSpec:
    """
    Spécification de décodage pour un type de couche.

    For RANGE_UINT8 layers, min_tag/max_tag specify the raster metadata
    tag names that store the original value range (used for decoding).
    """
    name: str
    encoding: LayerEncoding
    nodata_in: float = 255.0
    nodata_out: float = np.nan
    min_tag: Optional[str] = None
    max_tag: Optional[str] = None


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
        encoding=LayerEncoding.RANGE_UINT8,
        min_tag="MIN_ELEVATION",
        max_tag="MAX_ELEVATION",
    ),
    "building_height": LayerSpec(
        name="BuildingHeight",
        encoding=LayerEncoding.FLOAT32_NATIVE,
        nodata_in=-9999.0,
        nodata_out=np.nan,
    ),
    "lst": LayerSpec(
        name="LST",
        encoding=LayerEncoding.RANGE_UINT8,
        min_tag="MIN_TEMPERATURE",
        max_tag="MAX_TEMPERATURE",
    ),
    "dsm": LayerSpec(
        name="DSM",
        encoding=LayerEncoding.FLOAT32_NATIVE,
        nodata_in=-9999.0,
        nodata_out=np.nan,
    ),
    "imperviousness": LayerSpec(
        name="Imperviousness",
        encoding=LayerEncoding.FLOAT32_NATIVE,
        nodata_in=-9999.0,
        nodata_out=np.nan,
    ),
    "ndbi": LayerSpec(
        name="NDBI",
        encoding=LayerEncoding.SPECTRAL_INDEX,
    ),
    "albedo": LayerSpec(
        name="Albedo",
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

        if spec.encoding == LayerEncoding.RANGE_UINT8:
            return self._decode_range_uint8(raw, spec, raster_path)

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
        logger.debug(f"Decoding {spec.name} as FLOAT32_NATIVE")
        data = raw.astype(np.float32)
        nodata_mask = (raw == spec.nodata_in) | ~np.isfinite(data)
        data[nodata_mask] = np.nan
        logger.debug(f"  nodata_mask: {nodata_mask.sum():,}")
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
        nodata_mask = (raw == int(spec.nodata_in)) | ~np.isfinite(raw)
        decoded = (raw.astype(np.float32) / 254.0) * 2.0 - 1.0
        decoded[nodata_mask] = np.nan
        return decoded, nodata_mask

    @staticmethod
    def _decode_range_uint8(
        raw: np.ndarray,
        spec: LayerSpec,
        raster_path: Optional[str],
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Décode un raster uint8 encodé sur une plage [min, max].

        Lit les tags min_tag/max_tag depuis les métadonnées du fichier :
          decode : valeur = pixel / 254 * (max - min) + min

        Fallback en passthrough si les métadonnées sont absentes.
        """
        nodata_mask = (raw == int(spec.nodata_in)) | ~np.isfinite(raw)

        value_min, value_max = LayerDecoder._read_range_tags(
            raster_path, spec.min_tag, spec.max_tag,
        )

        if value_min is not None and value_max is not None:
            decoded = (
                raw.astype(np.float32) / 254.0
                * (value_max - value_min)
                + value_min
            )
            logger.debug(
                f"{spec.name} decoded: [{value_min:.1f}, {value_max:.1f}] "
                f"from uint8 [{raw.min()}, {raw.max()}]"
            )
        else:
            logger.warning(
                f"{spec.name} raster has no {spec.min_tag}/{spec.max_tag} metadata. "
                "Using raw uint8 values as-is."
            )
            decoded = raw.astype(np.float32)

        decoded[nodata_mask] = np.nan
        return decoded, nodata_mask

    @staticmethod
    def _read_range_tags(
        raster_path: Optional[str],
        min_tag: Optional[str],
        max_tag: Optional[str],
    ) -> tuple[Optional[float], Optional[float]]:
        """
        Lit min_tag et max_tag depuis les métadonnées du fichier raster.
        Retourne (None, None) si absent.
        """
        if raster_path is None or min_tag is None or max_tag is None:
            return None, None

        try:
            with rasterio.open(raster_path) as src:
                tags = src.tags()
                value_min = tags.get(min_tag)
                value_max = tags.get(max_tag)

            if value_min is not None and value_max is not None:
                return float(value_min), float(value_max)

        except Exception as exc:
            logger.warning(f"Could not read metadata from '{raster_path}': {exc}")

        return None, None