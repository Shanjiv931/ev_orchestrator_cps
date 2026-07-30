import { useEffect } from "react";

/**
 * R3F sizes its <canvas> from a ResizeObserver that can miss the container's
 * initial layout pass in some browser contexts (seen in automated/headless
 * panes where requestAnimationFrame is throttled), leaving the canvas stuck
 * at the default 300x150. setTimeout (unlike rAF) still fires in those
 * contexts, so it's used here to force R3F to re-measure its container.
 */
export function useCanvasResizeKick() {
  useEffect(() => {
    const id = setTimeout(() => window.dispatchEvent(new Event("resize")), 50);
    return () => clearTimeout(id);
  }, []);
}
