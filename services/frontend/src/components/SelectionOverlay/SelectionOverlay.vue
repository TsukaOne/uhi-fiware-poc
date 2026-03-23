<template>
  <div class="selection-overlay-wrapper" v-if="visible">
    <!-- ======================== -->
    <!-- 2D MODE: SVG overlay     -->
    <!-- ======================== -->
    <template v-if="is2D">
      <svg class="selection-svg" :width="svgWidth" :height="svgHeight">
        <defs>
          <mask :id="maskId" x="0" y="0" :width="svgWidth" :height="svgHeight">
            <rect x="0" y="0" :width="svgWidth" :height="svgHeight" fill="white"/>
            <polygon
              v-if="screenPoints.length >= 3"
              :points="screenPointsString"
              fill="black"
            />
          </mask>
        </defs>

        <rect
          x="0" y="0"
          :width="svgWidth" :height="svgHeight"
          fill="rgba(0,0,0,0.60)"
          :mask="`url(#${maskId})`"
        />

        <polygon
          v-if="screenPoints.length >= 3"
          :points="screenPointsString"
          fill="none"
          stroke="#22d3a0"
          stroke-width="2"
          stroke-dasharray="6 3"
          opacity="0.7"
        />

        <g v-for="(pt, i) in screenPoints" :key="i">
          <circle :cx="pt.x" :cy="pt.y" r="5" fill="#22d3a0" opacity="0.9"/>
          <circle :cx="pt.x" :cy="pt.y" r="9" fill="none" stroke="#22d3a0" stroke-width="1" opacity="0.4"/>
        </g>
      </svg>

    </template>
  </div>
</template>

