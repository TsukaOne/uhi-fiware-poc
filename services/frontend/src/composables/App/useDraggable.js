import { ref, computed } from 'vue'

/**
 * useDraggable — Makes a floating panel draggable anywhere on screen.
 *
 * Reusable for any panel that needs a drag handle (toolbox bar, temperature panel, etc.).
 * The caller is responsible for registering onMouseMove and stopDrag on the window,
 * since those listeners are typically shared with other global mouse handlers.
 *
 * Usage:
 *   const { style, startDrag, onMouseMove, stopDrag } = useDraggable(initialX, initialY)
 *   // Template: <div :style="style"> <handle @mousedown="startDrag"> </div>
 *   // Window:   window.addEventListener('mousemove', onMouseMove)
 *   //           window.addEventListener('mouseup', stopDrag)
 *
 * @param {number} initialX - Starting left position in pixels
 * @param {number} initialY - Starting top position in pixels
 */
export function useDraggable(initialX, initialY) {

  const position = ref({ x: initialX, y: initialY })
  const isDragging = ref(false)

  // Offset between the pointer position and the panel's top-left corner,
  // captured on mousedown so the panel doesn't jump when drag starts.
  let offsetX = 0
  let offsetY = 0

  /** CSS style object to bind with :style on the panel element */
  const style = computed(() => ({
    left: position.value.x + 'px',
    top:  position.value.y + 'px',
  }))

  /** Call this on the drag handle's mousedown event to begin dragging */
  function startDrag(e) {
    isDragging.value = true
    offsetX = e.clientX - position.value.x
    offsetY = e.clientY - position.value.y
  }

  /** Call this from the global window mousemove handler */
  function onMouseMove(e) {
    if (!isDragging.value) return
    position.value.x = e.clientX - offsetX
    position.value.y = e.clientY - offsetY
  }

  /** Call this from the global window mouseup handler */
  function stopDrag() {
    isDragging.value = false
  }

  return { position, isDragging, style, startDrag, onMouseMove, stopDrag }
}
