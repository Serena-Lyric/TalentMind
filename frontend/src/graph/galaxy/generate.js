import * as THREE from 'three';
import { CONFIG, FAMILIES, spiralPoint } from './config.js';

export function randomSource(seed) {
  let state = seed >>> 0;
  return () => { state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return (state + .5) / 4294967296; };
}
const gaussian = random => Math.sqrt(-2 * Math.log(random())) * Math.cos(2 * Math.PI * random());
const baseColor = new THREE.Color('#6989c5');
const coreColor = new THREE.Color('#ffe7ce');
const familyColors = FAMILIES.map(family => new THREE.Color(family.color));
const starColor = new THREE.Color('#c7daee');
const fieldColor = new THREE.Color('#7385ac');
function noise(x, z) {
  const hash = (a, b) => { const n = Math.sin(a * 83.13 + b * 177.17) * 43871.71; return n - Math.floor(n); };
  const ix = Math.floor(x), iz = Math.floor(z);
  const sx = x - ix, sz = z - iz, u = sx * sx * (3 - 2 * sx), v = sz * sz * (3 - 2 * sz);
  return (hash(ix, iz) * (1 - u) + hash(ix + 1, iz) * u) * (1 - v) + (hash(ix, iz + 1) * (1 - u) + hash(ix + 1, iz + 1) * u) * v;
}

function disk(random, kind) {
  let r;
  do { r = -CONFIG.spiral.diskScale * Math.log(random() * random()); } while (r > CONFIG.radius);
  const branch = Math.floor(random() * 4);
  const fill = Math.exp(-r * r / 380);
  // P1-A.2: small arm meanders/width variations; inter-arm fill is discrete stars, not more fog.
  const variation = noise(r * .05, branch * 3.7);
  const width = CONFIG.spiral.width * (.6 + r / 130) * (.78 + .46 * variation) * (kind === 'mist' ? 1.6 : 1);
  const wander = .075 * (noise(r * .035 + 2, branch * 2.1) - .5) * 2;
  const deviation = gaussian(random) * width + wander + (random() - .5) * Math.PI * 2 * fill;
  let [x, , z] = spiralPoint(r, branch, deviation);
  // A shared exponential disk softly connects the arms at every radius.
  const interarmFraction = kind === 'mist' ? .32 : kind === 'dust' ? .18 : .12;
  if (random() < interarmFraction) {
    const angle = random() * Math.PI * 2; x = r * Math.cos(angle); z = r * Math.sin(angle);
  }
  return [x + gaussian(random) * 1.4, gaussian(random) * (CONFIG.spiral.thickness + 2.6 * fill), z + gaussian(random) * 1.4];
}

function tint(position, random, color) {
  const [x, , z] = position, radius = Math.hypot(x, z);
  let weight = .2;
  let red = baseColor.r * weight, green = baseColor.g * weight, blue = baseColor.b * weight;
  // Preserve the established blue/violet/cyan palette with broad color transitions.
  for (let index = 0; index < FAMILIES.length; index++) {
    const family = FAMILIES[index], tint = familyColors[index];
    const distance = (x-family.center[0])**2 + (z-family.center[2])**2;
    const influence = Math.exp(-distance/(family.spread*1.25)**2)*2.4;
    red += tint.r*influence; green += tint.g*influence; blue += tint.b*influence;
    weight += influence;
  }
  color.setRGB(red/weight, green/weight, blue/weight);
  color.lerp(coreColor, Math.exp(-radius * radius / 150) * .85);
  const texture = noise(x / 11, z / 11) * .65 + noise(x / 3.4, z / 3.4) * .35;
  color.multiplyScalar((.4 + 1.05 * texture) * (.9 + random() * .2));
  return color;
}

export function generateParticles(kind, field = null) {
  const count = CONFIG.particles[kind], seed = field?.nodeCount && kind !== 'field' ? field.seed : CONFIG.seed;
  const random = randomSource(seed + Object.keys(CONFIG.particles).indexOf(kind) * 997);
  const position = new Float32Array(count * 3), color = new Float32Array(count * 3), scale = new Float32Array(count), phase = new Float32Array(count);
  const reusableColor = new THREE.Color();
  for (let i = 0; i < count; i++) {
    let p;
    if (kind === 'core') {
      // Gamma radius avoids an inverse-log pile-up at the origin; no central sprite.
      const r = -3.5 * Math.log(random() * random());
      const angle = random() * Math.PI * 2;
      p = [Math.cos(angle) * r + gaussian(random) * .5, gaussian(random) * (1.5 + r * .16), Math.sin(angle) * r];
    } else if (kind === 'field') {
      const angle = random() * Math.PI * 2, cos = random() * 2 - 1, r = 280 + random() * 220;
      p = [r * Math.sqrt(1 - cos * cos) * Math.cos(angle), r * cos, r * Math.sqrt(1 - cos * cos) * Math.sin(angle)];
    } else {
      do { p = disk(random, kind); } while (random() > .4 + .6 * noise(p[0] / 8, p[2] / 8));
    }
    if (field && field.nodeCount && kind !== 'field') p = field.sample(p, random, kind);
    position.set(p, i * 3);
    const c = kind === 'field' ? reusableColor.copy(fieldColor).multiplyScalar(.4 + random() * .5) : tint(p, random, reusableColor);
    if (kind === 'stars') c.lerp(starColor, .25);
    if (kind !== 'field') {
      const edge = Math.max(0, Math.min(1, (110-Math.hypot(p[0],p[2]))/35));
      c.multiplyScalar(edge * edge * (3-2*edge));
    }
    color.set([c.r, c.g, c.b], i * 3);
    scale[i] = .55 + random() ** 1.5 * 1.6;
    phase[i] = random() * Math.PI * 2;
  }
  return { position, color, scale, phase, count };
}
