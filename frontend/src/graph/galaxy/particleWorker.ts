import { createGalaxySpatialFieldCache, type FieldInput } from './GalaxySpatialField'
// @ts-expect-error Existing deterministic particle generator.
import { generateParticles } from './generate.js'
// @ts-expect-error Existing particle configuration.
import { CONFIG } from './config.js'

const worker = self as unknown as {
  onmessage: ((event: MessageEvent<{ input: FieldInput | null }>) => void) | null
  postMessage: (value: unknown, transfer: Transferable[]) => void
}
worker.onmessage = ({ data }) => {
  const started = performance.now()
  const field = data.input ? createGalaxySpatialFieldCache().get(data.input) : null
  for (const kind of Object.keys(CONFIG.particles)) {
    const particles = generateParticles(kind, field)
    worker.postMessage({ kind, particles, elapsedMs: performance.now() - started },
      [particles.position.buffer, particles.color.buffer, particles.scale.buffer, particles.phase.buffer])
  }
}
