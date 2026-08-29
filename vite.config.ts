/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';

// 生产构建禁止 DEMO_MODE=true：本站不允许在生产目录放置模拟数据。
if (process.env.DEMO_MODE === 'true') {
  throw new Error('DEMO_MODE=true 禁止用于生产构建（vite build）。生产环境必须使用真实数据。');
}

// 子路径部署：支持 VITE_BASE=repo-name（推荐，Windows Git Bash 下不会被 MSYS 改写）
// 或 VITE_BASE=/repo-name/。规范化为 /repo-name/ 形式。
const rawBase = process.env.VITE_BASE?.trim();
const normalizedBase = rawBase
  ? `/${rawBase.replace(/^\/+|\/+$/g, "")}/`
  : '/';

export default defineConfig({
  base: normalizedBase,
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
