import { createApp, computed, nextTick, onMounted, onUnmounted, reactive, ref, shallowRef, watch } from 'vue/dist/vue.esm-bundler.js';
import { communityColor, dust, fit, labelBoxes, makeIndex, palette, project, radius, search, typeColors, typeNames, visibleNodes } from './model.js';
import { canvasRenderer, threeRenderer } from './renderers.js';
import './style.css';

createApp({
  setup() {
    const route = ref(new URLSearchParams(location.search).get('route') === 'b' ? 'b' : 'a');
    const stage = ref(), canvas = ref(), overlay = ref();
    const data = shallowRef(null), error = ref(''), selected = ref(null), hovered = ref(null), query = ref(''), cursor = ref(-1);
    const types = reactive({ job: true, skill: true, industry: true });
    const view = reactive({ k: 1, x: 0, y: 0, yaw: 0, pitch: 0 });
    const colorMode = ref('community'), decoration = ref(true), cap = ref(6), density = ref(1), rotation = ref(false);
    const saved = shallowRef(null), recording = ref(false), recordingUrl = ref('');
    const stats = reactive({ visible: 0, drawn: 0, direct: 0, submitted: 0, outside: 0, labels: 0, load: 0, render: 0, p95: 0, engine: '', dust: 0, fallback: false });
    const matches = computed(() => data.value ? search(data.value.nodes, query.value, types) : []);
    const current = computed(() => { const id = selected.value; return index?.byId.get(id); });
    const currentCommunity = computed(() => data.value?.communities.find(c => c.id === current.value?.communityId));
    const currentEdges = computed(() => selected.value ? index.adjacent.get(selected.value) : []);
    const zoom = computed(() => view.k / overviewK);
    const level = computed(() => zoom.value >= 3.5 ? '近景 · 叶子与场景' : zoom.value >= 1.6 ? '中景 · 共享能力' : '全景 · 岗位骨干');
    const major = computed(() => data.value?.communities.filter(c => c.jobCount > 2) || []);
    let index, particles = [], renderer, width = 1, height = 1, overviewK = 1, scheduled = false, observer, initializing = false;
    let projected = [], drawTimes = [], pointer = null, disposed = false, generation = 0, media = null, recordingStream = null, recordingTimer = null;
    function invalidate() { if (!scheduled && !disposed) { scheduled = true; requestAnimationFrame(draw); } }
    function fullView() {
      if (!data.value) return;
      Object.assign(view, fit(data.value.nodes, width, height, { ...view, yaw: 0, pitch: 0 }));
      overviewK = view.k; saved.value = null; invalidate();
    }
    function select(id) { selected.value = id; invalidate(); }
    function clear() { selected.value = null; invalidate(); }
    function step(direction) {
      if (!matches.value.length) return;
      cursor.value = (cursor.value + direction + matches.value.length) % matches.value.length;
      const node = matches.value[cursor.value]; select(node.nodeId);
      const [x, y] = project(node.xyz, view);
      if (x < 70 || y < 70 || x > width - 100 || y > height - 70) {
        view.x += width / 2 - x; view.y += height / 2 - y;
      }
      invalidate();
    }
    function viewAll() {
      if (!current.value) return;
      if (!saved.value) saved.value = { ...view };
      const ids = new Set([selected.value]);
      for (const e of currentEdges.value) { ids.add(e.source); ids.add(e.target); }
      const nodes = [...ids].map(id => index.byId.get(id)).filter(n => types[n.type]);
      Object.assign(view, fit(nodes, width, height, view)); invalidate();
    }
    function restore() { if (saved.value) { Object.assign(view, saved.value); saved.value = null; invalidate(); } }
    function changeZoom(factor, x = width / 2, y = height / 2) {
      const next = Math.max(overviewK * .45, Math.min(overviewK * 40, view.k * factor));
      const ratio = next / view.k; view.x = x - (x - view.x) * ratio; view.y = y - (y - view.y) * ratio; view.k = next; invalidate();
    }
    function focusCommunity(id) {
      const nodes = data.value.nodes.filter(n => n.type === 'job' && n.communityId === id);
      Object.assign(view, fit(nodes, width, height, view)); invalidate();
    }
    function semanticZoom(target) {
      const p = current.value ? project(current.value.xyz, view) : [width / 2, height / 2];
      changeZoom(target / zoom.value, p[0], p[1]);
    }
    function wheel(event) {
      const rect = stage.value.getBoundingClientRect();
      changeZoom(Math.exp(-event.deltaY * .0015), event.clientX - rect.left, event.clientY - rect.top);
    }
    function down(event) {
      if (event.button !== 0) return;
      canvas.value.setPointerCapture(event.pointerId);
      pointer = { x: event.clientX, y: event.clientY, lastX: event.clientX, lastY: event.clientY, moved: false };
    }
    function hit(x, y) {
      let winner = null, distance = Infinity;
      for (const n of projected) {
        const d = Math.hypot(n.screen[0] - x, n.screen[1] - y);
        if (d < Math.max(7, n.radius + 3) && d < distance) { winner = n; distance = d; }
      }
      return winner?.nodeId || null;
    }
    function move(event) {
      const rect = stage.value.getBoundingClientRect();
      if (pointer) {
        const dx = event.clientX - pointer.lastX, dy = event.clientY - pointer.lastY;
        pointer.moved ||= Math.hypot(event.clientX - pointer.x, event.clientY - pointer.y) > 4;
        if (rotation.value && route.value === 'b') { view.yaw += dx * .005; view.pitch = Math.max(-.8, Math.min(.8, view.pitch + dy * .005)); }
        else { view.x += dx; view.y += dy; }
        pointer.lastX = event.clientX; pointer.lastY = event.clientY;
      } else hovered.value = hit(event.clientX - rect.left, event.clientY - rect.top);
      invalidate();
    }
    function up(event) {
      if (pointer && !pointer.moved) {
        const rect = stage.value.getBoundingClientRect();
        select(hit(event.clientX - rect.left, event.clientY - rect.top));
      }
      pointer = null;
    }
    async function initRenderer() {
      if (!data.value || disposed) return;
      const token = ++generation;
      initializing = true; renderer?.dispose(); renderer = null;
      // A canvas cannot switch context type. Vue recreates only the isolated viewport.
      await nextTick();
      if (disposed || token !== generation) return;
      try {
        const next = route.value === 'b' ? await threeRenderer(canvas.value) : canvasRenderer(canvas.value);
        if (disposed || token !== generation) { next.dispose(); return; }
        renderer = next;
        stats.fallback = false;
      } catch (e) {
        if (disposed || token !== generation) return;
        error.value = `WebGL2 无法启动：${e.message}。可切回路线 A。`;
        initializing = false; return;
      }
      stats.engine = renderer.name; initializing = false;
      resize();
    }
    function resize() {
      if (!renderer || !stage.value) return;
      const w = stage.value.clientWidth, h = stage.value.clientHeight;
      if (width > 1) { view.x += (w - width) / 2; view.y += (h - height) / 2; }
      width = w; height = h;
      const ratio = Math.min(devicePixelRatio, 2);
      renderer.resize(width, height, ratio);
      overlay.value.width = width * ratio; overlay.value.height = height * ratio;
      overlay.value.getContext('2d').setTransform(ratio, 0, 0, ratio, 0, 0);
      if (overviewK === 1) fullView(); invalidate();
    }
    function draw() {
      scheduled = false;
      if (!renderer || initializing || !data.value) return;
      const started = performance.now();
      const found = new Set(matches.value.map(n => n.nodeId));
      const visible = visibleNodes(data.value, { selected: selected.value, zoom: zoom.value, types, matches: [...found] }, index);
      const visibleIds = new Set(visible.map(n => n.nodeId));
      const adjacentIds = new Set([selected.value]);
      for (const e of currentEdges.value) { adjacentIds.add(e.source); adjacentIds.add(e.target); }
      projected = visible.map(n => ({ ...n, screen: project(n.xyz, view), radius: radius(n, zoom.value, cap.value, n.nodeId === selected.value),
        active: n.nodeId === selected.value || n.nodeId === hovered.value || found.has(n.nodeId),
        color: n.nodeId === selected.value ? '#ffffff' : colorMode.value === 'type' ? typeColors[n.type] : communityColor(n.communityId),
        alpha: selected.value && !adjacentIds.has(n.nodeId) ? .2 : n.nodeId === selected.value ? 1 : .82 }));
      const byScreen = new Map(projected.map(n => [n.nodeId, n]));
      const inside = p => p[0] >= 0 && p[1] >= 0 && p[0] <= width && p[1] <= height;
      const edgeCandidates = selected.value ? currentEdges.value : data.value.edges;
      const edges = [];
      let outside = 0;
      for (const e of edgeCandidates) {
        if (!visibleIds.has(e.source) || !visibleIds.has(e.target)) continue;
        if (!selected.value && zoom.value < 1.6) continue;
        if (!selected.value && edges.length >= (zoom.value >= 3.5 ? 900 : 180)) break;
        const a = byScreen.get(e.source).screen, b = byScreen.get(e.target).screen;
        if (selected.value && (!inside(a) || !inside(b))) outside++;
        edges.push({ ...e, a, b, active: !!selected.value, color: e.type === 'APPLIES_TO' ? '#c6a0ee' : e.type === 'RELATED_TO' ? '#eab56e' : '#83d9d2' });
      }
      renderer.draw({ width, height, view, nodes: projected, dust: decoration.value ? particles : [], fog: decoration.value ? data.value.communities.filter(c => c.jobCount > 2).map(c => ({ ...c, color: communityColor(c.id) })) : [], edges });
      const ctx = overlay.value.getContext('2d'); ctx.clearRect(0, 0, width, height);
      ctx.font = '12px "Microsoft YaHei", sans-serif';
      const candidates = projected.filter(n => inside(n.screen) && (n.active || zoom.value >= 3.5 || zoom.value >= 1.6 && n.type === 'job'))
        .map(n => ({ id: n.nodeId, x: n.screen[0], y: n.screen[1], width: ctx.measureText(n.label).width, priority: n.nodeId === selected.value ? 1000 : n.nodeId === hovered.value ? 900 : found.has(n.nodeId) ? 800 : n.type === 'job' ? 100 : n.importance }));
      const labels = labelBoxes(candidates, width, height, density.value);
      for (const n of projected) {
        const [x, y] = n.screen;
        if (n.active) { ctx.strokeStyle = n.nodeId === selected.value ? '#fff' : '#f5d9a2'; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(x, y, n.radius + 4, 0, Math.PI * 2); ctx.stroke(); }
        if (labels.has(n.nodeId)) {
          const w = ctx.measureText(n.label).width;
          ctx.fillStyle = '#080f20de'; ctx.fillRect(x + 7, y - 13, w + 8, 20);
          ctx.fillStyle = n.active ? '#fff' : '#c6d4df'; ctx.fillText(n.label, x + 11, y + 1);
        }
      }
      if (zoom.value < 1.6) for (const c of major.value) {
        const [x, y] = project(c.center, view);
        ctx.font = '600 12px "Microsoft YaHei", sans-serif'; ctx.fillStyle = '#e5edf6';
        ctx.fillText(`${c.id} · ${c.jobCount} 岗位`, x - 40, y - c.radius * view.k - 13);
        ctx.font = '11px "Microsoft YaHei", sans-serif'; ctx.fillStyle = communityColor(c.id);
        ctx.fillText(c.terms.slice(0, 3).join(' / '), x - 40, y - c.radius * view.k + 6);
      }
      if (zoom.value < 1.6) {
        const shelf = data.value.communities.filter(c => c.jobCount <= 2);
        if (shelf.length) {
          const [x,y] = project(shelf[0].center,view);
          ctx.fillStyle = '#8299ab'; ctx.font = '11px "Microsoft YaHei", sans-serif';
          ctx.fillText(`小群 / 单岗位 · ${shelf.reduce((s,c)=>s+c.jobCount,0)} 岗位`, x-15, y-35);
        }
      }
      stats.visible = visible.length; stats.drawn = projected.filter(n => inside(n.screen)).length;
      stats.direct = currentEdges.value.length; stats.submitted = selected.value ? edges.length : 0;
      stats.outside = outside; stats.labels = labels.size; stats.dust = decoration.value ? particles.length : 0;
      stats.render = Math.round((performance.now() - started) * 10) / 10;
      drawTimes.push(stats.render); if (drawTimes.length > 300) drawTimes.shift();
      stats.p95 = [...drawTimes].sort((a, b) => a - b)[Math.floor((drawTimes.length - 1) * .95)];
      stage.value.dataset.r0 = JSON.stringify({ route: route.value, view: { ...view }, selected: selected.value, sourceSha256: data.value.metadata.sourceSha256, layoutSha256: data.value.metadata.layoutSha256, ...stats });
    }
    function neighbor(e) { return index.byId.get(e.source === selected.value ? e.target : e.source); }
    function exportAudit() {
      const body = { metadata: data.value.metadata, view: { ...view }, selected: current.value || null, directEdges: currentEdges.value, stats: { ...stats }, viewport: { width, height, dpr: devicePixelRatio }, drawTimesMs: drawTimes };
      download(new Blob([JSON.stringify(body, null, 2)], { type: 'application/json' }), `r0-${route.value}-audit.json`);
    }
    function download(blob, name) { const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 30000); }
    function screenshot() {
      const image = document.createElement('canvas'); image.width = canvas.value.width; image.height = canvas.value.height;
      const ctx = image.getContext('2d'); ctx.fillStyle = '#060c19'; ctx.fillRect(0, 0, image.width, image.height);
      ctx.drawImage(canvas.value, 0, 0); ctx.drawImage(overlay.value, 0, 0);
      image.toBlob(blob => download(blob, `r0-${route.value}.png`));
    }
    function stopRecording() { if (media?.state === 'recording') media.stop(); }
    function record() {
      if (recording.value) { stopRecording(); return; }
      if (!window.MediaRecorder || !HTMLCanvasElement.prototype.captureStream) { error.value = '此浏览器不支持画布录屏，请使用 Edge / Chrome。'; return; }
      const target = document.createElement('canvas'); target.width = canvas.value.width; target.height = canvas.value.height;
      const ctx = target.getContext('2d');
      recordingStream = target.captureStream(30);
      const chunks = [];
      const mimeType = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'].find(t => MediaRecorder.isTypeSupported(t));
      media = new MediaRecorder(recordingStream, { mimeType });
      media.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
      media.onstop = () => {
        clearInterval(recordingTimer); recordingStream.getTracks().forEach(t => t.stop()); recording.value = false;
        if (recordingUrl.value) URL.revokeObjectURL(recordingUrl.value);
        recordingUrl.value = URL.createObjectURL(new Blob(chunks, { type: mimeType }));
      };
      recordingTimer = setInterval(() => { ctx.fillStyle = '#060c19'; ctx.fillRect(0, 0, target.width, target.height); ctx.drawImage(canvas.value, 0, 0); ctx.drawImage(overlay.value, 0, 0); }, 1000 / 30);
      media.start(); recording.value = true;
    }
    watch([query, types], () => { cursor.value = -1; if (current.value && !types[current.value.type]) selected.value = null; invalidate(); });
    watch([colorMode, decoration, cap, density], invalidate);
    watch(route, async () => {
      stopRecording(); rotation.value = false; error.value = ''; stats.render = 0; drawTimes = [];
      if (route.value === 'a') { view.yaw = 0; view.pitch = 0; }
      history.replaceState(null, '', `?route=${route.value}`); await initRenderer();
    });
    onMounted(async () => {
      const started = performance.now();
      try {
        const response = await fetch('./data.json');
        if (!response.ok) throw new Error('请先运行 scripts/nebula_r0.py 生成只读研究快照');
        const payload = await response.json(); index = makeIndex(payload); data.value = payload; particles = dust(payload.communities);
        await nextTick(); await initRenderer();
        observer = new ResizeObserver(resize); observer.observe(stage.value); stats.load = Math.round(performance.now() - started);
      } catch (e) { error.value = e.message; }
    });
    onUnmounted(() => { disposed = true; observer?.disconnect(); renderer?.dispose(); stopRecording(); if (recordingUrl.value) URL.revokeObjectURL(recordingUrl.value); });
    return { route, stage, canvas, overlay, data, error, selected, hovered, current, currentCommunity, query, matches, cursor, types, typeNames, palette, colorMode, decoration, cap, density, rotation, saved, stats, level, zoom, major, currentEdges, recording, recordingUrl,
      fullView, select, clear, step, viewAll, restore, changeZoom, semanticZoom, focusCommunity, wheel, down, move, up, neighbor, communityColor, exportAudit, screenshot, record };
  },
  template: `
    <div class="laboratory">
      <header><div class="brand"><span class="brand-symbol">✧</span><div><h1>Career Nebula <small>R0 / 视觉研究</small></h1><p>真实关联的空间切片 · 2026.10.17</p></div></div>
        <nav aria-label="原型路线"><button :class="{active:route==='a'}" @click="route='a'">A · 语义星云 <small>2D</small></button><button :class="{active:route==='b'}" @click="route='b'">B · 空间星系 <small>WebGL</small></button></nav>
        <div class="snapshot" v-if="data"><b>{{ data.nodes.length.toLocaleString() }}</b> 实体 <span>/</span> <b>{{ data.edges.length.toLocaleString() }}</b> 真实关系<small>固定快照 · 只读原型</small></div>
      </header>
      <div class="workspace">
        <aside class="controls">
          <p class="eyebrow">EXPLORE THE STRUCTURE</p><h2>从群落，到知识点</h2>
          <label for="search">搜索实体</label><div class="search"><input id="search" v-model="query" placeholder="Python / 岗位 / 场景" @keydown.enter.prevent="step($event.shiftKey ? -1 : 1)"><button @click="step(1)" aria-label="定位下一结果">↗</button></div>
          <div class="search-nav" v-if="query"><button @click="step(-1)" :disabled="!matches.length">上一项</button><span>{{ cursor + 1 }} / {{ matches.length }}</span><button @click="step(1)" :disabled="!matches.length">下一项</button></div>
          <div class="results" v-if="query"><button v-for="n in matches" :key="n.nodeId" @click="select(n.nodeId)">{{ typeNames[n.type] }} · {{ n.label }}</button><p v-if="!matches.length">没有匹配实体</p></div>
          <label>显示层级 <span>{{ zoom.toFixed(1) }}×</span></label><div class="segmented"><button @click="fullView">全景</button><button @click="semanticZoom(2.4)">中景</button><button @click="semanticZoom(6)">近景</button></div>
          <p class="muted">{{ level }}。选中时始终展开其全部真实直连；视口外可主动查看。</p>
          <label>实体类型 · 形状</label><div class="checks"><label v-for="(name,type) in typeNames" :key="type"><input type="checkbox" v-model="types[type]">{{ type==='job'?'◇':type==='skill'?'○':'□' }} {{ name }}</label></div>
          <label for="color-mode">颜色编码</label><select id="color-mode" v-model="colorMode"><option value="community">颜色 = 推断群落</option><option value="type">颜色 = 实体类型</option></select>
          <p class="muted" v-if="colorMode==='community'">C01–C27 为算法推断；颜色循环，C 编号区分身份，形状区分实体类型。</p><p class="muted" v-else>蓝=岗位，绿=技能，紫=场景；背景雾色仍表示推断群落。</p>
          <div class="settings"><label>节点半径上限 <select aria-label="节点半径上限" v-model.number="cap"><option :value="5">5 px</option><option :value="6">6 px</option><option :value="8">8 px</option></select></label><label>标签密度 <select aria-label="标签密度" v-model.number="density"><option :value="0">疏</option><option :value="1">标准</option><option :value="2">密</option></select></label></div>
          <label class="check"><input type="checkbox" v-model="decoration"> 装饰星尘 / 雾光</label><p class="muted">{{ stats.dust.toLocaleString() }} 装饰粒子 · 无命中、无业务计数</p>
          <label class="check" v-if="route==='b'"><input type="checkbox" v-model="rotation"> 显式旋转模式（拖拽）</label>
          <div class="group-title"><label>群落切片</label><span>仅推断</span></div><div class="community-list"><button v-for="c in major" :key="c.id" @click="focusCommunity(c.id)"><i :style="{background:communityColor(c.id)}"></i><span>{{ c.id }} · {{ c.terms.slice(0,2).join(' / ') }}</span><b>{{ c.jobCount }}</b></button></div>
          <div class="tools"><button @click="screenshot">保存画面</button><button @click="exportAudit">导出审计</button><button @click="record">{{ recording?'停止录屏':'录制画布' }}</button><a v-if="recordingUrl" :href="recordingUrl" :download="'r0-'+route+'.webm'">保存录屏</a></div>
        </aside>
        <main ref="stage" class="stage" :aria-label="'路线 '+route.toUpperCase()+' 图谱画布'">
          <div class="view-tag"><span class="live-dot"></span>{{ level }}<small>{{ stats.engine }}</small></div>
          <canvas :key="route" ref="canvas" class="scene" @wheel.prevent="wheel" @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="up" @pointerleave="hovered=null" aria-label="可缩放平移图谱"></canvas><canvas ref="overlay" class="labels"></canvas>
          <div class="error" role="alert" v-if="error">{{ error }}</div><div class="loading" v-if="!data&&!error">正在读取固定图谱快照…</div>
          <div class="floating-tools"><button @click="changeZoom(1.4)" aria-label="放大">＋</button><button @click="changeZoom(1/1.4)" aria-label="缩小">−</button><button @click="fullView" aria-label="完整全览">⊙</button><button v-if="saved" @click="restore">返回原视角</button></div>
          <div class="canvas-foot"><span>单击原位选中 · 滚轮缩放 · 拖拽{{ rotation?'旋转':'平移' }}</span><span>{{ stats.drawn }} 屏内实体 / {{ stats.visible }} 展开</span></div>
        </main>
        <aside class="detail">
          <template v-if="current"><div class="detail-title"><p class="eyebrow">{{ typeNames[current.type] }} / SNAPSHOT ENTITY</p><button @click="clear" aria-label="关闭详情">×</button></div><h2>{{ current.label }}</h2><code>{{ current.nodeId }}</code>
            <div class="kpis"><div><b>{{ stats.direct }}</b><span>原始直连</span></div><div><b>{{ stats.submitted }}</b><span>过滤后提交</span></div></div><p class="muted">{{ stats.outside }} 条关系至少一个端点在画布外。单击未改变视角。</p>
            <button class="primary" @click="viewAll">查看全部关联</button><button v-if="saved" @click="restore" class="return">返回原视角</button>
            <h3>推断归属</h3><p>{{ current.communityId }} · {{ currentCommunity?.terms.slice(0,3).join(' / ') }}</p><p class="muted" v-if="Object.keys(current.communityMembership).length>1">跨群落桥梁：{{ Object.entries(current.communityMembership).map(([k,v])=>k+': '+v).join('，') }}。归属色取最多邻接岗位的群落。</p>
            <details><summary>原快照属性 / 证据入口</summary><pre>{{ JSON.stringify(current.properties,null,2) }}</pre></details><p class="muted">快照属性为历史产物；不代表已验证的新 M2 五态或已审核职业分类。</p>
            <h3>全部真实直连 <small>{{ currentEdges.length }}</small></h3><div class="neighbors"><button v-for="e in currentEdges" :key="e.edgeId" @click="select(neighbor(e).nodeId)"><span>{{ neighbor(e).label }}</span><small>{{ e.type }} · {{ e.edgeId }}</small></button></div>
          </template>
          <template v-else><p class="eyebrow">READ THE NEBULA</p><h2>每颗知识星点<br>都保留真实身份</h2><p class="intro">五个主要群落从岗位共享技能中浮现。它们有交叠，也有边缘；名称只是描述性技能，不是正式职业分类。</p><div class="empty-orbit">✧</div><h3>三层视图</h3><ol><li>全景：岗位骨干、群落摘要</li><li>中景：共享能力、桥梁</li><li>近景：单次技能与场景</li></ol><h3>关系图例</h3><p class="muted">实线 REQUIRES<br>点线 APPLIES_TO<br>虚线 RELATED_TO</p><h3>实验边界</h3><p class="muted">共享技能投影 / Louvain / IDF<br>空间坐标用于阅读，距离不是相似度标尺。深度是稳定视觉铺排，不表示职级或能力强弱。</p></template>
          <div class="provenance" v-if="data"><span>DATA FINGERPRINT</span><code>{{ data.metadata.sourceSha256.slice(0,20) }}…</code><p>旧交接快照 · 非在线库实时态</p></div>
        </aside>
      </div>
      <footer><span>独立研究原型 · 未替换正式 Career Nebula</span><span>读取 {{ stats.load }} ms · 本帧 {{ stats.render }} ms · 近期 p95 {{ stats.p95 }} ms <small>CPU 提交计时，非 GPU 帧率</small></span></footer>
    </div>`
}).mount('#app');
