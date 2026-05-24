import { demoAnalysis } from "@/lib/demo-data";
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
    return demoAnalysis;
  }
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (!stored) {
    return demoAnalysis;
  }
  try {
    return normalizeAnalysis(JSON.parse(stored) as Partial<AnalysisResult>);
  } catch {
    return demoAnalysis;
  }
}

function normalizeAnalysis(candidate: Partial<AnalysisResult>): AnalysisResult {
  const contributorPlan = {
    ...demoAnalysis.contributor_plan,
    ...candidate.contributor_plan,
    good_first_issues:
      candidate.contributor_plan?.good_first_issues ??
      candidate.intelligence?.good_first_issues ??
      demoAnalysis.contributor_plan.good_first_issues,
    contribution_paths:
      candidate.contributor_plan?.contribution_paths ??
      candidate.intelligence?.contribution_paths ??
      demoAnalysis.contributor_plan.contribution_paths,
  };

  return {
    ...demoAnalysis,
    ...candidate,
    summary: { ...demoAnalysis.summary, ...candidate.summary },
    architecture: { ...demoAnalysis.architecture, ...candidate.architecture },
    contributor_plan: contributorPlan,
    intelligence: {
      ...demoAnalysis.intelligence,
      ...candidate.intelligence,
      good_first_issues:
        candidate.intelligence?.good_first_issues ??
        contributorPlan.good_first_issues ??
        demoAnalysis.intelligence.good_first_issues,
      contribution_paths:
        candidate.intelligence?.contribution_paths ??
        contributorPlan.contribution_paths ??
        demoAnalysis.intelligence.contribution_paths,
    },
    code_intelligence: {
      ...demoAnalysis.code_intelligence,
      ...candidate.code_intelligence,
      auth: { ...demoAnalysis.code_intelligence.auth, ...candidate.code_intelligence?.auth },
      state: { ...demoAnalysis.code_intelligence.state, ...candidate.code_intelligence?.state },
      runtime: { ...demoAnalysis.code_intelligence.runtime, ...candidate.code_intelligence?.runtime },
      deployment: { ...demoAnalysis.code_intelligence.deployment, ...candidate.code_intelligence?.deployment },
      symbols: candidate.code_intelligence?.symbols ?? demoAnalysis.code_intelligence.symbols,
      routes: candidate.code_intelligence?.routes ?? demoAnalysis.code_intelligence.routes,
      semantic_memory: candidate.code_intelligence?.semantic_memory ?? demoAnalysis.code_intelligence.semantic_memory,
      symbol_graph: candidate.code_intelligence?.symbol_graph ?? demoAnalysis.code_intelligence.symbol_graph,
      retrieval_stats: candidate.code_intelligence?.retrieval_stats ?? demoAnalysis.code_intelligence.retrieval_stats,
    },
    timeline: normalizeTimelineEvents(candidate.timeline ?? demoAnalysis.timeline),
    agent_manifest: { ...demoAnalysis.agent_manifest, ...candidate.agent_manifest },
  };
}

export async function analyzeRepository(
  repoUrl: string,
  onTimelineEvent: (event: TimelineEvent) => void,
): Promise<AnalysisResult> {
  if (typeof window !== "undefined" && "EventSource" in window) {
    try {
      return await analyzeWithSse(repoUrl, onTimelineEvent);
    } catch {
      return analyzeWithPost(repoUrl, onTimelineEvent);
    }
  }
  return analyzeWithPost(repoUrl, onTimelineEvent);
}

function analyzeWithSse(repoUrl: string, onTimelineEvent: (event: TimelineEvent) => void) {
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

async function analyzeWithPost(repoUrl: string, onTimelineEvent: (event: TimelineEvent) => void): Promise<AnalysisResult> {
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
  return result;
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
