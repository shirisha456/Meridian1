import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A standalone server bundle keeps the production Docker image small —
  // only .next/standalone + .next/static + public/ need to ship, not the
  // full node_modules tree.
  output: "standalone",
};

export default nextConfig;
