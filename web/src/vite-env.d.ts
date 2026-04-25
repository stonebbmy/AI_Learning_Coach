/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PROMETHEUS_URL?: string
  readonly VITE_GRAFANA_URL?: string
}

import 'vue-router'
declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    urlKey?: string
    defaultUrl?: string
  }
}
