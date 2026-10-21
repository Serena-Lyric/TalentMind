export function graphShortcut(event: KeyboardEvent, composing = false): 'immersive' | 'panels' | null {
  if (composing || event.isComposing || event.keyCode === 229 || event.repeat || event.defaultPrevented
    || event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) return null
  const path = event.composedPath?.() || []
  const targets = [event.target, ...path] as (Element | null)[]
  if (targets.some(target => target?.closest?.('input, textarea, select, [role="textbox"], [contenteditable]:not([contenteditable="false"])'))) return null
  return event.key.toLowerCase() === 'y' ? 'immersive' : event.key.toLowerCase() === 'h' ? 'panels' : null
}
