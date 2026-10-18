import fs from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const repo = fileURLToPath(new URL('../../../', import.meta.url));
for (const [name, ref] of [['.p1a-baseline', '7edfea6'], ['.p1a1-baseline', '994edb6']]) {
  const git = args => execFileSync('git', args, { cwd: repo, encoding: 'utf8' });
  const paths = git(['ls-tree', '-r', '--name-only', ref, 'frontend/visual-lab/src', 'frontend/visual-lab/index.html']).trim().split('\n');
  for (const path of paths) {
    const relative = path.slice('frontend/visual-lab/'.length), target = `${repo}/frontend/visual-lab/${name}/${relative}`;
    let content = git(['show', `${ref}:${path}`]).replaceAll('\r\n', '\n');
    if (relative === 'index.html') content = content.replace('/src/main.js', `/${name}/src/main.js`);
    if (ref === '7edfea6' && relative === 'src/main.js') {
      content = content.replace("  if (params.get('view') === 'selected')", "  if (params.get('view') === 'core') camera.position.setLength(43);\n  if (params.get('view') === 'selected')");
      content = content.replace('dustClock += dt * state.speed;', "if (!params.has('still')) dustClock += dt * state.speed;");
      content = content.replace('    composer.render();', "    composer.render();\n    if (params.has('still') && !root.dataset.capture) root.dataset.capture = JSON.stringify({ seed: CONFIG.seed, camera: camera.position.toArray(), target: orbit.target.toArray(), width: root.clientWidth, height: root.clientHeight, dpr: renderer.getPixelRatio(), dustClock, selected: state.selected, render: CONFIG.render, particles: CONFIG.particles });");
    }
    await fs.mkdir(fileURLToPath(new URL('.', `file:///${target.replaceAll('\\', '/')}`)), { recursive: true });
    // Replays are generated into new/identical ignored files; refuse unrelated content.
    try { await fs.writeFile(target, content, { flag: 'wx' }); }
    catch (error) { if (error.code !== 'EEXIST' || (await fs.readFile(target, 'utf8')).replaceAll('\r\n', '\n') !== content) throw error; }
  }
}
console.log('Historical replays ready; only matching DEV capture bookmarks added to original P1-A.');
