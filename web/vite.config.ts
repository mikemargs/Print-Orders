import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Print Order Manager',
        short_name: 'Print Orders',
        description: 'Multi-store print order production management',
        theme_color: '#351c15',
        background_color: '#f7f4ef',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/pwa-512.png', sizes: '512x512', type: 'image/png' }
        ]
      },
      workbox: {
        navigateFallbackDenylist: [/^\/api\//],
        globPatterns: ['**/*.{js,css,html,png,svg,ico}']
      }
    })
  ],
  server: { proxy: { '/api': 'http://localhost:8000' } },
  build: { outDir: 'dist', sourcemap: true },
  test: { environment: 'jsdom', setupFiles: './src/test/setup.ts', globals: true, include: ['src/**/*.test.{ts,tsx}'] }
})
