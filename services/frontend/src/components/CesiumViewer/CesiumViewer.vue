<template>
  <div ref="cesiumContainer" class="cesium-container"></div>
</template>

<script setup>
  import { useCesiumViewer } from './CesiumViewer.js'

  const props = defineProps({
    layers: { type: Array, required: true },
    activeLayers: { type: Array, default: () => [] },
    viewMode: { type: String, required: true },
    buildingVisible: { type: Boolean, default: true },
    treeVisible: { type: Boolean, default: false },
    drawingMode: { type: String, default: null },
    swipeEnabled: { type: Boolean, default: false },
    swipePosition: { type: Number, default: 0.5 },
    swipeLeftLayerId: { type: String, default: null },
    swipeRightLayerId: { type: String, default: null },
    sunSimEnabled: { type: Boolean, default: false },
    sunSimTime: { type: Number, default: 720 },
    tBase: { type: Number, default: null },
    uhiMin: { type: Number, default: null },
    uhiMax: { type: Number, default: null },
    predictionOverlay: { type: Object, default: null }
  })

  const emit = defineEmits(['geometry-drawn', 'drawing-active', 'pixel-click'])

  const { cesiumContainer, getViewer, flyTo, undoLastPoint } = useCesiumViewer(props, emit)

  defineExpose({
    getViewer,
    flyTo,
    undoLastPoint
  })
</script>

<style src="./CesiumViewer.css"></style>

