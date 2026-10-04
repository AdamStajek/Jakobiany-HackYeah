import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "..", "GOOGLE_");
  return {
    define: {
      __GOOGLE_MAPS_BROWSER_KEY__: JSON.stringify(
        env.GOOGLE_MAPS_BROWSER_API_KEY ?? env.GOOGLE_API_KEY ?? "",
      ),
    },
    plugins: [react()],
    server: {
      proxy: {
        "/api": { target: "http://127.0.0.1:8000", changeOrigin: false },
      },
    },
  };
});
