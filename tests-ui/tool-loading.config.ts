import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({ plugins: [react()], build: {
  outDir: ".theme-backups/tool-loading-qa", emptyOutDir: false,
  rollupOptions: { input: "tests-ui/tool-loading.html" },
} });
