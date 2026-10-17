// Loaded only by Vite DEV with ?diagnostics=1; absent from the production bundle.
export function mountDiagnostics(app) {
  const frames = [], gl = app.renderer.getContext(), gpuInfo = gl.getExtension('WEBGL_debug_renderer_info');
  const environment = { userAgent: navigator.userAgent, gpu: gpuInfo ? gl.getParameter(gpuInfo.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER), webgl: gl.getParameter(gl.VERSION) };
  const panel = document.createElement('aside'); panel.id = 'diagnostics';
  panel.innerHTML = '<strong>DEV / 真机诊断</strong><p>本页是开发测试模式，截图入口不含此面板。</p><button id="run-checks">运行交互检查</button><button id="record">录制约20秒操作</button><label>输入保护测试<input id="typing" placeholder="在此输入 WASDQE"></label><pre id="stats"></pre><pre id="checks"></pre><a id="record-download" hidden>下载真实 WebGL 操作录像</a>';
  document.querySelector('#universe').append(panel);
  const stats = panel.querySelector('#stats'), checks = panel.querySelector('#checks');
  const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
  const wheel = deltaY => app.canvas.dispatchEvent(new WheelEvent('wheel', { deltaY, cancelable: true, bubbles: true }));
  async function hold(key, ms) {
    app.canvas.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
    await delay(ms);
    app.canvas.dispatchEvent(new KeyboardEvent('keyup', { key, bubbles: true }));
  }
  const near = (a, b) => Math.abs(a - b) < .001;
  const equal = (a, b) => a.every((value, index) => near(value, b[index]));
  function summarize() {
    const f = frames.slice(-300).filter(frame => frame > 0).sort((a, b) => a - b);
    const average = f.reduce((sum, frame) => sum + frame, 0) / f.length;
    return { ...app.snapshot(), frameSamples: f.length, meanMs: +average.toFixed(2), fps: +(1000 / average).toFixed(1), p95Ms: +f[Math.floor(f.length * .95)]?.toFixed(2), ...environment };
  }
  setInterval(() => { stats.textContent = JSON.stringify(summarize(), null, 2); }, 1000);
  document.addEventListener('visibilitychange', () => { frames.length = 0; });
  panel.querySelector('#run-checks').onclick = async () => {
    const button = panel.querySelector('#run-checks');
    if (button.disabled || panel.querySelector('#record').disabled) return;
    button.disabled = true;
    frames.length = 0;
    const results = [], savedCamera = app.camera.position.clone(), savedTarget = app.orbit.target.clone(), savedSpeed = app.state.speed;
    const check = (name, passed, evidence) => { results.push({ name, passed, evidence }); checks.textContent = JSON.stringify(results, null, 2); };
    try {
      app.select(null); const start = app.snapshot(); wheel(-120); const after = app.snapshot();
      check('未选中滚轮只改变装饰流速', near(start.distance, after.distance) && after.speed > start.speed, { before: start.speed, after: after.speed, distance: after.distance });
      wheel(10000); const paused = app.snapshot(); await delay(400); check('流速下限为零且装饰时钟暂停', paused.speed === 0 && near(paused.dustClock, app.snapshot().dustClock));
      wheel(-10000); check('流速上限为2', app.state.speed === 2);
      const beforeSelect = app.snapshot(); app.select(app.nodes[0]); const selected = app.snapshot();
      check('选中相机不动', equal(beforeSelect.camera, selected.camera) && equal(beforeSelect.target, selected.target));
      wheel(-120); check('选中后滚轮只缩放', app.snapshot().distance < selected.distance && app.state.speed === selected.speed);
      wheel(-10000); check('缩放下限24', near(app.snapshot().distance, 24));
      wheel(10000); check('缩放上限520', near(app.snapshot().distance, 520));
      app.camera.position.copy(savedCamera); app.orbit.target.copy(savedTarget); app.orbit.update();
      const qStart = app.snapshot().distance; await hold('q', 500); const qEnd = app.snapshot().distance;
      await hold('e', 500); check('Q/E连续缩放', qEnd < qStart - 5 && app.snapshot().distance > qEnd + 5, { qStart, qEnd, eEnd: app.snapshot().distance });
      for (const key of ['w', 'a', 's', 'd']) {
        const target = app.snapshot().target; await hold(key, 300); check(`${key.toUpperCase()}连续平移`, !equal(target, app.snapshot().target));
      }
      for (const tag of ['input', 'textarea', 'select', 'div']) {
        const input = document.createElement(tag); if (tag === 'div') input.contentEditable = 'true'; panel.append(input); input.focus();
        const before = app.snapshot(); input.dispatchEvent(new KeyboardEvent('keydown', { key: 'q', bubbles: true })); await delay(150);
        const afterInput = app.snapshot(); check(`${tag}输入保护`, near(before.distance, afterInput.distance) && equal(before.target, afterInput.target)); input.remove();
      }
      for (const flag of ['isComposing', 'ctrlKey', 'altKey', 'metaKey']) {
        const before = app.snapshot().distance;
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'q', [flag]: true })); await delay(100);
        check(`${flag}保护`, near(before, app.snapshot().distance));
      }
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'q' })); window.dispatchEvent(new Event('blur'));
      const beforeBlur = app.snapshot().distance; await delay(150); check('失焦清除按键', near(beforeBlur, app.snapshot().distance));
      const positions = app.nodes.map(node => [...node.position]); await delay(300);
      check('知识坐标不随动画变化', app.nodes.every((node, index) => equal(node.position, positions[index])));
      for (const [width, height] of [[960, 640], [1600, 900]]) {
        app.root.style.width = `${width}px`; app.root.style.height = `${height}px`;
        const expected = Math.floor(width * Math.min(devicePixelRatio, 1.5));
        const resized = () => app.canvas.width === expected && near(app.camera.aspect, width / height);
        const deadline = performance.now() + 3000;
        while (!resized() && performance.now() < deadline) await delay(50);
        check(`容器resize ${width}×${height}`, resized(), { expected, actual: app.canvas.width, aspect: app.camera.aspect });
      }
    } catch (error) { check('诊断异常', false, error.message); }
    finally {
      app.root.style.width = ''; app.root.style.height = ''; app.select(null); app.camera.position.copy(savedCamera); app.orbit.target.copy(savedTarget); app.state.speed = savedSpeed; app.orbit.update();
      panel.dataset.checks = JSON.stringify(results); panel.dataset.finished = 'true';
      button.disabled = false;
    }
  };
  panel.querySelector('#record').onclick = async () => {
    if (panel.querySelector('#record').disabled || panel.querySelector('#run-checks').disabled) return;
    const button = panel.querySelector('#record'); button.disabled = true;
    const stream = app.canvas.captureStream(30), chunks = [];
    const type = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'].find(value => MediaRecorder.isTypeSupported(value));
    const recorder = new MediaRecorder(stream, { mimeType: type, videoBitsPerSecond: 6500000 });
    const done = new Promise(resolve => { recorder.onstop = resolve; });
    recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
    const savedCamera = app.camera.position.clone(), savedTarget = app.orbit.target.clone(), savedSpeed = app.state.speed;
    try {
      app.select(null); app.state.speed = .4; const started = performance.now(); recorder.start(1000);
      await delay(3000); await hold('d', 1000); await hold('w', 700); await hold('q', 1300);
      wheel(-450); await delay(3000); wheel(10000); await delay(1800); wheel(-300); await delay(1800);
      app.select(app.nodes[0]); await delay(2000); wheel(-180); await delay(1700); await hold('e', 700); await delay(3000);
      recorder.stop(); await done;
      const blob = new Blob(chunks, { type }), link = panel.querySelector('#record-download');
      if (link.dataset.url) URL.revokeObjectURL(link.dataset.url);
      link.href = URL.createObjectURL(blob); link.dataset.url = link.href; link.download = 'career-nebula-real-webgl.webm'; link.hidden = false;
      const saved = await fetch('/__visual-lab-capture', { method: 'POST', body: blob });
      const result = await saved.json(); if (!saved.ok) throw new Error(result.error ?? '本机录像保存失败');
      panel.dataset.recording = JSON.stringify({ bytes: blob.size, durationMs: performance.now() - started, mimeType: type, saved: result, capture: 'real canvas.captureStream 30fps; scripted DOM keyboard/wheel + diagnostic selection; no static frames' });
    } catch (error) { checks.textContent = `录制失败：${error.message}`; if (recorder.state === 'recording') recorder.stop(); }
    finally { stream.getTracks().forEach(track => track.stop()); app.select(null); app.camera.position.copy(savedCamera); app.orbit.target.copy(savedTarget); app.state.speed = savedSpeed; app.orbit.update(); button.disabled = false; }
  };
  return elapsed => { frames.push(elapsed); if (frames.length > 600) frames.shift(); };
}
