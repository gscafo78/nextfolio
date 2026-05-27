import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import path from "path";

const backendHost = process.env.VITE_BACKEND_HOST ?? "localhost:8000";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icons/apple-touch-icon-v2.png", "icons/favicon-32x32.png"],
      manifest: {
        name: "Nextfolio",
        short_name: "Nextfolio",
        description: "Il tuo portafoglio finanziario personale",
        theme_color: "#1d4ed8",
        background_color: "#f0f7ff",
        display: "standalone",
        orientation: "portrait",
        start_url: "/",
        scope: "/",
        lang: "it",
        icons: [
          {
            src: "/icons/icon-192x192-v2.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "/icons/icon-512x512-v2.png",
            sizes: "512x512",
            type: "image/png",
          },
          {
            src: "/icons/icon-512x512-v2.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//, /^\/sw\.js$/, /^\/offline\.html$/],
        // Runtime cache: API calls with stale-while-revalidate
        runtimeCaching: [
          {
            urlPattern: /^\/api\/v1\/portfolio\//,
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "portfolio-api",
              expiration: {
                maxEntries: 20,
                maxAgeSeconds: 5 * 60, // 5 min
              },
            },
          },
          {
            urlPattern: /^\/api\/v1\/transactions/,
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "transactions-api",
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60,
              },
            },
          },
        ],
      },
      // In dev mode, don't activate SW to avoid caching issues
      devOptions: {
        enabled: false,
      },
    }),
  ],
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
