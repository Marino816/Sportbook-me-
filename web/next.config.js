/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  async redirects() {
    return [
      { source: "/account", destination: "/profile", permanent: true },
    ];
  },
};

module.exports = nextConfig;
