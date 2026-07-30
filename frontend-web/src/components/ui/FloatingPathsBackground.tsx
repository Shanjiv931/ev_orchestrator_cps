import type { ReactNode } from "react";
import { motion } from "framer-motion";
import clsx from "clsx";

// Adapted from a shadcn-style snippet that imported "motion/react" and a
// shadcn cn() helper from "@/lib/utils" - neither exists in this project.
// This app already uses framer-motion everywhere (same team, same API for
// the handful of props used here) rather than the newer "motion" package,
// and clsx directly rather than a cn()/tailwind-merge wrapper, matching
// every other component in src/components/ui/ - so this reuses those
// instead of adding two more dependencies for one component.
export function FloatingPathsBackground({
  position,
  children,
  className,
}: {
  position: number;
  className?: string;
  children?: ReactNode;
}) {
  const paths = Array.from({ length: 36 }, (_, i) => ({
    id: i,
    d: `M-${380 - i * 5 * position} -${189 + i * 6}C-${
      380 - i * 5 * position
    } -${189 + i * 6} -${312 - i * 5 * position} ${216 - i * 6} ${
      152 - i * 5 * position
    } ${343 - i * 6}C${616 - i * 5 * position} ${470 - i * 6} ${
      684 - i * 5 * position
    } ${875 - i * 6} ${684 - i * 5 * position} ${875 - i * 6}`,
    width: 0.5 + i * 0.03,
  }));

  return (
    <div className={clsx("w-full relative", className)}>
      <div className="absolute inset-0 pointer-events-none">
        {/* this app is always-dark (no light/dark toggle - see index.css),
            so the original's "text-slate-950 dark:text-white" is dropped
            in favor of a fixed low-opacity white that reads correctly
            against the app's own #05070D background unconditionally */}
        <svg className="w-full h-full text-white" viewBox="0 0 696 316" fill="none">
          {paths.map((path) => (
            <motion.path
              key={path.id}
              d={path.d}
              stroke="currentColor"
              strokeWidth={path.width}
              strokeOpacity={0.1 + path.id * 0.03}
              initial={{ pathLength: 0.3, opacity: 0.6 }}
              animate={{
                pathLength: 1,
                opacity: [0.3, 0.6, 0.3],
                pathOffset: [0, 1, 0],
              }}
              transition={{
                duration: 20 + Math.random() * 10,
                repeat: Infinity,
                ease: "linear",
              }}
            />
          ))}
        </svg>
      </div>
      {children}
    </div>
  );
}
