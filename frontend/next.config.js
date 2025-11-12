/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    domains: ['images.unsplash.com'],
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
  // No rewrites - all components use NEXT_PUBLIC_API_URL directly
  // For local development, set NEXT_PUBLIC_API_URL=http://localhost:8000
}

module.exports = nextConfig 