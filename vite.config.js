import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';
import { resolve } from 'path';

export default defineConfig({
  plugins: [
    tailwindcss(),
  ],

  // Resolve aliases matching previous webpack setup
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src/assets'),
    },
  },
  base: "/static/",
  build: {
    // Output into Django's static directory
    outDir: './src/lara_django_base/static/lara_django_base/',
    emptyOutDir: false,

    manifest: true,

    rollupOptions: {
      input: {
        "lara_django_base_core" : resolve(__dirname, 'src/assets/scripts/index.js'),
      },
      // Alpine and htmx are bundled HERE and exposed as globals.
      // Child apps (lara-django-materials, lara-django-people, …) declare
      // these as externals so they never re-bundle them.
      output: {
        // Keep predictable sub-directory structure
        entryFileNames: 'js/[name].[hash].js',
        chunkFileNames: 'js/[name].[hash].js',
        assetFileNames: (assetInfo) => {
          if (/\.css$/i.test(assetInfo.names ?? '')) {
            return 'css/[name].[hash][extname]';
          }
          if (/\.(png|jpe?g|gif|svg|ico|webp)$/i.test(assetInfo.names ?? '')) {
            return 'images/[name].[hash][extname]';
          }
          if (/\.(woff2?|eot|ttf|otf)$/i.test(assetInfo.names ?? '')) {
            return 'fonts/[name].[hash][extname]';
          }
          return 'assets/[name].[hash][extname]';
        },
      },
    },

    sourcemap: true,
  },

  // Dev server — proxies unknown requests to Django's runserver
  server: {
    host: 'localhost',
    port: 5174,
    strictPort: true,
    origin: 'http://localhost:5174',
    proxy: {
      // Forward everything that isn't a Vite asset to Django
      '^(?!/static|/@vite|/@fs)': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
