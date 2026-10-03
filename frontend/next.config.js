// Next.js config for the minimal demo frontend (TSD-003).
//
// /api/*, /health and /ready are rewritten to the backend URL, so judges see
// a single origin (calvino.rubrica.dev) and the Space's URL stays an
// implementation detail. The URL is configuration, never code: BACKEND_URL on
// Vercel, with NEXT_PUBLIC_BACKEND_URL and the local API as fallbacks.

const backendUrl =
  process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:7860";

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backendUrl}/api/:path*` },
      { source: "/health", destination: `${backendUrl}/health` },
      { source: "/ready", destination: `${backendUrl}/ready` },
    ];
  },
};

module.exports = nextConfig;
