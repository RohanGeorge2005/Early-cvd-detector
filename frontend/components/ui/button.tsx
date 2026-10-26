import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";
export function Button({ className, variant = "primary", children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; children: ReactNode }) {
  return <button className={cn("button", `button-${variant}`, className)} {...props}>{children}</button>;
}
