<template>
  <div class="selection-overlay-wrapper" v-if="visible">
    <!-- Dark overlay with SVG cutout -->
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

    <!-- Overlay sombre AVEC le masque — la zone découpée reste transparente -->
    <rect
        x="0" y="0"
        :width="svgWidth" :height="svgHeight"
        fill="rgba(0,0,0,0.60)"
        :mask="`url(#${maskId})`"
    />

    <!-- Bordure lumineuse sur la sélection — EN DEHORS du mask -->
    <polygon
        v-if="screenPoints.length >= 3"
        :points="screenPointsString"
        fill="none"
        stroke="#22d3a0"
        stroke-width="2"
        stroke-dasharray="6 3"
        opacity="0.7"
    />

    <!-- Points aux coins -->
    <g v-for="(pt, i) in screenPoints" :key="i">
        <circle :cx="pt.x" :cy="pt.y" r="5" fill="#22d3a0" opacity="0.9"/>
        <circle :cx="pt.x" :cy="pt.y" r="9" fill="none" stroke="#22d3a0" stroke-width="1" opacity="0.4"/>
    </g>
    </svg>

    <!-- Zone info badge -->
    <div
      class="zone-badge"
      :style="badgeStyle"
      v-if="zoneBadgePos"
    >
      <span class="zone-badge-label">ZONE SÉLECTIONNÉE</span>
      <span class="zone-badge-area" v-if="areaKm2">{{ areaKm2 }} km²</span>
    </div>
  </div>
</template>

<script setup>
    import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
    import * as Cesium from 'cesium'

    const maskId = `cutout-mask-${Math.random().toString(36).slice(2, 8)}`

    const props = defineProps({
    visible: { type: Boolean, default: false },
    geometry: { type: Object, default: null }, // { type, geoJSON, bounds }
    cesiumViewer: { type: Object, default: null }
    })

    const svgWidth = ref(window.innerWidth)
    const svgHeight = ref(window.innerHeight)
    const screenPoints = ref([])

    // Convert geo coords to screen pixels via Cesium camera
    function geoToScreen(lon, lat, height = 0) {
        if (!props.cesiumViewer) return null
        
        try {
            // Hauteur 10m pour éviter que le point soit sous le terrain
            const cartesian = Cesium.Cartesian3.fromDegrees(lon, lat, height)
            
            // Vérifier que le point est devant la caméra
            const cameraDirection = props.cesiumViewer.camera.direction
            const toPoint = Cesium.Cartesian3.subtract(
            cartesian, 
            props.cesiumViewer.camera.position, 
            new Cesium.Cartesian3()
            )
            // Produit scalaire : si négatif, le point est derrière la caméra
            if (Cesium.Cartesian3.dot(cameraDirection, toPoint) < 0) return null

            const screenPos = Cesium.SceneTransforms.worldToWindowCoordinates(
            props.cesiumViewer.scene,
            cartesian,
            new Cesium.Cartesian2()
            )
            
            if (!screenPos) return null
            // Filtrer les points hors écran
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
        coords = props.geometry.geoJSON.coordinates[0].slice(0, -1) // remove closing point
    }

    screenPoints.value = coords
        .map(([lon, lat]) => geoToScreen(lon, lat))
        .filter(Boolean)
    }

    // Reproject on every animation frame when visible
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

    watch(() => props.visible, (v) => {
    if (v) startReprojection()
    else stopReprojection()
    })

    onUnmounted(() => stopReprojection())

    const screenPointsString = computed(() =>
    screenPoints.value.map(p => `${p.x},${p.y}`).join(' ')
    )

    // Badge center position
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

    // Rough area calculation (Haversine approximation)
    const areaKm2 = computed(() => {
    if (!props.geometry) return null
    if (props.geometry.type === 'boundingBox' && props.geometry.bounds) {
        const { minLon, maxLon, minLat, maxLat } = props.geometry.bounds
        const R = 6371
        const dLat = (maxLat - minLat) * Math.PI / 180
        const dLon = (maxLon - minLon) * Math.PI / 180
        const midLat = ((minLat + maxLat) / 2) * Math.PI / 180
        const h = R * dLat
        const w = R * dLon * Math.cos(midLat)
        return (h * w).toFixed(2)
    }
    return null
    })

    // Resize handling
    function onResize() {
    svgWidth.value = window.innerWidth
    svgHeight.value = window.innerHeight
    }
    onMounted(() => window.addEventListener('resize', onResize))
    onUnmounted(() => window.removeEventListener('resize', onResize))
</script>

<style scoped>
    .selection-overlay-wrapper {
    position: absolute;
    inset: 0;
    z-index: 1000;
    pointer-events: none;
    }

    .selection-svg {
    position: absolute;
    inset: 0;
    pointer-events: none;
    }

    .zone-badge {
    position: absolute;
    pointer-events: none;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    }

    .zone-badge-label {
    font-family: 'Courier New', monospace;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.15em;
    color: #22d3a0;
    text-shadow: 0 0 12px rgba(34, 211, 160, 0.8);
    white-space: nowrap;
    background: rgba(0, 0, 0, 0.5);
    padding: 3px 8px;
    border-radius: 3px;
    border: 1px solid rgba(34, 211, 160, 0.3);
    }

    .zone-badge-area {
    font-family: 'Courier New', monospace;
    font-size: 13px;
    font-weight: 700;
    color: white;
    text-shadow: 0 0 8px rgba(255,255,255,0.5);
    }
</style>