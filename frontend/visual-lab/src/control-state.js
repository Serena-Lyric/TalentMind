import { CONFIG } from './config.js';
export const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
export function protectsInput(event) {
  return Boolean(event.isComposing || event.ctrlKey || event.metaKey || event.altKey ||
    event.target?.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target?.tagName));
}
export function wheelState(speed, distance, selection, delta) {
  if (selection !== null) return { speed, distance: clamp(distance * Math.exp(clamp(delta * .001, -6, 6)), CONFIG.camera.min, CONFIG.camera.max) };
  return { speed: clamp(speed - delta * .001, CONFIG.motion.min, CONFIG.motion.max), distance };
}
