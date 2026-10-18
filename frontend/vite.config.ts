import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'
import { resolve } from 'node:path'

// Serve/emit the single tracked snapshot; never duplicate it under public/.
const artifacts = {
  'historical.json': fileURLToPath(new URL('../exchange/m3/graph.json', import.meta.url)),
  'layout.json': fileURLToPath(new URL('../exchange/m3/overlays/p2-1-layout.json', import.meta.url)),
}
function historicalArtifacts() {
  return {
    name: 'historical-graph-artifacts',
    configureServer(server: any) {
      server.watcher.add(Object.values(artifacts))
      server.watcher.on('change',(path:string)=>{
        if(Object.values(artifacts).some(file=>resolve(file)===resolve(path))) server.restart()
      })
      server.middlewares.use((req: any,res: any,next: any) => {
        const name = req.url?.split('?')[0]?.replace(/^\/graph-artifacts\//, '') as keyof typeof artifacts
        if (!Object.prototype.hasOwnProperty.call(artifacts,name)) return next()
        res.setHeader('Content-Type','application/json; charset=utf-8')
        res.end(readFileSync(artifacts[name]))
      })
    },
    generateBundle(this: any) {
      for (const [name,path] of Object.entries(artifacts)) this.emitFile({type:'asset',fileName:`graph-artifacts/${name}`,source:readFileSync(path)})
    },
  }
}

export default defineConfig({
  define: { __GRAPH_LAYOUT_SHA256_LF__: JSON.stringify(createHash('sha256').update(readFileSync(artifacts['layout.json'],'utf8').replace(/\r\n/g,'\n')).digest('hex')) },
  base: "./",
  plugins: [vue(), historicalArtifacts()],
  resolve: {
    alias: {
      "@": "/src"
    }
  },
  server: {
    host: "0.0.0.0",
    port: 18080,
    proxy: {
      // 开发环境：/api 代理到后端（安装即用；默认 18000，可用 VITE_PROXY_TARGET 覆盖）
      "/api": {
        target: process.env.VITE_PROXY_TARGET || "http://127.0.0.1:18000",
        changeOrigin: true
      }
    }
  },
  preview: {
    host: "0.0.0.0",
    port: 4173
  },
  build: {
    outDir: "dist",
    assetsDir: "assets",
    sourcemap: false
  }
})
