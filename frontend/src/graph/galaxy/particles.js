import * as THREE from 'three';
import { CONFIG } from './config.js';
import { generateParticles } from './generate.js';

export function createDust(scene, crisp = false) {
  const layers = [];
  for (const kind of Object.keys(CONFIG.particles)) {
    const data = generateParticles(kind), geometry = new THREE.BufferGeometry();
    for (const [name, size] of [['position', 3], ['color', 3], ['scale', 1], ['phase', 1]]) geometry.setAttribute(name === 'position' ? name : `a${name}`, new THREE.BufferAttribute(data[name], size));
    const [size, opacity] = CONFIG.layers[kind];
    const material = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending,
      uniforms: { clock: { value: 0 }, size: { value: size }, opacity: { value: opacity }, pixels: { value: 900 }, maxPixels: { value: CONFIG.maxSprite[kind] }, drift: { value: kind === 'field' ? 0 : CONFIG.motion.amplitude },pixelRatio:{value:1},crisp:{value:crisp&&kind!=='mist'?1:0} },
      vertexShader: `
        attribute vec3 acolor; attribute float ascale; attribute float aphase;
        uniform float clock, size, pixels, drift, maxPixels, pixelRatio;
        varying vec3 tint; varying float breathe, pixelDiameter;
        void main(){
          vec3 p = position;
          // Bounded local movement preserves the arms and never rotates the network.
          p += drift * vec3(sin(clock*.21+aphase), sin(clock*.17+aphase)*.5, cos(clock*.19+aphase));
          vec4 view = modelViewMatrix * vec4(p,1.);
          gl_Position = projectionMatrix * view;
          gl_PointSize = clamp(size * ascale * pixels / max(1.,-view.z), .7, maxPixels);
          pixelDiameter=gl_PointSize/pixelRatio;
          tint = acolor; breathe = .94 + .06*sin(clock*.27+aphase);
        }`,
      fragmentShader: `
        uniform float opacity,crisp; varying vec3 tint; varying float breathe,pixelDiameter;
        void main(){
          float r = length(gl_PointCoord-vec2(.5))*2.;
          if(r>1.) discard;
          float diffuse=exp(-r*r*5.)-exp(-5.);
          // Screen-footprint profile, no camera-distance layer fade or cap changes.
          float exponent=max(5.,min(65.,.7*pixelDiameter*pixelDiameter));
          float sharp=.9*exp(-r*r*exponent)+.1*exp(-r*r*9.)-.9*exp(-exponent)-.1*exp(-9.);
          float a=mix(diffuse,sharp,crisp*smoothstep(2.5,4.,pixelDiameter))*opacity*breathe;
          gl_FragColor=vec4(tint,a);
        }`,
    });
    const points = new THREE.Points(geometry, material); points.frustumCulled = false;
    scene.add(points); layers.push(points);
  }
  return {
    update(clock) { for (const points of layers) points.material.uniforms.clock.value = clock; },
    resize(height, dpr) { layers.forEach((points, index) => { points.material.uniforms.pixels.value = height * dpr; points.material.uniforms.maxPixels.value = Object.values(CONFIG.maxSprite)[index] * dpr;points.material.uniforms.pixelRatio.value=dpr; }); },
    count: Object.values(CONFIG.particles).reduce((sum, value) => sum + value, 0),
  };
}
