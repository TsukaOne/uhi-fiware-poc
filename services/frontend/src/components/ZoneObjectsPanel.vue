<template>
  <!-- Main panel (hidden, not destroyed) -->
  <div v-if="visible" class="zone-objects-panel" :style="panelStyle" v-show="!isHidden">

    <!-- Toolbar: drag handle + title + hide arrow -->
    <div class="zop-toolbar">
      <div class="zop-drag" @mousedown.stop.prevent="startDragPanel" title="Drag to move">
        <i class="fas fa-ellipsis-vertical"></i>
      </div>
      <span class="zop-toolbar-title">
        <i class="fas fa-cubes"></i> Zone Objects
      </span>
      <button class="zop-hide-btn" @click="isHidden = true" title="Hide panel">
        <i class="fas fa-chevron-left"></i>
      </button>
    </div>

    <div class="zop-body">

      <!-- Visual drag-and-drop schema -->
      <div class="zop-schema">
        <div class="schema-steps">
          <div class="schema-step">
            <div class="schema-icon"><i class="fas fa-hand-pointer"></i></div>
            <span>Grab</span>
          </div>
          <div class="schema-arrow"><i class="fas fa-arrow-right"></i></div>
          <div class="schema-step">
            <div class="schema-icon"><i class="fas fa-arrows-alt"></i></div>
            <span>Drag</span>
          </div>
          <div class="schema-arrow"><i class="fas fa-arrow-right"></i></div>
          <div class="schema-step">
            <div class="schema-icon"><i class="fas fa-map-marker-alt"></i></div>
            <span>Drop on map</span>
          </div>
        </div>
        <p class="schema-hint">Drag objects from catalog onto the 3D map inside your zone.</p>
      </div>

      <!-- CATEGORY: Vegetation (collapsible) -->
      <div class="zop-category">
        <button class="zop-cat-toggle" @click="catOpen.vegetation = !catOpen.vegetation">
          <div class="zop-cat-title-inner">
            <i class="fas fa-tree"></i> Vegetation
          </div>
          <i :class="catOpen.vegetation ? 'fas fa-chevron-up' : 'fas fa-chevron-down'" class="zop-cat-chevron"></i>
        </button>
        <div v-if="catOpen.vegetation" class="zop-items">
          <div
            class="zop-item"
            draggable="true"
            @dragstart="onDragStart($event, 'tree_deciduous')"
          >
            <div class="zop-item-icon"><i class="fas fa-tree"></i></div>
            <span>Deciduous Tree</span>
          </div>
          <div
            class="zop-item"
            draggable="true"
            @dragstart="onDragStart($event, 'tree_conifer')"
          >
            <div class="zop-item-icon"><i class="fas fa-tree"></i></div>
            <span>Conifer Tree</span>
          </div>
          <div
            class="zop-item"
            draggable="true"
            @dragstart="onDragStart($event, 'shrub')"
          >
            <div class="zop-item-icon"><i class="fas fa-seedling"></i></div>
            <span>Shrub / Hedge</span>
          </div>
          <div
            class="zop-item"
            draggable="true"
            @dragstart="onDragStart($event, 'grass')"
          >
            <div class="zop-item-icon"><i class="fas fa-leaf"></i></div>
            <span>Grass Patch</span>
          </div>
        </div>
      </div>

      <!-- CATEGORY: Buildings (collapsible) -->
      <div class="zop-category">
        <button class="zop-cat-toggle" @click="catOpen.buildings = !catOpen.buildings">
          <div class="zop-cat-title-inner">
            <i class="fas fa-building"></i> Buildings
          </div>
          <i :class="catOpen.buildings ? 'fas fa-chevron-up' : 'fas fa-chevron-down'" class="zop-cat-chevron"></i>
        </button>
        <div v-if="catOpen.buildings" class="zop-items">
          <div
            class="zop-item"
            draggable="true"
            @dragstart="onDragStart($event, 'building_residential')"
          >
            <div class="zop-item-icon"><i class="fas fa-house"></i></div>
            <span>Residential</span>
          </div>
          <div
            class="zop-item"
            draggable="true"
            @dragstart="onDragStart($event, 'building_commercial')"
          >
            <div class="zop-item-icon"><i class="fas fa-building"></i></div>
            <span>Commercial</span>
          </div>
          <div
            class="zop-item"
            draggable="true"
            @dragstart="onDragStart($event, 'building_industrial')"
          >
            <div class="zop-item-icon"><i class="fas fa-industry"></i></div>
            <span>Industrial</span>
          </div>
        </div>
      </div>

      <!-- CATEGORY: Urban Furniture (collapsible) -->
      <div class="zop-category">
        <button class="zop-cat-toggle" @click="catOpen.furniture = !catOpen.furniture">
          <div class="zop-cat-title-inner">
            <i class="fas fa-road"></i> Urban Furniture
          </div>
          <i :class="catOpen.furniture ? 'fas fa-chevron-up' : 'fas fa-chevron-down'" class="zop-cat-chevron"></i>
        </button>
        <div v-if="catOpen.furniture" class="zop-items">
          <div
            class="zop-item"
            draggable="true"
            @dragstart="onDragStart($event, 'water_fountain')"
          >
            <div class="zop-item-icon"><i class="fas fa-droplet"></i></div>
            <span>Water Fountain</span>
          </div>
          <div
            class="zop-item"
            draggable="true"
            @dragstart="onDragStart($event, 'park_bench')"
          >
            <div class="zop-item-icon"><i class="fas fa-chair"></i></div>
            <span>Park Bench</span>
          </div>
          <div
            class="zop-item"
            draggable="true"
            @dragstart="onDragStart($event, 'solar_panel')"
          >
            <div class="zop-item-icon"><i class="fas fa-solar-panel"></i></div>
            <span>Solar Panel</span>
          </div>
        </div>
      </div>

      <!-- Placed objects (collapsible dropdown) -->
      <div v-if="placedObjects.length > 0" class="zop-placed">
        <button class="zop-cat-toggle placed" @click="showPlaced = !showPlaced">
          <div class="zop-cat-title-inner">
            <i class="fas fa-list"></i> Placed ({{ placedObjects.length }})
          </div>
          <i :class="showPlaced ? 'fas fa-chevron-up' : 'fas fa-chevron-down'" class="zop-cat-chevron"></i>
        </button>
        <div v-if="showPlaced" class="zop-placed-list">
          <div
            v-for="(obj, idx) in placedObjects"
            :key="obj.id"
            class="zop-placed-item"
          >
            <span class="zop-placed-name">{{ obj.label }}</span>
            <button class="zop-remove-btn" @click="removeObject(idx)" title="Remove">
              <i class="fas fa-trash-alt"></i>
            </button>
          </div>
        </div>
        <div class="zop-action-row">
          <button class="zop-toggle-btn" @click="toggleObjectsVisibility" :title="objectsVisible ? 'Hide 3D objects' : 'Show 3D objects'">
            <i :class="objectsVisible ? 'fas fa-eye' : 'fas fa-eye-slash'"></i>
            {{ objectsVisible ? 'Hide' : 'Show' }}
          </button>
          <button class="zop-clear-btn" @click="clearAllObjects">
            <i class="fas fa-broom"></i> Clear All
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Mini restore button when hidden -->
  <button v-if="visible && isHidden" class="zop-restore-btn" @click="isHidden = false" title="Show Zone Objects">
    <i class="fas fa-cubes"></i>
  </button>
