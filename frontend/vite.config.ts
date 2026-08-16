import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Several worktrees run their own backend; PIA_BACKEND_URL picks which
      // one this dev server talks to. Default stays the documented port.
      "/api": process.env.PIA_BACKEND_URL ?? "http://localhost:8000",
    },
  },
});
