import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build output goes to app/static/analysis/ so FastAPI can serve it as SPA.
export default defineConfig({
  plugins: [react()],
  base: "/static/analysis/",
  build: {
    outDir: "../app/static/analysis",
    emptyOutDir: true,
  },
  // Dev proxy: forward /jobs and /api to the running FastAPI backend.
  server: {
    proxy: {
      "/jobs": "http://localhost:8000",
      "/api": "http://localhost:8000",
    },
  },
});
