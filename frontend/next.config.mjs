/** @type {import('next').NextConfig} */
const useStandalone = process.env.NEXT_STANDALONE === "true";

const nextConfig = {
  reactStrictMode: true,
  ...(useStandalone ? { output: "standalone" } : {}),
};

export default nextConfig;
