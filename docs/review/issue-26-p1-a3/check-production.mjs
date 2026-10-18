import fs from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';

const { chromium } = await import(process.env.NEBULA_PLAYWRIGHT ? pathToFileURL(process.env.NEBULA_PLAYWRIGHT).href : 'playwright');
const out = fileURLToPath(new URL('./', import.meta.url)), checks = [], errors = [];
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const context = await browser.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
const check = (name, passed, evidence) => { checks.push({ name, passed, evidence }); assert.ok(passed, name); };
try {
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (['error', 'warning'].includes(m.type())) errors.push(m.text()); });
  for (const mode of ['', 'baseline', 'adaptive', 'unknown']) {
    await page.goto(`http://127.0.0.1:18130/?visual=${mode}&diagnostics=1&still=1`);
    await page.waitForFunction(() => document.querySelector('#universe').dataset.ready === 'true');
    const graph = JSON.parse(await page.locator('#universe').getAttribute('data-graph'));
    check(`${mode || 'default'} production exact M3`, graph.nodes === 7845 && graph.edges === 11412 && graph.sha256 === '6565d56dbc5a267eb90144f078c54f3d0c761c9a98ca29a18b4dc9c6cdde38e2');
    check(`${mode || 'default'} production mode and DEV exclusion`, (await page.locator('footer span:last-child').innerText()).endsWith(mode === 'adaptive' ? 'adaptive' : 'baseline') && await page.locator('#diagnostics').count() === 0 && await page.locator('#universe').getAttribute('data-capture') === null);
    await page.locator('#graph-query').fill('skill:python'); await page.locator('#graph-results').selectOption('skill:python');
    const detail = JSON.parse(await page.locator('#graph-detail pre').innerText());
    check(`${mode || 'default'} production original selected node/links`, detail.node.id === 'skill:python' && detail.node.job_count === 225 && detail.relationships.length === 222);
  }
  await page.goto('http://127.0.0.1:18130/?visual=adaptive&data=demo');
  await page.waitForFunction(() => document.querySelector('#universe').dataset.ready === 'true');
  check('production explicit synthetic fallback labelled', (await page.locator('.demo-mark').innerText()).includes('合成') && await page.locator('.sector').count() === 8);
  const dist = await fs.readFile(new URL('../../../frontend/visual-lab/dist/m3-graph.json', import.meta.url));
  check('production asset hash', createHash('sha256').update(dist).digest('hex') === '6565d56dbc5a267eb90144f078c54f3d0c761c9a98ca29a18b4dc9c6cdde38e2');
  for (const mode of ['baseline', 'adaptive']) {
    await page.goto(pathToFileURL(`${out}/${mode}-zoom-roundtrip.webm`).href);
    await page.waitForFunction(() => { const v = document.querySelector('video'); return v?.readyState >= 2 && v.videoWidth === 1600; });
    const metadata = await page.locator('video').evaluate(async video => {
      video.pause();
      // WebM MediaRecorder streams may initially report Infinity; seek to discover the end.
      if (!Number.isFinite(video.duration)) { video.currentTime = 1e8; await new Promise(resolve => video.addEventListener('seeked', resolve, { once: true })); }
      const duration = video.duration;
      for (const ratio of [.1, .5, .9]) {
        video.currentTime = duration * ratio; await new Promise(resolve => video.addEventListener('seeked', resolve, { once: true }));
      }
      return { width: video.videoWidth, height: video.videoHeight, duration, readyState: video.readyState };
    });
    check(`${mode} real zoom video decodes and seeks`, metadata.width === 1600 && metadata.height === 900 && metadata.duration > 8 && metadata.readyState >= 2, metadata);
  }
  check('normal production and video playback no errors/warnings', errors.length === 0, errors);
} finally {
  await fs.writeFile(`${out}/production.json`, JSON.stringify({ checks, errors, browser: browser.version() }, null, 2));
  await context.close(); await browser.close();
}
console.log(JSON.stringify({ checks: checks.length, errors }));
