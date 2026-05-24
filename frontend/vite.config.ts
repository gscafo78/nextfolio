import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

const backendHost = process.env.VITE_BACKEND_HOST ?? "localhost:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": {
        target: `http://${backendHost}`,
        changeOrigin: true,
      },
      "/ws": {
        target: `ws://${backendHost}`,
        ws: true,
      },
    },
  },
});
