# UHI Viewer — lightweight version

Interactive 3D viewer of the **Urban Heat Islands** of Brussels, built to be hosted on a small free server.

Visitors can:
- browse 11 map layers (UHI heatmap, NDVI, LST, orthophotos…);
- draw a zone and simulate the effect of trees, buildings or fountains on the heat;
- read live temperature sensors.

This branch (`free_publication`) only contains what has to be online. The full FIWARE platform lives on the **`main`** branch. That is where the data is prepared, with Orion-LD, MongoDB, ingestion, GeoServer and model training.

---

## Architecture

```
Internet ─► Caddy (HTTPS) ─► frontend (nginx) ─┬─ /             → the site (Vue 3 + CesiumJS)
                                               ├─ /tiles/       → data/tiles (static PNG map tiles)
                                               ├─ /basemap/     → CARTO basemap (API key added by nginx)
                                               └─ /prediction/  → prediction (FastAPI)
                                                                    ├─ data/processed  (rasters, read-only)
                                                                    ├─ data/models     (XGBoost model, read-only)
                                                                    └─ VLINDER / Sensors.community (outbound)
```

| Container | Role | Memory limit |
|---|---|---|
| `caddy` | HTTPS certificates and the only public entry point (ports 80/443) | 256 MB |
| `frontend` | Serves the site and the tiles; gates the API (method allow-list, rate limits) | 256 MB |
| `prediction` | Zone prediction, layer statistics, GeoTIFF download, live sensors | 4 GB |

### What moved where

| Feature | Full platform (`main`) | Lightweight version (this branch) |
|---|---|---|
| Map layers | GeoServer renders each image on demand | Pre-rendered tiles served by nginx |
| Sensors | Stored in Orion-LD / MongoDB | Kept in memory by `prediction`, `GET /sensors` |
| Layer file paths | Resolved from Orion entities | Fixed in `services/prediction/algorithm/config.py` |
| UHI legend range | Read from Orion | Constants in `services/frontend/src/App.js` |
| Ingestion, training, full-map prediction | Online | Run on `main`, then publish the results here |

---

## Data

`data/` is not tracked by git. The server needs:

| Path | Content | Size |
|---|---|---|
| `data/processed/` | The 9 input layers and the UHI heatmap (see `LAYER_FILES` and `UHI_HEATMAP_FILE` in [config.py](services/prediction/algorithm/config.py)) | ≈ 3.8 GB |
| `data/models/xgb_uhi_latest.joblib` | Trained XGBoost model | ≈ 3 MB |
| `data/tiles/` | Map tiles produced by `scripts/export_tiles.py` | ≈ 8–12 GB |

The other files of `data/processed/` (`lst.tif`, `rgb_masked.tif`, `nir_masked.tif`, `uhi_prediction_brussels_2024.tif`) and all of `data/raw/` are not needed online. `prediction` refuses to start and lists the missing files if one of the required files is absent.

---

## Configuration

Copy `.env.example` to `.env` and fill in:

| Variable | Used by | Purpose |
|---|---|---|
| `VITE_CESIUM_ION_TOKEN` | frontend build | Cesium terrain and geocoder |
| `CARTO_API_KEY` | nginx at runtime (Vite in dev) | Basemap key. It is added server-side and never reaches the browser |
| `DOMAIN` | Caddy | Public domain name, e.g. `uhi.example.com` |
| `TLS_EMAIL` | Caddy | Contact e-mail for Let's Encrypt |

---

## Run

**Locally, production build** — the site is at http://127.0.0.1:3000:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build prediction frontend
```

**Locally, with hot reload** — the containers above must be running. The site is at http://127.0.0.1:5173:
```bash
cd services/frontend
npm install
npm run dev
```

**On the server** — Caddy obtains the HTTPS certificate for `DOMAIN`:
```bash
docker compose up -d --build
```

---

## Updating the map tiles

The tiles are the exact images GeoServer renders on the full platform. To produce or refresh them:

1. Start GeoServer from the full platform:
   ```bash
   git switch main
   docker compose up -d geoserver
   git switch free_publication
   ```
   The container keeps running after switching back.
2. Export the tiles:
   ```bash
   python scripts/export_tiles.py                          # all layers, levels 10 to 16
   python scripts/export_tiles.py --layers uhi_prediction  # a single layer
   ```
   - Expect about 0.45 s per tile, which is roughly 13 h for all 11 layers.
   - The export is resumable: tiles already on disk are skipped. Delete a layer's folder to re-export it.
3. Copy `data/tiles/` to the server.

If you publish a new UHI heatmap or a new model, also update `UHI_MIN_CELSIUS` / `UHI_MAX_CELSIUS` in [App.js](services/frontend/src/App.js). They must match `uhi_min` / `uhi_max` of the model.

---

## Security notes

- Only Caddy publishes ports. `prediction` is reachable only through the nginx allow-list in [nginx.conf.template](services/frontend/nginx.conf.template): 5 routes, fixed HTTP methods, rate limits.
- Layer names are checked against a fixed list, so no file path ever comes from a request.
- Data volumes are mounted read-only.
- The CARTO key lives only in the server's `.env`. Browsers request `/basemap/z/x/y.png`, and nginx adds the key and verifies CARTO's certificate.
- [SECURITY_AUDIT.md](SECURITY_AUDIT.md) is the audit of the full platform and is kept for reference.

---

## Services

- [services/frontend](services/frontend/README.md) — Vue 3 + CesiumJS viewer, nginx gateway
- [services/prediction](services/prediction/README.md) — FastAPI zone prediction and sensors
- [scripts/export_tiles.py](scripts/export_tiles.py) — GeoServer → static tiles
