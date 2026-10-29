/// <reference types="vitest/config" />
import babel from "@rolldown/plugin-babel";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  // React Compiler 1.0 memoizes components and hooks at build time (react.dev, installation).
  plugins: [react(), babel({ presets: [reactCompilerPreset()] })],
  test: { setupFiles: ["./src/test/setup.ts"] },
  server: {
    // Extra host names allowed for the dev server (e.g. a private Tailscale name), comma-separated.
    // DEV_ALLOWED_HOSTS: extra host names (a private tunnel) the dev server answers to.
    allowedHosts: process.env.DEV_ALLOWED_HOSTS?.split(",").filter(Boolean) ?? [],
    port: 5173,
    strictPort: true,
    // API_TARGET lets another backend serve the dev frontend: a second branch, or the `api`
    // service when `make dev` runs this server in Docker. String targets set changeOrigin,
    // which rewrites Host to the target, so the backend must accept that host name
    // (DJANGO_ALLOWED_HOSTS) and list the dev origin in CSRF_TRUSTED_ORIGINS.
    proxy: {
      "/api": process.env.API_TARGET ?? "http://127.0.0.1:8010",
      "/admin": process.env.API_TARGET ?? "http://127.0.0.1:8010",
    },
  },
});
