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
        "glass-panel rounded-2xl p-4 shadow-[0_1px_3px_rgba(0,0,0,0.4)]",
        glow === "brand" && "shadow-[0_0_24px_-10px_rgba(34,197,94,0.35)]",
        glow === "electric" && "shadow-[0_0_24px_-10px_rgba(0,229,255,0.35)]",
        className,
      )}
      whileHover={hoverLift ? { y: -2, borderColor: "rgba(255,255,255,0.18)" } : undefined}
      transition={{ duration: 0.2, ease: "easeOut" }}
      {...props}
    >
      {children}
    </motion.div>
  );
}
