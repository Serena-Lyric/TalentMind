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
import { adaptM3, filterGraph } from './m3-adapter.js';

const params = new URLSearchParams(location.search), root = document.querySelector('#universe'), canvas = document.querySelector('#galaxy');
if (params.has('evidence')) document.body.classList.add('evidence');
async function start() { try {
  const real = params.get('data') !== 'demo';
  document.querySelector('footer span:last-child').textContent = 'CAREER NEBULA / P1-A.2 待审核';
  let graph;
  if (real) {
    const response = await fetch('/m3-graph.json');
    if (!response.ok) throw new Error(`M3 handover HTTP ${response.status}`);
    const bytes = await response.arrayBuffer();
    graph = adaptM3(JSON.parse(new TextDecoder().decode(bytes)));
    graph.provenance.sha256 = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), byte => byte.toString(16).padStart(2, '0')).join('');
  }
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.info.autoReset = false;
  renderer.setClearColor('#000001'); renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = CONFIG.render.exposure;
  const scene = new THREE.Scene(), dust = createDust(scene), knowledge = createKnowledge(scene, graph);
  const control = createCamera(canvas, (x, y) => select(knowledge.pick(x, y, control.camera, root.clientWidth, root.clientHeight)));
  const { camera, orbit, state } = control;
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  composer.addPass(new UnrealBloomPass(new THREE.Vector2(1, 1), CONFIG.render.bloomStrength, CONFIG.render.bloomRadius, CONFIG.render.bloomThreshold));
  composer.addPass(new OutputPass());
  const label = document.querySelector('#node-label'), sectorRoot = document.querySelector('#sectors');
  const sectorLabels = (real ? [] : FAMILIES).map(family => {
    const element = document.createElement('div'); element.className = 'sector';
    element.append(document.createTextNode(family.name)); const demo = document.createElement('small'); demo.textContent = 'DEMO'; element.append(demo); sectorRoot.append(element);
    return element;
  });
  let selection = null;
  let filters = { kind: 'all', relation: 'all', query: '', focus: null };
  const tools = document.querySelector('#graph-tools'), detailPanel = document.querySelector('#graph-detail');
  const resultList = document.querySelector('#graph-results'), counts = document.querySelector('#graph-counts');
  if (real) {
    tools.hidden = false;
    document.querySelector('.demo-mark').textContent = '正式 M3 交接快照 · 非实时库 · 待审核';
    document.querySelector('#sectors').setAttribute('aria-label', '真实图模式无演示职业分区');
    document.querySelector('#galaxy').setAttribute('aria-label', '真实 M3 知识节点三维图谱，可拖动和选择');
    document.querySelector('#node-kind').onchange = event => { filters.kind = event.target.value; applyFilter(); };
    document.querySelector('#edge-kind').onchange = event => { filters.relation = event.target.value; applyFilter(); };
    document.querySelector('#graph-query').oninput = event => { filters.query = event.target.value; applyFilter(); };
    resultList.onchange = () => select(knowledge.nodes.find(node => node.id === resultList.value));
    document.querySelector('#show-related').onclick = () => { if (selection) { filters = { kind: 'all', relation: 'all', query: '', focus: selection.id }; syncFilter(); applyFilter(); } };
    document.querySelector('#clear-filter').onclick = () => { filters = { kind: 'all', relation: 'all', query: '', focus: null }; syncFilter(); applyFilter(); };
    applyFilter();
  }
  function syncFilter() {
    document.querySelector('#node-kind').value = filters.kind; document.querySelector('#edge-kind').value = filters.relation; document.querySelector('#graph-query').value = filters.query;
  }
  function applyFilter() {
    const view = filterGraph(graph, filters); knowledge.filter(view);
    if (selection && !view.nodeIds.has(selection.id)) select(null);
    const matches = knowledge.nodes.filter(node => view.nodeIds.has(node.id));
    resultList.replaceChildren(...matches.slice(0, 100).map(node => { const option = document.createElement('option'); option.value = node.id; option.textContent = `${TYPES[node.type].name} · ${node.name}`; return option; }));
    resultList.selectedIndex = -1;
    counts.textContent = `知识节点 ${view.nodeIds.size} / ${graph.nodes.length} · 关系 ${view.edgeIndices.length} / ${graph.edges.length}`;
    root.dataset.graph = JSON.stringify({ ...graph.provenance, nodes: graph.nodes.length, edges: graph.edges.length, ...knowledge.counts(), filters });
  }
  function select(node) {
    selection = node; state.selected = node?.id ?? null; knowledge.select(state.selected); label.hidden = !node;
    if (node) {
      label.replaceChildren(document.createTextNode(node.name));
      const detail = document.createElement('small');
      detail.textContent = real ? `${TYPES[node.type].name} · ${node.id}\nexchange/m3/graph.json → nodes[${node.sourceIndex}]` : `演示${TYPES[node.type].name} · ${node.families.map(index => FAMILIES[index].name).join(' / ')}\n合成实体与关系，仅用于视觉验证`;
      label.append(detail);
    }
    if (real) {
      document.querySelector('#show-related').disabled = !node; detailPanel.hidden = !node;
      detailPanel.replaceChildren();
      if (node) {
        const title = document.createElement('strong'); title.textContent = node.name;
        const note = document.createElement('p'); note.textContent = '历史交接语义：is_required 仅为旧必备/加分，不代表新版五态。位置为展示布局。';
        const pre = document.createElement('pre');
        const related = knowledge.edges.filter(edge => edge.source === node.id || edge.target === node.id);
        pre.textContent = JSON.stringify({ source: graph.provenance, path: `nodes[${node.sourceIndex}]`, node: node.raw, relationships: related.map(edge => ({ path: `edges[${edge.sourceIndex}]`, ...edge.raw })) }, null, 2);
        detailPanel.append(title, note, pre);
      }
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
    renderer.info.reset(); composer.render();
    if (import.meta.env.DEV && params.has('still') && !root.dataset.capture) root.dataset.capture = JSON.stringify({ seed: CONFIG.seed, camera: camera.position.toArray().map(v => +v.toFixed(6)), target: orbit.target.toArray().map(v => +v.toFixed(6)), width: root.clientWidth, height: root.clientHeight, dpr: renderer.getPixelRatio(), dustClock, selected: state.selected, render: CONFIG.render, particles: CONFIG.particles, provenance: graph?.provenance ?? { mode: 'synthetic-demo' } });
    (real ? [] : FAMILIES).forEach((family, index) => {
      const p = project(family.center); const element = sectorLabels[index];
      element.style.left = `${p.x}px`; element.style.top = `${p.y}px`;
      element.style.opacity = p.visible ? (camera.position.distanceTo(orbit.target) < 65 ? '.45' : '.85') : '0';
    });
    if (selection) { const p = project(selection.position); label.style.left = `${Math.min(root.clientWidth - 300, Math.max(12, p.x + 28))}px`; label.style.top = `${Math.min(root.clientHeight - 120, Math.max(15, p.y - 25))}px`; label.hidden = !p.visible; }
    onFrame?.(elapsed);
  });
  root.dataset.ready = 'true';
  if (import.meta.env.DEV && params.has('diagnostics')) {
    const app = { renderer, snapshot: () => ({ selected: state.selected, speed: state.speed, dustClock, camera: camera.position.toArray(), target: orbit.target.toArray(), distance: camera.position.distanceTo(orbit.target), width: root.clientWidth, height: root.clientHeight, dpr: renderer.getPixelRatio(), particles: dust.count, nodes: knowledge.nodes.length, edges: knowledge.edges.length, ...knowledge.counts(), provenance: graph?.provenance ?? { mode: 'synthetic-demo' }, drawCalls: renderer.info.render.calls, movedFrames: state.movedFrames, visibility: document.visibilityState }), project, nodes: knowledge.nodes, select, root, canvas, camera, orbit, state };
    import('./diagnostics.js').then(module => { onFrame = module.mountDiagnostics(app); });
  }
} catch (error) {
  console.error(error); const failure = document.querySelector('#failure'); failure.hidden = false; failure.textContent = `银河初始化失败：${error.message}`;
} }
start();
