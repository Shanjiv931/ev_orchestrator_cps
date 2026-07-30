import { motion, type HTMLMotionProps } from "framer-motion";
import clsx from "clsx";

interface GlassCardProps extends HTMLMotionProps<"div"> {
  hoverLift?: boolean;
  glow?: "brand" | "electric" | "none";
}

export function GlassCard({ className, hoverLift = false, glow = "none", children, ...props }: GlassCardProps) {
  return (
    <motion.div
      className={clsx(
        "glass-panel rounded-2xl p-4",
        glow === "brand" && "shadow-[0_0_32px_-8px_rgba(16,185,129,0.35)]",
        glow === "electric" && "shadow-[0_0_32px_-8px_rgba(34,211,238,0.35)]",
        className,
      )}
      whileHover={hoverLift ? { y: -4, borderColor: "rgba(16,185,129,0.4)" } : undefined}
      transition={{ duration: 0.2, ease: "easeOut" }}
      {...props}
    >
      {children}
    </motion.div>
  );
}
