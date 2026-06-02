import path from "path";

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
// package.json è sempre dentro il build context (./frontend/) — funziona in Docker e in locale
import pkg from "./package.json";

const backendHost = process.env.VITE_BACKEND_HOST ?? "localhost:8000";
const APP_VERSION: string = pkg.version;

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
        skipWaiting: true,
        clientsClaim: true,
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
  define: {
    __APP_VERSION__: JSON.stringify(APP_VERSION),
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Core React — cambia raramente, cache a lungo termine
          "vendor-react":  ["react", "react-dom", "react-router-dom"],
          // Data fetching
          "vendor-query":  ["@tanstack/react-query", "axios"],
          // Grafici — chunk separato: ~300 KB, non caricato su pagine senza grafici
          "vendor-charts": ["recharts"],
          // Mappa mondo (Allocation) — separato per non pesare sulle altre pagine
          "vendor-maps":   ["react-simple-maps"],
          // i18n — solo al mount iniziale
          "vendor-i18n":   ["i18next", "react-i18next", "i18next-browser-languagedetector"],
          // Form
          "vendor-forms":  ["react-hook-form", "@hookform/resolvers", "zod"],
          // Sentry — non critico per il render iniziale
          "vendor-sentry": ["@sentry/react"],
          // Date utils (tree-shakeable ma vale separarlo)
          "vendor-dates":  ["date-fns"],
        },
      },
    },
    // Avvisa se un chunk supera 500 KB prima di gzip
    chunkSizeWarningLimit: 500,
  },
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
