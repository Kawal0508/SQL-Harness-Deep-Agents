import {defineConfig} from "vite";
import react from "@vitejs/plugin-react";

// The API is served by Backend/api.py on :8000. In dev, Vite serves the page
// and proxies the API routes there, so the same relative paths work in both
// dev and the built bundle that FastAPI itself serves.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(
      ["/ask", "/decide", "/schema"].map(p => [p, "http://localhost:8000"])
    ),
  },
});
