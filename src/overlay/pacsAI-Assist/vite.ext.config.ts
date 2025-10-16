    import { defineConfig } from 'vite';
    import react from '@vitejs/plugin-react';
    import path from 'path';

    export default defineConfig({
    plugins: [react()],
    build: {
        lib: {
        entry: path.resolve(__dirname, 'src/ohif-extension/pacsai.tsx'),
        name: 'ohifExtensionPacsAI',
        fileName: () => `pacsai.umd.js`,
        formats: ['umd'],
        },
        outDir: 'dist-ext',
        emptyOutDir: true,
        rollupOptions: {
        external: ['react', 'react-dom'],
        output: {
            globals: {
            react: 'React',
            'react-dom': 'ReactDOM',
            },
        },
        },
    },
    });