</template>

<script setup>
  import { ref, reactive, computed, watch, onMounted, onUnmounted, onBeforeUnmount } from 'vue'
  import * as Cesium from 'cesium'

  const props = defineProps({
    visible: { type: Boolean, default: false },
    geometry: { type: Object, default: null },
    cesiumViewer: { type: Object, default: null }
  })

  const emit = defineEmits(['close', 'objects-changed'])

  const placedObjects = ref([])
  const objectsVisible = ref(true)
  const isHidden = ref(false)
  const showPlaced = ref(true)
  let placedEntities = [] // Cesium entity references for cleanup

  // Category open state (all collapsed by default)
  const catOpen = reactive({
    vegetation: false,
    buildings: false,
    furniture: false,
  })

  // Drag state
  const panelPos = ref({ x: 16, y: 70 })
  const isDragging = ref(false)
  let dragOffsetX = 0
  let dragOffsetY = 0

  const panelStyle = computed(() => ({
    left: panelPos.value.x + 'px',
    top: panelPos.value.y + 'px',
  }))

  function startDragPanel(e) {
    isDragging.value = true
    const el = e.target.closest('.zone-objects-panel')
    const rect = el.getBoundingClientRect()
    dragOffsetX = e.clientX - rect.left
    dragOffsetY = e.clientY - rect.top
  }

  function onPanelMouseMove(e) {
    if (!isDragging.value) return
    panelPos.value.x = e.clientX - dragOffsetX
    panelPos.value.y = e.clientY - dragOffsetY
  }

  function stopPanelDrag() {
    isDragging.value = false
  }

  // Object type configs: icon color, default size, label
  const OBJECT_TYPES = {
    tree_deciduous: { label: 'Deciduous Tree', color: '#22c55e', icon: 'tree', height: 12 },
    tree_conifer:   { label: 'Conifer Tree',   color: '#15803d', icon: 'tree', height: 15 },
    shrub:          { label: 'Shrub / Hedge',  color: '#86efac', icon: 'seedling', height: 3 },
    grass:          { label: 'Grass Patch',    color: '#4ade80', icon: 'leaf', height: 0.5 },
    building_residential: { label: 'Residential', color: '#f59e0b', icon: 'house', height: 10 },
    building_commercial:  { label: 'Commercial',  color: '#3b82f6', icon: 'building', height: 25 },
    building_industrial:  { label: 'Industrial',  color: '#6b7280', icon: 'industry', height: 15 },
    water_fountain: { label: 'Water Fountain', color: '#06b6d4', icon: 'droplet', height: 2 },
    park_bench:     { label: 'Park Bench',     color: '#a78bfa', icon: 'chair', height: 1 },
    solar_panel:    { label: 'Solar Panel',    color: '#eab308', icon: 'solar-panel', height: 3 }
  }

  // Drag-and-drop handler
  function onDragStart(event, objectType) {
    event.dataTransfer.setData('application/zone-object', objectType)
    event.dataTransfer.effectAllowed = 'copy'
  }

  // Check if a lon/lat is inside the zone geometry
  function isInsideZone(lon, lat) {
    if (!props.geometry) return false

    let coords
    if (props.geometry.type === 'boundingBox' && props.geometry.bounds) {
      const { minLon, maxLon, minLat, maxLat } = props.geometry.bounds
      return lon >= minLon && lon <= maxLon && lat >= minLat && lat <= maxLat
    }

    if (props.geometry.type === 'polygon' && props.geometry.geoJSON) {
      coords = props.geometry.geoJSON.coordinates[0]
      // Ray casting algorithm
      let inside = false
      for (let i = 0, j = coords.length - 1; i < coords.length; j = i++) {
        const [xi, yi] = coords[i]
        const [xj, yj] = coords[j]
        const intersect = ((yi > lat) !== (yj > lat)) &&
          (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi)
        if (intersect) inside = !inside
      }
      return inside
    }

    return false
  }

  // Place an object at the given coordinates
  function placeObjectAt(objectType, lon, lat) {
    if (!props.cesiumViewer) return

    const config = OBJECT_TYPES[objectType]
    if (!config) return

    // Verify the drop is inside the zone
    if (!isInsideZone(lon, lat)) {
      console.warn('Object dropped outside zone, ignoring')
      return
    }

    const id = `zobj_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
    const color = Cesium.Color.fromCssColorString(config.color)

    // FOR TEST : Add a simple 3D representation: a colored cylinder/box clamped to ground
    const entity = props.cesiumViewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(lon, lat, config.height / 2),
      cylinder: {
        length: config.height,
        topRadius: config.height > 5 ? config.height * 0.3 : Math.max(1, config.height * 0.5),
        bottomRadius: config.height > 5 ? config.height * 0.35 : Math.max(1.2, config.height * 0.6),
        material: color.withAlpha(0.8),
        outline: true,
        outlineColor: color,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        classificationType: Cesium.ClassificationType.BOTH

      }
    })

    placedEntities.push(entity)
    placedObjects.value.push({
      id,
      type: objectType,
      label: config.label,
      lon,
      lat
    })

    emit('objects-changed', [...placedObjects.value])
    props.cesiumViewer.scene.requestRender()
  }

  // Remove an object by index
  function removeObject(idx) {
    if (!props.cesiumViewer) return

    const entity = placedEntities[idx]
    if (entity) {
      props.cesiumViewer.entities.remove(entity)
    }
    placedEntities.splice(idx, 1)
    placedObjects.value.splice(idx, 1)

    emit('objects-changed', [...placedObjects.value])
    props.cesiumViewer.scene.requestRender()
  }

  // Clear all objects
  function clearAllObjects() {
    if (!props.cesiumViewer) return

    placedEntities.forEach(entity => {
      try { props.cesiumViewer.entities.remove(entity) } catch (e) { /* ok */ }
    })
    placedEntities = []
    placedObjects.value = []

    emit('objects-changed', [])
    props.cesiumViewer.scene.requestRender()
  }

  // Toggle visibility of all placed 3D entities
  function toggleObjectsVisibility() {
    objectsVisible.value = !objectsVisible.value
    placedEntities.forEach(entity => {
      entity.show = objectsVisible.value
    })
    if (props.cesiumViewer) {
      props.cesiumViewer.scene.requestRender()
    }
  }

  // Handle drop on the Cesium canvas
  function onCanvasDrop(event) {
    event.preventDefault()
    const objectType = event.dataTransfer.getData('application/zone-object')
    if (!objectType || !props.cesiumViewer || !props.visible) return

    // Convert screen position to geographic coordinates
    const viewer = props.cesiumViewer
    const screenPos = new Cesium.Cartesian2(event.offsetX, event.offsetY)

    let cartesian = viewer.scene.pickPosition(screenPos)
    if (!Cesium.defined(cartesian)) {
      const ray = viewer.camera.getPickRay(screenPos)
      if (ray) cartesian = viewer.scene.globe.pick(ray, viewer.scene)
    }
    if (!Cesium.defined(cartesian)) {
      cartesian = viewer.camera.pickEllipsoid(screenPos, viewer.scene.globe.ellipsoid)
    }
    if (!Cesium.defined(cartesian)) return

    const cartographic = Cesium.Cartographic.fromCartesian(cartesian)
    const lon = Cesium.Math.toDegrees(cartographic.longitude)
    const lat = Cesium.Math.toDegrees(cartographic.latitude)

    placeObjectAt(objectType, lon, lat)
  }

  function onCanvasDragOver(event) {
    if (!props.visible) return
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
  }

  // Attach/detach drop listeners on the Cesium canvas
  let canvasEl = null

  function attachDropListeners() {
    if (!props.cesiumViewer) return
    canvasEl = props.cesiumViewer.scene.canvas
    if (canvasEl) {
      canvasEl.addEventListener('drop', onCanvasDrop)
      canvasEl.addEventListener('dragover', onCanvasDragOver)
    }
  }

  function detachDropListeners() {
    if (canvasEl) {
      canvasEl.removeEventListener('drop', onCanvasDrop)
      canvasEl.removeEventListener('dragover', onCanvasDragOver)
      canvasEl = null
    }
  }

  watch(() => props.visible, (v) => {
    if (v) {
      isHidden.value = false
      attachDropListeners()
    }
    else detachDropListeners()
  })

  watch(() => props.cesiumViewer, () => {
    if (props.visible) {
      detachDropListeners()
      attachDropListeners()
    }
  })

  // Clean up everything on geometry change or unmount
  watch(() => props.geometry, () => {
    clearAllObjects()
  })

  onMounted(() => {
    if (props.visible) attachDropListeners()
    window.addEventListener('mousemove', onPanelMouseMove)
    window.addEventListener('mouseup', stopPanelDrag)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('mousemove', onPanelMouseMove)
    window.removeEventListener('mouseup', stopPanelDrag)
  })

  onUnmounted(() => {
    clearAllObjects()
    detachDropListeners()
  })
</script>

<style scoped>
  .zone-objects-panel {
    position: absolute;
    width: 260px;
    max-height: calc(100vh - 100px);
    background: rgba(15, 20, 32, 0.97);
    backdrop-filter: blur(16px);
    border-radius: 14px;
    border: 1px solid rgba(34, 211, 160, 0.15);
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
    z-index: 1700;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  }

  /* Toolbar */
  .zop-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background: rgba(34, 211, 160, 0.08);
    border-bottom: 1px solid rgba(34, 211, 160, 0.12);
  }

  .zop-drag {
    width: 20px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: grab;
    color: rgba(255, 255, 255, 0.35);
    border-radius: 4px;
    transition: all 0.15s;
    flex-shrink: 0;
  }
  .zop-drag:hover { color: rgba(255,255,255,0.7); background: rgba(255,255,255,0.06); }
  .zop-drag:active { cursor: grabbing; color: white; }

  .zop-toolbar-title {
    flex: 1;
    color: #22d3a0;
    font-size: 13px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .zop-hide-btn {
    width: 26px;
    height: 26px;
    background: rgba(255,255,255,0.06);
    border: none;
    border-radius: 6px;
    color: rgba(255,255,255,0.4);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    transition: all 0.15s;
    flex-shrink: 0;
  }
  .zop-hide-btn:hover { background: rgba(255,255,255,0.12); color: white; }

  /* Restore button */
  .zop-restore-btn {
    position: absolute;
    top: 70px;
    left: 16px;
    width: 36px;
    height: 36px;
    background: rgba(10, 14, 22, 0.95);
    border: 1px solid rgba(34, 211, 160, 0.25);
    border-radius: 8px;
    color: #22d3a0;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    z-index: 1700;
    transition: all 0.15s;
    box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  }
  .zop-restore-btn:hover { background: rgba(34, 211, 160, 0.15); }

  .zop-body {
    padding: 12px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 10px;
    scrollbar-width: thin;
    scrollbar-color: rgba(34,211,160,0.3) transparent;
  }

  /* Visual schema */
  .zop-schema {
    padding: 10px;
    background: rgba(34, 211, 160, 0.04);
    border: 1px solid rgba(34, 211, 160, 0.12);
    border-radius: 8px;
  }

  .schema-steps {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    margin-bottom: 8px;
  }

  .schema-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }

  .schema-icon {
    width: 36px;
    height: 36px;
    background: rgba(34, 211, 160, 0.1);
    border: 1px solid rgba(34, 211, 160, 0.25);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    color: #22d3a0;
  }

  .schema-step span {
    font-size: 9px;
    color: rgba(255,255,255,0.5);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
  }

  .schema-arrow {
    color: rgba(34, 211, 160, 0.4);
    font-size: 12px;
    margin-top: -14px;
  }

  .schema-hint {
    margin: 0;
    font-size: 10px;
    color: rgba(255, 255, 255, 0.4);
    line-height: 1.4;
    text-align: center;
  }

  /* Category toggle */
  .zop-cat-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 8px 10px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 6px;
    color: rgba(255, 255, 255, 0.5);
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
  }
  .zop-cat-toggle:hover {
    background: rgba(255,255,255,0.06);
    color: rgba(255,255,255,0.7);
  }
  .zop-cat-toggle.placed {
    border-color: rgba(34, 211, 160, 0.15);
  }

  .zop-cat-title-inner {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .zop-cat-chevron {
    font-size: 9px;
    width: 12px;
    text-align: center;
  }

  .zop-items {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
    margin-top: 6px;
  }

  .zop-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 10px 6px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    cursor: grab;
    transition: all 0.15s;
    user-select: none;
  }

  .zop-item:hover {
    background: rgba(34, 211, 160, 0.1);
    border-color: rgba(34, 211, 160, 0.3);
  }

  .zop-item:active {
    cursor: grabbing;
    transform: scale(0.95);
  }

  .zop-item-icon {
    font-size: 18px;
    color: rgba(255, 255, 255, 0.7);
  }

  .zop-item span {
    font-size: 10px;
    color: rgba(255, 255, 255, 0.6);
    text-align: center;
    line-height: 1.3;
  }

  .zop-placed {
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding-top: 10px;
  }

  .zop-placed-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 150px;
    overflow-y: auto;
    margin-top: 6px;
  }

  .zop-placed-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 8px;
    background: rgba(255, 255, 255, 0.03);
    border-radius: 6px;
    font-size: 11px;
    color: rgba(255, 255, 255, 0.6);
  }

  .zop-placed-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .zop-remove-btn {
    background: none;
    border: none;
    color: rgba(255, 100, 100, 0.5);
    cursor: pointer;
    font-size: 11px;
    padding: 2px 4px;
    transition: color 0.15s;
  }
  .zop-remove-btn:hover {
    color: #f87171;
  }

  .zop-action-row {
    display: flex;
    gap: 6px;
    margin-top: 8px;
  }

  .zop-toggle-btn {
    flex: 1;
    padding: 7px;
    background: rgba(34, 211, 160, 0.08);
    border: 1px solid rgba(34, 211, 160, 0.2);
    border-radius: 6px;
    color: rgba(34, 211, 160, 0.7);
    font-size: 11px;
    cursor: pointer;
    transition: all 0.15s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }
  .zop-toggle-btn:hover {
    background: rgba(34, 211, 160, 0.15);
    color: #22d3a0;
  }

  .zop-clear-btn {
    flex: 1;
    padding: 7px;
    background: rgba(255, 100, 100, 0.08);
    border: 1px solid rgba(255, 100, 100, 0.2);
    border-radius: 6px;
    color: rgba(255, 100, 100, 0.7);
    font-size: 11px;
    cursor: pointer;
    transition: all 0.15s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }
  .zop-clear-btn:hover {
    background: rgba(255, 100, 100, 0.15);
    color: #f87171;
  }
</style>
