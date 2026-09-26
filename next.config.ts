import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // In local development, proxy /api/* to the FastAPI dev server so the browser
  // talks to one origin (no CORS). On Vercel, vercel.json routes /api/* to the
  // Python function in api/index.py instead.
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    const backend = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
