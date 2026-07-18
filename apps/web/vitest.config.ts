import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"
import path from "node:path"

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    // Auto-restore vi.stubGlobal() after each test so a stubbed (or rejecting)
    // global like `fetch` can't leak across test files — restoreAllMocks() alone
    // does not undo stubGlobal.
    unstubGlobals: true,
    // jsdom environment setup can exceed the 5s default for the first test in a
    // file when many files run in parallel under machine load (or in CI). Give it
    // headroom so env-setup contention doesn't manifest as spurious timeouts.
    testTimeout: 15000,
    hookTimeout: 15000,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
