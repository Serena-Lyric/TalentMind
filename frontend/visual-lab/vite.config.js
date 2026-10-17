import { defineConfig } from 'vite';
import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomUUID } from 'node:crypto';

export default defineConfig({
  plugins: [{
    name: 'local-visual-recording',
    configureServer(server) {
      server.middlewares.use('/__visual-lab-capture', async (request, response) => {
        if (request.method !== 'POST' || request.headers.host !== '127.0.0.1:18126' || request.headers.origin !== 'http://127.0.0.1:18126') {
          response.writeHead(403).end(); return;
        }
        try {
          const chunks = []; let length = 0;
          for await (const chunk of request) {
            length += chunk.length;
            if (length > 64 * 1024 * 1024) { response.writeHead(413).end(); return; }
            chunks.push(chunk);
          }
          const bytes = Buffer.concat(chunks);
          if (bytes.length < 4 || bytes.readUInt32BE(0) !== 0x1a45dfa3) { response.writeHead(415).end(); return; }
          // Fixed temp directory + generated name, never a path provided by the browser.
          const path = join(tmpdir(), `talentmind-p1a-${randomUUID()}.webm`);
          await writeFile(path, bytes, { flag: 'wx' });
          response.writeHead(200, { 'Content-Type': 'application/json' }).end(JSON.stringify({ path, bytes: bytes.length }));
        } catch (error) {
          response.writeHead(500, { 'Content-Type': 'application/json' }).end(JSON.stringify({ error: error.message }));
        }
      });
    },
  }],
});
