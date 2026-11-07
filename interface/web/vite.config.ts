import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Développement : `npm run dev` (port 5173) parle au serveur Python lancé à côté (python interface/serveur.py, port 8000).
// Le serveur refuse les requêtes d'une autre origine : le proxy retire l'en-tête Origin et se présente comme 127.0.0.1:8000.
const cible = process.env.MEDIMCOM_API || "http://127.0.0.1:8000";
const relais = { target: cible, changeOrigin: true,
  configure: (proxy: any) => proxy.on("proxyReq", (req: any) => req.removeHeader("origin")) };

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": relais, "/pictos": relais, "/journal": relais, "/credits": relais } },
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 800 },
});
