import { ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary";
  size?: "sm" | "md";
  loading?: boolean;
}

export function Button({ variant = "primary", size = "md", loading, children, disabled, className = "", ...props }: ButtonProps) {
  const base = "rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center justify-center";
  const sizes = {
    sm: "px-3 py-1.5",
    md: "px-4 py-2",
  };
  const variants = {
    primary: "bg-brand-500 hover:bg-brand-600 text-white",
    secondary: "bg-white dark:bg-slate-800 border border-gray-300 dark:border-slate-600 hover:bg-gray-50 dark:hover:bg-slate-700 text-gray-700 dark:text-slate-200",
  };

  return (
    <button
      className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? "Caricamento..." : children}
    </button>
  );
}
