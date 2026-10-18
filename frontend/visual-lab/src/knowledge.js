import * as THREE from 'three';
import { TYPES } from './config.js';
import { generateDemo } from './generate.js';

export function createKnowledge(scene, graph = generateDemo()) {
  const { nodes, edges } = graph, geometry = new THREE.BufferGeometry();
  let visible = new Set(nodes.map(node => node.id)), edgeIndices = edges.map((_, index) => index), selected = null;
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(nodes.flatMap(node => node.position), 3));
  geometry.setAttribute('aColor', new THREE.Float32BufferAttribute(nodes.flatMap(node => new THREE.Color(TYPES[node.type].color).toArray()), 3));
  geometry.setAttribute('aSize', new THREE.Float32BufferAttribute(nodes.map(node => TYPES[node.type].size), 1));
  geometry.setAttribute('aType', new THREE.Float32BufferAttribute(nodes.map(node => node.type), 1));
  geometry.setAttribute('aIndex', new THREE.Float32BufferAttribute(nodes.map((_, index) => index), 1));
  geometry.setAttribute('aVisible', new THREE.Float32BufferAttribute(nodes.map(() => 1), 1));
  const material = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending,
    uniforms: { selected: { value: -1 }, pixels: { value: 900 }, dpr: { value: 1 } },
    vertexShader: `
      attribute vec3 aColor; attribute float aSize, aType, aIndex, aVisible;
      uniform float selected, pixels, dpr;
      varying vec3 tint; varying float hot, type;
      void main(){
        hot = abs(selected-aIndex)<.1 ? 1. : 0.; type=aType; tint=aColor;
        vec4 view=modelViewMatrix*vec4(position,1.);
        gl_Position=projectionMatrix*view;
        if(aVisible<.5) gl_Position=vec4(2.,2.,2.,1.);
        gl_PointSize=mix(clamp(aSize*2.8*pixels/max(1.,-view.z),8.*dpr,26.*dpr),64.*dpr,hot);
      }`,
    fragmentShader: `
      varying vec3 tint; varying float hot, type;
      void main(){
        vec2 p=gl_PointCoord-.5; float r=length(p)*2.; if(r>1.) discard;
        float core=exp(-r*r*130.);
        float halo=exp(-r*r*7.)*.12;
        float detail=0.;
        if(type>.5 && type<1.5) detail=exp(-pow((r-.38)*30.,2.))*.035;
        if(type>2.5 && type<3.5) detail=exp(-pow((abs(p.x)+abs(p.y))*.95-.27,2.)*1600.)*.04;
        if(type>3.5) detail=exp(-pow((r-.56)*25.,2.))*.024;
        float selectedCore=exp(-r*r*380.)*4.;
        float selectedHalo=exp(-r*r*12.)*.3+exp(-r*r*4.5)*.035;
        vec3 light=mix(tint*(core*2.4+halo+detail), mix(tint,vec3(1.),.7)*selectedCore+tint*selectedHalo,hot);
        gl_FragColor=vec4(light,1.);
      }`,
  });
  const points = new THREE.Points(geometry, material); points.frustumCulled = false; points.renderOrder = 3; scene.add(points);
  const byId = new Map(nodes.map(node => [node.id, node]));
  // Batch the complete relationship set; one draw call per base/highlight layer.
  const paths = edges.map(edge => {
    const a = new THREE.Vector3(...byId.get(edge.source).position), b = new THREE.Vector3(...byId.get(edge.target).position);
    const mid = a.clone().lerp(b, .5); mid.y += 3 + a.distanceTo(b) * .13;
    const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
    const samples = curve.getPoints(12), path = [];
    for (let i = 0; i < 12; i++) path.push(...samples[i].toArray(), ...samples[i + 1].toArray());
    return path;
  });
  function batch(opacity) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(edges.length * 72), 3));
    g.setDrawRange(0, 0);
    const line = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: '#7199c8', transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false }));
    line.frustumCulled = false; line.renderOrder = 2; scene.add(line); return line;
  }
  const base = batch(.009), highlight = batch(.45);
  function write(line, indices) {
    const attribute = line.geometry.getAttribute('position');
    indices.forEach((index, offset) => attribute.array.set(paths[index], offset * 72));
    attribute.needsUpdate = true; line.geometry.setDrawRange(0, indices.length * 24);
  }
  function updateLines() {
    write(base, edgeIndices);
    write(highlight, edgeIndices.filter(index => edges[index].source === selected || edges[index].target === selected));
    base.material.opacity = selected ? .002 : .009;
  }
  updateLines();
  return {
    nodes, edges,
    select(id) {
      selected = visible.has(id) ? id : null;
      material.uniforms.selected.value = nodes.findIndex(node => node.id === selected);
      updateLines();
    },
    filter(view) {
      visible = view.nodeIds; edgeIndices = view.edgeIndices;
      const attribute = geometry.getAttribute('aVisible');
      nodes.forEach((node, index) => attribute.array[index] = Number(visible.has(node.id))); attribute.needsUpdate = true;
      this.select(selected);
    },
    counts() { return { visibleNodes: visible.size, visibleEdges: edgeIndices.length, highlightedEdges: highlight.geometry.drawRange.count / 24 }; },
    resize(height, dpr) { material.uniforms.pixels.value = height * dpr; material.uniforms.dpr.value = dpr; },
    pick(x, y, camera, width, height) {
      let best = null, distance = 12;
      for (const node of nodes) {
        if (!visible.has(node.id)) continue;
        const p = new THREE.Vector3(...node.position).project(camera);
        if (p.z < -1 || p.z > 1) continue;
        const d = Math.hypot((p.x + 1) * width / 2 - x, (1 - p.y) * height / 2 - y);
        if (d < distance) { best = node; distance = d; }
      }
      return best;
    },
  };
}
