import type { NextConfig } from "next";

// FOF_API_BASE is read at runtime from process.env (server-side only) by
// `web/lib/api.ts`. Don't pin it here — that would inline the build-time value
// into client bundles, which is wrong for both correctness (port can change in
// prod) and security (we don't want the loopback URL leaking to the browser).
const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Browser-side requests to /api/* (except /api/auth/*) are gated by the
  // Auth.js middleware and then rewritten to the FastAPI service. Keeping the
  // rewrite in Next.js means we don't have to duplicate auth checks in nginx
  // or the FastAPI process — the middleware is the single access boundary.
  async rewrites() {
    const target = process.env.FOF_API_BASE ?? "http://127.0.0.1:8000";
    return [
      { source: "/api/health", destination: `${target}/api/health` },
      { source: "/api/runs", destination: `${target}/api/runs` },
      { source: "/api/runs/:path*", destination: `${target}/api/runs/:path*` },
    ];
  },
};

export default nextConfig;
