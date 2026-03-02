<template>
  <div ref="cesiumContainer" class="cesium-container"></div>
</template>

<script setup>
import { useCesiumViewer } from './CesiumViewer.js'

const props = defineProps({
  layers: {
    type: Array,
    required: true
  },
  activeLayers: {
    type: Array,
    default: () => []
  },
  viewMode: {
    type: String,
    required: true
  },
  buildingVisible: {
    type: Boolean,
    default: true
  },
  drawingMode: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['geometry-drawn'])

const { cesiumContainer, getViewer, flyTo } = useCesiumViewer(props, emit)

defineExpose({
  getViewer,
  flyTo
})
</script>

<style src="./CesiumViewer.css"></style>

