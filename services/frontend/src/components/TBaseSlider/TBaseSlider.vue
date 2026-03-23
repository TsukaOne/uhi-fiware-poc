<template>
  <div class="tbase-panel">
    <div class="tbase-header">
      <i class="fas fa-thermometer-half"></i>
      <span class="tbase-title">Live Temperature</span>
      <button
        class="tbase-sync-btn"
        @click="fetchTBase"
        title="Refresh from VLINDER"
      >
        <i class="fas fa-sync-alt"></i>
      </button>
    </div>

    <div class="tbase-body">
      <div class="tbase-value-row">
        <span class="tbase-value">{{ tBase.toFixed(1) }} °C</span>
        <span class="tbase-source" :class="{ fallback: isFallback }">
          <i :class="sourceIcon"></i>
          {{ sourceLabel }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

import { predictionApi } from '../../services/predictionApi.js'

const props = defineProps({
  modelValue: { type: Number, default: 15.0 },
})

const emit = defineEmits(['update:modelValue'])

const tBase = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const isFallback = ref(false)
const stationName = ref('')
let pollTimer = null

const sourceIcon = computed(() => 'fas fa-satellite-dish')

const sourceLabel = computed(() => {
  if (isFallback.value) return `${stationName.value || 'VLINDER'} (cached)`
  return stationName.value || 'VLINDER'
})

async function fetchTBase() {
  try {
    const data = await predictionApi.getTBase()
    stationName.value = data.station_name || data.station_id
    isFallback.value = data.fallback
    tBase.value = data.value
  } catch (err) {
    console.warn('VLINDER fetch failed:', err)
    isFallback.value = true
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(fetchTBase, 10 * 60 * 1000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(() => {
  fetchTBase()
  startPolling()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style src="./TBaseSlider.css" scoped></style>
