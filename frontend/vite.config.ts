import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // Alias `@/` là quy ước bắt buộc của shadcn/ui.
    alias: { '@': path.resolve(__dirname, './src') },
  },
  build: {
    rollupOptions: {
      output: {
        // Tách vendor để lần deploy sau chỉ phải tải lại phần code app đã đổi.
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          motion: ['framer-motion'],
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Trong Docker, file đổi trên host không luôn phát sinh inotify event bên trong
    // container — polling đảm bảo HMR hoạt động.
    watch: { usePolling: true },
  },
})
