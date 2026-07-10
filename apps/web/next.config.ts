import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // Enables React's <ViewTransition> component so console route changes
    // (and project-tab switches, which are sub-routes) crossfade instead of
    // hard-cutting. Motion is suppressed under prefers-reduced-motion in
    // globals.css. See node_modules/next/dist/docs/.../view-transitions.md.
    viewTransition: true,
  },
};

export default nextConfig;
