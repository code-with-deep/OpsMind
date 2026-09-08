import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Docker Compose sets VITE_API_PROXY_TARGET=http://api:8000 on the process env.
  // loadEnv() only reads .env files, so prefer process.env for container networking.
  const apiProxyTarget =
    process.env.VITE_API_PROXY_TARGET ||
    env.VITE_API_PROXY_TARGET ||
    "http://localhost:8000";

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      port: 3000,
      host: "0.0.0.0",
      watch: {
        usePolling: true,
      },
      proxy: {
        "/auth": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/playbooks": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/data": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/access": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/notifications": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/investigations": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/tools": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/health": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/ready": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
