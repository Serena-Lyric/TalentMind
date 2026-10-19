import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'
import { resolve } from 'node:path'
import { realpathSync } from 'node:fs'
import { allowRealPreviewRequest } from './realPreview'

// Private bundles are explicit localhost dev previews; never emitted by build.
const previewRoot = process.env.M3_REAL_PREVIEW_DIR ? realpathSync(process.env.M3_REAL_PREVIEW_DIR) : null
const previewFiles = ['manifest.json','facts.json','sources.json','layout.json']
function realArtifacts() {
  return {name:'real-jd-private-preview',configureServer(server:any){
    if(!previewRoot)return
    server.middlewares.use((req:any,res:any,next:any)=>{
      if(!req.url?.startsWith('/real-graph-artifacts/'))return next()
      if(!allowRealPreviewRequest(req.socket.remoteAddress,req.headers.host,req.headers.origin)){res.statusCode=403;return res.end('Local preview only')}
      const name=req.url.slice('/real-graph-artifacts/'.length)
      if(!previewFiles.includes(name)){res.statusCode=404;return res.end()}
      const file=realpathSync(resolve(previewRoot,name))
      if(file!==resolve(previewRoot,name)){res.statusCode=403;return res.end()}
      res.setHeader('Content-Type','application/json; charset=utf-8');res.setHeader('Cache-Control','no-store')
      res.end(readFileSync(file))
    })
  }}
}

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
  define: { __REAL_GRAPH_MANIFEST_SHA256__:JSON.stringify(previewRoot?createHash('sha256').update(readFileSync(resolve(previewRoot,'manifest.json'),'utf8').replace(/\r\n/g,'\n')).digest('hex'):''), __GRAPH_LAYOUT_SHA256_LF__: JSON.stringify(createHash('sha256').update(readFileSync(artifacts['layout.json'],'utf8').replace(/\r\n/g,'\n')).digest('hex')) },
  base: "./",
  plugins: [vue(), historicalArtifacts(), realArtifacts()],
  resolve: {
    alias: {
      "@": "/src"
    }
  },
  server: {
    host: previewRoot ? "127.0.0.1" : "0.0.0.0",
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
