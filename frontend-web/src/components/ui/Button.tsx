import { motion, type HTMLMotionProps } from "framer-motion";
import clsx from "clsx";

type Variant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends HTMLMotionProps<"button"> {
  variant?: Variant;
  fullWidth?: boolean;
}

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    "bg-gradient-to-br from-emerald-500 to-emerald-600 text-white shadow-[0_0_24px_-6px_rgba(16,185,129,0.6)] hover:shadow-[0_0_32px_-4px_rgba(16,185,129,0.75)]",
  secondary:
    "bg-cyan-500/10 text-cyan-300 border border-cyan-400/30 hover:bg-cyan-500/20",
  ghost: "bg-white/5 text-slate-200 border border-white/10 hover:bg-white/10",
  danger: "bg-red-500/10 text-red-300 border border-red-400/30 hover:bg-red-500/20",
};

export function Button({ variant = "primary", fullWidth = false, className, children, disabled, ...props }: ButtonProps) {
  return (
    <motion.button
      whileHover={disabled ? undefined : { scale: 1.02 }}
      whileTap={disabled ? undefined : { scale: 0.97 }}
      transition={{ duration: 0.15 }}
      disabled={disabled}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium",
        "transition-colors duration-200 min-h-11 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#05070D]",
        fullWidth && "w-full",
        VARIANT_CLASSES[variant],
        className,
      )}
      {...props}
    >
      {children}
    </motion.button>
  );
}
