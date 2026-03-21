/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  /** Цель прокси Vite в dev (только vite.config, не в bundle) */
  readonly VITE_DEV_PROXY_TARGET?: string;
  readonly VITE_COUCHDB_URL?: string;
  readonly VITE_COUCHDB_DATABASE?: string;
  readonly VITE_COUCHDB_USER?: string;
  readonly VITE_COUCHDB_PASSWORD?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
