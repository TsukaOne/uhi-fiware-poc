# Urban Heat Island (UHI) Monitoring Platform

A FIWARE-based microservice platform for monitoring and predicting **Urban Heat Islands** in Brussels. The system ingests multi-source geospatial data, trains an XGBoost machine-learning model on 10+ raster layers, generates heat-risk predictions, ingests real-time sensor data, and serves everything through an interactive 3D web viewer.

Built on [FIWARE Orion-LD](https://github.com/FIWARE/context.Orion-LD) (NGSI-LD Context Broker) as the central data backbone — all services communicate through Orion entities and subscriptions in a fully **event-driven** architecture.

---

## Architecture

### Global Data Flow

This diagram traces the complete journey of data from raw inputs to the browser:

```mermaid
flowchart LR
    subgraph "Raw Inputs"
        RGB[RGB Orthophoto<br/>6 GB GeoTIFF]
        NIR[NIR Orthophoto<br/>4 GB GeoTIFF]
        DTM_SRC[DTM Source]
        BLDG[Buildings Data]
        QGIS["QGIS Preprocessed<br/>albedo.tif | dsm.tif<br/>imperviousness.tif | ndbi.tif"]
    end

    subgraph "Ingestion Service :8001"
        DL[Download & Extract]
        OV1[Build Overviews]
        NDVI_C[Compute NDVI]
        NDWI_C[Compute NDWI]
        LST_C[Compute LST]
        BH[Building Height]
        COG[Output as COG<br/>uint8 + DEFLATE]
    end

    subgraph "Orion-LD :1026"
        E_LAYERS["GeoSpatialLayer x12<br/>(RGB, NIR, NDVI, NDWI,<br/>DTM, LST, BuildingHeight,<br/>DSM, Albedo, NDBI,<br/>Imperviousness ...)"]
        E_UHI[UHIHeatMap]
        E_SENSORS["TemperatureSensor<br/>(VLINDER + Sensors.community)"]
    end

    subgraph "Prediction Service :8002"
        RESOLVE[Resolve layer paths<br/>from Orion entities]
        TRAIN[Train XGBoost<br/>10 features + distance]
        PREDICT[Generate UHI<br/>heat-risk raster]
        ZONE[Zone Prediction<br/>+ object impacts]
        SENSOR_SYNC[Sensor Ingestion<br/>periodic sync]
    end

    subgraph "GeoServer Sync"
        PUB[Auto-publish layers<br/>via REST API]
    end

    subgraph GeoServer
        WMS["WMS 1.3.0<br/>CRS:84"]
    end

    subgraph Frontend
        CESIUM["CesiumJS Globe<br/>+ layer controls<br/>+ zone drawing<br/>+ sensor markers"]
    end

    RGB --> DL
    NIR --> DL
    DTM_SRC --> DL
    BLDG --> DL
    DL --> OV1
    OV1 --> NDVI_C --> COG
    OV1 --> NDWI_C --> COG
    OV1 --> LST_C --> COG
    OV1 --> BH --> COG
    QGIS -- "copy to<br/>data/raw/" --> COG

    COG --> E_LAYERS

    E_LAYERS -- "subscription" --> RESOLVE
    RESOLVE --> TRAIN
    RESOLVE --> PREDICT
    RESOLVE --> ZONE
    PREDICT --> E_UHI

    SENSOR_SYNC --> E_SENSORS

    E_LAYERS -- "subscription" --> PUB
    E_UHI -- "subscription" --> PUB
    PUB --> WMS --> CESIUM
    E_SENSORS --> CESIUM
```

### Service Communication

Orion-LD acts as the central message bus. Services register entities and subscribe to changes — no service calls another directly.

```mermaid
graph TB
    subgraph "Docker Compose Network"
        MONGO[(MongoDB 5.0)]
        ORION[Orion-LD<br/>Context Broker]
        GS[GeoServer<br/>WMS Server]

        ING["Ingestion Service<br/>FastAPI :8001"]
        PRED["Prediction Service<br/>FastAPI :8002"]
        SYNC["GeoServer Sync<br/>FastAPI (internal)"]
        FE["Frontend<br/>Vue + Cesium :3000"]

        VLINDER["VLINDER API<br/>(external)"]
        SC["Sensors.community<br/>(external)"]
    end

    MONGO --- ORION

    ING -- "1 create/update<br/>GeoSpatialLayer entities" --> ORION
    ORION -- "2 subscription notification<br/>(layer changed)" --> PRED
    PRED -- "3 query entity filePath" --> ORION
    PRED -- "4 create/update<br/>UHIHeatMap entity" --> ORION
    PRED -- "5 periodic sensor sync" --> ORION
    ORION -- "6 subscription notification<br/>(publishToGeoserver=true)" --> SYNC
    SYNC -- "7 REST API<br/>publish layer" --> GS
    FE -- "WMS GetMap" --> GS
    FE -- "proxy /prediction" --> PRED
    FE -- "proxy /orion" --> ORION

    VLINDER -.-> PRED
    SC -.-> PRED

    style ORION fill:#ff6b35,color:#fff,stroke:#ff6b35
    style MONGO fill:#4db33d,color:#fff,stroke:#4db33d
    style GS fill:#5b8c5a,color:#fff,stroke:#5b8c5a
    style ING fill:#3498db,color:#fff,stroke:#3498db
    style PRED fill:#9b59b6,color:#fff,stroke:#9b59b6
    style SYNC fill:#e67e22,color:#fff,stroke:#e67e22
    style FE fill:#2ecc71,color:#fff,stroke:#2ecc71
```

### XGBoost Prediction Pipeline

The ML model combines 8 raster features + 2 computed distance features to predict heat-risk intensity:

```mermaid
flowchart TB
    subgraph "Input Rasters (8 layers)"
        NDVI[NDVI]
        NDWI[NDWI]
        NDBI[NDBI]
        DTM[DTM]
        DSM[DSM]
        BH[Building Height]
        ALB[Albedo]
        IMP[Imperviousness]
    end

    subgraph "Input Rasters for Loss function"
        LST[LST]
    end

    subgraph "Distance Features"
        DW[Distance to Water<br/>computed from NDWI]
        DP[Distance to Park<br/>computed from NDVI]
    end

    subgraph "XGBoost Model"
        FM["Feature Matrix<br/>10 features per pixel"]
        XGB["XGBoost Predict<br/>tiled inference"]
        OM["Objective Matrix<br/>Difference between LST_pixel and LST_ref"]
    end

    subgraph "Output"
        UHI["UHI Heat-Risk Map"]
        PNG["RGBA PNG overlay<br/>(zone prediction)"]
        COG2["Cloud-Optimized GeoTIFF<br/>(full-extent prediction)"]
    end

    NDVI & NDWI & NDBI & DTM & DSM & BH & ALB & IMP --> FM
    DW & DP --> FM
    LST --> OM
    OM --> XGB
    FM --> XGB
    XGB --> UHI
    UHI --> PNG
    UHI --> COG2
```

---

## Project Structure

```
uhi-fiware-poc/
├── docker-compose.yml          # Orchestrates all 7 services
├── env.example                 # Template for environment variables
├── .env                        # Active config (git-ignored, copy from env.example)
│
├── services/
│   ├── ingestion/              # Downloads orthophotos, computes NDVI/NDWI/LST/BuildingHeight
│   ├── prediction/             # XGBoost UHI prediction + sensor ingestion (VLINDER, Sensors.community)
│   ├── geoserver-sync/         # Auto-publishes Orion entities to GeoServer as WMS layers
│   └── frontend/               # Vue 3 + CesiumJS 3D web viewer
│
├── data/                       # Mounted volumes (git-ignored)
│   ├── raw/                    # Downloaded orthophotos + QGIS preprocessed files
│   ├── processed/              # COG outputs (NDVI, NDWI, LST, UHI, albedo, dsm, ...)
│   ├── models/                 # Trained XGBoost model artifacts
│   └── cache/                  # Intermediate processing cache
│
└── config/
    └── geoserver/              # GeoServer workspace config (runtime, git-ignored)
```

> Each service has its own detailed `README.md` with full file listings, API reference, and configuration.

---

## Quick Start

### Prerequisites

| Requirement | Minimum | Recommended |
|---|---|---|
| [Docker](https://docs.docker.com/get-docker/) + [Docker Compose](https://docs.docker.com/compose/install/) | v2+ | Latest |
| RAM | 8 GB | 16 GB |
| Disk space | 15 GB | 30 GB |
| OS | Windows 10/11, macOS, Linux | Any with Docker support |

### Step 1 — Clone the repository

```bash
git clone <repo-url>
cd uhi-fiware-poc
```

### Step 2 — Configure environment variables

```bash
cp env.example .env
```

The default `.env` points to the Brussels 2024 UrbIS orthophotos. Edit if needed.

### Step 3 — Place QGIS preprocessed raster files

> **Important:** Four raster layers must be preprocessed externally with QGIS and placed manually in `data/raw/` **before** running the prediction. These files are provided separately.

```bash
mkdir -p data/raw
```

Copy the following files into `data/raw/`:

| File | Description | Source |
|---|---|---|
| `albedo.tif` | Surface albedo (reflectivity) | Preprocessed in QGIS from satellite data |
| `dsm.tif` | Digital Surface Model (elevation including buildings/trees) | Preprocessed in QGIS from LiDAR/Copernicus |
| `imperviousness.tif` | Soil imperviousness index (0-100%) | Preprocessed in QGIS from Copernicus HRL |
| `ndbi.tif` | Normalized Difference Built-up Index | Preprocessed in QGIS from satellite bands |

These files must be **GeoTIFF format**, projected in **EPSG:31370** (Belgian Lambert 72), and cover the **Brussels Capital Region**. They are used as input features for the XGBoost UHI prediction model.

### Step 4 — Start all services

```bash
docker compose up -d
```

This starts 7 containers:

| Service | Container | Port | Description |
|---|---|---|---|
| MongoDB | `uhi-mongo` | 27017 | Orion-LD database |
| Orion-LD | `uhi-orion` | 1026 | NGSI-LD Context Broker |
| GeoServer | `uhi-geoserver` | 8080 | WMS tile server |
| Ingestion | `uhi-ingestion` | 8001 | Data ingestion pipeline |
| Prediction | `uhi-prediction` | 8002 | UHI prediction engine + sensor sync |
| GeoServer Sync | `uhi-geoserver-sync` | _(internal)_ | Auto-publishes layers to GeoServer |
| Frontend | `uhi-frontend` | 3000 | CesiumJS 3D web viewer |

Verify all containers are healthy:

```bash
docker compose ps
```

### Step 5 — Trigger the ingestion pipeline

```bash
curl -X POST http://localhost:8001/ingest/orthophotos \
  -H "Content-Type: application/json" -d "{}"
```

Monitor progress:

```bash
curl http://localhost:8001/status
```

> **Warning: Ingestion takes a long time.**
> The pipeline downloads ~10 GB of orthophotos and processes them into multiple spectral indices. Depending on your internet speed and hardware:
> - **Download:** 15–60 minutes (skipped if files already exist)
> - **Overview building:** 5–15 minutes per file
> - **NDVI/NDWI/LST computation:** 10–30 minutes each (windowed processing on 4–6 GB files)
> - **Total:** 1–3 hours on first run

The pipeline will:
1. Download RGB and NIR orthophotos, DTM, and Buildings data (~10 GB total)
2. Build overviews on the raw files (for fast WMS serving)
3. Compute NDVI, NDWI, and LST as Cloud-Optimized GeoTIFFs
4. Compute Building Height from DSM and DTM
5. Register all layers as NGSI-LD entities in Orion-LD

This automatically triggers:
- **GeoServer Sync** — publishes all layers to GeoServer as WMS

### Step 6 — Train the XGBoost prediction model

Once ingestion is complete **and** the 4 QGIS files are in place, train the model:

```bash
curl -X POST http://localhost:8002/training/start
```

Monitor training progress:

```bash
curl http://localhost:8002/training/status
```

> **Warning: Training can take 15–45 minutes** depending on your hardware (GPU recommended).
> The model samples pixels across all 10+ input layers, builds a feature matrix, and trains an XGBoost regressor.
### Step 7 — Generate the full UHI prediction

Once the model is trained, trigger a full-extent prediction:

```bash
curl -X POST http://localhost:8002/predict/manual
```

> **Warning: Full-extent prediction takes 20–60 minutes.** It runs tiled XGBoost inference across the entire Brussels raster extent. Progress is tracked in the logs.

This creates the `UHIHeatMap` entity in Orion, which automatically triggers GeoServer Sync to publish the prediction layer.

### Step 8 — View the results

Open [http://localhost:3000](http://localhost:3000) in your browser.

The CesiumJS 3D viewer provides:
- Toggle-able WMS layers (RGB, NIR, NDVI, NDWI, LST, UHI Prediction, ...)
- Per-layer opacity sliders
- Pixel click to query values across all layers
- Polygon drawing for zone-specific predictions
- Object impact simulation (trees, buildings, solar panels, ...)
- Real-time sensor markers (VLINDER + Sensors.community)
- Sun position simulation

---

## Complete Workflow Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant ING as Ingestion :8001
    participant ORION as Orion-LD :1026
    participant PRED as Prediction :8002
    participant SYNC as GeoServer Sync
    participant GS as GeoServer :8080
    participant FE as Frontend :3000

    Note over U: 1. Place QGIS files in data/raw/
    Note over U: albedo.tif, dsm.tif, imperviousness.tif, ndbi.tif

    U->>ING: POST /ingest/orthophotos
    activate ING
    Note over ING: Download RGB + NIR + DTM + Buildings<br/>(15-60 min)
    Note over ING: Compute NDVI, NDWI, LST<br/>(10-30 min each)
    ING->>ORION: Create GeoSpatialLayer entities (x11)
    deactivate ING

    ORION-->>SYNC: Subscription notification
    SYNC->>GS: Publish WMS layers

    U->>PRED: POST /training/start
    activate PRED
    PRED->>ORION: Query all layer file paths
    Note over PRED: Sample pixels, build feature matrix<br/>Train XGBoost (15-45 min)
    PRED->>ORION: Publish model metadata
    deactivate PRED

    U->>PRED: POST /predict/manual
    activate PRED
    PRED->>ORION: Resolve 10+ layer paths
    Note over PRED: Tiled XGBoost inference<br/>(20-60 min)
    PRED->>ORION: Create UHIHeatMap entity
    deactivate PRED

    ORION-->>SYNC: Subscription notification
    SYNC->>GS: Publish UHI prediction layer

    Note over PRED: Background: periodic sensor sync
    PRED->>ORION: Upsert TemperatureSensor entities

    U->>FE: Open http://localhost:3000
    FE->>GS: WMS GetMap (all layers)
    FE->>PRED: GET /sensors (live markers)
    Note over FE: Interactive 3D globe with<br/>all layers + sensor data
```

---

## NGSI-LD Data Model

### GeoSpatialLayer

Represents a geospatial raster layer:

| Property | Type | Example |
|---|---|---|
| `id` | string | `urn:ngsi-ld:GeoSpatialLayer:NDVI:brussels:2024` |
| `type` | string | `GeoSpatialLayer` |
| `layerType` | Property | `RGB`, `NIR`, `NDVI`, `NDWI`, `DTM`, `LST`, `BuildingHeight`, `DSM`, `Albedo`, `NDBI`, `Imperviousness` |
| `name` | Property | Human-readable name |
| `filePath` | Property | Container-internal path to GeoTIFF |
| `geoserverLayer` | Property | GeoServer layer name (e.g. `uhi:ndvi`) |
| `publishToGeoserver` | Property | `true` if the layer should be served via WMS |
| `boundingBox` | GeoProperty | WGS84 bounding polygon |
| `resolution` | Property | Spatial resolution in cm |

### UHIHeatMap

Represents a heat-risk prediction output:

| Property | Type | Example |
|---|---|---|
| `id` | string | `urn:ngsi-ld:UHIHeatMap:brussels:2024` |
| `type` | string | `UHIHeatMap` |
| `modelVersion` | Property | `xgb_v1` |
| `inputLayers` | Property | Array of input entity IDs |
| `filePath` | Property | Path to prediction GeoTIFF |
| `valueRange` | Property | `{min: 0, max: 1}` (0 = cool, 1 = hot) |

### TemperatureSensor

Represents a real-time sensor observation:

| Property | Type | Example |
|---|---|---|
| `id` | string | `urn:ngsi-ld:TemperatureSensor:vlinder:ukkel_kmi` |
| `type` | string | `TemperatureSensor` |
| `provider` | Property | `vlinder`, `sensors_community` |
| `temperature` | Property | `22.5` (with `observedAt`) |
| `humidity` | Property | `65.0` (with `observedAt`) |
| `location` | GeoProperty | Point with WGS84 coordinates |

---

## API Reference

### Ingestion Service (`:8001`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/ingest/orthophotos` | Start ingestion pipeline |
| `GET` | `/status` | Current pipeline status |
| `GET` | `/layers` | List registered layers from Orion |
| `GET` | `/health` | Health check |

### Prediction Service (`:8002`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/predict` | Orion subscription callback (auto) |
| `POST` | `/predict/manual` | Manual full-extent prediction trigger |
| `POST` | `/training/start` | Start XGBoost model training |
| `GET` | `/training/status` | Training progress |
| `POST` | `/zones/predict` | Zone prediction (GeoJSON polygon + objects) |
| `POST` | `/zones/stats` | Zone statistics (mean/min/max per layer) |
| `GET` | `/zones/pixel?lon=X&lat=Y` | Single pixel value lookup |
| `POST` | `/zones/export` | Export zone as GeoTIFF |
| `GET` | `/sensors` | List latest sensor readings |
| `POST` | `/sensors/sync` | Manual sensor sync trigger |
| `GET` | `/vlinder/tbase` | Temperature baseline (rural reference) |
| `GET` | `/health` | Health check |

### GeoServer Sync (internal)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/sync` | Orion notification handler |
| `POST` | `/sync/all` | Force full re-sync |
| `GET` | `/health` | Health check |

---

## Technology Stack

| Component | Technology | Role |
|---|---|---|
| Context Broker | [FIWARE Orion-LD](https://github.com/FIWARE/context.Orion-LD) 1.6.0 | NGSI-LD entity & subscription management |
| Database | MongoDB 5.0 | Orion-LD persistence |
| GIS Server | GeoServer 2.24.2 | WMS layer serving |
| Ingestion | Python 3.11 / FastAPI | Data download & raster processing |
| Prediction | Python 3.11 / FastAPI / XGBoost | ML-based UHI prediction + sensor ingestion |
| GeoServer Sync | Python 3.11 / FastAPI | Automated GeoServer configuration |
| Frontend | Vue 3 / CesiumJS 1.114.0 | Interactive 3D globe viewer |
| Base Map | OpenStreetMap | Base layer tiles |
| Raster Processing | Rasterio / NumPy / SciPy | GeoTIFF I/O & computation |
| ML Engine | XGBoost / scikit-learn | Heat-risk model training & inference |

---

## License

This project is developed by [FARI -- AI for the Common Good Institute](https://fari.brussels).
