import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react-swc";
import { defineConfig } from "vite";

// The build goes to dist/; the artefact copies it beside the back end, which
// serves it on the same domain. In development, Vite proxies the API to the
// back end on :8000, so the session cookie stays first-party.
const backend = "http://localhost:8000";

export default defineConfig({
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "./src") },
  },
  server: {
    proxy: { "/api": backend, "/auth": backend },
  },
  plugins: [
    tanstackRouter({ target: "react", autoCodeSplitting: true }),
    react(),
    tailwindcss(),
  ],
});
