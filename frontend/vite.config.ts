import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

export default defineConfig({
  base: "./",
  plugins: [vue()],
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