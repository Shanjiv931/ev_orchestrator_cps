import { memo, useMemo, type CSSProperties, type ReactNode } from "react";
import clsx from "clsx";

// Adapted from a shadcn-style snippet that imported "motion/react" and a
// shadcn cn() helper from "@/lib/utils" - neither exists in this project.
//
// The original (and an earlier version of this file) animated each path's
// pathLength/pathOffset via Framer Motion - a JS-driven rAF loop rewriting
// stroke-dasharray/stroke-dashoffset on 36 elements every frame. That
// property forces the browser to repaint, not just recomposite, so it runs
// on the *main* thread - the same thread React uses to render actual page
// content - and can never be truly "independent" of it: on a mid-power
// machine both jobs starved each other, which read as the whole app
// freezing rather than just the background looking choppy.
//
// This version only ever animates `transform` and `opacity`, and only via
// plain CSS @keyframes (see index.css's floating-paths-* rules) - no
// Framer Motion, no JS loop, nothing per-frame for React to even be aware
// of. Both properties can run entirely on the compositor thread, so the
// animation keeps going completely independent of whatever the main
// thread is doing - mounting a page, fetching data, re-rendering after an
// auth action - and vice versa.
export const FloatingPathsBackground = memo(function FloatingPathsBackground({
  position,
  children,
  className,
}: {
  position: number;
  className?: string;
  children?: ReactNode;
}) {
  const paths = useMemo(
    () =>
      Array.from({ length: 36 }, (_, i) => ({
        id: i,
        d: `M-${380 - i * 5 * position} -${189 + i * 6}C-${
          380 - i * 5 * position
        } -${189 + i * 6} -${312 - i * 5 * position} ${216 - i * 6} ${
          152 - i * 5 * position
        } ${343 - i * 6}C${616 - i * 5 * position} ${470 - i * 6} ${
          684 - i * 5 * position
        } ${875 - i * 6} ${684 - i * 5 * position} ${875 - i * 6}`,
        width: 0.5 + i * 0.03,
        opacityMin: 0.1 + i * 0.02,
        opacityMax: 0.25 + i * 0.03,
        duration: 12 + (i % 7) * 2,
        delay: (i % 11) * 0.4,
      })),
    [position],
  );

  return (
    <div className={clsx("w-full relative", className)}>
      <div className="absolute inset-0 pointer-events-none">
        {/* this app is always-dark (no light/dark toggle - see index.css),
            so the original's "text-slate-950 dark:text-white" is dropped
            in favor of a fixed color that reads correctly against the
            app's own #05070D background unconditionally */}
        <svg className="w-full h-full text-white" viewBox="0 0 696 316" fill="none">
          <g className="floating-paths-group">
            {paths.map((path) => (
              <path
                key={path.id}
                className="floating-paths-line"
                d={path.d}
                stroke="currentColor"
                fill="none"
                strokeWidth={path.width}
                style={
                  {
                    "--fp-opacity-min": path.opacityMin,
                    "--fp-opacity-max": path.opacityMax,
                    "--fp-duration": `${path.duration}s`,
                    "--fp-delay": `${path.delay}s`,
                  } as CSSProperties
                }
              />
            ))}
          </g>
        </svg>
      </div>
      {children}
    </div>
  );
});
