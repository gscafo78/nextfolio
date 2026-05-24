import { forwardRef, InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({ label, error, ...props }, ref) => (
  <div className="flex flex-col gap-1">
    {label && (
      <label className="text-sm font-medium text-gray-700">{label}</label>
    )}
    <input
      ref={ref}
      className={`px-3 py-2 border rounded-lg text-sm outline-none transition-colors focus:ring-2 focus:ring-brand-500 focus:border-transparent ${
        error ? "border-red-400 bg-red-50" : "border-gray-300 bg-white"
      }`}
      {...props}
    />
    {error && <p className="text-xs text-red-600">{error}</p>}
  </div>
));

Input.displayName = "Input";
