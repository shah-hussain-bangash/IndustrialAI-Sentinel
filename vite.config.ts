import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5187,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8127",
      "/docs": "http://127.0.0.1:8127",
      "/openapi.json": "http://127.0.0.1:8127",
    },
  },
  build: { outDir: "dist" },
});
