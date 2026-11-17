# Known Issues

## Blank screen on browser back/forward navigation
- **Description**: After navigating away from a page and then pressing the browser’s back or forward button, the page may render as blank. The URL updates correctly, but the content does not appear until a manual refresh.
- **Reproducibility**: Intermittent; observed on the `/recipes` page and likely other client‑side rendered pages. May be related to Next.js bfcache and React state persistence.
- **Workaround**: Manually refresh the page (F5 or Ctrl+R) after using back/forward navigation.

## Login page language briefly flashes then reverts to English
- **Description**: When visiting `/login` with a non-English browser language (e.g., Thai), the page briefly renders in the detected language, then flips to English. The lazy initializer in `TranslationProvider` correctly detects the browser language, but a subsequent `useEffect` triggered by NextAuth session status transitions overrides it.
- **Priority**: Low
- **Last investigated**: 2026-07-11 — functional updater added to unauthenticated useEffect branch to preserve lazy-initializer state, but issue persists due to SSR/hydration timing with `useSession()` status transitions.
- **Workaround**: User can manually select their language via the language selector dropdown on the login page.

## Notes
- No other known issues at this time.