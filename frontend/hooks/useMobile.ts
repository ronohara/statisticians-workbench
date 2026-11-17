"use client";

import { useState, useEffect } from "react";

/**
 * Returns true when the viewport width is below the given breakpoint (default 768px).
 * Handles SSR by initializing to false and updating on mount.
 */
export function useMobile(breakpoint = 768): boolean {
    const [isMobile, setIsMobile] = useState(false);

    useEffect(() => {
        const check = () => setIsMobile(window.innerWidth < breakpoint);
        check();
        window.addEventListener("resize", check);
        return () => window.removeEventListener("resize", check);
    }, [breakpoint]);

    return isMobile;
}
