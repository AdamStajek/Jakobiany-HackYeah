import { defineConfig, mergeConfig } from "vite";
import base from "./vite.config";
export default defineConfig((env) =>
  mergeConfig(
    base(env),
    defineConfig({
      server: {
        proxy: {
          "/api": { target: "http://127.0.0.1:8137", changeOrigin: false },
        },
      },
    }),
  ),
);
