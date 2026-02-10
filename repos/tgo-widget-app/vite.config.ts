import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // The widget bundle is served under /widget/, so use a relative base to avoid /assets/... 404s.
  base: './',
  plugins: [react({ jsxImportSource: '@emotion/react', babel: { plugins: ['@emotion/babel-plugin'] } })],
  server: { port: 5173 },
  preview: { port: 5174 },
  build: {
    manifest: true
  }
})
