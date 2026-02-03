import { cn } from "@/lib/utils";
import { LogoMark } from "./logo-mark";

type LogoLockupProps = {
  size?: number;
  className?: string;
};

export function LogoLockup({ size = 20, className }: LogoLockupProps) {
  return (
    <div className={cn("flex items-center gap-2", className)} aria-label="Tymebox">
      <LogoMark size={size} className="shrink-0" />
      <span className="text-[15px] font-semibold tracking-[0.01em] text-foreground/90">
        <span className="text-primary">Tyme</span>
        <span className="text-foreground">box</span>
      </span>
    </div>
  );
}
