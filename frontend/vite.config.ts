import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Where the dev server proxies /api/* to.
//
// Inside docker-compose, "localhost" resolves to the *frontend container
// itself*, not the backend — so the proxy must target the compose service
// name instead ("backend"). docker-compose.yml sets VITE_PROXY_TARGET for
// exactly this. Outside Docker (plain `npm run dev`), the env var is
// unset and it falls back to localhost, which is correct there.
const proxyTarget = process.env.VITE_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
