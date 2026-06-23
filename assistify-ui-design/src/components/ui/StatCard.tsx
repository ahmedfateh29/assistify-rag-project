import { ReactNode } from "react";
import { Card } from "./Card";

export function StatCard({
  icon,
  label,
  value,
  change,
  colorClass = "text-[#10a37f]",
}: {
  icon?: ReactNode;
  label: string;
  value: string;
  change?: string;
  colorClass?: string;
}) {
  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center justify-between">
        {icon ? <div className={colorClass}>{icon}</div> : <div />}
        {change && <span className="text-xs font-medium text-[#9ca3af]">{change}</span>}
      </div>
      <p className="text-sm text-[#9ca3af]">{label}</p>
      <p className="mt-1 text-2xl font-bold text-[#fafaff]">{value}</p>
    </Card>
  );
}
