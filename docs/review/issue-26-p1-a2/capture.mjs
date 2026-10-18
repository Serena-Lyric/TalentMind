import fs from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
const { chromium } = await import(process.env.NEBULA_PLAYWRIGHT ? pathToFileURL(process.env.NEBULA_PLAYWRIGHT).href : 'playwright');
const out = fileURLToPath(new URL('./', import.meta.url)), mode = process.argv[2] ?? 'capture';
const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding'] });
const context = await browser.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
const consoleEvents = [], manifest = { browser: browser.version(), headless: true, viewport: [1600, 900], dpr: 1, mode, samples: [] };
try {
  for (const [label, path] of [['p1a', '/.p1a-baseline/index.html'], ['p1a1', '/.p1a1-baseline/index.html'], ['p1a2', '/']]) {
    for (const view of ['overview', 'arm', 'core', 'selected', 'zoom']) {
      const page = await context.newPage();
      page.on('pageerror', e => consoleEvents.push({ label, view, type: 'pageerror', message: e.message }));
      page.on('console', m => { if (['error', 'warning'].includes(m.type())) consoleEvents.push({ label, view, type: m.type(), message: m.text() }); });
      const url = `http://127.0.0.1:18127${path}?data=demo&diagnostics=1&view=${view === 'arm' ? 'near' : view === 'zoom' ? 'selected' : view}${mode === 'capture' ? '&still=1' : ''}`;
      await page.goto(url, { waitUntil: 'networkidle' });
      await page.waitForSelector('#diagnostics');
      await page.addStyleTag({ content: '#diagnostics{display:none!important}' });
      if (view === 'zoom') { await page.locator('#galaxy').hover({ position: { x: 800, y: 450 } }); await page.mouse.wheel(0, -240); }
      await page.waitForTimeout(1500);
      if (mode === 'perf') {
        await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
        await page.waitForFunction(() => { try { return JSON.parse(document.querySelector('#stats').textContent).frameSamples >= 300; } catch { return false; } }, null, { timeout: 120000 });
      }
      const stats = JSON.parse(await page.locator('#stats').innerText());
      const sample = { label, view, url, stats, capture: await page.locator('#universe').getAttribute('data-capture') };
      if (mode === 'capture') {
        const filename = `${label}-${view}.png`; await page.screenshot({ path: `${out}/${filename}`, scale: 'css' });
        sample.file = filename; sample.sha256 = createHash('sha256').update(await fs.readFile(`${out}/${filename}`)).digest('hex');
      }
      await fs.writeFile(`${out}/${label}-${mode}-${view}.json`, JSON.stringify(sample, null, 2));
      manifest.samples.push(sample); console.log(JSON.stringify({ label, view, mode, fps: stats.fps, p95: stats.p95Ms, gpu: stats.gpu }));
      await page.close();
    }
  }
  await fs.writeFile(`${out}/${mode}-manifest.json`, JSON.stringify(manifest, null, 2));
  await fs.writeFile(`${out}/${mode}-console.json`, JSON.stringify(consoleEvents, null, 2));
  if (consoleEvents.length) throw new Error(`Console problems: ${JSON.stringify(consoleEvents)}`);
} finally { await context.close(); await browser.close(); }
