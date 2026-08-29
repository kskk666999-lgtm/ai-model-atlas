/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';

// 生产构建禁止 DEMO_MODE=true：本站不允许在生产目录放置模拟数据。
if (process.env.DEMO_MODE === 'true') {
  throw new Error('DEMO_MODE=true 禁止用于生产构建（vite build）。生产环境必须使用真实数据。');
}

export default defineConfig({
  base: process.env.VITE_BASE || '/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  build: {
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ['echarts'],
          react: ['react', 'react-dom', 'react-router-dom'],
        },
      },
    },
  },
});
