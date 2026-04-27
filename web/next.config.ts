import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  env: {
    FOF_API_BASE: process.env.FOF_API_BASE ?? "http://127.0.0.1:8000",
  },
};

export default nextConfig;
