import { emptyAnalysis } from "@/lib/demo-data";
import { normalizeTimelineEvent, normalizeTimelineEvents } from "@/lib/timeline";
import type { AnalysisResult, ChatResponse, TimelineEvent } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const STORAGE_KEY = "codesherpa:last-analysis";

export function saveAnalysis(result: AnalysisResult) {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(result));
  }
}

export function loadAnalysis(): AnalysisResult {
  if (typeof window === "undefined") {
    return emptyAnalysis;
  }
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (!stored) {
    return emptyAnalysis;
  }
  try {
    const parsed = JSON.parse(stored) as Partial<AnalysisResult>;
    if (parsed.repo_id === "demo-codesherpa") {
      return emptyAnalysis;
    }
    return normalizeAnalysis(parsed);
  } catch {
    return emptyAnalysis;
  }
}

function normalizeAnalysis(candidate: Partial<AnalysisResult>): AnalysisResult {
  const fallback = emptyAnalysis;
  const contributorPlan = {
    ...fallback.contributor_plan,
    ...candidate.contributor_plan,
    good_first_issues:
      candidate.contributor_plan?.good_first_issues ??
      candidate.intelligence?.good_first_issues ??
      fallback.contributor_plan.good_first_issues,
    contribution_paths:
      candidate.contributor_plan?.contribution_paths ??
      candidate.intelligence?.contribution_paths ??
      fallback.contributor_plan.contribution_paths,
  };

  return {
    ...fallback,
    ...candidate,
    summary: { ...fallback.summary, ...candidate.summary },
    architecture: { ...fallback.architecture, ...candidate.architecture },
    contributor_plan: contributorPlan,
    intelligence: {
      ...fallback.intelligence,
      ...candidate.intelligence,
      good_first_issues:
        candidate.intelligence?.good_first_issues ??
        contributorPlan.good_first_issues ??
        fallback.intelligence.good_first_issues,
      contribution_paths:
        candidate.intelligence?.contribution_paths ??
        contributorPlan.contribution_paths ??
        fallback.intelligence.contribution_paths,
    },
    code_intelligence: {
      ...fallback.code_intelligence,
      ...candidate.code_intelligence,
      auth: { ...fallback.code_intelligence.auth, ...candidate.code_intelligence?.auth },
      state: { ...fallback.code_intelligence.state, ...candidate.code_intelligence?.state },
      runtime: { ...fallback.code_intelligence.runtime, ...candidate.code_intelligence?.runtime },
      deployment: { ...fallback.code_intelligence.deployment, ...candidate.code_intelligence?.deployment },
      symbols: candidate.code_intelligence?.symbols ?? fallback.code_intelligence.symbols,
      routes: candidate.code_intelligence?.routes ?? fallback.code_intelligence.routes,
      semantic_memory: candidate.code_intelligence?.semantic_memory ?? fallback.code_intelligence.semantic_memory,
      symbol_graph: candidate.code_intelligence?.symbol_graph ?? fallback.code_intelligence.symbol_graph,
      retrieval_stats: candidate.code_intelligence?.retrieval_stats ?? fallback.code_intelligence.retrieval_stats,
    },
    timeline: normalizeTimelineEvents(candidate.timeline ?? fallback.timeline),
    agent_manifest: {
      ...fallback.agent_manifest,
      ...candidate.agent_manifest,
      workflow: {
        ...fallback.agent_manifest.workflow,
        ...candidate.agent_manifest?.workflow,
      },
    },
  };
}

export async function analyzeRepository(
  repoUrl: string,
  onTimelineEvent: (event: TimelineEvent) => void,
  onAnalysisUpdate?: (result: AnalysisResult, stage: string) => void,
): Promise<AnalysisResult> {
  if (typeof window !== "undefined" && "EventSource" in window) {
    try {
      return await analyzeWithSse(repoUrl, onTimelineEvent, onAnalysisUpdate);
    } catch {
      return analyzeWithPost(repoUrl, onTimelineEvent, onAnalysisUpdate);
    }
  }
  return analyzeWithPost(repoUrl, onTimelineEvent, onAnalysisUpdate);
}

function analyzeWithSse(repoUrl: string, onTimelineEvent: (event: TimelineEvent) => void, onAnalysisUpdate?: (result: AnalysisResult, stage: string) => void) {
  return new Promise<AnalysisResult>((resolve, reject) => {
    const source = new EventSource(`${API_URL}/timeline/stream?repo_url=${encodeURIComponent(repoUrl)}&use_cache=true`);
    const timeout = window.setTimeout(() => {
      source.close();
      reject(new Error("Timeline stream timed out"));
    }, 120000);

    source.addEventListener("timeline", (event) => {
      try {
        const normalized = normalizeTimelineEvent(JSON.parse((event as MessageEvent).data));
        if (normalized) onTimelineEvent(normalized);
      } catch {
        const normalized = normalizeTimelineEvent({ status: "running", metadata: { event_type: "unknown" } });
        if (normalized) onTimelineEvent(normalized);
      }
    });

    source.addEventListener("analysis", (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent).data) as { stage?: string; result?: Partial<AnalysisResult> };
        if (!payload.result) return;
        const result = normalizeAnalysis(payload.result);
        saveAnalysis(result);
        onAnalysisUpdate?.(result, payload.stage ?? analysisPhase(result));
      } catch {
        // Timeline streaming continues even if a partial result is malformed.
      }
    });

    source.addEventListener("complete", (event) => {
      window.clearTimeout(timeout);
      source.close();
      try {
        const result = normalizeAnalysis(JSON.parse((event as MessageEvent).data) as Partial<AnalysisResult>);
        saveAnalysis(result);
        resolve(result);
      } catch (cause) {
        reject(cause);
      }
    });

    source.addEventListener("error", (event) => {
      window.clearTimeout(timeout);
      source.close();
      reject(event);
    });
  });
}

