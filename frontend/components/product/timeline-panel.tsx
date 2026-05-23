"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  Check,
  CircleDotDashed,
  Cpu,
  Loader2,
  Radio,
  ShieldCheck,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { TimelineEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

const statusIcon = {
  queued: CircleDotDashed,
  running: Loader2,
  completed: Check,
  failed: ShieldCheck,
};

export function TimelinePanel({
  events,
  compact = false,
}: {
  events: TimelineEvent[];
  compact?: boolean;
}) {
  const latest = events[events.length - 1];

  return (
    <section className="glass-panel overflow-hidden rounded-lg">
      <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-teal-300/20 bg-teal-300/10">
            <Radio className="h-4 w-4 text-teal-200" />
          </div>

          <div>
            <h2 className="text-sm font-semibold text-white">
              AI Agent Timeline
            </h2>

            <p className="text-xs text-white/[0.48]">
              {latest
                ? latest.title
                : "Awaiting repository signal"}
            </p>
          </div>
        </div>

        <Badge
          variant={
            latest?.status === "running"
              ? "amber"
              : "default"
          }
        >
          {latest?.status === "running"
            ? "streaming"
            : "ready"}
        </Badge>
      </div>

      <div
        className={cn(
          "timeline-mask max-h-[560px] overflow-hidden px-5 py-4",
          compact && "max-h-[360px]"
        )}
      >
        <div className="relative space-y-4">
          <div className="absolute left-[15px] top-3 h-full w-px bg-gradient-to-b from-teal-300/70 via-white/[0.14] to-transparent" />

          <AnimatePresence initial={false}>
            {events.map((event, index) => {
              const Icon = statusIcon[event.status] ?? Cpu;

              return (
                <motion.div
                  key={`${event.id}-${index}`}
                  initial={{
                    opacity: 0,
                    y: 18,
                    filter: "blur(6px)",
                  }}
                  animate={{
                    opacity: 1,
                    y: 0,
                    filter: "blur(0px)",
                  }}
                  exit={{
                    opacity: 0,
                    y: -8,
                  }}
                  transition={{
                    duration: 0.35,
                    ease: "easeOut",
                  }}
                  className="relative flex gap-4"
                >
                  <div
                    className={cn(
                      "z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border bg-black",
                      event.status === "running"
                        ? "border-amber-300/30 text-amber-200 shadow-[0_0_20px_rgba(245,158,11,0.2)]"
                        : "border-teal-300/25 text-teal-200"
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-4 w-4",
                        event.status === "running" &&
                          "animate-spin"
                      )}
                    />
                  </div>

                  <div className="min-w-0 flex-1 rounded-lg border border-white/[0.08] bg-black/[0.24] px-4 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="font-mono text-xs uppercase tracking-[0.16em] text-white/[0.38]">
                        {event.agent}
                      </div>

                      <span
                        suppressHydrationWarning
                        className="font-mono text-[11px] text-white/[0.34]"
                      >
                        {typeof window !== "undefined"
                          ? new Date(
                              event.timestamp
                            ).toLocaleTimeString()
                          : ""}
                      </span>
                    </div>

                    <div className="mt-1 flex items-center gap-2">
                      <h3 className="truncate text-sm font-medium text-white">
                        {event.title}
                      </h3>

                      {event.status === "running" ? (
                        <span className="h-2 w-2 rounded-full bg-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.8)]" />
                      ) : null}
                    </div>

                    <p className="mt-1 line-clamp-2 text-sm leading-6 text-white/[0.58]">
                      {event.detail}
                    </p>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>

          {events.length === 0 ? (
            <div className="rounded-lg border border-dashed border-white/[0.12] bg-white/[0.03] p-6 text-sm text-white/[0.48]">
              <span className="font-mono text-teal-200">
                codesherpa.runtime
              </span>

              <span className="animate-cursor">_</span>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}