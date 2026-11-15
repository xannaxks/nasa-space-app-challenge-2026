import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Backend is only used for route calculation now; /maps/* is served
      // locally from frontend/public/maps/ (pre-converted PNGs + GeoJSON).
      '/route': 'http://localhost:8000',
      '/routes': 'http://localhost:8000',
    },
  },
});