async function analyzeWithPost(repoUrl: string, onTimelineEvent: (event: TimelineEvent) => void, onAnalysisUpdate?: (result: AnalysisResult, stage: string) => void): Promise<AnalysisResult> {
  const synthetic = [
    "Repository Analysis Agent initialized",
    "Cloning repository",
    "Detecting frameworks",
    "Mapping architecture",
    "Generating onboarding guide",
  ];
  synthetic.forEach((title, index) => {
    window.setTimeout(() => {
      onTimelineEvent({
        id: `local-${index}`,
        timestamp: new Date().toISOString(),
        agent: index < 3 ? "Repository Analysis Agent" : "Architecture Mapping Agent",
        title,
        detail: "Waiting for backend analysis response.",
        status: "running",
        confidence: "medium",
      });
    }, index * 450);
  });

  const response = await fetch(`${API_URL}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_url: repoUrl, use_cache: true }),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  const result = normalizeAnalysis((await response.json()) as Partial<AnalysisResult>);
  saveAnalysis(result);
  onAnalysisUpdate?.(result, "complete");
  return result;
}

export function normalizeRepositoryUrl(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (/^github\.com\//i.test(trimmed)) return `https://${trimmed}`;
  return trimmed;
}

export function analysisPhase(result: AnalysisResult) {
  const phase = result.agent_manifest?.workflow?.analysis_phase;
  return typeof phase === "string" ? phase : "complete";
}

export function createPendingAnalysis(repoUrl: string): AnalysisResult {
  const normalized = normalizeRepositoryUrl(repoUrl);
  const name = repositoryName(normalized);
  const timestamp = new Date().toISOString();
  return normalizeAnalysis({
    ...emptyAnalysis,
    repo_id: "analysis-starting",
    repo_url: normalized,
    analyzed_at: timestamp,
    summary: {
      ...emptyAnalysis.summary,
      repo_id: "analysis-starting",
      repo_url: normalized,
      name,
      description: "Fast repository analysis is starting.",
    },
    architecture: {
      ...emptyAnalysis.architecture,
      summary: "Dashboard shell is live while CodeSherpa scans manifests, roots, routes, and semantic memory.",
      graph_metrics: { analysis_phase: "starting", nodes: 0, edges: 0 },
      topology: { analysis_phase: "starting" },
    },
    intelligence: {
      ...emptyAnalysis.intelligence,
      architecture_brief: "Repository metadata is streaming in.",
      demo_headline: `Analyzing ${name}.`,
    },
    timeline: [
      {
        id: "local-analysis-starting",
        timestamp,
        agent: "Dashboard Runtime",
        title: "Analysis stream opened",
        detail: "Rendering the dashboard shell immediately while repository intelligence streams in.",
        status: "running",
        confidence: "high",
        metadata: { phase: "starting" },
      },
    ],
    agent_manifest: {
      ...emptyAnalysis.agent_manifest,
      workflow: {
        ...emptyAnalysis.agent_manifest.workflow,
        analysis_phase: "starting",
        deep_status: "queued",
      },
    },
  });
}

function repositoryName(repoUrl: string) {
  try {
    const url = new URL(repoUrl);
    const [owner, repo] = url.pathname.replace(/^\/+/, "").replace(/\.git$/, "").split("/");
    return owner && repo ? `${owner}/${repo}` : "Repository analysis";
  } catch {
    const compact = repoUrl.replace(/^https?:\/\//i, "").replace(/^github\.com\//i, "").replace(/\.git$/i, "");
    return compact || "Repository analysis";
  }
}

export async function sendChat(repoId: string, message: string): Promise<ChatResponse> {
  try {
    const response = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_id: repoId, message }),
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return (await response.json()) as ChatResponse;
  } catch {
    const analysis = loadAnalysis();
    return {
      repo_id: repoId,
      answer: `I can answer from the local analysis cache. ${analysis.architecture.summary}\n\nStart with ${analysis.summary.entry_points
        .slice(0, 3)
        .map((file) => `\`${file}\``)
        .join(", ")}.`,
      cited_files: analysis.summary.entry_points.slice(0, 4),
      cited_symbols: analysis.code_intelligence.symbols.slice(0, 4).map((symbol) => symbol.id),
      cited_routes: analysis.code_intelligence.routes.slice(0, 4).map((route) => `${route.method} ${route.path}`),
      context_items: analysis.code_intelligence.semantic_memory.slice(0, 4),
      confidence: "medium",
      remembered: false,
    };
  }
}
