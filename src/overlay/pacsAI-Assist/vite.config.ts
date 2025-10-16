import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    // build normal de tu app (déjalo como está)
  },
  // 👇 crea un build separado de la extensión
  define: {},
});
