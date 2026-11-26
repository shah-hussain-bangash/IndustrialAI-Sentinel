import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({ plugins: [react()], build: { outDir: ".theme-backups/condition-links-qa", emptyOutDir: false, rollupOptions: { input: ["tests-ui/condition-links.html", "tests-ui/attention.html"] } } });
