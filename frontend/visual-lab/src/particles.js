import * as THREE from 'three';
import { CONFIG } from './config.js';
import { generateParticles } from './generate.js';

export function createDust(scene) {
  const layers = [];
  for (const kind of Object.keys(CONFIG.particles)) {
    const data = generateParticles(kind), geometry = new THREE.BufferGeometry();
    for (const [name, size] of [['position', 3], ['color', 3], ['scale', 1], ['phase', 1], ['alpha', 1], ['haze', 1]]) geometry.setAttribute(name === 'position' ? name : `a${name}`, new THREE.BufferAttribute(data[name], size));
    const material = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending,
      uniforms: { clock: { value: 0 }, pixels: { value: 900 }, maxPixels: { value: CONFIG.maxSprite[kind] }, resolvePixels: { value: CONFIG.hazeResolvePixels }, fadeFloor: { value: CONFIG.hazeFadeFloor }, drift: { value: kind === 'field' ? 0 : CONFIG.motion.amplitude } },
      vertexShader: `
        attribute vec3 acolor; attribute float ascale, aphase, aalpha, ahaze;
        uniform float clock, pixels, drift, maxPixels, resolvePixels, fadeFloor;
        varying vec3 tint; varying float breathe, alpha, haze;
        void main(){
          vec3 p = position;
          // Bounded local movement preserves the arms and never rotates the network.
          p += drift * vec3(sin(clock*.21+aphase), sin(clock*.17+aphase)*.5, cos(clock*.19+aphase));
          vec4 view = modelViewMatrix * vec4(p,1.);
          gl_Position = projectionMatrix * view;
          float projected = ascale * pixels / max(1.,-view.z);
          gl_PointSize = clamp(projected, .7, maxPixels);
          float resolve = clamp(resolvePixels / max(projected,.001), fadeFloor,1.);
          tint = acolor; alpha = aalpha * mix(1.,resolve,ahaze); haze = ahaze; breathe = .94 + .06*sin(clock*.27+aphase);
        }`,
      fragmentShader: `
        varying vec3 tint; varying float breathe, alpha, haze;
        void main(){
          float r = length(gl_PointCoord-vec2(.5))*2.;
          if(r>1.) discard;
          float falloff = mix(5.,3.5,haze);
          float a = (exp(-r*r*falloff)-exp(-falloff))*alpha*breathe;
          gl_FragColor=vec4(tint,a);
        }`,
    });
    for (const isHaze of [false, true]) {
      const indices = [];
      for (let i = 0; i < data.count; i++) if (Boolean(data.haze[i]) === isHaze) indices.push(i);
      if (!indices.length) continue;
      const subset = new THREE.BufferGeometry();
      for (const [name, attribute] of Object.entries(geometry.attributes)) subset.setAttribute(name, attribute);
      subset.setIndex(indices);
      const points = new THREE.Points(subset, material.clone()); points.frustumCulled = false;
      points.layers.set(isHaze ? 1 : 0); points.userData.kind = kind; points.userData.renderScale = isHaze ? CONFIG.hazeRenderScale : 1;
      scene.add(points); layers.push(points);
    }
    material.dispose();
  }
  return {
    update(clock) { for (const points of layers) points.material.uniforms.clock.value = clock; },
    resize(height, dpr) { layers.forEach(points => { const ratio = dpr * points.userData.renderScale; points.material.uniforms.pixels.value = height * ratio; points.material.uniforms.maxPixels.value = CONFIG.maxSprite[points.userData.kind] * ratio; points.material.uniforms.resolvePixels.value = CONFIG.hazeResolvePixels * ratio; }); },
    count: Object.values(CONFIG.particles).reduce((sum, value) => sum + value, 0),
  };
}
