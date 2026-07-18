import type { ReactNode } from "react";
import Skeleton from "./Skeleton";

type Props = {
  label: string;
  value: ReactNode;
  caption?: ReactNode;
  icon?: ReactNode;
  iconTone?: "default" | "success" | "warning";
  progress?: number;
  loading?: boolean;
};

export default function KpiCard({
  label,
  value,
  caption,
  icon,
  iconTone = "default",
  progress,
  loading,
}: Props) {
  if (loading) {
    return (
      <div className="kpi-card">
        <Skeleton height={12} width="50%" />
        <Skeleton height={28} width="40%" style={{ marginTop: 8 }} />
        <Skeleton height={10} width="70%" style={{ marginTop: 8 }} />
      </div>
    );
  }

  return (
    <div className="kpi-card">
      <div className="kpi-top">
        <span className="kpi-label">{label}</span>
        {icon ? <span className={`kpi-icon ${iconTone === "default" ? "" : iconTone}`}>{icon}</span> : null}
      </div>
      <div className="kpi-value">{value}</div>
      {caption ? <div className="kpi-caption">{caption}</div> : null}
      {typeof progress === "number" ? (
        <div className="progress-bar" aria-hidden="true">
          <span style={{ width: `${Math.max(0, Math.min(100, progress * 100))}%` }} />
        </div>
      ) : null}
    </div>
  );
}
