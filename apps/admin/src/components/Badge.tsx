import type { ReactNode } from "react";

type Variant = "neutral" | "success" | "warning" | "danger" | "info" | "sidebar";

type Props = {
  variant?: Variant;
  children: ReactNode;
  className?: string;
};

export default function Badge({ variant = "neutral", children, className }: Props) {
  return <span className={`badge ${variant}${className ? ` ${className}` : ""}`}>{children}</span>;
}
