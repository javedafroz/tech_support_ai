import type { CSSProperties } from "react";

type Props = {
  width?: string | number;
  height?: string | number;
  style?: CSSProperties;
  className?: string;
};

export default function Skeleton({ width = "100%", height = 16, style, className }: Props) {
  return (
    <div
      className={`skeleton${className ? ` ${className}` : ""}`}
      style={{ width, height, ...style }}
      aria-hidden="true"
    />
  );
}
