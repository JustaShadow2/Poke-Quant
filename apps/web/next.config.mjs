/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Lean, self-contained server bundle for the Docker runner stage.
  output: "standalone",
};

export default nextConfig;
