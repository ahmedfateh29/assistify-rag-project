import { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-lg border border-[#333333] bg-[#2b2b2b]", className)}>
      {children}
    </div>
  );
}
