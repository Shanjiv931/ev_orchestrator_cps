import { motion, type HTMLMotionProps } from "framer-motion";
import clsx from "clsx";

type Variant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends HTMLMotionProps<"button"> {
  variant?: Variant;
  fullWidth?: boolean;
}

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    "bg-black text-white border border-white/15 shadow-[0_1px_2px_rgba(0,0,0,0.5)] hover:bg-[#151515] hover:border-white/25 hover:shadow-[0_4px_12px_-4px_rgba(0,0,0,0.6)]",
  secondary:
    "bg-[#151515] text-slate-200 border border-white/10 hover:bg-[#1a1a1a] hover:border-white/20",
  ghost: "bg-transparent text-white border border-transparent hover:bg-white/5",
  danger: "bg-red-900/30 text-red-300 border border-red-500/25 hover:bg-red-900/50 hover:border-red-500/40",
};

export function Button({ variant = "primary", fullWidth = false, className, children, disabled, ...props }: ButtonProps) {
  return (
    <motion.button
      whileHover={disabled ? undefined : { y: -1 }}
      whileTap={disabled ? undefined : { scale: 0.98 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      disabled={disabled}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold",
        "transition-all duration-200 min-h-11 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50 focus-visible:ring-offset-2 focus-visible:ring-offset-black",
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
