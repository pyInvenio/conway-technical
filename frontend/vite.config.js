import { defineConfig } from "vite";
import { sveltekit } from "@sveltejs/kit/vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    sveltekit({
      vitePlugin: {
        dynamicCompileOptions({ filename }) {
          // Disable runes for iconify to avoid $$props issues
          if (filename?.includes('@iconify/svelte')) {
            return { runes: false };
          }
        }
      }
    })
  ],

  optimizeDeps: {
    exclude: ['@iconify/svelte']
  },

  server: {
    port: 5173,
    strictPort: false,
  },

  preview: {
    port: 4173,
    strictPort: false,
  },
});
