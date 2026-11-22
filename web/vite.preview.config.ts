import { defineConfig } from "vite";
export default defineConfig({
  preview: {
    host: "127.0.0.1",
    port: 5181,
    proxy: { "/api": { target: "http://127.0.0.1:8001", changeOrigin: false } },
  },
});
