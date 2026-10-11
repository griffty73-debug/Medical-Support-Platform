import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => ({
  plugins: [vue()],
  define: { __PORTAL__: JSON.stringify(mode === 'doctor' ? 'doctor' : 'patient') },
  server: { proxy: { '/api': 'http://127.0.0.1:5001' } },
}))
