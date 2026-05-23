import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "animate-shimmer rounded-lg bg-[linear-gradient(90deg,rgba(255,255,255,0.06)_0%,rgba(255,255,255,0.12)_50%,rgba(255,255,255,0.06)_100%)] bg-[length:400px_100%]",
        className,
      )}
      {...props}
    />
  );
}

export { Skeleton };
