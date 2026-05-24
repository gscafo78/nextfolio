import { ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary";
  loading?: boolean;
}

export function Button({ variant = "primary", loading, children, disabled, ...props }: ButtonProps) {
  const base = "px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
  const variants = {
    primary: "bg-brand-500 hover:bg-brand-600 text-white",
    secondary: "bg-white border border-gray-300 hover:bg-gray-50 text-gray-700",
  };

  return (
    <button className={`${base} ${variants[variant]} inline-flex items-center justify-center`} disabled={disabled || loading} {...props}>
      {loading ? "Caricamento..." : children}
    </button>
  );
}
