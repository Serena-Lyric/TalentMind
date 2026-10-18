import './style.css';
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { CONFIG, FAMILIES, TYPES } from './config.js';
import { createDust } from './particles.js';
import { createKnowledge } from './knowledge.js';
import { createCamera } from './camera.js';
import { createHazePass } from './haze-pass.js';

const params = new URLSearchParams(location.search), root = document.querySelector('#universe'), canvas = document.querySelector('#galaxy');
if (params.has('evidence')) document.body.classList.add('evidence');
try {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.setClearColor('#000001'); renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = CONFIG.render.exposure;
  const scene = new THREE.Scene(), dust = createDust(scene), knowledge = createKnowledge(scene);
  const control = createCamera(canvas, (x, y) => select(knowledge.pick(x, y, control.camera, root.clientWidth, root.clientHeight)));
  const { camera, orbit, state } = control;
  const haze = createHazePass(renderer, scene, camera);
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  composer.addPass(haze.pass);
  composer.addPass(new UnrealBloomPass(new THREE.Vector2(1, 1), CONFIG.render.bloomStrength, CONFIG.render.bloomRadius, CONFIG.render.bloomThreshold));
  composer.addPass(new OutputPass());
  const label = document.querySelector('#node-label'), sectorRoot = document.querySelector('#sectors');
  const sectorLabels = FAMILIES.map(family => {
    const element = document.createElement('div'); element.className = 'sector';
    element.append(document.createTextNode(family.name)); const demo = document.createElement('small'); demo.textContent = 'DEMO'; element.append(demo); sectorRoot.append(element);
    return element;
  });
  let selection = null;
  function select(node) {
    selection = node; state.selected = node?.id ?? null; knowledge.select(state.selected); label.hidden = !node;
    if (node) {
      label.replaceChildren(document.createTextNode(node.name));
      const detail = document.createElement('small');
      detail.textContent = `演示${TYPES[node.type].name} · ${node.families.map(index => FAMILIES[index].name).join(' / ')}\n合成实体与关系，仅用于视觉验证`;
      label.append(detail);
    }
  }
  function project(position) {
    const p = new THREE.Vector3(...position).project(camera);
    return { x: (p.x + 1) * root.clientWidth / 2, y: (1 - p.y) * root.clientHeight / 2, visible: p.z > -1 && p.z < 1 && Math.abs(p.x) < .94 && Math.abs(p.y) < .88 };
  }
  function resize() {
    const width = root.clientWidth, height = root.clientHeight, dpr = Math.min(devicePixelRatio, CONFIG.render.dpr);
    camera.aspect = width / height; camera.updateProjectionMatrix();
    renderer.setPixelRatio(dpr); renderer.setSize(width, height, false); composer.setPixelRatio(dpr); composer.setSize(width, height);
    dust.resize(height, dpr); knowledge.resize(height, dpr);
    haze.resize(width, height, dpr);
  }
  const observer = new ResizeObserver(resize); observer.observe(root); resize();
  let last = performance.now(), dustClock = 0, onFrame = null;
  // Named views are reproducible evidence bookmarks, not node-click camera movement.
  if (params.get('view') === 'mid') { camera.position.sub(orbit.target).multiplyScalar(.62).add(orbit.target); }
  if (params.get('view') === 'near') {
    const offset = camera.position.clone().setLength(43); orbit.target.set(...FAMILIES[0].center); camera.position.copy(orbit.target).add(offset);
  }
  if (import.meta.env.DEV && params.get('view') === 'core') camera.position.setLength(43);
  if (params.get('view') === 'selected') select(knowledge.nodes[0]);
  canvas.addEventListener('webglcontextlost', event => { event.preventDefault(); const error = document.querySelector('#failure'); error.hidden = false; error.textContent = 'WebGL 上下文已丢失，请重新加载此视觉实验。'; });
  renderer.setAnimationLoop(now => {
    const elapsed = now - last; last = now;
    if (document.hidden) return;
    const dt = Math.min(elapsed / 1000, .05); control.update(dt); if (!(import.meta.env.DEV && params.has('still'))) dustClock += dt * state.speed; dust.update(dustClock);
    haze.render(); composer.render();
    if (import.meta.env.DEV && params.has('still') && !root.dataset.capture) root.dataset.capture = JSON.stringify({ seed: CONFIG.seed, camera: camera.position.toArray().map(v => +v.toFixed(6)), target: orbit.target.toArray().map(v => +v.toFixed(6)), width: root.clientWidth, height: root.clientHeight, dpr: renderer.getPixelRatio(), dustClock, selected: state.selected, render: CONFIG.render, particles: CONFIG.particles });
    FAMILIES.forEach((family, index) => {
      const p = project(family.center); const element = sectorLabels[index];
      element.style.left = `${p.x}px`; element.style.top = `${p.y}px`;
      element.style.opacity = p.visible ? (camera.position.distanceTo(orbit.target) < 65 ? '.45' : '.85') : '0';
    });
    if (selection) { const p = project(selection.position); label.style.left = `${Math.min(root.clientWidth - 300, Math.max(12, p.x + 28))}px`; label.style.top = `${Math.min(root.clientHeight - 120, Math.max(15, p.y - 25))}px`; label.hidden = !p.visible; }
    onFrame?.(elapsed);
  });
  root.dataset.ready = 'true';
  if (import.meta.env.DEV && params.has('diagnostics')) {
    const app = { renderer, snapshot: () => ({ selected: state.selected, speed: state.speed, dustClock, camera: camera.position.toArray(), target: orbit.target.toArray(), distance: camera.position.distanceTo(orbit.target), width: root.clientWidth, height: root.clientHeight, dpr: renderer.getPixelRatio(), particles: dust.count, nodes: knowledge.nodes.length, edges: knowledge.edges.length, movedFrames: state.movedFrames, visibility: document.visibilityState }), project, nodes: knowledge.nodes, select, root, canvas, camera, orbit, state };
    import('./diagnostics.js').then(module => { onFrame = module.mountDiagnostics(app); });
  }
} catch (error) {
  console.error(error); const failure = document.querySelector('#failure'); failure.hidden = false; failure.textContent = `银河初始化失败：${error.message}`;
}
