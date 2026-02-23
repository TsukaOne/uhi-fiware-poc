"""
BUILDING HEIGHT PROCESSOR

Generates a building height raster from UrbIS 3D BuildingFaces GeoPackage
using ROOFSURFACE only.

Pipeline:
- Filter TYPE == ROOFSURFACE
- Extract absolute Z from roof geometry
- Rasterize polygon IDs on DTM grid
- Compute minimum DTM per polygon
- Compute relative height = Z_abs - min(DTM_polygon)
- Clamp negative values to 0

Output:
- float32 GeoTIFF
- Same resolution, extent and CRS as DTM
- NoData preserved
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pyogrio
import rasterio
from rasterio.features import rasterize
from scipy import ndimage


logger = logging.getLogger(__name__)

NODATA_VALUE = -9999.0


def _extract_max_z(geom) -> Optional[float]:
    """Extract maximum Z from Polygon or MultiPolygon geometry."""
    if geom is None:
        return None

    z_values = []

    if geom.geom_type == "MultiPolygon":
        for poly in geom.geoms:
            z_values.extend([c[2] for c in poly.exterior.coords if len(c) == 3])

    return max(z_values) if z_values else None


def process_building_heights(
    gpkg_path: str,
    dtm_path: str,
    output_path: str,
    layer_name: str = "BuildingFaces"
) -> str:
    """
    Generate building relative height raster aligned on DTM grid.

    Args:
        gpkg_path: UrbIS 3D GeoPackage path
        dtm_path: DTM GeoTIFF path (reference grid)
        output_path: Output GeoTIFF path
        layer_name: GeoPackage layer name

    Returns:
        Output path
    """

    logger.info("Loading DTM reference grid...")

    with rasterio.open(dtm_path) as dtm:
        dtm_array = dtm.read(1)
        dtm_transform = dtm.transform
        dtm_crs = dtm.crs
        dtm_width = dtm.width
        dtm_height = dtm.height
        dtm_nodata = dtm.nodata

    logger.info("Loading GeoPackage (ROOFSURFACE only)...")

    gdf = pyogrio.read_dataframe(
        gpkg_path,
        layer=layer_name,
        columns=["TYPE"],
        on_invalid="ignore"
    )

    if gdf.crs != dtm_crs:
        gdf = gdf.to_crs(dtm_crs)

    # Semantic filtering
    gdf = gdf[gdf["TYPE"] == "ROOFSURFACE"]

    if gdf.empty:
        raise ValueError("No ROOFSURFACE features found.")

    logger.info(f"ROOFSURFACE count: {len(gdf)}")

    # Extract absolute Z
    logger.info("Extracting absolute roof elevation (Z)...")

    gdf["Z"] = gdf.geometry.apply(_extract_max_z)
    gdf = gdf.dropna(subset=["Z"])
    gdf = gdf[gdf.geometry.area > 0]

    if gdf.empty:
        raise ValueError("No valid geometries with Z found.")

    # Rasterize polygon IDs
    logger.info("Rasterizing polygon IDs on DTM grid...")

    polygon_ids = np.arange(1, len(gdf) + 1, dtype=np.int32)

    polygons_raster = rasterize(
        zip(gdf.geometry, polygon_ids),
        out_shape=(dtm_height, dtm_width),
        transform=dtm_transform,
        fill=0,
        dtype=np.int32,
        all_touched=False
    )

    mask_polygons = polygons_raster > 0

    # Compute minimum DTM per polygon
    logger.info("Computing minimum DTM per polygon...")

    dtm_safe = dtm_array.copy()
    if dtm_nodata is not None:
        dtm_safe[dtm_safe == dtm_nodata] = np.inf

    min_dtm_per_polygon = ndimage.minimum(
        dtm_safe,
        labels=polygons_raster,
        index=polygon_ids
    )

    dtm_min_raster = np.zeros_like(dtm_array, dtype=np.float32)
    dtm_min_raster[mask_polygons] = min_dtm_per_polygon[
        polygons_raster[mask_polygons] - 1
    ]

    # Compute relative height
    logger.info("Computing relative building height...")

    building_absolute = np.zeros_like(dtm_array, dtype=np.float32)
    building_absolute[mask_polygons] = gdf.Z.values[
        polygons_raster[mask_polygons] - 1
    ]

    building_height = np.full_like(
        building_absolute,
        NODATA_VALUE,
        dtype=np.float32
    )

    valid_mask = mask_polygons
    if dtm_nodata is not None:
        valid_mask &= (dtm_array != dtm_nodata)

    building_height[valid_mask] = (
        building_absolute[valid_mask] -
        dtm_min_raster[valid_mask]
    )

    # Physical constraint
    building_height[building_height < 0] = 0

    # Save raster
    logger.info("Writing output GeoTIFF...")

    profile = {
        "driver": "GTiff",
        "height": dtm_height,
        "width": dtm_width,
        "count": 1,
        "dtype": "float32",
        "crs": dtm_crs,
        "transform": dtm_transform,
        "nodata": NODATA_VALUE,
        "compress": "lzw"
    }

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(building_height, 1)
        dst.update_tags(
            LAYER_TYPE="BUILDING_HEIGHT",
            SOURCE_GPKG=Path(gpkg_path).name,
            SOURCE_DTM=Path(dtm_path).name,
            UNIT="meters",
            HEIGHT_TYPE="Relative to terrain",
            FILTER="ROOFSURFACE only"
        )

    logger.info(f"Building height raster saved to: {output_path}")

    return output_path
