/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_GUEST_ENABLED?: string;
  readonly VITE_EVALS_ENABLED?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
