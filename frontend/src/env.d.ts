/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare const __GRAPH_LAYOUT_SHA256_LF__: string
declare const __REAL_GRAPH_MANIFEST_SHA256__: string
