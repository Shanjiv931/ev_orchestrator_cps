/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  server: {
    host: true,
    // Docker Desktop's Windows bind mount doesn't reliably forward inotify
    // events into the container, so chokidar's default watcher misses file
    // changes silently (no error, just stale HMR). Polling works around it.
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      // docker-compose runs this service via `npm run dev`, not a
      // production build (every other service in this stack runs its
      // live-mounted source directly too, e.g. the backend via uvicorn
      // against mounted code) - vite-plugin-pwa's service worker is
      // disabled in dev mode by default, which would make the whole
      // offline-first behavior silently inactive in what `docker compose
      // up` actually serves. devOptions keeps it active in dev too.
      devOptions: {
        enabled: true,
        type: 'module',
      },
      manifest: {
        name: 'MeridianGrid',
        short_name: 'MeridianGrid',
        description: 'AI-driven EV charging orchestration for India',
        theme_color: '#05070D',
        background_color: '#05070D',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/pwa-192.svg', sizes: '192x192', type: 'image/svg+xml' },
          { src: '/pwa-512.svg', sizes: '512x512', type: 'image/svg+xml' },
        ],
      },
      workbox: {
        // Offline-first: last-known nearby station/swap-point list stays
        // available read-only with no network (Section 5.8), syncing
        // again automatically once connectivity returns.
        //
        // urlPattern must require cross-origin (the backend API's own
        // origin, e.g. localhost:8000), not just a path substring match -
        // a plain /stations/ regex with no origin check also matches the
        // frontend's OWN same-origin client-side route at "/stations"
        // (the SPA page itself), which Workbox then intercepts as
        // navigation and caches under the wrong key entirely, silently
        // breaking the real API cache lookup used when offline.
        runtimeCaching: [
          {
            urlPattern: ({ url, sameOrigin }) =>
              !sameOrigin && /\/(stations|feeders|twin)(\/|$)/.test(url.pathname),
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              networkTimeoutSeconds: 3,
              cacheableResponse: { statuses: [0, 200] },
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 },
            },
          },
        ],
      },
    }),
  ],
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
