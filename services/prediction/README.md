# Prediction Service

FastAPI service behind the viewer's `/prediction/` routes. It provides four things:
- **Zone prediction**: runs the XGBoost model on a user-drawn polygon, with optional placed objects such as trees or buildings, and returns a colored PNG.
- **Statistics**: decoded statistics of the input layers, for a zone or for a whole layer.
- **Download**: a layer as a GeoTIFF, either full or cropped to a zone.
- **Live sensors**: latest readings of VLINDER and Sensors.community stations, kept in memory.

This service does not train the model and does not compute the full UHI map: both are done on the full platform (`main` branch), and their results are read from disk.

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/predict/zone` | `{geometry, objects[]}` → RGBA PNG (base64), bounds, UHI statistics |
| `POST` | `/predict/zone/stats` | `{geometry}` → mean/min/max/std of every layer in the zone |
| `POST` | `/predict/layer/stats` | `{layer, geometry?}` → statistics of one layer |
| `POST` | `/predict/download` | `{layer, geometry?}` → GeoTIFF, full or cropped |
| `GET` | `/sensors` | Latest readings of all sensor providers |
| `GET` | `/health` | Health check |

Accepted `layer` values are the 9 input layers and `uhi`, which is the full UHI heatmap. Any other name returns `422`.

## Data files

All paths are fixed in [config.py](algorithm/config.py) (`LAYER_FILES`, `UHI_HEATMAP_FILE`, `MODEL_FILE`). At startup the service checks that every file exists, and refuses to start if one is missing.

| Layer | File (in `DATA_PROCESSED_PATH`) |
|---|---|
| ndvi | `ndvi_brussels_2024.tif` |
| ndwi | `ndwi_brussels_2024.tif` |
| ndbi | `ndbi_brussels_2024.tif` |
| dtm | `dtm_brussels_2021.tif` |
| dsm | `dsm_brussels_2024.tif` |
| building_height | `building_height_brussels.tif` |
| imperviousness | `imperviousness_brussels_2024.tif` |
| albedo | `albedo_brussels_2024.tif` |
| lst | `lst_cog_2024.tif` |
| uhi (heatmap) | `uhi_xgb_heatmap_brussels_2024.tif` |
| model (in `MODEL_PATH`) | `xgb_uhi_latest.joblib` |

The rasters are uint8 COGs: values 0 to 254 hold the data and 255 is nodata. [layer_decoder.py](algorithm/domain/layer_decoder.py) converts them to physical values. For the UHI heatmap, the value is `pixel / 254 × (max − min) + min` in °C, where the range comes from its `VALUE_RANGE` tag.

## Model

The model takes 10 features: NDVI, NDWI, NDBI, DTM, DSM, building height, imperviousness, albedo, distance to water (computed from NDWI) and distance to park (computed from NDVI). It predicts the temperature gap with a rural reference point (LST_pixel − LST_rural, in °C).

For a zone prediction, placed objects first modify the input features around their position. The deltas are defined in `OBJECT_IMPACTS` in [zone_predictor.py](algorithm/application/zone_predictor.py). The model then predicts the pixels inside the polygon.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATA_PROCESSED_PATH` | `/data/processed` | Folder of the input rasters and heatmap |
| `MODEL_PATH` | `/data/models` | Folder of the trained model |
| `VLINDER_STATIONS` | 6 Brussels stations | Comma-separated Mooncake station IDs |
| `SENSOR_REFRESH_INTERVAL` | `600` | Seconds between two sensor refreshes |
| `SC_CENTER_LAT` / `SC_CENTER_LON` | `50.83653` / `4.38047` | Center of the Sensors.community query |
| `SC_RADIUS_KM` | `9.91` | Radius of the Sensors.community query |

## Project structure

```
prediction/
├── main.py                              # Composition root: wiring, startup checks, routers
├── Dockerfile
├── requirements.txt
└── algorithm/
    ├── config.py                        # Settings and data file names
    ├── api/
    │   ├── zone_router.py               # /predict/* endpoints
    │   └── sensor_router.py             # /sensors
    ├── application/
    │   └── zone_predictor.py            # Zone inference, statistics, object impacts
    ├── domain/
    │   └── layer_decoder.py             # uint8 raster values → physical units
    └── infrastructure/
        └── sensor_ingestion/
            ├── base_provider.py         # Provider interface
            ├── vlinder_provider.py      # VLINDER / Mooncake adapter
            ├── sensors_community_provider.py
            ├── models.py                # SensorReading, StationMetadata
            └── sensor_cache.py          # Periodic refresh, readings kept in memory
```

## Run alone

```bash
# from the repo root, without the other services
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build --no-deps prediction
# interactive API docs: http://127.0.0.1:8002/docs
```
In production, `/docs` is not exposed: nginx only forwards the routes the viewer uses.
