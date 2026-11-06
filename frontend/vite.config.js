import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = {
  target: "http://127.0.0.1:8080",
  changeOrigin: true,
};

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/health": api,
      "/tasks": api,
      "/commitments": api,
      "/events": api,
      "/action-requests": api,
      "/brief": api,
      "/approvals": api,
      "/system": api,
      "/agent": api,
      "/catch-up": api,
      "/shopping": api,
      "/hooks": api,
      "/commute": api,
      "/memory": api,
    },
  },
});
