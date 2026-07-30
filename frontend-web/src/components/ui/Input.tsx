import { forwardRef, type InputHTMLAttributes, type SelectHTMLAttributes } from "react";
import clsx from "clsx";

const fieldClasses =
  "w-full rounded-xl bg-white/5 border border-white/10 px-3.5 py-2.5 text-sm text-slate-100 " +
  "placeholder:text-slate-500 outline-none transition-colors duration-150 " +
  "focus:border-emerald-400/60 focus:bg-white/[0.07] focus-visible:ring-2 focus-visible:ring-emerald-400/40";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => <input ref={ref} className={clsx(fieldClasses, className)} {...props} />,
);
Input.displayName = "Input";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <select ref={ref} className={clsx(fieldClasses, "cursor-pointer", className)} {...props}>
      {children}
    </select>
  ),
);
Select.displayName = "Select";

export function FieldLabel({ children }: { children: React.ReactNode }) {
  return <label className="text-xs font-medium text-slate-400 mb-1 block">{children}</label>;
}
