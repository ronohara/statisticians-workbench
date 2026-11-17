"use client";

import { useEffect, useRef } from "react";

/**
 * The fixed strip at the top of the viewport that the indicator banners render
 * into — the demo banner and the example-user banner.
 *
 * They used to be two independently `fixed top-0` elements, so when both were
 * visible (a demo system signs you in as an example user) the higher z-index won
 * and the other was hidden behind it. Here they are siblings in a column, so they
 * stack in DOM order instead.
 *
 * The strip also publishes its own height as `--banner-stack-h`, so the shell can
 * offset its content by the space actually taken rather than guessing: the
 * previous scheme offset by 24px on desktop whatever was showing, which two
 * stacked banners would have overrun. The variable is 0px when nothing renders.
 *
 * The container itself is inert — `pointer-events-none` — so the empty strip
 * never swallows a click in the page beneath; each banner re-enables pointer
 * events for itself.
 */
export default function BannerStack({ children }: { children: React.ReactNode }) {
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const el = ref.current;
        if (!el) return;
        const root = document.documentElement;
        const publish = () => {
            root.style.setProperty("--banner-stack-h", `${el.offsetHeight}px`);
        };
        publish();
        const observer = new ResizeObserver(publish);
        observer.observe(el);
        return () => {
            observer.disconnect();
            root.style.removeProperty("--banner-stack-h");
        };
    }, []);

    return (
        <div
            ref={ref}
            className="fixed top-0 start-0 end-0 z-[9999] flex flex-col pointer-events-none"
        >
            {children}
        </div>
    );
}
