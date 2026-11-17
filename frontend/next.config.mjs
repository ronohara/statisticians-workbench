/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    serverActions: {
      bodySizeLimit: '50mb',
    },
    // Next.js rewrite proxy defaults to 30s timeout. AI-augmented
    // dbdesign analysis can take 60-250s with large schemas and slow
    // LLM providers. 300s gives 2.5x headroom from 120s baseline.
    proxyTimeout: 300_000,
  },
  allowedDevOrigins: ['x360.sentuny.com'],
  async rewrites() {
    return {
      // beforeFiles: checked BEFORE the filesystem (frontend /api route
      // handlers). This is what lets a rewrite override the frontend handler
      // it is cutting over — the array form (afterFiles) is shadowed by the
      // filesystem route and never fires for any path that still has a
      // handler. proxy.ts (the middleware) still runs first: auth bridge
      // (session -> Bearer) for authenticated /api requests, and the 307
      // login redirect for unauthenticated non-public paths.
      beforeFiles: [
        {
          source: "/api/test",
          destination: "http://127.0.0.1:8000/hello",
        },
        {
          source: "/api/health",
          destination: "http://127.0.0.1:8000/api/health",
        },
        {
          source: "/api/recipes",
          destination: "http://127.0.0.1:8000/api/recipes/",
        },
        {
          source: "/api/recipes/:path*",
          destination: "http://127.0.0.1:8000/api/recipes/:path*",
        },
        {
          source: "/api/groups",
          destination: "http://127.0.0.1:8000/api/groups/",
        },
        {
          source: "/api/groups/:path*",
          destination: "http://127.0.0.1:8000/api/groups/:path*",
        },
        {
          source: "/api/user/audio-presets/:path*",
          destination: "http://127.0.0.1:8000/api/user/audio-presets/:path*",
        },
        {
          source: "/api/features",
          destination: "http://127.0.0.1:8000/api/features",
        },
        {
          source: "/api/licence",
          destination: "http://127.0.0.1:8000/api/licence",
        },
        {
          source: "/api/licence/:path*",
          destination: "http://127.0.0.1:8000/api/licence/:path*",
        },
        {
          source: "/api/access/:path*",
          destination: "http://127.0.0.1:8000/api/access/:path*",
        },
        // ===== P3 G1 — settings (items 3, 7, 10, 11) =====
        {
          source: "/api/public-settings",
          destination: "http://127.0.0.1:8000/api/public-settings",
        },
        {
          source: "/api/global-settings",
          destination: "http://127.0.0.1:8000/api/global-settings",
        },
        {
          source: "/api/user-settings",
          destination: "http://127.0.0.1:8000/api/user-settings",
        },
        {
          source: "/api/user/profile",
          destination: "http://127.0.0.1:8000/api/user/profile",
        },
        {
          source: "/api/admin/global-settings",
          destination: "http://127.0.0.1:8000/api/admin/global-settings",
        },
        // AI tuning has its own endpoints (plan Item 4b of
        // workbench-AI-timeout-policy-plan.html).
        //
        // THESE ARE LISTED INDIVIDUALLY BECAUSE NOTHING ELSE IS A CATCH-ALL. Every
        // route in this file is enumerated by hand — 60 of them — so a new backend
        // path that is not added here never reaches the backend at all: the browser's
        // request 404s inside Next.js and the client receives its HTML 404 page.
        //
        // That is the failure recorded in workbench-AI-models-testing-plan-v2.html
        // (Item 27): "a route verified by curl is not a route the browser can reach."
        // Both endpoints below were verified by curl against :8000 before this line
        // existed, which was correct and insufficient.
        {
          source: "/api/admin/tuning",
          destination: "http://127.0.0.1:8000/api/admin/tuning",
        },
        {
          source: "/api/admin/tuning/reset",
          destination: "http://127.0.0.1:8000/api/admin/tuning/reset",
        },
        // ===== P3 G2 — connections (items 12–19) =====
        {
          source: "/api/ai-providers",
          destination: "http://127.0.0.1:8000/api/ai-providers",
        },
        {
          source: "/api/test-ai",
          destination: "http://127.0.0.1:8000/api/test-ai",
        },
        {
          source: "/api/user/database-connections",
          destination: "http://127.0.0.1:8000/api/user/database-connections",
        },
        {
          source: "/api/user/database-connections/available",
          destination: "http://127.0.0.1:8000/api/user/database-connections/available",
        },
        {
          // Subpaths of the collection — `/probe`, and whatever comes next.
          //
          // These rewrites match EXACTLY, so a path segment not listed here is
          // never forwarded: it reaches Next.js, which has no such handler, and
          // the browser reports a network failure rather than the backend's real
          // answer. Measured 2026-11-06 — `Check now` on the connection page
          // showed "Network error while testing connection" while the backend was
          // answering 200 to the same URL.
          //
          // `:path*` rather than one entry per subpath, for the reason the recipes
          // and groups rewrites already use it: the next subpath then works
          // without anyone remembering this file exists. The exact entries above
          // are checked first, so they still win.
          source: "/api/user/database-connections/:path*",
          destination: "http://127.0.0.1:8000/api/user/database-connections/:path*",
        },
        {
          source: "/api/user/ai-connections",
          destination: "http://127.0.0.1:8000/api/user/ai-connections",
        },
        {
          source: "/api/user/ai-connections/available",
          destination: "http://127.0.0.1:8000/api/user/ai-connections/available",
        },
        {
          source: "/api/user/ai-connections/:connectionId/models",
          destination: "http://127.0.0.1:8000/api/user/ai-connections/:connectionId/models",
        },
        
        {
          // The discovery walk, routed (Item 31). Listed explicitly for the same
          // reason as the test route below: these rewrites are per route, so a
          // backend route absent from this list 404s in the browser while curl
          // against :8000 works — the failure mode that cost a whole debugging
          // session once already.
          source: "/api/user/ai-connections/:connectionId/models/discover",
          destination:
            "http://127.0.0.1:8000/api/user/ai-connections/:connectionId/models/discover",
        },
        {
          // Runs one suitability test (AI model suitability plan, Item 8).
          // The rewrites are explicit per route, so a route added to the
          // backend is NOT reachable from the browser until it is listed here —
          // without this entry every run returned the frontend's own 404.
          source: "/api/user/ai-connections/:connectionId/models/test",
          destination:
            "http://127.0.0.1:8000/api/user/ai-connections/:connectionId/models/test",
        },
        // ===== P3 G3 — datasets + email-pdf (pre-existing port + item 27) =====
        {
          source: "/api/datasets",
          destination: "http://127.0.0.1:8000/api/datasets/",
        },
        {
          source: "/api/datasets/:path*",
          destination: "http://127.0.0.1:8000/api/datasets/:path*",
        },
        {
          source: "/api/dbdesign/email-pdf",
          destination: "http://127.0.0.1:8000/api/dbdesign/email-pdf",
        },
        // ===== P3 G4 — auth (authenticated) (items 8, 9) =====
        {
          source: "/api/user/role",
          destination: "http://127.0.0.1:8000/api/user/role",
        },
        {
          source: "/api/user/change-password",
          destination: "http://127.0.0.1:8000/api/user/change-password",
        },
        {
          source: "/api/auth/change-password",
          destination: "http://127.0.0.1:8000/api/auth/change-password",
        },
        // ===== P3 G5 — admin (items 1, 2, 4, 5, 6) =====
        {
          source: "/api/admin/users",
          destination: "http://127.0.0.1:8000/api/admin/users",
        },
        {
          source: "/api/admin/users/:userId",
          destination: "http://127.0.0.1:8000/api/admin/users/:userId",
        },
        {
          source: "/api/admin/set-password",
          destination: "http://127.0.0.1:8000/api/admin/set-password",
        },
        {
          source: "/api/admin/groups",
          destination: "http://127.0.0.1:8000/api/admin/groups",
        },
        {
          source: "/api/admin/groups/promote",
          destination: "http://127.0.0.1:8000/api/admin/groups/promote",
        },
        {
          source: "/api/admin/groups/shared",
          destination: "http://127.0.0.1:8000/api/admin/groups/shared",
        },
        {
          source: "/api/admin/groups/user",
          destination: "http://127.0.0.1:8000/api/admin/groups/user",
        },
        {
          source: "/api/admin/groups/user/:userId",
          destination: "http://127.0.0.1:8000/api/admin/groups/user/:userId",
        },
        {
          source: "/api/admin/groups/users",
          destination: "http://127.0.0.1:8000/api/admin/groups/users",
        },
        {
          source: "/api/admin/groups/description",
          destination: "http://127.0.0.1:8000/api/admin/groups/description",
        },
        {
          source: "/api/admin/ai-providers",
          destination: "http://127.0.0.1:8000/api/admin/ai-providers",
        },
        {
          source: "/api/admin/models",
          destination: "http://127.0.0.1:8000/api/admin/models",
        },
                        {
          source: "/api/admin/visualization-types",
          destination: "http://127.0.0.1:8000/api/admin/visualization-types",
        },
        {
          source: "/api/admin/visualization-types/:typeId",
          destination: "http://127.0.0.1:8000/api/admin/visualization-types/:typeId",
        },
        // ===== P3 G6 — visualizations (items 25, 26) =====
        {
          source: "/api/visualization-types",
          destination: "http://127.0.0.1:8000/api/visualization-types",
        },
        {
          source: "/api/visualization-types/:slug",
          destination: "http://127.0.0.1:8000/api/visualization-types/:slug",
        },
        {
          source: "/api/visualization-instances",
          destination: "http://127.0.0.1:8000/api/visualization-instances",
        },
        {
          source: "/api/visualization-instances/:id/render",
          destination: "http://127.0.0.1:8000/api/visualization-instances/:id/render",
        },
        {
          source: "/api/visualization-instances/:id",
          destination: "http://127.0.0.1:8000/api/visualization-instances/:id",
        },
        // ===== P3 G7 — languages + translations (items 23, 24) =====
        {
          source: "/api/languages",
          destination: "http://127.0.0.1:8000/api/languages",
        },
        {
          source: "/api/translations",
          destination: "http://127.0.0.1:8000/api/translations",
        },
        // ===== P3 G8 — auth flows (unauthenticated) (items 20, 21, 22) =====
        {
          source: "/api/register",
          destination: "http://127.0.0.1:8000/api/register",
        },
        {
          source: "/api/auth/forgot-password",
          destination: "http://127.0.0.1:8000/api/auth/forgot-password",
        },
        {
          source: "/api/auth/reset-password",
          destination: "http://127.0.0.1:8000/api/auth/reset-password",
        },
        {
          source: "/api/auth/verify-email",
          destination: "http://127.0.0.1:8000/api/auth/verify-email",
        },
        {
          source: "/api/auth/verify-request",
          destination: "http://127.0.0.1:8000/api/auth/verify-request",
        },
        // NOTE: /api/dbdesign/[...path] (SSE streaming) is NOT rewritten — only
        // the exact /api/dbdesign/email-pdf path above cuts over; the remaining
        // dbdesign subpaths stay on the frontend SSE API route.
      ],
    };
  },
  async redirects() {
    return [
      {
        source: "/settings/global",
        destination: "/admin/setup/limits",
        permanent: true,
      },
      {
        source: "/datasets/:id/preparation",
        destination: "/recipes",
        permanent: true,
      },
      {
        source: "/datasets/:id/preparation/:ruleId",
        destination: "/recipes",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
