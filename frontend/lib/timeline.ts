import type { Confidence, TimelineEvent } from "@/lib/types";

type TimelineEventType =
  | "runtime_init"
  | "repository_scan"
  | "semantic_index"
  | "graph_build"
  | "memory_persist"
  | "analysis_complete";

type TimelineCopy = {
  agent: string;
  title: string;
  detail: string;
};

const fallbackCopy: TimelineCopy = {
  agent: "Repository workflow",
  title: "Processing repository event",
  detail: "Repository analysis is streaming this step.",
};

const eventTypeCopy: Record<TimelineEventType, TimelineCopy> = {
  runtime_init: {
    agent: "Runtime",
    title: "Runtime initialized",
    detail: "Loading workflow instructions, tools, skills, and repository analysis agents.",
  },
  repository_scan: {
    agent: "Repository scan",
    title: "Repository scan in progress",
    detail: "Scanning files, folders, manifests, framework signals, and entry points.",
  },
  semantic_index: {
    agent: "Semantic index",
    title: "Semantic index in progress",
    detail: "Extracting symbols, routes, runtime roles, and grounded memory items.",
  },
  graph_build: {
    agent: "Architecture graph",
    title: "Architecture graph in progress",
    detail: "Building architecture boundaries, dependency relationships, and runtime flow.",
  },
  memory_persist: {
    agent: "Repository memory",
    title: "Repository memory updating",
    detail: "Persisting compact repository facts, architecture notes, and timeline context.",
  },
  analysis_complete: {
    agent: "Analysis",
    title: "Repository analysis complete",
    detail: "Repository summary, architecture map, contributor plan, and memory payload are ready.",
  },
};

const validStatuses = new Set<TimelineEvent["status"]>(["queued", "running", "completed", "failed"]);
const validConfidence = new Set<Confidence>(["low", "medium", "high"]);
const internalKeyPattern = /^(codesherpa|gitagent|runtime)[_-][a-z0-9_-]*_?$/i;
const partialInternalPattern = /(?:^|[_-])runtime[_-]?$/i;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function isRawInternalKey(value: string) {
  if (!value) return false;
  const compact = value.trim();
  return internalKeyPattern.test(compact) || partialInternalPattern.test(compact) || compact === "codesherpa.runtime";
}

function safeText(value: unknown) {
  const text = stringValue(value);
  if (!text || isRawInternalKey(text)) return null;
  return text;
}

function safeStatus(value: unknown): TimelineEvent["status"] {
  const status = stringValue(value).toLowerCase() as TimelineEvent["status"];
  return validStatuses.has(status) ? status : "running";
}

function safeConfidence(value: unknown): Confidence {
  const confidence = stringValue(value).toLowerCase() as Confidence;
  return validConfidence.has(confidence) ? confidence : "medium";
}

function safeTimestamp(value: unknown) {
  const date =
    value instanceof Date
      ? value
      : typeof value === "number" || typeof value === "string"
        ? new Date(value)
        : new Date();
  return Number.isNaN(date.getTime()) ? new Date().toISOString() : date.toISOString();
}

function candidateEventType(value: string): TimelineEventType | null {
  const normalized = value.toLowerCase().replace(/^codesherpa[_-]?runtime[_-]?/, "").replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  if (!normalized) return null;
  if (normalized.includes("runtime") || normalized.includes("initialized") || normalized.includes("init")) return "runtime_init";
  if (normalized.includes("repository") || normalized.includes("scan") || normalized.includes("clone") || normalized.includes("framework")) return "repository_scan";
  if (normalized.includes("semantic") || normalized.includes("symbol") || normalized.includes("index")) return "semantic_index";
  if (normalized.includes("graph") || normalized.includes("architecture") || normalized.includes("boundary")) return "graph_build";
  if (normalized.includes("memory") || normalized.includes("persist") || normalized.includes("cache")) return "memory_persist";
  if (normalized.includes("complete") || normalized.includes("ready") || normalized.includes("finished")) return "analysis_complete";
  return null;
}

function readEventType(payload: Record<string, unknown>): TimelineEventType | null {
  const metadata = isRecord(payload.metadata) ? payload.metadata : {};
  const candidates = [
    payload.event_type,
    payload.type,
    payload.kind,
    payload.stage,
    metadata.event_type,
    metadata.type,
    metadata.kind,
    metadata.stage,
    payload.id,
    payload.title,
    payload.agent,
  ];
  for (const candidate of candidates) {
    const text = stringValue(candidate);
    if (!text) continue;
    const type = candidateEventType(text);
    if (type) return type;
  }
  return null;
}

function hasExplicitEventType(payload: Record<string, unknown>) {
  const metadata = isRecord(payload.metadata) ? payload.metadata : {};
  return [payload.event_type, payload.type, payload.kind, payload.stage, metadata.event_type, metadata.type, metadata.kind, metadata.stage].some(
    (candidate) => Boolean(stringValue(candidate)),
  );
}

export function normalizeTimelineEvent(payload: unknown, index = 0): TimelineEvent | null {
  if (!isRecord(payload)) return null;

  const eventType = readEventType(payload);
  const explicitUnknownType = !eventType && hasExplicitEventType(payload);
  const copy = eventType ? eventTypeCopy[eventType] : fallbackCopy;
  const metadata = isRecord(payload.metadata) ? payload.metadata : {};
  const rawId = stringValue(payload.id);
  const rawTitle = stringValue(payload.title);
  const rawAgent = stringValue(payload.agent);
  const rawDetail = stringValue(payload.detail);
  const incompleteRuntimePayload = [rawId, rawTitle, rawAgent, rawDetail].some(isRawInternalKey) && !safeText(payload.title) && !safeText(payload.detail);
  const status = safeStatus(payload.status);

  return {
    id: rawId || `timeline-${eventType ?? "event"}-${index}`,
    timestamp: safeTimestamp(payload.timestamp),
    agent: explicitUnknownType ? fallbackCopy.agent : safeText(payload.agent) ?? copy.agent,
    title: explicitUnknownType ? fallbackCopy.title : safeText(payload.title) ?? copy.title,
    detail: explicitUnknownType ? fallbackCopy.detail : safeText(payload.detail) ?? copy.detail,
    status,
    confidence: safeConfidence(payload.confidence),
    metadata: {
      ...metadata,
      event_type: eventType ?? "unknown",
      __timeline_streaming: status === "running" || incompleteRuntimePayload,
    },
  };
}

export function normalizeTimelineEvents(events: unknown): TimelineEvent[] {
  return (Array.isArray(events) ? events : [])
    .map((event, index) => normalizeTimelineEvent(event, index))
    .filter((event): event is TimelineEvent => Boolean(event));
}
