import { project } from './model.js';

export function canvasRenderer(canvas) {
  const ctx = canvas.getContext('2d');
  return {
    name: 'Canvas 2D',
    resize(w, h, dpr) { canvas.width = w * dpr; canvas.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); },
    draw(frame) {
      const { width, height, view, nodes, dust, fog, edges } = frame;
      ctx.clearRect(0, 0, width, height);
      ctx.globalCompositeOperation = 'lighter';
      for (const c of fog) {
        const [x, y] = project(c.center, view), r = c.radius * view.k * 2.2;
        const g = ctx.createRadialGradient(x, y, 0, x, y, Math.max(1, r));
        g.addColorStop(0, c.color + '23'); g.addColorStop(.35, c.color + '10'); g.addColorStop(1, c.color + '00');
        ctx.fillStyle = g; ctx.fillRect(x - r, y - r, r * 2, r * 2);
      }
      for (const d of dust) {
        const [x, y] = project(d.xyz, view);
        if (x < 0 || y < 0 || x > width || y > height) continue;
        ctx.globalAlpha = d.alpha; ctx.fillStyle = d.color;
        ctx.fillRect(x, y, d.size, d.size);
      }
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = 'source-over';
      for (const e of edges) {
        ctx.globalAlpha = e.active ? .32 : .14;
        ctx.strokeStyle = e.color; ctx.lineWidth = e.active ? .85 : .45;
        ctx.setLineDash(e.type === 'APPLIES_TO' ? [2, 4] : e.type === 'RELATED_TO' ? [6, 4] : []);
        ctx.beginPath(); ctx.moveTo(e.a[0], e.a[1]); ctx.lineTo(e.b[0], e.b[1]); ctx.stroke();
      }
      ctx.setLineDash([]);
      ctx.globalCompositeOperation = 'lighter';
      for (const n of nodes) {
        ctx.globalAlpha = n.alpha;
        const [x, y] = n.screen, r = n.radius;
        if (x < -20 || y < -20 || x > width + 20 || y > height + 20) continue;
        ctx.shadowColor = n.color; ctx.shadowBlur = n.active ? 12 : 3;
        ctx.fillStyle = n.color; ctx.beginPath();
        if (n.type === 'job') { ctx.moveTo(x, y - r); ctx.lineTo(x + r, y); ctx.lineTo(x, y + r); ctx.lineTo(x - r, y); ctx.closePath(); }
        else if (n.type === 'industry') ctx.rect(x - r * .8, y - r * .8, r * 1.6, r * 1.6);
        else ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0; ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    },
    dispose() { ctx.clearRect(0, 0, canvas.width, canvas.height); },
  };
}

export async function threeRenderer(canvas) {
  const T = await import('three');
  const renderer = new T.WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true });
  const scene = new T.Scene();
  const camera = new T.OrthographicCamera(0, 1, 1, 0, -20000, 20000);
  camera.position.z = 10000;
  const disposables = [];
  function points() {
    const geometry = new T.BufferGeometry();
    const material = new T.ShaderMaterial({ transparent: true, depthTest: false, depthWrite: false, blending: T.AdditiveBlending,
      uniforms: { dpr: { value: 1 } },
      vertexShader: `attribute vec3 tint; attribute float diameter; attribute float opacity; attribute float shape; varying vec3 c; varying float a; varying float s; uniform float dpr;
        void main(){ c=tint; a=opacity; s=shape; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); gl_PointSize=diameter*dpr; }`,
      fragmentShader: `varying vec3 c; varying float a; varying float s;
        void main(){ vec2 p=gl_PointCoord*2.-1.; float r=length(p); if(s>.5&&s<1.5)r=abs(p.x)+abs(p.y); if(s>1.5)r=max(abs(p.x),abs(p.y)); if(r>1.)discard;
          float light=exp(-r*r*5.); gl_FragColor=vec4(c*(.65+light),a*(.25+light*.75)); }` });
    const object = new T.Points(geometry, material); object.frustumCulled = false; scene.add(object); disposables.push(geometry, material);
    return { geometry, material };
  }
  const haze = points(), stars = points(), nodes = points();
  const lineGeometry = new T.BufferGeometry();
  const lineMaterial = new T.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: .3, depthTest: false, blending: T.NormalBlending });
  const lines = new T.LineSegments(lineGeometry, lineMaterial); lines.frustumCulled = false; scene.add(lines); disposables.push(lineGeometry, lineMaterial);
  let width = 1, height = 1, dpr = 1;
  function upload(layer, items) {
    const position = [], color = [], diameter = [], opacity = [], shape = [];
    for (const item of items) {
      position.push(item.screen[0], height - item.screen[1], item.screen[2] || 0);
      const c = new T.Color(item.color); color.push(c.r, c.g, c.b);
      diameter.push(item.diameter); opacity.push(item.alpha); shape.push(item.shape || 0);
    }
    for (const [key, array, count] of [['position', position, 3], ['tint', color, 3], ['diameter', diameter, 1], ['opacity', opacity, 1], ['shape', shape, 1]]) layer.geometry.setAttribute(key, new T.Float32BufferAttribute(array, count));
    layer.material.uniforms.dpr.value = dpr;
  }
  return {
    name: `Three.js ${T.REVISION} / WebGL2`,
    resize(w, h, ratio) { width = w; height = h; dpr = ratio; renderer.setPixelRatio(dpr); renderer.setSize(w, h, false); camera.left = 0; camera.right = w; camera.top = h; camera.bottom = 0; camera.updateProjectionMatrix(); },
    draw(frame) {
      upload(haze, frame.fog.map(c => ({ screen: project(c.center, frame.view), color: c.color, alpha: .09, diameter: Math.min(950, c.radius * frame.view.k * 5) })));
      upload(stars, frame.dust.map(d => ({ screen: project(d.xyz, frame.view), color: d.color, alpha: d.alpha, diameter: d.size * 2.3 })));
      upload(nodes, frame.nodes.map(n => ({ ...n, diameter: n.radius * 2, shape: n.type === 'job' ? 1 : n.type === 'industry' ? 2 : 0 })));
      const positions = [], colors = [];
      for (const e of frame.edges) {
        const c = new T.Color(e.color);
        // R0: Three line layer uses geometry dashes for the same relation legend as Canvas.
        const count = e.type === 'REQUIRES' ? 1 : e.type === 'APPLIES_TO' ? 16 : 8;
        for (let i = 0; i < count; i++) {
          for (const t of [i / count, count === 1 ? 1 : (i + .5) / count]) {
            positions.push(e.a[0] + (e.b[0] - e.a[0]) * t, height - (e.a[1] + (e.b[1] - e.a[1]) * t), 0); colors.push(c.r, c.g, c.b);
          }
        }
      }
      lineGeometry.setAttribute('position', new T.Float32BufferAttribute(positions, 3));
      lineGeometry.setAttribute('color', new T.Float32BufferAttribute(colors, 3));
      renderer.render(scene, camera);
    },
    dispose() { disposables.forEach(o => o.dispose()); renderer.dispose(); },
    info() { return { renderer: renderer.getContext().getParameter(renderer.getContext().RENDERER), maxPointSize: renderer.getContext().getParameter(renderer.getContext().ALIASED_POINT_SIZE_RANGE)[1] }; },
  };
}
