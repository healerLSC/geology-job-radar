import type { NextConfig } from "next";

const basePath = process.env.SITE_BASE_PATH ?? "";

const nextConfig: NextConfig = {
  output: "export",
  basePath,
  assetPrefix: basePath || undefined,
  images: { unoptimized: true },
  trailingSlash: true,
  turbopack: { root: process.cwd() },
};

export default nextConfig;
