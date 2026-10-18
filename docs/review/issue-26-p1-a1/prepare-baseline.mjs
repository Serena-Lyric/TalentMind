import fs from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { join, resolve, sep } from 'node:path';

const repository = fileURLToPath(new URL('../../../', import.meta.url));
const destination = join(repository, 'frontend/visual-lab/.p1a-baseline');
const git = args => execFileSync('git', args, { cwd: repository, encoding: 'utf8' });
const paths = git(['ls-tree', '-r', '--name-only', '7edfea6', 'frontend/visual-lab/src', 'frontend/visual-lab/index.html']).trim().split('\n');
for (const path of paths) {
  const relative = path.slice('frontend/visual-lab/'.length), target = resolve(destination, relative);
  if (!target.startsWith(resolve(destination) + sep)) throw new Error('Baseline path outside replay directory');
  let text = git(['show', `7edfea6:${path}`]).replaceAll('\r\n', '\n');
  if (relative === 'index.html') text = text.replace('/src/main.js', '/.p1a-baseline/src/main.js');
  if (relative === 'src/main.js') {
    text = text.replace("  if (params.get('view') === 'selected')", "  if (import.meta.env.DEV && params.get('view') === 'core') camera.position.setLength(43);\n  if (params.get('view') === 'selected')");
    text = text.replace('dustClock += dt * state.speed;', "if (!(import.meta.env.DEV && params.has('still'))) dustClock += dt * state.speed;");
    text = text.replace('    composer.render();', "    composer.render();\n    if (import.meta.env.DEV && params.has('still') && !root.dataset.capture) root.dataset.capture = JSON.stringify({ seed: CONFIG.seed, camera: camera.position.toArray().map(v => +v.toFixed(6)), target: orbit.target.toArray().map(v => +v.toFixed(6)), width: root.clientWidth, height: root.clientHeight, dpr: renderer.getPixelRatio(), dustClock, selected: state.selected, render: CONFIG.render, particles: CONFIG.particles });");
  }
  await fs.mkdir(resolve(target, '..'), { recursive: true });
  try { await fs.writeFile(target, text, { flag: 'wx' }); }
  catch (error) {
    if (error.code !== 'EEXIST') throw error;
    const actual = (await fs.readFile(target, 'utf8')).replaceAll('\r\n', '\n');
    if (actual !== text) {
      let offset = 0; while (offset < Math.min(actual.length, text.length) && actual[offset] === text[offset]) offset++;
      throw new Error(`Baseline differs at ${relative}:${offset}; refusing overwrite. Expected ${JSON.stringify(text.slice(offset, offset + 50))}, got ${JSON.stringify(actual.slice(offset, offset + 50))}`);
    }
  }
}
console.log('P1-A 7edfea6 replay ready; only identical DEV capture bookmarks added.');
