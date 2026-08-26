import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      { source: "/account", destination: "/profile", permanent: true },
    ];
  },
};

export default nextConfig;
