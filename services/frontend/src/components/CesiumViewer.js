import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as Cesium from 'cesium'

/**
 * CESIUM VIEWER COMPONENT
 */

const cesiumContainer = ref(null)
let viewer = null
let buildingTileset = null
let TreeTileset = null
let treeLoaded = false
let terrainProvider = null
const wmsLayers = new Map()

// Drawing state
let drawingMode = null

// Swipe state
let swipeActive = false
const preSwipeLayerShow = new Map()
let isDrawing = false
let drawnPoints = []
let drawnEntities = new Map()
let activeEntity = null
let mouseHandler = null
let previewEntity = null
let currentMousePosition = null
let pointEntities = []

// GeoServer WMS endpoint
const GEOSERVER_URL = window.location.port === '3000' 
  ? '/geoserver' 
  : 'http://localhost:8080/geoserver'  

// Brussels center coordinates (WGS84)
const BRUSSELS_CENTER = {
  longitude: 4.3517,
  latitude: 50.8503,
  height: 5000
}


export function useCesiumViewer(props, emit) {

  
  // ========================================
  // CESIUM INITIALIZATION
  // ========================================

  // Initialize Cesium viewer on component mount
  onMounted(async () => {
    await initCesium()
  })
  
  // Clean up Cesium resources on component unmount
  onUnmounted(() => {
    cleanupCesium()
  })
   
  async function initCesium() {
    // TODO: Set Cesium Ion token for 3D tileset streaming
    Cesium.Ion.defaultAccessToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJhY2E3ZDhlNC03Yjc0LTQzM2QtYmI5My0zYWQ3NjIwOTk0OTciLCJpZCI6Mjc4NzM4LCJpYXQiOjE3NDA0ODg1MjB9.VsZjL6pbKSwR_SBbxUq-KRweOU_P3R8DKjSpeD0EICY"

    // Initialize viewer with minimal UI
    viewer = new Cesium.Viewer(cesiumContainer.value, {
      baseLayerPicker: false,
      geocoder: true,
      homeButton: true,
      sceneModePicker: false,
      navigationHelpButton: false,
      animation: false,
      timeline: false,
      fullscreenButton: true,
      vrButton: false,
      infoBox: true,
      selectionIndicator: false,
      shadows: false,
      shouldAnimate: false
    })

    // ========================================
    // RENDER ON DEMAND: only render when scene changes, not every frame
    // ========================================
    viewer.scene.requestRenderMode = true
    viewer.scene.maximumRenderTimeChange = 0.0

    // ========================================
    // TERRAIN INITIALIZATION (LOAD ONCE)
    // ========================================
    try {
      // Load Cesium World Terrain for ground-accurate building placement
      // requestVertexNormals/requestWaterMask disabled for performance (not needed without lighting)
      terrainProvider = await Cesium.createWorldTerrainAsync({
        requestWaterMask: false,
        requestVertexNormals: false
      })
      viewer.terrainProvider = terrainProvider
    } catch (error) {
      console.warn('Failed to load Cesium World Terrain, using ellipsoid:', error)
    }

    // ========================================
    // DEPTH TESTING 
    // ========================================

    // Enable depth testing so buildings respect terrain
    viewer.scene.globe.depthTestAgainstTerrain = true

    // Set up imagery for cartographic appearance
    setupImageryProviders()

    // Set initial camera to Brussels, top-down view
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(
        BRUSSELS_CENTER.longitude,
        BRUSSELS_CENTER.latitude,
        500
      ),
      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-50),
        roll: 0
      },
      duration: 0
    })

    // ========================================
    // LOAD TILESET
    // ========================================
    try {
      // Load 3D tileset from Cesium ion asset
      buildingTileset = await Cesium.Cesium3DTileset.fromIonAssetId(3474524)
      viewer.scene.primitives.add(buildingTileset)

      // Performance: SSE, foveated rendering, cache limits
      buildingTileset.maximumScreenSpaceError = 32
      buildingTileset.foveatedScreenSpaceError = true
      buildingTileset.foveatedConeSize = 0.15
      buildingTileset.foveatedTimeDelay = 0.2
      buildingTileset.cacheBytes = 256 * 1024 * 1024
      buildingTileset.maximumCacheOverflowBytes = 128 * 1024 * 1024
      buildingTileset.depthFailMaterial = Cesium.Color.TRANSPARENT

      // dynamicScreenSpaceError: reduces quality for distant tiles automatically
      buildingTileset.dynamicScreenSpaceError = true
      buildingTileset.dynamicScreenSpaceErrorDensity = 0.00278
      buildingTileset.dynamicScreenSpaceErrorFactor = 4.0
      buildingTileset.dynamicScreenSpaceErrorHeightFalloff = 0.25

      // skipLevelOfDetail: jump directly to the right LOD, skipping intermediates
      buildingTileset.skipLevelOfDetail = true
      buildingTileset.baseScreenSpaceError = 1024
      buildingTileset.skipScreenSpaceErrorFactor = 16
      buildingTileset.skipLevels = 1
      buildingTileset.immediatelyLoadDesiredLevelOfDetail = false

      // Aggressively cull tile requests while moving
      buildingTileset.cullRequestsWhileMoving = true
      buildingTileset.cullRequestsWhileMovingMultiplier = 60

      // TreeTileset: lazy-loaded on first user toggle (see watch treeVisible)
      
    } catch (error) {
    }

    // ========================================
    // DYNAMIC SSE: lower quality during movement, full quality when still
    // ========================================
    viewer.camera.moveStart.addEventListener(() => {
      if (buildingTileset) buildingTileset.maximumScreenSpaceError = 64
      if (TreeTileset) TreeTileset.maximumScreenSpaceError = 96
    })
    viewer.camera.moveEnd.addEventListener(() => {
      if (buildingTileset) buildingTileset.maximumScreenSpaceError = 32
      if (TreeTileset) TreeTileset.maximumScreenSpaceError = 48
    })

    // ========================================
    // INIT INITIAL WMS LAYERS
    // ========================================
    if (props.layers) {
      props.layers.forEach(layer => {
        if (layer.visible) {
          addWmsLayer(layer)
        }
      })
    }
  }
  let manualPanHandler = null

  function updateViewMode(mode) {
    if (!viewer) return
    const controller = viewer.scene.screenSpaceCameraController

    if (manualPanHandler) {
      manualPanHandler.destroy()
      manualPanHandler = null
    }
    if (mode === '2D') {
      // ========================================
      // 2D MODE: CONSTRAINED TOP-DOWN 3D
      // ========================================
      
      // Lock camera navigation to top-down only
      controller.enableTilt = false
      controller.enableRotate = false
      controller.enableLook = false
      // Allow pan and zoom
      controller.enableTranslate = false
      controller.enableZoom = true

      controller.rotateEventTypes = []
      controller.tiltEventTypes = []
      controller.lookEventTypes = []
      controller.translateEventTypes = []

      controller.translateEventTypes = [
        Cesium.CameraEventType.LEFT_DRAG
     ]
      
      // Force camera to strict top-down orientation
      viewer.camera.setView({
        destination: viewer.camera.position,
        orientation: {
          heading: Cesium.Math.toRadians(0),
          pitch: Cesium.Math.toRadians(-90),
          roll: 0
        }
      })

      let isDragging = false
      let lastMousePosition = null

      manualPanHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)

      manualPanHandler.setInputAction((event) => {
        isDragging = true
        lastMousePosition = Cesium.Cartesian2.clone(event.position)
      }, Cesium.ScreenSpaceEventType.LEFT_DOWN)

      manualPanHandler.setInputAction((event) => {
        if (!isDragging || !lastMousePosition) return

        // Récupérer la position monde sous la souris (avant et après mouvement)
        const currentPos = event.endPosition

        const ray1 = viewer.camera.getPickRay(lastMousePosition)
        const ray2 = viewer.camera.getPickRay(currentPos)

        if (!ray1 || !ray2) return

        const globe = viewer.scene.globe
        const p1 = globe.pick(ray1, viewer.scene)
        const p2 = globe.pick(ray2, viewer.scene)

        if (!p1 || !p2) return

        // Calculer le delta et déplacer la caméra dans la direction opposée
        const delta = Cesium.Cartesian3.subtract(p1, p2, new Cesium.Cartesian3())
        viewer.camera.position = Cesium.Cartesian3.add(
          viewer.camera.position,
          delta,
          new Cesium.Cartesian3()
        )

        lastMousePosition = Cesium.Cartesian2.clone(currentPos)
      }, Cesium.ScreenSpaceEventType.MOUSE_MOVE)

      manualPanHandler.setInputAction(() => {
        isDragging = false
        lastMousePosition = null
      }, Cesium.ScreenSpaceEventType.LEFT_UP)
        
        // Disable lighting effects for cleaner map rendering (unless sun sim active)
        if (!props.sunSimEnabled) {
          viewer.scene.globe.enableLighting = false
        }
        viewer.scene.fog.enabled = false
        
        // Keep buildings hidden in 2D mode for a cleaner cartographic view
        if (buildingTileset) {
          buildingTileset.show = false
        }
        if (TreeTileset) {
          TreeTileset.show = false
        }
        
        // Keep fog disabled for clear cartographic view
        viewer.scene.fog.enabled = false
      
    } else if (mode === '3D') {
      // ========================================
      // 3D MODE: FULL CESIUM INTERACTION
      // ========================================
      controller.rotateEventTypes = [
        Cesium.CameraEventType.LEFT_DRAG
      ]
      controller.tiltEventTypes = [
        Cesium.CameraEventType.MIDDLE_DRAG,
        Cesium.CameraEventType.PINCH,
        { eventType: Cesium.CameraEventType.LEFT_DRAG, modifier: Cesium.KeyboardEventModifier.CTRL },
        { eventType: Cesium.CameraEventType.RIGHT_DRAG, modifier: Cesium.KeyboardEventModifier.CTRL }
      ]
      controller.lookEventTypes = [
        { eventType: Cesium.CameraEventType.LEFT_DRAG, modifier: Cesium.KeyboardEventModifier.SHIFT }
      ]
      controller.translateEventTypes = [
        Cesium.CameraEventType.LEFT_DRAG
      ]
      // Enable all camera controls
      controller.enableTilt = true
      controller.enableRotate = true
      controller.enableLook = true
      controller.enableTranslate = true
      controller.enableZoom = true
      controller.enableRubberBandSelect = false
      
      // Disable rubber band select for cleaner interaction
      controller.enableRubberBandSelect = false
      
      viewer.scene.globe.enableLighting = props.sunSimEnabled

      // Ensure atmosphere is visible
      viewer.scene.skyAtmosphere.show = true

      // Show buildings with full 3D context
      if (buildingTileset) {
        buildingTileset.show = true
      }

      // Restore sun simulation shadows if active
      if (props.sunSimEnabled) {
        updateSunSimulation(true, props.sunSimTime)
      }
      
      // Move camera to 3D perspective 
      viewer.camera.flyTo({
        destination: viewer.camera.position,
        orientation: {
          heading: Cesium.Math.toRadians(45),
          pitch: Cesium.Math.toRadians(-45),
          roll: 0
        },
        duration: 0.5
      })
      
    }
  }

  // ========================================
  // DRAWING FUNCTIONS
  // ========================================
  // Start drawing mode for specified geometry type (polygon or bounding box)
  function startDrawing(mode) {
    if (!viewer) return

    drawingMode = mode
    drawnPoints = []
    isDrawing = true
    
    // Emit drawing mode state
    if (emit) emit('drawing-active', true)

    // Initialize mouse handler for drawing
    if (!mouseHandler) {
      mouseHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
    }

    // Handle mouse click for adding points
    mouseHandler.setInputAction((click) => {
      if (!isDrawing || !drawingMode) return
      let cartesian = viewer.scene.pickPosition(click.position)
      if (!Cesium.defined(cartesian)) {
        const ray = viewer.camera.getPickRay(click.position)
        if (ray) cartesian = viewer.scene.globe.pick(ray, viewer.scene)
      }

      // 3. Dernier recours : ellipsoïde
      if (!Cesium.defined(cartesian)) {
        cartesian = viewer.camera.pickEllipsoid(
          click.position,
          viewer.scene.globe.ellipsoid
        )
      }

      if (!Cesium.defined(cartesian)) return

      let cartographic = Cesium.Cartographic.fromCartesian(cartesian)
      
      const lon = Cesium.Math.toDegrees(cartographic.longitude)
      const lat = Cesium.Math.toDegrees(cartographic.latitude)

      cartesian = Cesium.Cartesian3.fromDegrees(lon, lat, cartographic.height)

      drawnPoints.push({ longitude: lon, latitude: lat, cartesian })

      // Visual feedback: draw points as circles
      const pointEntity = viewer.entities.add({
        position: cartesian,
        point: {
          pixelSize: 8,
          color: Cesium.Color.GREEN,
          outlineColor: Cesium.Color.WHITE,
          outlineWidth: 2,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        }
      })
      pointEntities.push(pointEntity)
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)

    // Handle mouse move to update preview entity
    mouseHandler.setInputAction((move) => {
      if (!isDrawing || !drawingMode) return
      currentMousePosition = move.endPosition
      updateDrawingPreview(move.endPosition)
    }, Cesium.ScreenSpaceEventType.MOUSE_MOVE)

    // Handle right-click to finish drawing
    mouseHandler.setInputAction(() => {
      if (!isDrawing || !drawingMode) return
      finishDrawing()
    }, Cesium.ScreenSpaceEventType.RIGHT_CLICK)

  }
  // Update drawing visualization (preview entity and legend)
  function updateDrawingPreview(mousePos) {
    if (!drawingMode || drawnPoints.length < 1) return
    
    // Ray pick to get accurate position on terrain
    const ray = viewer.camera.getPickRay(mousePos)
    const mouseCartesian = ray
      ? viewer.scene.globe.pick(ray, viewer.scene) ||
        viewer.camera.pickEllipsoid(mousePos, viewer.scene.globe.ellipsoid)
      : null

    if (!mouseCartesian) return

    // Remove previous entity if exists
    if (previewEntity) {
      viewer.entities.remove(previewEntity)
      previewEntity = null
    }

    if (drawingMode === 'polygon' && drawnPoints.length >=2) {
      const positions = [...drawnPoints.map(p => p.cartesian), mouseCartesian]
      previewEntity = viewer.entities.add({
        polygon: {
          hierarchy: new Cesium.PolygonHierarchy(positions),
          material: Cesium.Color.GREEN.withAlpha(0.2),
          outline: true,
          outlineColor: Cesium.Color.LIME,
          outlineWidth: 2,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, // ← ici
          classificationType: Cesium.ClassificationType.TERRAIN
        }
      })
    } 
    else if (drawingMode === 'polygon' && drawnPoints.length === 1) {
      // Draw single point as polyline
      previewEntity = viewer.entities.add({
        polyline: {
          positions: [drawnPoints[0].cartesian, mouseCartesian],
          width: 2,
          material: Cesium.Color.LIME.withAlpha(0.8),
          clampToGround: true,
        }
      })
    }
    else if (drawingMode === 'boundingBox' && drawnPoints.length  >= 1) {
      const mouseCartographic = Cesium.Cartographic.fromCartesian(mouseCartesian)
      const mouseLon = Cesium.Math.toDegrees(mouseCartographic.longitude)
      const mouseLat = Cesium.Math.toDegrees(mouseCartographic.latitude)
      
      const minLat = Math.min(drawnPoints[0].latitude, mouseLat)
      const maxLat = Math.max(drawnPoints[0].latitude, mouseLat)
      const minLon = Math.min(drawnPoints[0].longitude, mouseLon)
      const maxLon = Math.max(drawnPoints[0].longitude, mouseLon)

      const boxCorners = [
        Cesium.Cartesian3.fromDegrees(minLon, minLat),
        Cesium.Cartesian3.fromDegrees(maxLon, minLat),
        Cesium.Cartesian3.fromDegrees(maxLon, maxLat),
        Cesium.Cartesian3.fromDegrees(minLon, maxLat)
      ]

      previewEntity = viewer.entities.add({
        polygon: {
          hierarchy: new Cesium.PolygonHierarchy(boxCorners),
          material: Cesium.Color.BLUE.withAlpha(0.2),
          outline: true,
          outlineColor: Cesium.Color.CYAN,
          outlineWidth: 2,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, // ← ici
          classificationType: Cesium.ClassificationType.TERRAIN,
        }
      })
      
    }
  }

  function finishDrawing() {
    if (drawnPoints.length < 2) {
      stopDrawing()
      return
    }
     if (previewEntity) {
      viewer.entities.remove(previewEntity)
      previewEntity = null
    }

    const geometry = {
      type: drawingMode,
      points: drawnPoints,
      timestamp: new Date().toISOString()
    }

    if (drawingMode === 'polygon') {
      geometry.geoJSON = {
        type: 'Polygon',
        coordinates: [drawnPoints.map(p => [p.longitude, p.latitude])]
      }
      geometry.summary = {
        type: 'Polygon',
        pointCount: drawnPoints.length,
        coordinates: drawnPoints.map(p => `(${p.latitude.toFixed(5)}, ${p.longitude.toFixed(5)})`)
      }
    } else if (drawingMode === 'boundingBox') {
      const minLat = Math.min(drawnPoints[0].latitude, drawnPoints[1].latitude)
      const maxLat = Math.max(drawnPoints[0].latitude, drawnPoints[1].latitude)
      const minLon = Math.min(drawnPoints[0].longitude, drawnPoints[1].longitude)
      const maxLon = Math.max(drawnPoints[0].longitude, drawnPoints[1].longitude)

      geometry.bounds = { minLon, maxLon, minLat, maxLat }
      geometry.geoJSON = {
        type: 'Polygon',
        coordinates: [[
          [minLon, minLat],
          [maxLon, minLat],
          [maxLon, maxLat],
          [minLon, maxLat],
          [minLon, minLat]
        ]]
      }
      geometry.summary = {
        type: 'Bounding Box',
        bounds: `N:${maxLat.toFixed(5)} S:${minLat.toFixed(5)} E:${maxLon.toFixed(5)} W:${minLon.toFixed(5)}`
      }
    }

    console.log('→ Drawing finished:', geometry)

    // Emit geometry to parent component
    if (emit) {
      emit('geometry-drawn', geometry)
      emit('drawing-active', false)
    }

    stopDrawing()
  }

  function stopDrawing() {
    isDrawing = false
    drawingMode = null
    drawnPoints = []

    pointEntities.forEach(e => viewer.entities.remove(e))
    pointEntities = []

    if (previewEntity) {
      viewer.entities.remove(previewEntity)
      previewEntity = null
    }

    if (mouseHandler) {
      mouseHandler.removeInputAction(Cesium.ScreenSpaceEventType.LEFT_CLICK)
      mouseHandler.removeInputAction(Cesium.ScreenSpaceEventType.RIGHT_CLICK)
      mouseHandler.destroy()
      mouseHandler = null
    }
  }

  

  // ========================================
  // WMS LAYER MANAGEMENT
  // ========================================

  function setupImageryProviders() {
    // Remove default imagery
    viewer.imageryLayers.removeAll()
    const cartoDBProvider = new Cesium.UrlTemplateImageryProvider({
      url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
      subdomains: ['a', 'b', 'c', 'd'],
      credit: '© CartoDB'
    })

    viewer.imageryLayers.addImageryProvider(cartoDBProvider)
  }

  function addWmsLayer(layerConfig) {
    if (!viewer || wmsLayers.has(layerConfig.id)) return

    const provider = new Cesium.WebMapServiceImageryProvider({
      url: `${GEOSERVER_URL}/uhi/wms`,
      layers: layerConfig.wmsLayer,
      parameters: {
        service: 'WMS',
        version: '1.1.1',
        request: 'GetMap',
        format: 'image/png',
        transparent: true,
        styles: '',
        crs: 'EPSG:4326'
      },
      enablePickFeatures: true,
      credit: 'UHI Brussels - FARI'
    })

    const imageryLayer = viewer.imageryLayers.addImageryProvider(provider)
    imageryLayer.alpha = layerConfig.opacity
    
    // CRITICAL: Ensure GeoTIFF layers align with terrain
    // By enabling globe depth testing, WMS layers will clamp to terrain elevation
    // This prevents floating or buried effects in 3D mode
    imageryLayer.show = true

    wmsLayers.set(layerConfig.id, imageryLayer)
  }

  function removeWmsLayer(layerId) {
    if (!viewer || !wmsLayers.has(layerId)) return

    const layer = wmsLayers.get(layerId)
    viewer.imageryLayers.remove(layer)
    wmsLayers.delete(layerId)
  }

  function updateLayerOpacity(layerId, opacity) {
    if (!wmsLayers.has(layerId)) return

    const layer = wmsLayers.get(layerId)
    layer.alpha = opacity
  }

  // ========================================
  // UHI DYNAMIC SLD (T_base-dependent colormap)
  // ========================================

  const UHI_LAYER_ID = 'uhi_prediction'

  // Fixed absolute temperature color scale
  const TEMP_COLORS = [
    { temp: 10, color: '#313695' },
    { temp: 15, color: '#4575b4' },
    { temp: 20, color: '#74add1' },
    { temp: 25, color: '#fee090' },
    { temp: 30, color: '#f46d43' },
    { temp: 35, color: '#d73027' },
    { temp: 40, color: '#a50026' },
    { temp: 45, color: '#67001f' },
  ]

  function tempToPixel(tempAbs, tBase, uhiMin, uhiMax) {
    // T_abs = tBase + (pixel / 254) * (uhiMax - uhiMin) + uhiMin
    // => pixel = (T_abs - tBase - uhiMin) / (uhiMax - uhiMin) * 254
    const p = (tempAbs - tBase - uhiMin) / (uhiMax - uhiMin) * 254
    return Math.max(0, Math.min(254, Math.round(p)))
  }

  function buildUhiSldBody(wmsLayerName, tBase, uhiMin, uhiMax) {
    const entries = TEMP_COLORS
      .map(({ temp, color }) => {
        const qty = tempToPixel(temp, tBase, uhiMin, uhiMax)
        return `          <ColorMapEntry color="${color}" quantity="${qty}" label="${temp}°C"/>`
      })
      .join('\n')

    return `<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
  xsi:schemaLocation="http://www.opengis.net/sld StyledLayerDescriptor.xsd"
  xmlns="http://www.opengis.net/sld"
  xmlns:ogc="http://www.opengis.net/ogc"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <NamedLayer>
    <Name>${wmsLayerName}</Name>
    <UserStyle>
      <Title>UHI Dynamic</Title>
      <FeatureTypeStyle>
        <Rule>
          <RasterSymbolizer>
            <ColorMap type="ramp">
${entries}
              <ColorMapEntry color="#000000" quantity="255" opacity="0" label="nodata"/>
            </ColorMap>
          </RasterSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>`
  }

  function refreshUhiLayer(tBase, uhiMin, uhiMax) {
    if (!viewer || tBase == null || uhiMin == null || uhiMax == null) return

    const layerConfig = props.layers.find(l => l.id === UHI_LAYER_ID)
    if (!layerConfig || !layerConfig.visible) return

    // Remove old layer
    if (wmsLayers.has(UHI_LAYER_ID)) {
      const old = wmsLayers.get(UHI_LAYER_ID)
      viewer.imageryLayers.remove(old)
      wmsLayers.delete(UHI_LAYER_ID)
    }

    const sldBody = buildUhiSldBody(layerConfig.wmsLayer, tBase, uhiMin, uhiMax)

    const provider = new Cesium.WebMapServiceImageryProvider({
      url: `${GEOSERVER_URL}/uhi/wms`,
      layers: layerConfig.wmsLayer,
      parameters: {
        service: 'WMS',
        version: '1.1.1',
        request: 'GetMap',
        format: 'image/png',
        transparent: true,
        SLD_BODY: sldBody,
        crs: 'EPSG:4326'
      },
      enablePickFeatures: true,
      credit: 'UHI Brussels - FARI'
    })

    const imageryLayer = viewer.imageryLayers.addImageryProvider(provider)
    imageryLayer.alpha = layerConfig.opacity
    imageryLayer.show = true
    wmsLayers.set(UHI_LAYER_ID, imageryLayer)
  }

  // ========================================
  // SWIPE / SPLIT LAYER MANAGEMENT
  // ========================================

  function updateSwipeConfig(enabled, position, leftLayerId, rightLayerId) {
    if (!viewer) return

    viewer.scene.splitPosition = enabled ? position : 1.0

    if (!enabled) {
      swipeActive = false
      wmsLayers.forEach((layer, id) => {
        layer.show = preSwipeLayerShow.has(id) ? preSwipeLayerShow.get(id) : false
        layer.splitDirection = Cesium.SplitDirection.NONE
      })
      // Remove layers that were loaded exclusively for swipe
      Array.from(preSwipeLayerShow.entries())
        .filter(([, wasVisible]) => !wasVisible)
        .forEach(([id]) => removeWmsLayer(id))
      preSwipeLayerShow.clear()
      return
    }

    // Save pre-swipe visibility on first activation
    if (!swipeActive) {
      swipeActive = true
      wmsLayers.forEach((layer, id) => {
        preSwipeLayerShow.set(id, layer.show)
      })
    }

    // Ensure left/right layers are loaded even if not currently visible
    for (const layerId of [leftLayerId, rightLayerId]) {
      if (!layerId || wmsLayers.has(layerId)) continue
      const cfg = props.layers.find(l => l.id === layerId)
      if (cfg) {
        addWmsLayer(cfg)
        if (!preSwipeLayerShow.has(layerId)) preSwipeLayerShow.set(layerId, false)
      }
    }

    // Apply split directions: only show left/right layers, hide others
    wmsLayers.forEach((layer, id) => {
      if (id === leftLayerId) {
        layer.show = true
        layer.splitDirection = Cesium.SplitDirection.LEFT
      } else if (id === rightLayerId) {
        layer.show = true
        layer.splitDirection = Cesium.SplitDirection.RIGHT
      } else {
        layer.show = false
        layer.splitDirection = Cesium.SplitDirection.NONE
      }
    })
  }

  // ========================================
  // SUN SIMULATION
  // ========================================

  function updateSunSimulation(enabled, timeMinutes) {
    if (!viewer) return
    
    if (enabled) {
      console.log('→ SunSim enabled, updating sun position and shadows')
      viewer.shadows = true
      viewer.scene.globe.enableLighting = true
      viewer.terrainShadows = Cesium.ShadowMode.RECEIVE_ONLY

      if (buildingTileset) {
        buildingTileset.shadows = Cesium.ShadowMode.ENABLED
      }

      // Set sun position via clock time (local browser time → Cesium JulianDate)
      const now = new Date()
      const simDate = new Date(
        now.getFullYear(),
        now.getMonth(),
        now.getDate(),
        Math.floor(timeMinutes / 60),
        timeMinutes % 60,
        0
      )
      viewer.clock.currentTime = Cesium.JulianDate.fromDate(simDate)
      viewer.clock.shouldAnimate = false

      // Shadow quality
      viewer.shadowMap.size = 2048
      viewer.shadowMap.softShadows = true
      viewer.shadowMap.darkness = 0.3
      triggerCameraFly()
    } else {
      viewer.shadows = false
      viewer.scene.globe.enableLighting = false
      viewer.terrainShadows = Cesium.ShadowMode.DISABLED
      triggerCameraFly()
      if (buildingTileset) {
        buildingTileset.shadows = Cesium.ShadowMode.DISABLED
      }

      viewer.clock.shouldAnimate = false
    }
  }
  
  function triggerCameraFly() {
    if (viewer) {
      viewer.camera.flyTo({
        destination: viewer.camera.position,
        orientation: {
          heading: viewer.camera.heading,
          pitch: viewer.camera.pitch + 0.001,
          roll: 0
        },
        duration: 0.01
      })
    }
  }

  // ========================================
  // WATCHERS FOR STATE CHANGES
  // ========================================

  // Watch viewMode and update interaction mode accordingly
  watch(() => props.viewMode, (newMode) => {
    updateViewMode(newMode)
  })

  // Watch building visibility
  watch(() => props.buildingVisible, (isVisible) => {
    if (buildingTileset) {
      buildingTileset.show = isVisible
      console.log(`→ Buildings ${isVisible ? 'shown' : 'hidden'}`)
    }
  })

  // Watch tree visibility — lazy-load on first activation
  watch(() => props.treeVisible, async (isVisible) => {
    if (isVisible && !treeLoaded) {
      try {
        TreeTileset = await Cesium.Cesium3DTileset.fromUrl(
          "https://digitaltwin.s3.gra.io.cloud.ovh.net/tilesets_manager/3dtiles_vegetation_ds4/tileset.json"
        )
        TreeTileset.maximumScreenSpaceError = 48
        TreeTileset.foveatedScreenSpaceError = true
        TreeTileset.foveatedConeSize = 0.15
        TreeTileset.foveatedTimeDelay = 0.2
        TreeTileset.cacheBytes = 128 * 1024 * 1024
        TreeTileset.depthFailMaterial = Cesium.Color.TRANSPARENT
        TreeTileset.dynamicScreenSpaceError = true
        TreeTileset.dynamicScreenSpaceErrorDensity = 0.00278
        TreeTileset.dynamicScreenSpaceErrorFactor = 4.0
        TreeTileset.dynamicScreenSpaceErrorHeightFalloff = 0.25
        TreeTileset.skipLevelOfDetail = true
        TreeTileset.baseScreenSpaceError = 1024
        TreeTileset.skipScreenSpaceErrorFactor = 16
        TreeTileset.skipLevels = 1
        TreeTileset.cullRequestsWhileMoving = true
        TreeTileset.cullRequestsWhileMovingMultiplier = 60
        viewer.scene.primitives.add(TreeTileset)
        treeLoaded = true
      } catch (error) {
        console.warn('Failed to load tree tileset:', error)
      }
    } else if (TreeTileset) {
      TreeTileset.show = isVisible
    }
  })

  // Watch layers for visibility and opacity changes
  watch(() => props.layers.map(l => ({ id: l.id, visible: l.visible, opacity: l.opacity })),
    (newLayers) => {
      newLayers.forEach(layer => {
        const existingLayer = wmsLayers.has(layer.id)
        const layerConfig = props.layers.find(l => l.id === layer.id)

        if (layer.visible && !existingLayer) {
          // Use dynamic SLD for UHI layer when tBase is available
          if (layer.id === UHI_LAYER_ID && props.tBase != null && props.uhiMin != null && props.uhiMax != null) {
            refreshUhiLayer(props.tBase, props.uhiMin, props.uhiMax)
          } else {
            addWmsLayer(layerConfig)
          }
        } else if (!layer.visible && existingLayer) {
          removeWmsLayer(layer.id)
        } else if (layer.visible && existingLayer) {
          updateLayerOpacity(layer.id, layer.opacity)
        }
      })
    },
    { deep: true }
  )

  // Watch T_base changes — refresh UHI colormap
  watch(() => props.tBase, (newTBase) => {
    if (newTBase != null && props.uhiMin != null && props.uhiMax != null) {
      refreshUhiLayer(newTBase, props.uhiMin, props.uhiMax)
    }
  })

  // Watch drawing mode changes
  watch(() => props.drawingMode, (newMode) => {
    if (newMode) {
      startDrawing(newMode)
    } else if (isDrawing) {
      stopDrawing()
    }
  })

  // Watch swipe mode/layer changes
  watch(
    [() => props.swipeEnabled, () => props.swipeLeftLayerId, () => props.swipeRightLayerId],
    ([enabled, leftId, rightId]) => {
      updateSwipeConfig(enabled, props.swipePosition, leftId, rightId)
    }
  )

  // Watch swipe position separately (frequent updates from drag)
  watch(() => props.swipePosition, (position) => {
    if (viewer && props.swipeEnabled) {
      viewer.scene.splitPosition = position
      viewer.scene.requestRender()
    }
  })

  // Watch sun simulation toggle
  watch(() => props.sunSimEnabled, (enabled) => { 
    updateSunSimulation(enabled, props.sunSimTime)
  })

  // Watch sun simulation time (slider drag)
  watch(() => props.sunSimTime, (timeMinutes) => {
    if (props.sunSimEnabled) {
      updateSunSimulation(true, timeMinutes)
    }
  })

  // ========================================
  // CLEANUP
  // ========================================

  function cleanupCesium() {
    if (viewer) {
      // Clear WMS layers
      wmsLayers.forEach((imageryLayer) => {
        viewer.imageryLayers.remove(imageryLayer)
      })
      wmsLayers.clear()

      // Destroy viewer
      viewer.destroy()
      viewer = null
    }
  }

  // Expose public API
  return {
    cesiumContainer,
    getViewer: () => viewer,
    getTileset: () => buildingTileset,
    flyTo: (longitude, latitude, height) => {
      if (viewer) {
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(longitude, latitude, height)
        })
      }
    }
  }
}
