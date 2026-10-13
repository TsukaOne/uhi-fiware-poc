# Frontend — UHI Viewer

A **Vue 3 + CesiumJS** application showing the Urban Heat Islands of Brussels on a 3D globe. In production the same container's **nginx** serves the site and the map tiles, and is the only gateway to the prediction API and the basemap.

## Features

- **3D globe**: Cesium terrain, 3D buildings and trees, free-flight mode, sun simulation.
- **11 map layers**: UHI heatmap, RGB and NIR orthophotos, NDVI, NDWI, NDBI, LST, DTM, DSM, imperviousness and albedo. Each layer has its own opacity, a legend, and a swipe comparison.
- **Zone workflow**: draw a zone, read its statistics, place objects (trees, buildings, fountains, solar panels…), then predict the UHI.
- **Layer actions**: statistics and GeoTIFF download, for a whole layer or a drawn box. The photo layers (RGB, NIR) have no such actions.
- **Live sensors**: VLINDER and Sensors.community markers with temperature, humidity and wind.

## Where the data comes from

The app only calls same-origin paths:

| Path | Content | Development (Vite proxy) | Production (nginx) |
|---|---|---|---|
| `/tiles/<layer>/{z}/{x}/{y}.png` | Map layer tiles | → frontend container (`127.0.0.1:3000`) | `data/tiles`, mounted read-only |
| `/basemap/{z}/{x}/{y}.png` | CARTO basemap | → CARTO, key added by Vite | → CARTO, key added by nginx |
| `/prediction/*` | Prediction API | → `127.0.0.1:8002` | → `prediction:8000`, 5 allowed routes only |

The tiles use Cesium's `GeographicTilingScheme`: 512 px tiles, levels 10 to 16, limited to the Brussels extent. The constants in [useTileLayers.js](src/composables/Cesium/useTileLayers.js) must match those of [scripts/export_tiles.py](../../scripts/export_tiles.py). A layer's tiles folder is its `id` in [App.js](src/App.js).

The CARTO key is read from `CARTO_API_KEY` in the repository root `.env`:
- in development, by [vite.config.js](vite.config.js), on the Node side;
- in production, by nginx at container start, from [nginx.conf.template](nginx.conf.template).

It is never bundled into the browser code.

## Development

```bash
# from the repo root: prediction (8002) + frontend container serving the tiles (3000)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build prediction frontend

cd services/frontend
npm install
npm run dev
# -> http://127.0.0.1:5173
```

## Production build

The [Dockerfile](Dockerfile) builds in two stages:
1. `node:20-alpine` runs `npm run build`. `VITE_CESIUM_ION_TOKEN` is passed as a build argument.
2. `nginx:alpine` serves `dist/`. At start, the nginx image fills `${CARTO_API_KEY}` into the config template. Only `CARTO_*` variables are substituted.

## Project structure

```
frontend/
├── src/
│   ├── main.js                          # Vue entry point, Cesium token and request limits
│   ├── App.vue / App.js / App.css       # Root component, app state, layer definitions
│   ├── components/
│   │   ├── CesiumViewer/                # Globe setup, wires the Cesium composables
│   │   ├── LayerControls/               # Layer toggles, opacity, legends, sensors list
│   │   ├── SelectionOverlay/            # Highlight of the drawn zone
│   │   ├── ZoneInfoPanel/               # Zone statistics
│   │   ├── ZoneObjectsPanel/            # Drag-and-drop urban objects
│   │   └── PredictionPanel/             # Zone prediction and before/after comparison
│   ├── composables/
│   │   ├── App/                         # useWorkflow, useLayerInfo, useDownload, useDraggable
│   │   └── Cesium/                      # useTileLayers, useDrawing, usePredictionOverlay,
│   │                                    # useSensorMarkers, useSunSimulation, useCameraControls,
│   │                                    # useFlyMode, useRoofFunctions
│   └── services/
│       ├── api.js                       # fetch wrapper with readable errors
│       └── predictionApi.js             # /prediction endpoints
├── nginx.conf.template                  # Gateway: SPA, tiles, basemap proxy, API allow-list
├── vite.config.js                       # Dev server and proxies
├── Dockerfile
└── package.json
```

## Dependencies

- **Vue 3**: reactive UI
- **CesiumJS**: 3D globe
- **Vite** with **vite-plugin-cesium**: build and dev server
- **Font Awesome 6**: icons
