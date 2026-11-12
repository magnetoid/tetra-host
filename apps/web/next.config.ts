import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // scripts/deploy.sh builds into a staging folder and swaps it in only when the build
  // succeeds, so a failed build never takes the running console down.
  distDir: process.env.TETRA_NEXT_DIST_DIR || ".next",
  experimental: {
    // Enables React's <ViewTransition> component so console route changes
    // (and project-tab switches, which are sub-routes) crossfade instead of
    // hard-cutting. Motion is suppressed under prefers-reduced-motion in
    // globals.css. See node_modules/next/dist/docs/.../view-transitions.md.
    viewTransition: true,
  },
};

export default nextConfig;
