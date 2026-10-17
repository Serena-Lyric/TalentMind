import * as THREE from 'three';
import { TYPES } from './config.js';
import { generateDemo } from './generate.js';

export function createKnowledge(scene) {
  const { nodes, edges } = generateDemo(), geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(nodes.flatMap(node => node.position), 3));
  geometry.setAttribute('aColor', new THREE.Float32BufferAttribute(nodes.flatMap(node => new THREE.Color(TYPES[node.type].color).toArray()), 3));
  geometry.setAttribute('aSize', new THREE.Float32BufferAttribute(nodes.map(node => TYPES[node.type].size), 1));
  geometry.setAttribute('aType', new THREE.Float32BufferAttribute(nodes.map(node => node.type), 1));
  geometry.setAttribute('aIndex', new THREE.Float32BufferAttribute(nodes.map((_, index) => index), 1));
  const material = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending,
    uniforms: { selected: { value: -1 }, pixels: { value: 900 }, dpr: { value: 1 } },
    vertexShader: `
      attribute vec3 aColor; attribute float aSize, aType, aIndex;
      uniform float selected, pixels, dpr;
      varying vec3 tint; varying float hot, type;
      void main(){
        hot = abs(selected-aIndex)<.1 ? 1. : 0.; type=aType; tint=aColor;
        vec4 view=modelViewMatrix*vec4(position,1.);
        gl_Position=projectionMatrix*view;
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
  const lines = edges.map((edge, index) => {
    const a = new THREE.Vector3(...byId.get(edge.source).position), b = new THREE.Vector3(...byId.get(edge.target).position);
    const mid = a.clone().lerp(b, .5); mid.y += 3 + a.distanceTo(b) * .13;
    const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
    const g = new THREE.BufferGeometry().setFromPoints(curve.getPoints(48));
    const colors = [];
    for (let i = 0; i <= 48; i++) {
      const fade = .25 + .75 * Math.sin(Math.PI * i / 48);
      colors.push(.32 * fade, .46 * fade, .65 * fade);
    }
    g.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    const m = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: index % 4 ? .013 : .032, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false });
    const line = new THREE.Line(g, m); line.renderOrder = 2; scene.add(line);
    return { edge, line };
  });
  return {
    nodes, edges,
    select(id) {
      material.uniforms.selected.value = nodes.findIndex(node => node.id === id);
      for (const { edge, line } of lines) {
        const direct = edge.source === id || edge.target === id;
        line.material.opacity = direct ? .5 : id === null ? .022 : .004;
      }
    },
    resize(height, dpr) { material.uniforms.pixels.value = height * dpr; material.uniforms.dpr.value = dpr; },
    pick(x, y, camera, width, height) {
      let best = null, distance = 12;
      for (const node of nodes) {
        const p = new THREE.Vector3(...node.position).project(camera);
        if (p.z < -1 || p.z > 1) continue;
        const d = Math.hypot((p.x + 1) * width / 2 - x, (1 - p.y) * height / 2 - y);
        if (d < distance) { best = node; distance = d; }
      }
      return best;
    },
  };
}
