import * as THREE from 'three';
import { CONFIG } from './config.js';
import { generateParticles } from './generate.js';

export function createDust(scene, visual = 'baseline') {
  const layers = [];
  let pixelRatio = 1;
  for (const kind of Object.keys(CONFIG.particles)) {
    const data = generateParticles(kind), geometry = new THREE.BufferGeometry();
    for (const [name, size] of [['position', 3], ['color', 3], ['scale', 1], ['phase', 1]]) geometry.setAttribute(name === 'position' ? name : `a${name}`, new THREE.BufferAttribute(data[name], size));
    const [size, opacity] = CONFIG.layers[kind];
    const material = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending,
      uniforms: { clock: { value: 0 }, size: { value: size }, opacity: { value: opacity }, pixels: { value: 900 }, maxPixels: { value: CONFIG.maxSprite[kind] }, drift: { value: kind === 'field' ? 0 : CONFIG.motion.amplitude } },
      vertexShader: `
        attribute vec3 acolor; attribute float ascale; attribute float aphase;
        uniform float clock, size, pixels, drift, maxPixels;
        varying vec3 tint; varying float breathe;
        void main(){
          vec3 p = position;
          // Bounded local movement preserves the arms and never rotates the network.
          p += drift * vec3(sin(clock*.21+aphase), sin(clock*.17+aphase)*.5, cos(clock*.19+aphase));
          vec4 view = modelViewMatrix * vec4(p,1.);
          gl_Position = projectionMatrix * view;
          gl_PointSize = clamp(size * ascale * pixels / max(1.,-view.z), .7, maxPixels);
          tint = acolor; breathe = .94 + .06*sin(clock*.27+aphase);
        }`,
      fragmentShader: `
        uniform float opacity; varying vec3 tint; varying float breathe;
        void main(){
          float r = length(gl_PointCoord-vec2(.5))*2.;
          if(r>1.) discard;
          float a = (exp(-r*r*5.)-exp(-5.))*opacity*breathe;
          gl_FragColor=vec4(tint,a);
        }`,
    });
    const points = new THREE.Points(geometry, material); points.frustumCulled = false;
    scene.add(points); layers.push({ kind, points });
  }
  return {
    update(clock, distance = CONFIG.camera.distance, fov = CONFIG.camera.fov) {
      const span = distance * Math.tan(fov * Math.PI / 360) / Math.tan(CONFIG.camera.fov * Math.PI / 360);
      const t = visual === 'adaptive' ? THREE.MathUtils.clamp((CONFIG.adaptive.far - span) / (CONFIG.adaptive.far - CONFIG.adaptive.near), 0, 1) : 0;
      const detail = t * t * (3 - 2 * t);
      for (const { kind, points } of layers) {
        const uniforms = points.material.uniforms, [opacity, cap] = CONFIG.adaptive.layers[kind];
        uniforms.clock.value = clock;
        uniforms.opacity.value = CONFIG.layers[kind][1] * (1 + (opacity - 1) * detail);
        uniforms.maxPixels.value = CONFIG.maxSprite[kind] * pixelRatio * (1 + (cap - 1) * detail);
      }
    },
    resize(height, dpr) { pixelRatio = dpr; layers.forEach(({ kind, points }) => { points.material.uniforms.pixels.value = height * dpr; points.material.uniforms.maxPixels.value = CONFIG.maxSprite[kind] * dpr; }); },
    count: Object.values(CONFIG.particles).reduce((sum, value) => sum + value, 0),
  };
}