<script setup>
  import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
  import * as Cesium from 'cesium'

  const maskId = `cutout-mask-${Math.random().toString(36).slice(2, 8)}`

  const props = defineProps({
    visible: { type: Boolean, default: false },
    geometry: { type: Object, default: null },
    cesiumViewer: { type: Object, default: null },
    viewMode: { type: String, default: '2D' }
  })

  const is2D = computed(() => props.viewMode === '2D')

  // ========================================
  // 2D SVG STATE & PROJECTION
  // ========================================
  const svgWidth = ref(window.innerWidth)
  const svgHeight = ref(window.innerHeight)
  const screenPoints = ref([])

  function geoToScreen(lon, lat, height = 0) {
    if (!props.cesiumViewer) return null
    try {
      const cartesian = Cesium.Cartesian3.fromDegrees(lon, lat, height)
      const cameraDirection = props.cesiumViewer.camera.direction
      const toPoint = Cesium.Cartesian3.subtract(
        cartesian,
        props.cesiumViewer.camera.position,
        new Cesium.Cartesian3()
      )
      if (Cesium.Cartesian3.dot(cameraDirection, toPoint) < 0) return null

      const screenPos = Cesium.SceneTransforms.worldToWindowCoordinates(
        props.cesiumViewer.scene,
        cartesian,
        new Cesium.Cartesian2()
      )
      if (!screenPos) return null
      if (screenPos.x < -100 || screenPos.x > window.innerWidth + 100) return null
      if (screenPos.y < -100 || screenPos.y > window.innerHeight + 100) return null
      return { x: screenPos.x, y: screenPos.y }
    } catch (e) {
      return null
    }
  }

  function buildScreenPoints() {
    if (!props.geometry || !props.cesiumViewer) {
      screenPoints.value = []
      return
    }

    let coords = []
    if (props.geometry.type === 'boundingBox' && props.geometry.bounds) {
      const { minLon, maxLon, minLat, maxLat } = props.geometry.bounds
      coords = [
        [minLon, minLat],
        [maxLon, minLat],
        [maxLon, maxLat],
        [minLon, maxLat],
      ]
    } else if (props.geometry.type === 'polygon' && props.geometry.geoJSON) {
      coords = props.geometry.geoJSON.coordinates[0].slice(0, -1)
    }

    screenPoints.value = coords
      .map(([lon, lat]) => geoToScreen(lon, lat))
      .filter(Boolean)
  }

  // Reprojection for 2D SVG
  let rafId = null
  function startReprojection() {
    function tick() {
      buildScreenPoints()
      rafId = requestAnimationFrame(tick)
    }
    tick()
  }
  function stopReprojection() {
    if (rafId) cancelAnimationFrame(rafId)
    rafId = null
  }

  const screenPointsString = computed(() =>
    screenPoints.value.map(p => `${p.x},${p.y}`).join(' ')
  )

  const zoneBadgePos = computed(() => {
    if (screenPoints.value.length < 3) return null
    const xs = screenPoints.value.map(p => p.x)
    const ys = screenPoints.value.map(p => p.y)
    return {
      x: (Math.min(...xs) + Math.max(...xs)) / 2,
      y: (Math.min(...ys) + Math.max(...ys)) / 2
    }
  })

  const badgeStyle = computed(() => {
    if (!zoneBadgePos.value) return {}
    return {
      left: zoneBadgePos.value.x + 'px',
      top: zoneBadgePos.value.y + 'px',
      transform: 'translate(-50%, -50%)'
    }
  })

  // ========================================
  // 3D CESIUM ENTITIES
  // ========================================
  let cesiumEntities = [] // track entities we add to viewer

  // Get geometry coordinates in [lon, lat] format
  function getGeometryCoords() {
    if (!props.geometry) return []
    if (props.geometry.type === 'boundingBox' && props.geometry.bounds) {
      const { minLon, maxLon, minLat, maxLat } = props.geometry.bounds
      return [
        [minLon, minLat],
        [maxLon, minLat],
        [maxLon, maxLat],
        [minLon, maxLat]
      ]
    }
    if (props.geometry.type === 'polygon' && props.geometry.geoJSON) {
      return props.geometry.geoJSON.coordinates[0].slice(0, -1)
    }
    return []
  }

  // Add 3D highlight entities to Cesium viewer
  function add3DHighlight() {
    if (!props.cesiumViewer || !props.geometry) return

    const coords = getGeometryCoords()
    // Polygons must have at least 3 points
    if (coords.length < 3) return

    // Convert to Cesium coordinates
    const positions = coords.map(([lon, lat]) => Cesium.Cartesian3.fromDegrees(lon, lat))

    // Semi-transparent fill polygon clamped to terrain
    const fillEntity = props.cesiumViewer.entities.add({
      polygon: {
        // Avoid z-fighting by slightly raising the polygon above ground
        hierarchy: new Cesium.PolygonHierarchy(positions),
        // Transparent fill
        material: Cesium.Color.fromCssColorString('#22d3a0').withAlpha(0.18),
        // Clamp to terrain
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        // Ensure it renders on top of terrain but below other entities
        classificationType: Cesium.ClassificationType.BOTH
      }
    })
    cesiumEntities.push(fillEntity)

    // Border polyline clamped to ground
    const borderPositions = [...positions, positions[0]]
    // Dashed line material for bordeer
    const borderEntity = props.cesiumViewer.entities.add({
      polyline: {
        positions: borderPositions,
        width: 3,
        material: new Cesium.PolylineDashMaterialProperty({
          color: Cesium.Color.fromCssColorString('#22d3a0'),
          dashLength: 12
        }),
        clampToGround: true
      }
    })
    cesiumEntities.push(borderEntity)

    // Corner point entities
    coords.forEach(([lon, lat]) => {
      const ptEntity = props.cesiumViewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(lon, lat),
        point: {
          pixelSize: 7,
          color: Cesium.Color.fromCssColorString('#22d3a0'),
          outlineColor: Cesium.Color.fromCssColorString('#22d3a0').withAlpha(0.4),
          outlineWidth: 3,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
        }
      })
      cesiumEntities.push(ptEntity)
    })

    // Request a render so entities appear immediately
    if (props.cesiumViewer.scene) {
      props.cesiumViewer.scene.requestRender()
    }
  }

  function remove3DHighlight() {
    if (!props.cesiumViewer) return
    cesiumEntities.forEach(entity => {
      try { props.cesiumViewer.entities.remove(entity) } catch (e) { /* already removed */ }
    })
    cesiumEntities = []
    if (props.cesiumViewer.scene) {
      props.cesiumViewer.scene.requestRender()
    }
  }

  // ========================================
  // ORCHESTRATION: switch between 2D/3D
  // ========================================
  function syncHighlight() {
    // Always clean up first
    stopReprojection()
    remove3DHighlight()

    if (!props.visible || !props.geometry) return

    if (is2D.value) {
      startReprojection()
    } else {
      add3DHighlight()
    }
  }

  watch(() => props.visible, syncHighlight)
  watch(() => props.viewMode, syncHighlight)
  watch(() => props.geometry, syncHighlight, { deep: true })

  onUnmounted(() => {
    stopReprojection()
    remove3DHighlight()
  })

  // Resize handling (2D only)
  function onResize() {
    svgWidth.value = window.innerWidth
    svgHeight.value = window.innerHeight
  }
  onMounted(() => window.addEventListener('resize', onResize))
  onUnmounted(() => window.removeEventListener('resize', onResize))
</script>

<style src="./SelectionOverlay.css" scoped></style>
