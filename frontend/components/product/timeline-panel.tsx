"use client";

import { useMemo } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  BrainCircuit,
  Check,
  CircleDotDashed,
  Cpu,
  Database,
  FileSearch,
  Loader2,
  Network,
  Radio,
  ShieldCheck,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { normalizeTimelineEvents } from "@/lib/timeline";
import type { TimelineEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

const statusIcon = {
  queued: CircleDotDashed,
  running: Loader2,
  completed: Check,
  failed: ShieldCheck,
};

const statusLabel: Record<TimelineEvent["status"], string> = {
  queued: "queued",
  running: "streaming",
  completed: "complete",
  failed: "needs attention",
};

type TimelineLayout = "feed" | "console";

type EventVisual = {
  Icon: LucideIcon;
  label: string;
  iconClass: string;
  markerClass: string;
  cardClass: string;
};

const eventVisuals: Record<string, EventVisual> = {
  runtime_init: {
    Icon: Cpu,
    label: "runtime",
    iconClass: "border-cyan-300/22 bg-cyan-300/10 text-cyan-100",
    markerClass: "bg-cyan-300/70",
    cardClass: "hover:border-cyan-200/18",
  },
  repository_scan: {
    Icon: FileSearch,
    label: "analyzing",
    iconClass: "border-sky-300/22 bg-sky-300/10 text-sky-100",
    markerClass: "bg-sky-300/70",
    cardClass: "hover:border-sky-200/18",
  },
  semantic_index: {
    Icon: BrainCircuit,
    label: "indexing",
    iconClass: "border-violet-300/22 bg-violet-300/10 text-violet-100",
    markerClass: "bg-violet-300/70",
    cardClass: "hover:border-violet-200/18",
  },
  graph_build: {
    Icon: Network,
    label: "graph",
    iconClass: "border-teal-300/22 bg-teal-300/10 text-teal-100",
    markerClass: "bg-teal-300/70",
    cardClass: "hover:border-teal-200/18",
  },
  memory_persist: {
    Icon: Database,
    label: "memory",
    iconClass: "border-emerald-300/22 bg-emerald-300/10 text-emerald-100",
    markerClass: "bg-emerald-300/70",
    cardClass: "hover:border-emerald-200/18",
  },
  analysis_complete: {
    Icon: Sparkles,
    label: "complete",
    iconClass: "border-amber-300/22 bg-amber-300/10 text-amber-100",
    markerClass: "bg-amber-300/70",
    cardClass: "hover:border-amber-200/18",
  },
  unknown: {
    Icon: Activity,
    label: "workflow",
    iconClass: "border-white/[0.12] bg-white/[0.06] text-white/[0.72]",
    markerClass: "bg-white/40",
    cardClass: "hover:border-white/[0.14]",
  },
};

const stateClass: Record<TimelineEvent["status"], string> = {
  queued: "border-white/[0.08] bg-white/[0.04] text-white/[0.44]",
  running: "border-amber-300/18 bg-amber-300/10 text-amber-100",
  completed: "border-teal-300/16 bg-teal-300/8 text-teal-100",
  failed: "border-red-300/20 bg-red-300/10 text-red-100",
};

function formatTime(timestamp: string) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function eventType(event: TimelineEvent) {
  const type = event.metadata?.event_type;
  return typeof type === "string" && type in eventVisuals ? type : "unknown";
}

function visualForEvent(event: TimelineEvent) {
  if (event.status === "failed") {
    return {
      ...eventVisuals.unknown,
      Icon: ShieldCheck,
      label: "attention",
      iconClass: "border-red-300/24 bg-red-300/10 text-red-100",
      markerClass: "bg-red-300/70",
      cardClass: "hover:border-red-200/18",
    };
  }
  return eventVisuals[eventType(event)] ?? eventVisuals.unknown;
}

function visualLabel(event: TimelineEvent, visual: EventVisual) {
  if (eventType(event) === "memory_persist" && /cache|restored|reused/i.test(`${event.title} ${event.detail}`)) {
    return "memory restored";
  }
  return visual.label;
}

function TimelineSkeletonCard({ compact = false }: { compact?: boolean }) {
  return (
    <div className="relative">
      <Skeleton className="absolute left-0 top-3 h-2 w-2 rounded-full" />

      <div className={cn("ml-4 min-w-0 rounded-lg border border-white/[0.08] bg-black/[0.18] px-3 py-3", compact ? "min-h-[88px]" : "min-h-[98px]")}>
        <div className="flex items-center justify-between gap-3">
          <Skeleton className="h-3.5 w-28 rounded" />
          <Skeleton className="h-3.5 w-12 rounded" />
        </div>
        <Skeleton className="mt-3 h-4 w-3/5 rounded" />
        <Skeleton className="mt-2 h-3.5 w-full rounded" />
        {!compact ? <Skeleton className="mt-1.5 h-3.5 w-2/3 rounded" /> : null}
      </div>
    </div>
  );
}

function TimelineEventCard({
  event,
  index,
  compact,
  layout,
}: {
  event: TimelineEvent;
  index: number;
  compact: boolean;
  layout: TimelineLayout;
}) {
  const stateIcon = statusIcon[event.status] ?? Cpu;
  const visual = visualForEvent(event);
  const label = visualLabel(event, visual);
  const Icon = event.status === "running" ? stateIcon : visual.Icon;

  return (
    <motion.div
      key={`${event.id}-${index}`}
      initial={{
        opacity: 0,
        y: 12,
        filter: "blur(5px)",
      }}
      animate={{
        opacity: 1,
        y: 0,
        filter: "blur(0px)",
      }}
      exit={{
        opacity: 0,
        y: -6,
      }}
      transition={{
        duration: 0.28,
        ease: "easeOut",
      }}
      className={cn("relative", layout === "console" && index % 2 === 1 && "lg:translate-y-3")}
    >
      <div className={cn("absolute left-0 top-4 h-2 w-2 rounded-full shadow-[0_0_16px_rgba(255,255,255,0.16)]", visual.markerClass)} />

      <div
        className={cn(
          "ml-4 min-w-0 rounded-lg border border-white/[0.075] bg-black/[0.24] px-3 py-2.5 transition-colors",
          compact ? "min-h-[92px]" : "min-h-[104px]",
          visual.cardClass,
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <span className={cn("flex h-6 w-6 shrink-0 items-center justify-center rounded-md border", visual.iconClass)}>
              <Icon className={cn("h-3.5 w-3.5", event.status === "running" && "animate-spin")} />
            </span>

            <div className="flex min-w-0 flex-wrap items-center gap-1.5">
              <span className="rounded border border-white/[0.07] px-1.5 py-0.5 text-[10px] uppercase leading-none text-white/[0.46]">
                {label}
              </span>
              <span className={cn("rounded border px-1.5 py-0.5 text-[10px] uppercase leading-none", stateClass[event.status])}>
                {statusLabel[event.status]}
              </span>
            </div>
          </div>

          <span suppressHydrationWarning className="shrink-0 pt-1 font-mono text-[10px] text-white/[0.3]">
            {typeof window !== "undefined" ? formatTime(event.timestamp) : ""}
          </span>
        </div>

        <h3 className="mt-2 truncate text-[13px] font-semibold leading-5 text-white">
          {event.title}
        </h3>

        <p className={cn("mt-1 text-xs leading-5 text-white/[0.52]", compact ? "line-clamp-1" : "line-clamp-2")}>
          {event.detail}
        </p>
      </div>
    </motion.div>
  );
}

export function TimelinePanel({
  events,
  compact = false,
  layout = "feed",
}: {
  events: TimelineEvent[];
  compact?: boolean;
  layout?: TimelineLayout;
}) {
  const normalizedEvents = useMemo(() => normalizeTimelineEvents(events), [events]);
  const latest = normalizedEvents[normalizedEvents.length - 1];
  const showStreamingSkeleton = latest?.status === "running" || latest?.metadata?.__timeline_streaming === true;
  const consoleLayout = layout === "console";

  return (
    <section className="glass-panel h-fit min-w-0 overflow-hidden rounded-lg">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-teal-300/18 bg-teal-300/10">
            <Radio className="h-3.5 w-3.5 text-teal-200" />
          </div>

          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-white">AI Agent Timeline</h2>

            <p className="truncate text-xs text-white/[0.48]">
              {latest
                ? latest.title
                : "Awaiting repository signal"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="neutral">{normalizedEvents.length} events</Badge>
          <Badge variant={latest?.status === "running" ? "amber" : "default"}>{latest ? statusLabel[latest.status] : "ready"}</Badge>
        </div>
      </div>

      <div
        className={cn(
          "timeline-mask overflow-y-auto px-4 py-4 [scrollbar-color:rgba(255,255,255,0.16)_transparent] [scrollbar-width:thin]",
          compact ? "max-h-[430px]" : "max-h-[560px]",
          consoleLayout && "max-h-[460px]",
        )}
      >
        <div className="relative">
          <div className={cn("pointer-events-none absolute bottom-4 left-[3px] top-5 w-px bg-gradient-to-b from-teal-300/25 via-white/[0.08] to-transparent", consoleLayout && "lg:hidden")} />

          <div className={cn("grid gap-3", consoleLayout ? "lg:grid-cols-2" : "grid-cols-1")}>
            <AnimatePresence initial={false}>
              {normalizedEvents.map((event, index) => (
                <TimelineEventCard key={`${event.id}-${index}`} event={event} index={index} compact={compact} layout={layout} />
              ))}
            </AnimatePresence>

            {showStreamingSkeleton ? <TimelineSkeletonCard compact={compact} /> : null}

            {normalizedEvents.length === 0 ? (
              <>
                <TimelineSkeletonCard compact={compact} />
                {!compact || consoleLayout ? <TimelineSkeletonCard compact={compact} /> : null}
              </>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}
