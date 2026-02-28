import { ref } from 'vue'

/**
 * Layer Controls Composition Function
 * Manages layer panel state and UI interactions
 */
export function useLayerControls() {
  const isCollapsed = ref(false)

  /**
   * Generate CSS gradient for layer legend
   * Maps min/max values to color gradient
   */
  function getLegendStyle(legend) {
    return {
      background: `linear-gradient(to right, ${legend.min.color}, ${legend.max.color})`
    }
  }

  return {
    isCollapsed,
    getLegendStyle
  }
}
