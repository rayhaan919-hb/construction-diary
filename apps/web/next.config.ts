import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  serverExternalPackages: ["@react-pdf/renderer", "sharp"],
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
