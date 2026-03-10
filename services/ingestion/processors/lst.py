"""
LST (LAND SURFACE TEMPERATURE) Processor

LST represents the temperature of the land surface, which is influenced by various factors such as solar radiation, atmospheric conditions, and surface properties. It is derived from satellite data and provides information about the thermal characteristics of the Earth's surface.

Output is a Cloud-Optimized GeoTIFF (COG) with:
- DEFLATE compression with horizontal predictor
- 512x512 internal tiles
- Internal overviews (pyramids) at 2x, 4x, 8x, 16x, 32x

Uses windowed processing for large files to avoid memory issues.
"""


import logging
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window
import numpy as np

from processors.cog import build_overviews,create_cog_profile,COG_BLOCKSIZE


logger = logging.getLogger(__name__)

TILE_SIZE = 2048

def process_lst(
    lst_path: str,
    output_path: str,
    tile_size: int = TILE_SIZE
):
    """
    Process LST to COG with uint8 normalization.
    Temperature values are scaled from [min_temp, max_temp] to [0, 254] (for visualization),
    with 255 reserved for nodata.

    Args: 
        lst_path: Land Surface Temperature tif file path
        output_path: Land Surface Temperature COG output path
        tile_size: Tile Size for COG 
    """
    logger.info(f"Converting LST to COG: {lst_path}")

    with rasterio.open(lst_path) as src:
        # Copy the profile of LST
        profile = src.profile.copy()

        # Use uint8 like other layers
        profile = create_cog_profile(profile, dtype="uint8")
        NODATA_VALUE = 255
        profile["nodata"] = NODATA_VALUE

        height = src.height
        width = src.width
        # First pass: find min/max for normalization
        valid_data = []
        for row_off in range(0, height, tile_size):
            for col_off in range(0, width, tile_size):
                #Create a window to read
                win_height = min(tile_size, height - row_off)
                win_width = min(tile_size, width - col_off)
                window = Window(col_off, row_off, win_width, win_height)
                
                data = src.read(1, window=window).astype(np.float32)

                # Filter out nodata (astype float32 allows np.isnan on integer sources)
                if src.nodata is not None:
                    mask = (data != src.nodata) & (~np.isnan(data))
                else:
                    mask = ~np.isnan(data)
                
                if mask.any():
                    valid_data.append(data[mask])
        
        if not valid_data:
            raise ValueError(f"No valid (non-nodata) pixels found in {lst_path}. Check that the file contains actual LST data.")

        all_valid = np.concatenate(valid_data)
        min_val = float(np.min(all_valid))
        max_val = float(np.max(all_valid))
        

        # Second pass: normalize and write
        with rasterio.open(output_path, "w", **profile) as dst:
            for row_off in range(0, height, tile_size):
                for col_off in range(0, width, tile_size):
                    #Create a window to read
                    win_height = min(tile_size, height - row_off)
                    win_width = min(tile_size, width - col_off)
                    window = Window(col_off, row_off, win_width, win_height)

                    data = src.read(1, window=window).astype(np.float32)

                    # Create mask for valid data
                    if src.nodata is not None:
                        valid_mask = (data != src.nodata) & (~np.isnan(data))
                    else:
                        valid_mask = ~np.isnan(data)
                    
                    # Normalize to [0, 254]
                    normalized = np.full(data.shape, NODATA_VALUE, dtype=np.uint8)
                    if valid_mask.any():
                        normalized[valid_mask] = np.clip(
                            ((data[valid_mask] - min_val) / (max_val - min_val)) * 254,
                            0,
                            254
                        ).astype(np.uint8)
                    
                    dst.write(normalized, 1, window=window)
            
            dst.update_tags(
                LAYER_TYPE="LST",
                SOURCE=lst_path,
                DATA_TYPE="Temperature",
                UNIT="celsius",
                MIN_TEMPERATURE=str(min_val),
                MAX_TEMPERATURE=str(max_val)
            )
    
    build_overviews(output_path, resampling=Resampling.average)

    logger.info(f"LST COG saved to: {output_path}")
    return output_path