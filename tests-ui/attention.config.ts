import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({ plugins: [react()], build: {
  outDir: ".theme-backups/attention-qa", emptyOutDir: false,
  rollupOptions: { input: "tests-ui/attention.html" },
} });
