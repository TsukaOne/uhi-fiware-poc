"""
Export the map layers of the local GeoServer as static PNG tiles.

The tile grid is the one Cesium requests from a WMS server (GeographicTilingScheme:
2 x 1 tiles at level 0, each tile spanning 180 / 2**level degrees), so the saved
images are exactly what the viewer displayed. Tiles already on disk are skipped,
which makes the export resumable.

Usage:  python scripts/export_tiles.py [--layers uhi_prediction ndvi] [--max-level 15]
"""
from __future__ import annotations

import argparse
import math
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

GEOSERVER_WMS_URL = "http://localhost:8080/geoserver/uhi/wms"
WORKSPACE = "uhi"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "tiles"

LAYERS = [
    "uhi_prediction", "rgb", "nir", "ndvi", "ndwi", "dtm",
    "lst", "dsm", "ndbi", "imperviousness", "albedo",
]

BRUSSELS_EXTENT = (4.20, 50.75, 4.50, 50.92)  # west, south, east, north
MIN_LEVEL = 10
MAX_LEVEL = 16
TILE_SIZE_PX = 512
LEVEL_ZERO_TILE_DEGREES = 180.0
WEST_EDGE_DEGREES = -180.0
NORTH_EDGE_DEGREES = 90.0

WORKERS = 16
REQUEST_TIMEOUT_S = 60


def tile_degrees(level: int) -> float:
    return LEVEL_ZERO_TILE_DEGREES / 2 ** level


def tile_columns_and_rows(level: int) -> tuple[range, range]:
    west, south, east, north = BRUSSELS_EXTENT
    size = tile_degrees(level)
    columns = range(math.floor((west - WEST_EDGE_DEGREES) / size), math.floor((east - WEST_EDGE_DEGREES) / size) + 1)
    rows = range(math.floor((NORTH_EDGE_DEGREES - north) / size), math.floor((NORTH_EDGE_DEGREES - south) / size) + 1)
    return columns, rows


def tile_bbox(level: int, x: int, y: int) -> str:
    size = tile_degrees(level)
    west = WEST_EDGE_DEGREES + x * size
    north = NORTH_EDGE_DEGREES - y * size
    return f"{west},{north - size},{west + size},{north}"


def fetch_tile(layer: str, level: int, x: int, y: int) -> bytes:
    query = urlencode({
        "service": "WMS", "version": "1.1.1", "request": "GetMap",
        "layers": f"{WORKSPACE}:{layer}", "styles": "", "srs": "EPSG:4326",
        "bbox": tile_bbox(level, x, y), "width": TILE_SIZE_PX, "height": TILE_SIZE_PX,
        "format": "image/png", "transparent": "true",
    })
    with urlopen(f"{GEOSERVER_WMS_URL}?{query}", timeout=REQUEST_TIMEOUT_S) as response:
        body = response.read()
        if response.headers.get_content_type() != "image/png":
            raise RuntimeError(f"GeoServer error for {layer} {level}/{x}/{y}: {body[:300]!r}")
        return body


def export_tile(layer: str, level: int, x: int, y: int) -> None:
    tile_path = OUTPUT_DIR / layer / str(level) / str(x) / f"{y}.png"
    if tile_path.exists():
        return
    image = fetch_tile(layer, level, x, y)
    tile_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = tile_path.with_suffix(".part")
    partial_path.write_bytes(image)
    partial_path.replace(tile_path)


def export_layer(layer: str, max_level: int, pool: ThreadPoolExecutor) -> None:
    for level in range(MIN_LEVEL, max_level + 1):
        columns, rows = tile_columns_and_rows(level)
        tiles = [(layer, level, x, y) for x in columns for y in rows]
        started = time.perf_counter()
        list(pool.map(lambda tile: export_tile(*tile), tiles))
        print(f"{layer} level {level}: {len(tiles)} tiles in {time.perf_counter() - started:.0f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--layers", nargs="+", default=LAYERS, choices=LAYERS)
    parser.add_argument("--max-level", type=int, default=MAX_LEVEL)
    args = parser.parse_args()

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for layer in args.layers:
            export_layer(layer, args.max_level, pool)


if __name__ == "__main__":
    main()
