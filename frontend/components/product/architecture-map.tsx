"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { select, type Selection } from "d3-selection";
import "d3-transition";
import { zoom, zoomIdentity, type ZoomBehavior, type ZoomTransform } from "d3-zoom";
import { motion } from "framer-motion";
import {
  Activity,
  Box,
  Braces,
  ChevronDown,
  ChevronRight,
  Database,
  Eye,
  FileSearch,
  FileText,
  Flame,
  GitBranch,
  GitFork,
  Layers3,
  LocateFixed,
  Network,
  Search,
  Server,
  Shield,
  Sparkles,
  TestTube2,
  Workflow,
  ZoomIn,
  ZoomOut,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ComplexityMeter } from "@/components/product/intelligence-panel";
import { loadAnalysis } from "@/lib/api";
import type { AnalysisResult, ArchitectureEdge, ArchitectureNode } from "@/lib/types";
import { cn } from "@/lib/utils";

type ArchitectureViewMode = "runtime" | "infrastructure" | "dependency" | "ownership" | "file";
type EdgeRouteMode = "orthogonal" | "bundled";
type DetailLevel = "overview" | "standard" | "deep";
type ArchitectureDomain = "frontend" | "shared" | "backend" | "infrastructure" | "manifests";

type GraphNode = ArchitectureNode & {
  parent?: string;
  cluster?: boolean;
  clusterKey?: string;
  clusterChildren?: ArchitectureNode[];
  architectureRoot?: boolean;
  domain?: ArchitectureDomain;
  depth?: number;
  file_count?: number;
  importance: number;
  visualRank: "primary" | "secondary" | "supporting" | "muted";
};

type PositionedNode = GraphNode & {
  x: number;
  y: number;
  width: number;
  height: number;
};

type GraphEdge = ArchitectureEdge & {
  source: string;
  target: string;
  importance: number;
  runtimeCritical: boolean;
  aggregated?: boolean;
  aggregateCount?: number;
};

type PositionedEdge = GraphEdge & {
  sourceNode: PositionedNode;
  targetNode: PositionedNode;
};

type ExpansionNode = {
  id: string;
  label: string;
  type: ArchitectureNode["type"];
  role?: string;
  file_count?: number;
  confidence?: ArchitectureNode["confidence"];
  files?: string[];
  framework?: string | null;
  entrypoint?: boolean;
};

type ExpansionPayload = {
  nodes?: ExpansionNode[];
  edges?: Array<{ source: string; target: string; weight?: number; kind?: string; reasons?: string[]; files?: string[] }>;
  explanation?: string;
};

type DomainDefinition = {
  id: string;
  label: string;
  type: ArchitectureNode["type"];
  role: string;
  description: string;
  group: ArchitectureDomain;
};

const WIDTH = 1540;
const HEIGHT = 820;
const LANE_PADDING = 98;
const MAX_EXPANSION_CHILDREN = 8;
const MAX_QUERY_MATCHES = 12;
const MAX_VISIBLE_NODES = 30;
const MAX_VISIBLE_EDGES = 34;

const modeLabels: Record<ArchitectureViewMode, string> = {
  runtime: "Runtime",
  infrastructure: "Infra",
  dependency: "Deps",
  ownership: "Owners",
  file: "Files",
};

const modeDescriptions: Record<ArchitectureViewMode, string> = {
  runtime: "Request flow, runtime entrypoints, shared boundaries, and deployment targets.",
  infrastructure: "Hosting, CI, manifests, deployment configs, and runtime targets.",
  dependency: "Weighted import and dependency relationships with weak config noise suppressed.",
  ownership: "Team-shaped source domains, hotspots, and contribution boundaries.",
  file: "Progressive folder drilldown for expanded architecture nodes.",
};

const iconByType = {
  frontend: Layers3,
  backend: Server,
  shared: GitFork,
  data: Database,
  infra: Shield,
  docs: FileText,
  tests: TestTube2,
  config: Braces,
  package: Box,
};

const viewIcons = {
  runtime: Workflow,
  infrastructure: Shield,
  dependency: GitBranch,
  ownership: Network,
  file: FileSearch,
};

const domainDefinitions: Record<ArchitectureDomain, DomainDefinition> = {
  frontend: {
    id: "domain:frontend",
    label: "Frontend",
    type: "frontend",
    role: "client and UI boundary",
    description: "Interactive surfaces, client routes, views, and user-facing entrypoints.",
    group: "frontend",
  },
  shared: {
    id: "domain:shared",
    label: "Shared/Core",
    type: "shared",
    role: "shared runtime and reusable core",
    description: "Common libraries, framework code, shared data contracts, docs, and validation surfaces.",
    group: "shared",
  },
  backend: {
    id: "domain:backend",
    label: "Backend/API",
    type: "backend",
    role: "server and API boundary",
    description: "Server runtime, API routes, controllers, services, persistence, and background work.",
    group: "backend",
  },
  infrastructure: {
    id: "domain:infrastructure",
    label: "Infrastructure",
    type: "infra",
    role: "deployment and operations boundary",
    description: "Hosting, CI, containers, release automation, and runtime deployment targets.",
    group: "infrastructure",
  },
  manifests: {
    id: "domain:manifests",
    label: "Manifests",
    type: "config",
    role: "dependency and project manifests",
    description: "Package manifests, lockfiles, build metadata, and workspace configuration evidence.",
    group: "manifests",
  },
};

const laneX: Record<string, number> = {
  frontend: 200,
  shared: 565,
  backend: 930,
  infrastructure: 1280,
  manifests: 1280,
  testing: 565,
  docs: 565,
};

const laneLabels: Array<{ key: string; label: string; x: number; width: number }> = [
  { key: "frontend", label: "Frontend", x: 42, width: 315 },
  { key: "shared", label: "Shared/Core", x: 407, width: 315 },
  { key: "backend", label: "Backend/API", x: 772, width: 315 },
  { key: "infrastructure", label: "Infra/Deploy", x: 1132, width: 350 },
];

function numberFrom(value: unknown, fallback = 0) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function metricValue(metrics: Record<string, unknown> | undefined, key: string) {
  const value = metrics?.[key];
  return typeof value === "number" || typeof value === "string" ? value : "0";
}

function expansionMap(analysis: AnalysisResult): Record<string, ExpansionPayload> {
  const fileGraph = analysis.architecture.file_graph;
  if (!fileGraph || typeof fileGraph !== "object") return {};
  const expansions = (fileGraph as { expansions?: unknown }).expansions;
  return expansions && typeof expansions === "object" ? (expansions as Record<string, ExpansionPayload>) : {};
}

function hotspotMap(analysis: AnalysisResult) {
  const map = new Map<string, number>();
  for (const hotspot of analysis.architecture.hotspots ?? []) {
    const id = hotspot.id;
    const intensity = hotspot.intensity;
    if (typeof id === "string" && typeof intensity === "number") {
      map.set(id, intensity);
    }
  }
  return map;
}

function riskWarnings(analysis: AnalysisResult) {
  const warnings = analysis.architecture.risk_analysis?.warnings;
  return Array.isArray(warnings) ? warnings.filter((warning): warning is Record<string, unknown> => typeof warning === "object" && warning !== null) : [];
}

function edgeTrace(edge: ArchitectureEdge) {
  const traces = edge.metadata?.import_traces;
  return Array.isArray(traces) ? traces.filter((trace): trace is Record<string, unknown> => typeof trace === "object" && trace !== null) : [];
}

function nodeGroup(node: ArchitectureNode, mode: ArchitectureViewMode) {
  const graphNode = node as GraphNode;
  if (graphNode.domain) {
    return graphNode.domain === "manifests" ? "infrastructure" : graphNode.domain;
  }
  if (mode === "infrastructure") {
    if (node.type === "infra" || node.type === "config" || node.id === "deployment") return "infrastructure";
    if (node.type === "backend" || node.type === "data") return "backend";
    if (node.type === "frontend") return "frontend";
    return "shared";
  }
  if (mode === "ownership") return node.group ?? node.type;
  if (node.type === "frontend") return "frontend";
  if (node.type === "backend" || node.type === "data") return "backend";
  if (node.type === "infra" || node.type === "config" || node.id === "deployment") return "infrastructure";
  if (node.type === "tests") return "testing";
  if (node.type === "docs") return "docs";
  return "shared";
}

function domainId(domain: ArchitectureDomain) {
  return domainDefinitions[domain].id;
}

function domainFromId(id: string): ArchitectureDomain | null {
  const match = (Object.keys(domainDefinitions) as ArchitectureDomain[]).find((domain) => domainDefinitions[domain].id === id);
  return match ?? null;
}

function manifestSignal(node: ArchitectureNode) {
  const normalized = `${node.id} ${node.label} ${node.role ?? ""}`.toLowerCase();
  return (
    node.id === "manifest" ||
    node.type === "package" ||
    /(^|\/)(package|pnpm-workspace|requirements|pyproject|poetry|cargo|go\.mod|pom|composer|gemfile|lockfile)/.test(normalized) ||
    normalized.includes("package-lock") ||
    normalized.includes("pnpm-lock") ||
    normalized.includes("yarn.lock")
  );
}

function architectureDomainForNode(node: ArchitectureNode): ArchitectureDomain {
  const normalized = `${node.id} ${node.label} ${node.role ?? ""} ${node.runtime_classification ?? ""}`.toLowerCase();
  if (manifestSignal(node)) return "manifests";
  if (node.type === "backend" || node.type === "data") return "backend";
  if (node.type === "frontend") return "frontend";
  if (node.type === "infra" || node.type === "config" || node.id === "deployment" || /deploy|infra|docker|ci|workflow|vercel|render|railway|terraform/.test(normalized)) return "infrastructure";
  if (/backend|server|api|controller|service|database|worker|queue/.test(normalized)) return "backend";
  if (/frontend|client|ui|view|page|component/.test(normalized)) return "frontend";
  return "shared";
}

function nodeImportance(node: ArchitectureNode, hotspots: Map<string, number>) {
  let score = 1.2;
  const dependencyCount = numberFrom(node.dependency_count);
  const ownership = numberFrom(node.ownership_score);
  const hotspot = hotspots.get(node.id) ?? hotspots.get(node.id.split("/", 1)[0]) ?? 0;
  if (node.entrypoint) score += 5.4;
  if (node.id === "src" || node.id === "app" || node.id === "frontend" || node.id === "backend" || node.id === "root") score += 2.4;
  if (node.id === "deployment") score += 3.6;
  if (node.type === "frontend" || node.type === "backend") score += 3.1;
  if (node.type === "shared" || node.type === "data") score += 2.1;
  if (node.type === "infra") score += 1.2;
  if (node.type === "docs" || node.type === "tests" || node.type === "config") score -= 0.9;
  score += Math.min(4, dependencyCount * 0.32);
  score += Math.min(2.4, ownership * 2);
  score += hotspot * 3.8;
  return Math.max(0.4, score);
}

function visualRank(importance: number): GraphNode["visualRank"] {
  if (importance >= 7.2) return "primary";
  if (importance >= 4.4) return "secondary";
  if (importance >= 2.4) return "supporting";
  return "muted";
}

function nodeSize(node: GraphNode) {
  if (node.architectureRoot) return { width: 230, height: 96 };
  if ((node.depth ?? 0) >= 2) return { width: 172, height: 66 };
  if (node.visualRank === "primary") return { width: 198, height: 90 };
  if (node.visualRank === "secondary") return { width: 184, height: 82 };
  if (node.visualRank === "supporting") return { width: 168, height: 74 };
  return { width: 150, height: 64 };
}

function edgeImportance(edge: ArchitectureEdge, nodesById: Map<string, ArchitectureNode>) {
  const source = nodesById.get(String(edge.source));
  const target = nodesById.get(String(edge.target));
  const kind = edge.kind ?? "dependency";
  let score = 0;
  if (kind === "import") score += 4.2;
  if (kind === "deployment") score += 5.4;
  if (kind === "asset") score += 2.2;
  if (kind === "semantic") score += 2;
  if (kind === "manifest") score += 0.8;
  score += Math.min(5, numberFrom(edge.weight, 1) * 0.78);
  if (edge.confidence === "high") score += 1.2;
  if (edge.confidence === "low") score -= 1.1;
  if (source?.entrypoint || target?.entrypoint) score += 1.6;
  if (source?.type === "frontend" && (target?.type === "backend" || target?.type === "data")) score += 1.7;
  if (source?.type === "frontend" && target?.type === "shared") score += 1.1;
  if (source?.type === "backend" && target?.type === "shared") score += 1.1;
  if (source?.id === "deployment" || target?.id === "deployment" || source?.type === "infra" || target?.type === "infra") score += 1.3;
  return Math.max(0.1, score);
}

function runtimeCriticalEdge(edge: ArchitectureEdge, nodesById: Map<string, ArchitectureNode>) {
  const source = nodesById.get(String(edge.source));
  const target = nodesById.get(String(edge.target));
  if (edge.kind === "deployment") return true;
  if (source?.entrypoint || target?.entrypoint) return true;
  if (source?.type === "frontend" && (target?.type === "backend" || target?.type === "shared")) return true;
  if (source?.type === "backend" && (target?.type === "shared" || target?.type === "data")) return true;
  return false;
}

function edgeAllowedInMode(edge: GraphEdge, mode: ArchitectureViewMode) {
  const kind = edge.kind ?? "dependency";
  const threshold = mode === "runtime" ? 4.1 : mode === "dependency" ? 3.0 : mode === "infrastructure" ? 2.2 : mode === "file" ? 1.4 : 3.4;
  if (mode === "runtime") {
    if (kind === "manifest") return false;
    return edge.runtimeCritical || edge.importance >= threshold;
  }
  if (mode === "infrastructure") return kind === "deployment" || kind === "manifest" || edge.source.includes("cluster:") || edge.target.includes("cluster:") || edge.importance >= 4.2;
  if (mode === "dependency") return kind === "import" || (kind === "semantic" && edge.importance >= 4.2);
  if (mode === "ownership") return edge.importance >= threshold || edge.runtimeCritical;
  return edge.importance >= threshold;
}

function nodeColor(node: GraphNode, active: boolean, matched: boolean) {
  const base =
    node.type === "frontend"
      ? "border-teal-300/28 bg-teal-300/[0.095] text-teal-50"
      : node.type === "backend"
        ? "border-amber-300/30 bg-amber-300/[0.09] text-amber-50"
        : node.type === "shared"
          ? "border-violet-300/24 bg-violet-300/[0.075] text-violet-50"
          : node.type === "data"
            ? "border-blue-300/24 bg-blue-300/[0.075] text-blue-50"
            : node.type === "infra"
              ? "border-rose-300/24 bg-rose-300/[0.075] text-rose-50"
              : node.type === "tests"
                ? "border-emerald-300/20 bg-emerald-300/[0.055] text-emerald-50"
                : node.type === "docs"
                  ? "border-sky-300/18 bg-sky-300/[0.055] text-sky-50"
                  : node.type === "config"
                    ? "border-zinc-300/16 bg-zinc-300/[0.055] text-zinc-100"
                    : "border-white/[0.12] bg-white/[0.055] text-white";
  const rank =
    node.architectureRoot
      ? "shadow-[0_18px_42px_rgba(0,0,0,0.28)]"
      : node.visualRank === "primary"
        ? "shadow-[0_16px_34px_rgba(0,0,0,0.24)]"
      : node.visualRank === "muted"
        ? "opacity-75"
        : "shadow-[0_12px_28px_rgba(0,0,0,0.2)]";
  const state = active ? "ring-1 ring-white/55" : matched ? "ring-1 ring-teal-200/70" : "";
  return cn(base, rank, state);
}

function edgeColor(edge: GraphEdge, active: boolean) {
  if (active) return "rgba(255,255,255,0.82)";
  if (edge.kind === "deployment") return "rgba(251,113,133,0.58)";
  if (edge.kind === "import" && edge.runtimeCritical) return "rgba(45,212,191,0.64)";
  if (edge.kind === "import") return "rgba(125,211,252,0.5)";
  if (edge.kind === "asset") return "rgba(56,189,248,0.4)";
  if (edge.kind === "manifest") return "rgba(161,161,170,0.24)";
  if (edge.kind === "semantic") return "rgba(196,181,253,0.38)";
  return "rgba(255,255,255,0.36)";
}

function nodeBackground(node: GraphNode) {
  const tint =
    node.type === "frontend"
      ? "rgba(45,212,191,0.13)"
      : node.type === "backend"
        ? "rgba(245,158,11,0.12)"
        : node.type === "shared"
          ? "rgba(167,139,250,0.11)"
          : node.type === "data"
            ? "rgba(96,165,250,0.11)"
            : node.type === "infra"
              ? "rgba(251,113,133,0.1)"
              : node.type === "config"
                ? "rgba(212,212,216,0.08)"
                : "rgba(255,255,255,0.08)";
  return `linear-gradient(180deg, ${tint}, rgba(9, 11, 15, 0.93))`;
}

function detailLevel(scale: number): DetailLevel {
  if (scale < 0.72) return "overview";
  if (scale > 1.18) return "deep";
  return "standard";
}

function fileMatchesNode(file: string, node: ArchitectureNode) {
  if (!file) return false;
  if (node.id === "root") return !file.includes("/");
  if (file === node.id || file.startsWith(`${node.id}/`)) return true;
  const root = file.split("/", 1)[0];
  return root === node.id;
}

function semanticMatchIds(analysis: AnalysisResult, nodes: ArchitectureNode[], query: string) {
  const normalized = query.trim().toLowerCase();
  const matched = new Set<string>();
  if (!normalized) return matched;
  const relevantFiles = new Set<string>();
  if (/(auth|login|session|jwt|token|protected|role|permission)/.test(normalized)) {
    analysis.code_intelligence.auth.files.forEach((file) => relevantFiles.add(file));
    analysis.code_intelligence.auth.login_routes.forEach((route) => relevantFiles.add(route.file));
    analysis.code_intelligence.auth.protected_routes.forEach((route) => relevantFiles.add(route.file));
  }
  if (/(api|route|endpoint|controller|request)/.test(normalized)) {
    analysis.code_intelligence.routes.forEach((route) => relevantFiles.add(route.file));
  }
  if (/(state|redux|zustand|provider|context|query|store|hook|swr)/.test(normalized)) {
    [...analysis.code_intelligence.state.stores, ...analysis.code_intelligence.state.providers, ...analysis.code_intelligence.state.hooks, ...analysis.code_intelligence.state.cache_layers].forEach((symbol) =>
      relevantFiles.add(symbol.file),
    );
  }
  if (/(prisma|database|db|schema|model)/.test(normalized)) {
    analysis.code_intelligence.symbols.filter((symbol) => ["schema", "model"].includes(symbol.type) || /prisma|database|db|schema|model/i.test(symbol.file)).forEach((symbol) => relevantFiles.add(symbol.file));
  }
  if (/(deploy|deployment|infra|ci|docker|vercel|render)/.test(normalized)) {
    const files = analysis.code_intelligence.deployment.files;
    if (Array.isArray(files)) files.filter((file): file is string => typeof file === "string").forEach((file) => relevantFiles.add(file));
  }
  for (const file of relevantFiles) {
    nodes.forEach((node) => {
      if (fileMatchesNode(file, node)) matched.add(node.id);
    });
  }
  return matched;
}

function graphNodeFromArchitectureNode(node: ArchitectureNode, hotspots: Map<string, number>, depth = 1, parent?: string): GraphNode {
  const importance = nodeImportance(node, hotspots);
  return {
    ...node,
    parent,
    domain: architectureDomainForNode(node),
    depth,
    importance,
    visualRank: visualRank(importance),
  };
}

function importantNodes(nodes: GraphNode[], limit: number) {
  return [...nodes].sort((a, b) => b.importance - a.importance || a.label.localeCompare(b.label)).slice(0, limit);
}

function nodeSearchText(node: GraphNode) {
  const files = stringArray(node.metadata?.files).join(" ");
  return `${node.id} ${node.label} ${node.role ?? ""} ${node.description} ${node.framework ?? ""} ${node.runtime_classification ?? ""} ${files}`.toLowerCase();
}

function domainNode(domain: ArchitectureDomain, children: GraphNode[]): GraphNode {
  const definition = domainDefinitions[domain];
  const fileCount = children.reduce((sum, node) => sum + numberFrom(node.metadata?.file_count, node.file_count ?? 1), 0);
  const dependencyCount = children.reduce((sum, node) => sum + numberFrom(node.dependency_count), 0);
  const maxImportance = children.length ? Math.max(...children.map((node) => node.importance)) : 0;
  const importance = children.length ? Math.max(4.2, Math.min(8.6, 4.6 + children.length * 0.2 + maxImportance * 0.26)) : 1.4;
  return {
    id: definition.id,
    label: definition.label,
    type: definition.type,
    description: children.length ? definition.description : `No ${definition.label.toLowerCase()} boundary was detected in the current analysis.`,
    confidence: children.length ? "high" : "low",
    role: definition.role,
    entrypoint: children.some((node) => node.entrypoint),
    dependency_count: dependencyCount,
    ownership_score: children.length ? Math.max(...children.map((node) => numberFrom(node.ownership_score))) : 0,
    runtime_classification: definition.role,
    group: definition.group,
    metadata: { file_count: fileCount, files: children.flatMap((node) => stringArray(node.metadata?.files).length ? stringArray(node.metadata?.files) : [node.id]).slice(0, 24) },
    cluster: true,
    clusterChildren: children,
    architectureRoot: true,
    domain,
    depth: 0,
    file_count: fileCount,
    importance,
    visualRank: children.length ? "primary" : "muted",
  };
}

function buildViewModel(
  analysis: AnalysisResult,
  mode: ArchitectureViewMode,
  expandedNodes: Set<string>,
  query: string,
  expansions: Record<string, ExpansionPayload>,
  hotspots: Map<string, number>,
) {
  const activeExpandedId = expandedNodes.values().next().value ?? null;
  const baseNodes: GraphNode[] = analysis.architecture.nodes.map((node) => graphNodeFromArchitectureNode(node, hotspots));
  const nodeMap = new Map<string, GraphNode>(baseNodes.map((node) => [node.id, node]));
  const sourceNodes = [...baseNodes];
  const sourceEdges: ArchitectureEdge[] = analysis.architecture.edges.map((edge) => ({ ...edge, source: String(edge.source), target: String(edge.target) }));

  const expandedDomain = activeExpandedId ? domainFromId(activeExpandedId) : null;
  const activeParent = activeExpandedId && !expandedDomain ? nodeMap.get(activeExpandedId) : null;

  if (activeParent) {
    const expansion = expansions[activeParent.id];
    for (const child of expansion?.nodes ?? []) {
      if (nodeMap.has(child.id)) continue;
      const childImportance = nodeImportance({ ...activeParent, ...child, id: child.id, label: child.label, type: child.type, description: `${child.file_count ?? 1} files`, confidence: child.confidence ?? activeParent.confidence }, hotspots);
      const graphNode: GraphNode = {
        id: child.id,
        label: child.label,
        type: child.type,
        description: `${child.file_count ?? 1} files under ${activeParent.label}`,
        confidence: child.confidence ?? activeParent.confidence ?? "medium",
        role: child.role ?? "file group",
        framework: child.framework ?? activeParent.framework,
        entrypoint: child.entrypoint ?? false,
        dependency_count: 0,
        ownership_score: activeParent.ownership_score ?? 0,
        runtime_classification: activeParent.runtime_classification,
        group: activeParent.group ?? child.type,
        metadata: { file_count: child.file_count ?? 1, files: child.files ?? [] },
        parent: activeParent.id,
        domain: activeParent.domain,
        depth: (activeParent.depth ?? 1) + 1,
        file_count: child.file_count,
        importance: Math.max(1.8, childImportance - 1.6),
        visualRank: visualRank(Math.max(1.8, childImportance - 1.6)),
      };
      nodeMap.set(child.id, graphNode);
      sourceNodes.push(graphNode);
    }
    for (const edge of expansion?.edges ?? []) {
      sourceEdges.push({
        source: edge.source,
        target: edge.target,
        label: edge.kind === "asset" ? "asset" : "imports",
        confidence: "medium",
        kind: edge.kind ?? "import",
        weight: edge.weight ?? 1,
        reasons: edge.reasons ?? [],
        files: edge.files ?? [],
        metadata: { import_traces: edge.files?.map((file) => ({ source_file: file, statement: edge.reasons?.[0] ?? "internal dependency" })) ?? [] },
      });
    }
  }

  const nodeAlias = new Map<string, string>();
  const visibleNodeMap = new Map<string, GraphNode>();
  const childrenByDomain = new Map<ArchitectureDomain, GraphNode[]>();

  for (const node of baseNodes) {
    const domain = node.domain ?? architectureDomainForNode(node);
    childrenByDomain.set(domain, [...(childrenByDomain.get(domain) ?? []), node]);
  }

  const roots = (Object.keys(domainDefinitions) as ArchitectureDomain[]).map((domain) => domainNode(domain, childrenByDomain.get(domain) ?? []));
  for (const root of roots) {
    visibleNodeMap.set(root.id, root);
  }

  for (const node of sourceNodes) {
    const domain = node.domain ?? architectureDomainForNode(node);
    nodeAlias.set(node.id, domainId(domain));
  }

  function addVisibleNode(node: GraphNode) {
    visibleNodeMap.set(node.id, node);
    nodeAlias.set(node.id, node.id);
  }

  if (expandedDomain) {
    importantNodes(childrenByDomain.get(expandedDomain) ?? [], MAX_EXPANSION_CHILDREN).forEach(addVisibleNode);
  } else if (activeParent) {
    addVisibleNode(activeParent);
    importantNodes(sourceNodes.filter((node) => node.parent === activeParent.id), MAX_EXPANSION_CHILDREN).forEach(addVisibleNode);
  }

  const semanticMatches = semanticMatchIds(analysis, sourceNodes, query);
  const queryLower = query.trim().toLowerCase();
  const textMatches = new Set<string>();

  if (queryLower) {
    for (const root of roots) {
      if (nodeSearchText(root).includes(queryLower)) textMatches.add(root.id);
    }
    const matches = sourceNodes.filter((node) => nodeSearchText(node).includes(queryLower) || semanticMatches.has(node.id));
    for (const node of importantNodes(matches, MAX_QUERY_MATCHES)) {
      addVisibleNode(node);
      textMatches.add(node.id);
      if (node.domain) textMatches.add(domainId(node.domain));
    }
  }

  const scoredEdges = sourceEdges.map((edge) => {
    const importance = edgeImportance(edge, nodeMap);
    return {
      ...edge,
      source: nodeAlias.get(String(edge.source)) ?? String(edge.source),
      target: nodeAlias.get(String(edge.target)) ?? String(edge.target),
      importance,
      runtimeCritical: runtimeCriticalEdge(edge, nodeMap),
    };
  });

  const aggregatedEdges = new Map<string, GraphEdge>();
  for (const edge of scoredEdges) {
    if (edge.source === edge.target) continue;
    if (!visibleNodeMap.has(edge.source) || !visibleNodeMap.has(edge.target)) continue;
    const key = `${edge.source}->${edge.target}:${edge.kind ?? "dependency"}`;
    const existing = aggregatedEdges.get(key);
    if (!existing) {
      aggregatedEdges.set(key, { ...edge, aggregateCount: 1 });
      continue;
    }
    existing.weight = numberFrom(existing.weight, 1) + numberFrom(edge.weight, 1);
    existing.importance = Math.max(existing.importance, edge.importance) + 0.18;
    existing.runtimeCritical = existing.runtimeCritical || edge.runtimeCritical;
    existing.aggregated = true;
    existing.aggregateCount = (existing.aggregateCount ?? 1) + 1;
    existing.files = Array.from(new Set([...(existing.files ?? []), ...(edge.files ?? [])])).slice(0, 12);
    existing.reasons = Array.from(new Set([...(existing.reasons ?? []), ...(edge.reasons ?? [])])).slice(0, 8);
  }

  let edges = Array.from(aggregatedEdges.values()).filter((edge) => edgeAllowedInMode(edge, mode));
  edges = edges.sort((a, b) => b.importance - a.importance).slice(0, mode === "file" ? MAX_VISIBLE_EDGES + 10 : MAX_VISIBLE_EDGES);

  if (queryLower && textMatches.size) {
    const keep = new Set(textMatches);
    edges.forEach((edge) => {
      if (textMatches.has(edge.source) || textMatches.has(edge.target)) {
        keep.add(edge.source);
        keep.add(edge.target);
      }
    });
    edges = edges.filter((edge) => keep.has(edge.source) && keep.has(edge.target));
  }

  const laneCounts = new Map<string, number>();
  const nodes = Array.from(visibleNodeMap.values())
    .sort((a, b) => {
      const aPriority = (a.architectureRoot ? 1000 : 0) + (a.id === activeExpandedId ? 500 : 0) + (textMatches.has(a.id) ? 260 : 0) + a.importance;
      const bPriority = (b.architectureRoot ? 1000 : 0) + (b.id === activeExpandedId ? 500 : 0) + (textMatches.has(b.id) ? 260 : 0) + b.importance;
      return bPriority - aPriority || a.label.localeCompare(b.label);
    })
    .filter((node) => {
      const lane = nodeGroup(node, mode);
      const limit = lane === "infrastructure" ? 8 : 7;
      const count = laneCounts.get(lane) ?? 0;
      if (count >= limit) return false;
      laneCounts.set(lane, count + 1);
      return true;
    })
    .slice(0, MAX_VISIBLE_NODES)
    .sort((a, b) => domainSort(a, mode) - domainSort(b, mode) || (a.depth ?? 0) - (b.depth ?? 0) || b.importance - a.importance);
  const nodeIds = new Set(nodes.map((node) => node.id));
  edges = edges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target));

  return { nodes, edges, matchedIds: textMatches };
}

function domainSort(node: GraphNode, mode: ArchitectureViewMode) {
  const group = nodeGroup(node, mode);
  const order = ["frontend", "shared", "backend", "infrastructure", "manifests", "testing", "docs", "config", "package"];
  return order.indexOf(group) === -1 ? 99 : order.indexOf(group);
}

function lanePriority(node: GraphNode) {
  if (node.architectureRoot) return node.domain === "manifests" ? 16 : 0;
  if ((node.depth ?? 0) >= 2) return 52 - node.importance;
  if (node.parent) return 36 - node.importance;
  return 24 - node.importance;
}

function layoutLane(nodes: GraphNode[], group: string, mode: ArchitectureViewMode): PositionedNode[] {
  const sorted = [...nodes].sort((a, b) => lanePriority(a) - lanePriority(b) || b.importance - a.importance || a.id.localeCompare(b.id));
  const top = 92;
  const bottom = HEIGHT - 72;
  const available = bottom - top;
  const sizes = sorted.map(nodeSize);
  const groupBreaks = sorted.slice(0, -1).filter((node, index) => node.architectureRoot || (node.depth ?? 0) !== (sorted[index + 1]?.depth ?? 0)).length;
  const totalHeight = sizes.reduce((sum, size) => sum + size.height, 0);
  const preferredGap = sorted.length <= 2 ? 58 : sorted.length <= 5 ? 42 : 30;
  const denseGap = sorted.length > 1 ? Math.max(18, Math.min(preferredGap, (available - totalHeight - groupBreaks * 18) / (sorted.length - 1))) : 0;
  const total = totalHeight + denseGap * Math.max(0, sorted.length - 1) + groupBreaks * 18;
  let y = Math.max(top, top + (available - total) / 2);
  const baseX = mode === "ownership" ? laneX[group] ?? laneX.shared : laneX[group] ?? laneX.shared;

  return sorted.map((node, index) => {
    const size = sizes[index];
    const indent = node.architectureRoot ? 0 : (node.depth ?? 1) >= 2 ? 54 : 32;
    const positioned = {
      ...node,
      ...size,
      x: Math.min(WIDTH - size.width / 2 - 42, baseX + indent),
      y: y + size.height / 2,
    };
    y += size.height + denseGap;
    if (node.architectureRoot || (node.depth ?? 0) !== (sorted[index + 1]?.depth ?? 0)) y += 18;
    return positioned;
  });
}

function resolveCollisions(nodes: PositionedNode[], mode: ArchitectureViewMode): PositionedNode[] {
  const grouped = new Map<string, PositionedNode[]>();
  for (const node of nodes) {
    const group = nodeGroup(node, mode);
    grouped.set(group, [...(grouped.get(group) ?? []), node]);
  }
  const resolved: PositionedNode[] = [];
  for (const [group, laneNodes] of grouped) {
    const sorted = [...laneNodes].sort((a, b) => a.y - b.y);
    let cursor = LANE_PADDING;
    for (const node of sorted) {
      const minY = cursor + node.height / 2;
      const y = Math.max(node.y, minY);
      const clampedY = Math.min(HEIGHT - LANE_PADDING - node.height / 2, y);
      resolved.push({ ...node, y: clampedY, x: laneX[group] ? node.x : laneX.shared });
      cursor = clampedY + node.height / 2 + 26;
    }
  }
  return resolved;
}

function deterministicLayout(nodes: GraphNode[], mode: ArchitectureViewMode): PositionedNode[] {
  const grouped = new Map<string, GraphNode[]>();
  for (const node of nodes) {
    const group = nodeGroup(node, mode);
    grouped.set(group, [...(grouped.get(group) ?? []), node]);
  }
  const positioned = Array.from(grouped.entries()).flatMap(([group, groupNodes]) => layoutLane(groupNodes, group, mode));
  return resolveCollisions(positioned, mode);
}

function edgePath(edge: PositionedEdge, routeMode: EdgeRouteMode, index = 0) {
  const source = edge.sourceNode;
  const target = edge.targetNode;
  const leftToRight = source.x <= target.x;
  const sx = source.x + (leftToRight ? source.width / 2 - 4 : -source.width / 2 + 4);
  const sy = source.y;
  const tx = target.x + (leftToRight ? -target.width / 2 + 4 : target.width / 2 - 4);
  const ty = target.y;
  const sameLane = Math.abs(source.x - target.x) < 96;
  const laneOffset = ((index % 5) - 2) * 14;
  const direction = leftToRight ? 1 : -1;
  const bend = Math.max(70, Math.abs(tx - sx) * (routeMode === "bundled" ? 0.36 : 0.28));
  if (sameLane) {
    const sideX = Math.max(source.x + source.width / 2, target.x + target.width / 2) + 54 + (index % 3) * 18;
    const exitX = source.x + source.width / 2 - 2;
    const enterX = target.x + target.width / 2 - 2;
    return `M ${exitX} ${sy} C ${sideX} ${sy + laneOffset}, ${sideX} ${ty - laneOffset}, ${enterX} ${ty}`;
  }
  if (Math.abs(target.x - source.x) > 520) {
    const topCorridor = Math.min(source.y - source.height / 2, target.y - target.height / 2) - 44 - (index % 3) * 22;
    const bottomCorridor = Math.max(source.y + source.height / 2, target.y + target.height / 2) + 44 + (index % 3) * 22;
    const corridorY = topCorridor > 118 ? topCorridor : Math.min(HEIGHT - 118, bottomCorridor);
    const midX = sx + (tx - sx) / 2;
    return `M ${sx} ${sy} C ${sx + direction * 72} ${sy}, ${sx + direction * 72} ${corridorY}, ${midX} ${corridorY} C ${tx - direction * 72} ${corridorY}, ${tx - direction * 72} ${ty}, ${tx} ${ty}`;
  }
  if (routeMode === "bundled") {
    const bundleY = (sy + ty) / 2 + laneOffset;
    return `M ${sx} ${sy} C ${sx + (leftToRight ? bend : -bend)} ${bundleY}, ${tx - (leftToRight ? bend : -bend)} ${bundleY}, ${tx} ${ty}`;
  }
  const c1y = sy + Math.max(-60, Math.min(60, (ty - sy) * 0.18)) + laneOffset;
  const c2y = ty - Math.max(-60, Math.min(60, (ty - sy) * 0.18)) - laneOffset;
  return `M ${sx} ${sy} C ${sx + direction * bend} ${c1y}, ${tx - direction * bend} ${c2y}, ${tx} ${ty}`;
}

function focusNeighborhood(edges: PositionedEdge[], activeNode: string | null, activeEdgeKey: string | null, matchedIds: Set<string>, query: string) {
  const nodes = new Set<string>();
  const edgeKeys = new Set<string>();
  if (query.trim() && matchedIds.size) {
    matchedIds.forEach((id) => nodes.add(id));
  }
  if (activeEdgeKey) {
    const edge = edges.find((candidate, index) => `${candidate.sourceNode.id}-${candidate.targetNode.id}-${index}` === activeEdgeKey);
    if (edge) {
      nodes.add(edge.sourceNode.id);
      nodes.add(edge.targetNode.id);
      edgeKeys.add(activeEdgeKey);
    }
  }
  if (!activeNode && nodes.size === 0) return { nodes, edgeKeys };
  if (activeNode) nodes.add(activeNode);
  for (const edge of edges) {
    const source = edge.sourceNode.id;
    const target = edge.targetNode.id;
    if (nodes.has(source) || nodes.has(target)) {
      nodes.add(source);
      nodes.add(target);
    }
  }
  edges.forEach((edge, index) => {
    const source = edge.sourceNode.id;
    const target = edge.targetNode.id;
    if (nodes.has(source) && nodes.has(target)) edgeKeys.add(`${source}-${target}-${index}`);
  });
  return { nodes, edgeKeys };
}

function visibleNodeText(node: PositionedNode, level: DetailLevel, matched: boolean) {
  if (node.architectureRoot) return { title: true, meta: level !== "overview" || matched, description: level === "deep" || matched };
  if (matched || node.visualRank === "primary") return { title: true, meta: level !== "overview", description: level === "deep" };
  if (node.visualRank === "secondary") return { title: true, meta: level !== "overview", description: false };
  if (node.visualRank === "supporting") return { title: level !== "overview", meta: false, description: false };
  return { title: level === "deep", meta: false, description: false };
}

function nodeVisibleAtDetail(node: PositionedNode, level: DetailLevel, focused: boolean, matched: boolean, expanded: boolean, expandedChild: boolean) {
  if (node.architectureRoot || focused || matched || expanded) return true;
  if (expandedChild && level !== "overview") return true;
  if (level === "overview") return false;
  if (level === "standard") return (node.depth ?? 1) <= 1 && node.visualRank !== "muted";
  return true;
}

function edgeLabel(edge: GraphEdge) {
  const label = edge.aggregated ? `${edge.label} (${edge.aggregateCount})` : edge.label;
  return label.length > 22 ? `${label.slice(0, 19)}...` : label;
}

export function ArchitectureMapView() {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [viewMode, setViewMode] = useState<ArchitectureViewMode>("runtime");
  const [routeMode, setRouteMode] = useState<EdgeRouteMode>("orthogonal");
  const [query, setQuery] = useState("");
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedEdgeKey, setSelectedEdgeKey] = useState<string | null>(null);
  const [positions, setPositions] = useState<PositionedNode[]>([]);
  const [transform, setTransform] = useState<ZoomTransform>(zoomIdentity);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const viewportRef = useRef<SVGGElement | null>(null);
  const zoomRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const layoutFrameRef = useRef<number | null>(null);

  useEffect(() => {
    setAnalysis(loadAnalysis());
  }, []);

  const expansions = useMemo(() => (analysis ? expansionMap(analysis) : {}), [analysis]);
  const hotspots = useMemo(() => (analysis ? hotspotMap(analysis) : new Map<string, number>()), [analysis]);
  const warnings = useMemo(() => (analysis ? riskWarnings(analysis) : []), [analysis]);
  const currentDetail = detailLevel(transform.k);

  const graph = useMemo(() => {
    if (!analysis) return null;
    return buildViewModel(analysis, viewMode, expandedNodes, query, expansions, hotspots);
  }, [analysis, expandedNodes, expansions, hotspots, query, viewMode]);

  useEffect(() => {
    if (!graph) return;
    if (layoutFrameRef.current) window.cancelAnimationFrame(layoutFrameRef.current);
    layoutFrameRef.current = window.requestAnimationFrame(() => {
      setPositions(deterministicLayout(graph.nodes, viewMode));
    });
    return () => {
      if (layoutFrameRef.current) window.cancelAnimationFrame(layoutFrameRef.current);
    };
  }, [graph, viewMode]);

  useEffect(() => {
    if (!svgRef.current || zoomRef.current) return;
    const behavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.46, 2.35])
      .on("zoom", (event: { transform: ZoomTransform }) => {
        setTransform(event.transform);
        select(viewportRef.current).attr("transform", event.transform.toString());
      });
    zoomRef.current = behavior;
    select(svgRef.current).call(behavior as unknown as (selection: Selection<SVGSVGElement, unknown, null, undefined>) => void);
  }, []);

  const visiblePositions = useMemo(
    () =>
      positions.filter((node) =>
        nodeVisibleAtDetail(node, currentDetail, node.id === hoveredNode || node.id === selectedNode, graph?.matchedIds.has(node.id) ?? false, expandedNodes.has(node.id), Boolean(node.parent && expandedNodes.has(node.parent))),
      ),
    [currentDetail, expandedNodes, graph?.matchedIds, hoveredNode, positions, selectedNode],
  );
  const positionById = useMemo(() => new Map(visiblePositions.map((node) => [node.id, node])), [visiblePositions]);
  const renderedEdges = useMemo<PositionedEdge[]>(() => {
    if (!graph) return [];
    return graph.edges
      .map((edge) => {
        const sourceNode = positionById.get(edge.source);
        const targetNode = positionById.get(edge.target);
        if (!sourceNode || !targetNode) return null;
        return { ...edge, sourceNode, targetNode };
      })
      .filter((edge): edge is PositionedEdge => Boolean(edge));
  }, [graph, positionById]);

  const selectedEdge = useMemo(() => {
    if (!selectedEdgeKey) return null;
    return renderedEdges.find((edge, index) => `${edge.sourceNode.id}-${edge.targetNode.id}-${index}` === selectedEdgeKey) ?? null;
  }, [renderedEdges, selectedEdgeKey]);

  const active = useMemo(() => focusNeighborhood(renderedEdges, hoveredNode ?? selectedNode, selectedEdgeKey, graph?.matchedIds ?? new Set(), query), [graph?.matchedIds, hoveredNode, query, renderedEdges, selectedEdgeKey, selectedNode]);

  if (!analysis || !graph) {
    return null;
  }

  const selectedNodeData = selectedNode ? positions.find((node) => node.id === selectedNode) : null;
  const selectedExpansion = selectedNode ? expansions[selectedNode] : null;
  const riskScore = numberFrom(analysis.architecture.risk_analysis?.score, 0);
  const graphMetrics = analysis.architecture.graph_metrics;
  const deploymentFiles = Array.isArray(analysis.code_intelligence.deployment.files) ? analysis.code_intelligence.deployment.files.filter((file): file is string => typeof file === "string") : [];
  const flowItems = [
    { label: "Frontend", value: analysis.architecture.nodes.filter((node) => node.type === "frontend").slice(0, 3).map((node) => node.label).join(", ") || "not detected" },
    { label: "Shared/Core", value: analysis.architecture.nodes.filter((node) => node.type === "shared" || node.type === "data").slice(0, 3).map((node) => node.label).join(", ") || "not detected" },
    { label: "Backend/API", value: analysis.architecture.nodes.filter((node) => node.type === "backend").slice(0, 3).map((node) => node.label).join(", ") || "not detected" },
    { label: "Deployment", value: deploymentFiles.slice(0, 3).join(", ") || analysis.architecture.nodes.filter((node) => node.id === "deployment" || node.type === "infra").slice(0, 3).map((node) => node.label).join(", ") || "not detected" },
  ];

  function toggleNode(node: PositionedNode) {
    setSelectedNode(node.id);
    if (node.architectureRoot || expansions[node.id]?.nodes?.length) {
      setExpandedNodes((current) => {
        if (current.has(node.id)) return new Set();
        return new Set([node.id]);
      });
    }
  }

  function zoomBy(amount: number) {
    if (!svgRef.current || !zoomRef.current) return;
    select(svgRef.current).transition().duration(220).call(zoomRef.current.scaleBy as never, amount);
  }

  function resetView() {
    if (!svgRef.current || !zoomRef.current) return;
    select(svgRef.current).transition().duration(260).call(zoomRef.current.transform as never, zoomIdentity);
  }

  return (
    <div className="space-y-6">
      <section className="glass-panel rounded-lg p-6">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="max-w-3xl">
            <Badge variant="amber" className="mb-3">architecture intelligence</Badge>
            <h1 className="text-2xl font-semibold text-white">Architecture Map</h1>
            <p className="mt-2 text-sm leading-6 text-white/[0.58]">{analysis.architecture.summary}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge>{analysis.architecture.confidence} confidence</Badge>
            <Badge variant={riskScore > 65 ? "red" : riskScore > 30 ? "amber" : "neutral"}>{riskScore}/100 risk</Badge>
            <Badge variant="neutral">{visiblePositions.length} visible nodes</Badge>
          </div>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-4">
          {flowItems.map((item, index) => (
            <div key={item.label} className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-teal-200">0{index + 1}</span>
                <span className="text-xs uppercase text-white/[0.42]">{item.label}</span>
              </div>
              <div className="mt-2 truncate text-sm text-white/[0.78]">{item.value}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-6">
        <div className="space-y-4">
          <div className="glass-panel rounded-lg p-3">
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative min-w-[250px] flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/[0.38]" />
                <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search auth, api, prisma, routes, deploy" className="pl-9" />
              </div>
              <div className="flex rounded-lg border border-white/[0.08] bg-black/[0.22] p-1">
                {(Object.keys(modeLabels) as ArchitectureViewMode[]).map((mode) => {
                  const Icon = viewIcons[mode];
                  return (
                    <Button key={mode} size="sm" variant={viewMode === mode ? "default" : "ghost"} onClick={() => setViewMode(mode)} title={modeDescriptions[mode]}>
                      <Icon className="h-3.5 w-3.5" />
                      {modeLabels[mode]}
                    </Button>
                  );
                })}
              </div>
              <div className="flex rounded-lg border border-white/[0.08] bg-black/[0.22] p-1">
                {(["orthogonal", "bundled"] as EdgeRouteMode[]).map((mode) => (
                  <Button key={mode} size="sm" variant={routeMode === mode ? "secondary" : "ghost"} onClick={() => setRouteMode(mode)} className="capitalize">
                    {mode}
                  </Button>
                ))}
              </div>
              <Button size="icon" variant="outline" onClick={() => zoomBy(1.2)} title="Zoom in">
                <ZoomIn className="h-4 w-4" />
              </Button>
              <Button size="icon" variant="outline" onClick={() => zoomBy(0.82)} title="Zoom out">
                <ZoomOut className="h-4 w-4" />
              </Button>
              <Button size="icon" variant="outline" onClick={resetView} title="Reset view">
                <LocateFixed className="h-4 w-4" />
              </Button>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Badge variant="neutral">{currentDetail} detail</Badge>
              <Badge variant="neutral">{graph.edges.length} visible edges</Badge>
              <Badge variant="neutral">single-level drilldown</Badge>
            </div>
          </div>

          <div className="glass-panel relative overflow-x-auto overflow-y-hidden rounded-lg">
            <svg ref={svgRef} className="h-[760px] min-w-[1180px] w-full touch-none select-none" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="xMidYMin meet" role="img" aria-label="Layered architecture intelligence graph">
              <defs>
                <marker id="graph-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(255,255,255,0.42)" />
                </marker>
                <filter id="node-glow" x="-45%" y="-45%" width="190%" height="190%">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>
              <g>
                {laneLabels.map((lane) => (
                  <g key={lane.key}>
                    <rect x={lane.x} y="24" width={lane.width} height={HEIGHT - 52} rx="8" fill="rgba(255,255,255,0.018)" stroke="rgba(255,255,255,0.035)" />
                    <text x={lane.x + 16} y="52" className="fill-white/[0.24] text-[11px] uppercase tracking-[0.16em]">
                      {lane.label}
                    </text>
                  </g>
                ))}
              </g>
              <g ref={viewportRef}>
                {renderedEdges.map((edge, index) => {
                  const key = `${edge.sourceNode.id}-${edge.targetNode.id}-${index}`;
                  const activeEdge = active.edgeKeys.has(key) || selectedEdgeKey === key;
                  const muted = active.nodes.size > 0 && !activeEdge;
                  const strokeWidth = Math.max(1, Math.min(3.6, edge.runtimeCritical ? 1.2 + edge.importance * 0.2 : 0.9 + edge.importance * 0.14));
                  const midpoint = { x: (edge.sourceNode.x + edge.targetNode.x) / 2, y: (edge.sourceNode.y + edge.targetNode.y) / 2 };
                  const showEdgeLabel = activeEdge || currentDetail === "deep";
                  const path = edgePath(edge, routeMode, index);
                  return (
                    <g
                      key={key}
                      className={cn("transition-opacity duration-200", muted && "opacity-[0.08]")}
                      onMouseEnter={() => setSelectedEdgeKey(key)}
                      onMouseLeave={() => setSelectedEdgeKey(null)}
                    >
                      <motion.path
                        d={path}
                        stroke={edgeColor(edge, activeEdge)}
                        strokeWidth={activeEdge ? strokeWidth + 0.8 : strokeWidth}
                        strokeOpacity={muted ? 0.12 : activeEdge ? 0.92 : edge.kind === "manifest" ? 0.3 : edge.importance < 3 ? 0.34 : 0.72}
                        markerEnd="url(#graph-arrow)"
                        fill="none"
                        initial={{ pathLength: 0, opacity: 0 }}
                        animate={{ pathLength: 1, opacity: 1 }}
                        transition={{ duration: 0.58, delay: Math.min(0.26, index * 0.01) }}
                      />
                      {edge.runtimeCritical && activeEdge && currentDetail === "deep" ? (
                        <circle r="2.8" fill={edgeColor(edge, activeEdge)} opacity={muted ? 0 : 0.72}>
                          <animateMotion dur={`${Math.max(3.2, 9.5 - edge.importance * 0.34)}s`} repeatCount="indefinite" path={path} />
                        </circle>
                      ) : null}
                      {showEdgeLabel ? (
                        <g className="pointer-events-none">
                          <rect x={midpoint.x - 58} y={midpoint.y - 22} width="116" height="20" rx="5" fill="rgba(0,0,0,0.68)" stroke="rgba(255,255,255,0.08)" />
                          <text x={midpoint.x} y={midpoint.y - 8} textAnchor="middle" className="fill-white/[0.68] text-[10px]">
                            {edgeLabel(edge)}
                          </text>
                        </g>
                      ) : null}
                    </g>
                  );
                })}

                {visiblePositions.map((node) => {
                  const Icon = iconByType[node.type] ?? Box;
                  const activeNode = active.nodes.has(node.id) || selectedNode === node.id;
                  const muted = active.nodes.size > 0 && !activeNode;
                  const matched = graph.matchedIds.has(node.id);
                  const expandable = Boolean(node.architectureRoot || expansions[node.id]?.nodes?.length);
                  const expanded = expandedNodes.has(node.id);
                  const text = visibleNodeText(node, currentDetail, matched);
                  return (
                    <foreignObject
                      key={node.id}
                      x={node.x - node.width / 2}
                      y={node.y - node.height / 2}
                      width={node.width}
                      height={node.height}
                      className={cn("overflow-visible transition-opacity duration-200", muted && "opacity-[0.18]")}
                    >
                      <motion.button
                        type="button"
                        onClick={() => toggleNode(node)}
                        onMouseEnter={() => setHoveredNode(node.id)}
                        onMouseLeave={() => setHoveredNode(null)}
                        whileHover={{ scale: 1.01 }}
                        className={cn("h-full w-full overflow-hidden rounded-lg border p-3 text-left backdrop-blur-sm", nodeColor(node, activeNode, matched))}
                        style={{ background: nodeBackground(node) }}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex min-w-0 items-center gap-2">
                            <Icon className={cn("shrink-0 opacity-85", node.architectureRoot ? "h-5 w-5" : "h-4 w-4")} />
                            {text.title ? <span className={cn("truncate font-mono leading-none", node.architectureRoot ? "text-[15px]" : "text-[13px]")}>{node.label}</span> : null}
                          </div>
                          {expandable ? expanded ? <ChevronDown className="h-4 w-4 shrink-0 text-white/[0.58]" /> : <ChevronRight className="h-4 w-4 shrink-0 text-white/[0.5]" /> : <span className="font-mono text-[10px] text-white/[0.36]">{node.dependency_count ?? 0}</span>}
                        </div>
                        {text.meta ? (
                          <div className="mt-2 flex min-h-5 flex-wrap gap-1 overflow-hidden">
                            <span className="rounded border border-white/[0.08] px-1.5 py-0.5 text-[9px] uppercase text-white/[0.44]">{node.cluster ? `${node.file_count ?? 0} items` : node.group ?? node.type}</span>
                            {node.entrypoint ? <span className="rounded border border-white/[0.08] px-1.5 py-0.5 text-[9px] uppercase text-white/[0.44]">entry</span> : null}
                            {node.architectureRoot ? <span className="rounded border border-teal-300/15 px-1.5 py-0.5 text-[9px] uppercase text-teal-100/70">lane</span> : null}
                          </div>
                        ) : null}
                        {text.description ? <p className="mt-2 line-clamp-2 text-xs leading-5 text-white/[0.58]">{node.role ?? node.description}</p> : null}
                      </motion.button>
                    </foreignObject>
                  );
                })}
              </g>
            </svg>

            <div className="pointer-events-none absolute bottom-4 right-4 rounded-md border border-white/[0.07] bg-black/45 p-1.5 opacity-70 backdrop-blur-sm">
              <svg className="h-16 w-28" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="xMidYMid meet" aria-hidden>
                {visiblePositions.map((node) => (
                  <circle key={node.id} cx={node.x} cy={node.y} r={node.architectureRoot ? 12 : 7} fill="rgba(255,255,255,0.58)" />
                ))}
                <rect
                  x={Math.max(0, -transform.x / transform.k)}
                  y={Math.max(0, -transform.y / transform.k)}
                  width={WIDTH / transform.k}
                  height={HEIGHT / transform.k}
                  fill="none"
                  stroke="rgba(45,212,191,0.55)"
                  strokeWidth="7"
                />
              </svg>
            </div>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-3">
          <ComplexityMeter intelligence={analysis.intelligence} />

          <Card className="glass-panel">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                Architecture Story
              </CardTitle>
              <CardDescription>{modeDescriptions[viewMode]}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {analysis.architecture.dependency_flow.slice(0, 4).map((flow, index) => (
                <div key={`${flow}-${index}`} className="flex gap-3 rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
                  <span className="font-mono text-xs text-teal-200">0{index + 1}</span>
                  <p className="text-sm leading-6 text-white/[0.62]">{flow}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="glass-panel">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-4 w-4" />
                Graph Evidence
              </CardTitle>
              <CardDescription>Signal-filtered architecture view</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              {[
                ["imports", metricValue(graphMetrics, "imports_resolved")],
                ["relationships", graph.edges.length],
                ["nodes", visiblePositions.length],
                ["connected", metricValue(graphMetrics, "connected_ratio")],
              ].map(([label, value]) => (
                <div key={label} className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
                  <div className="font-mono text-lg text-white">{value}</div>
                  <div className="mt-1 text-xs uppercase text-white/[0.38]">{label}</div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="glass-panel">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Eye className="h-4 w-4" />
                Focus
              </CardTitle>
              <CardDescription>Selected node, cluster, or relationship</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {selectedNodeData ? (
                <>
                  <div className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate font-mono text-sm text-white">{selectedNodeData.label}</div>
                        <p className="mt-2 text-sm leading-6 text-white/[0.62]">
                          {selectedNodeData.cluster
                            ? selectedNodeData.description
                            : selectedExpansion?.explanation ?? `${selectedNodeData.label} is a ${selectedNodeData.role ?? selectedNodeData.type} boundary with ${selectedNodeData.dependency_count ?? 0} dependency signals.`}
                        </p>
                      </div>
                      <Badge variant={selectedNodeData.visualRank === "primary" ? "default" : "neutral"}>{selectedNodeData.visualRank}</Badge>
                    </div>
                  </div>
                  {selectedNodeData.clusterChildren?.length ? (
                    <div className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
                      <div className="mb-2 text-xs uppercase text-white/[0.38]">cluster contents</div>
                      <div className="space-y-2">
                        {selectedNodeData.clusterChildren.slice(0, 8).map((node) => (
                          <div key={node.id} className="flex items-center justify-between gap-2 text-sm">
                            <span className="truncate font-mono text-white/[0.72]">{node.label}</span>
                            <span className="text-xs text-white/[0.38]">{node.type}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {selectedExpansion?.nodes?.length ? (
                    <div className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
                      <div className="mb-2 text-xs uppercase text-white/[0.38]">drilldown</div>
                      <div className="space-y-2">
                        {selectedExpansion.nodes.slice(0, 8).map((node) => (
                          <div key={node.id} className="flex items-center justify-between gap-2 text-sm">
                            <span className="truncate font-mono text-white/[0.72]">{node.label}</span>
                            <span className="text-xs text-white/[0.38]">{node.file_count ?? 1} files</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </>
              ) : selectedEdge ? (
                <div className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
                  <div className="text-sm font-medium text-white">{selectedEdge.sourceNode.label} {"->"} {selectedEdge.targetNode.label}</div>
                  <p className="mt-2 text-sm leading-6 text-white/[0.62]">{selectedEdge.reasons?.[0] ?? `This ${selectedEdge.kind ?? "dependency"} edge has importance ${selectedEdge.importance.toFixed(1)}.`}</p>
                  <div className="mt-3 space-y-2">
                    {edgeTrace(selectedEdge).slice(0, 5).map((trace, index) => (
                      <div key={`${trace.source_file}-${index}`} className="rounded border border-white/[0.08] bg-white/[0.04] p-2 font-mono text-xs text-white/[0.58]">
                        {String(trace.source_file ?? "unknown")} {"->"} {String(trace.target_file ?? "unknown")}
                        <br />
                        {String(trace.statement ?? "")}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3 text-sm leading-6 text-white/[0.62]">
                  {analysis.architecture.boundaries[0] ?? "Runtime boundaries are derived from entrypoints, import traces, symbol roles, and deployment evidence."}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="glass-panel">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Flame className="h-4 w-4" />
                Risk And Hotspots
              </CardTitle>
              <CardDescription>Coupling, cycles, drift, and dependency pressure</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {warnings.slice(0, 3).map((warning, index) => (
                <div key={`${warning.type}-${index}`} className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium capitalize text-white">{String(warning.type ?? "risk").replaceAll("_", " ")}</span>
                    <Badge variant={warning.severity === "high" ? "red" : warning.severity === "medium" ? "amber" : "neutral"}>{String(warning.severity ?? "low")}</Badge>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-white/[0.62]">{String(warning.message ?? "")}</p>
                </div>
              ))}
              {(analysis.architecture.hotspots ?? []).slice(0, 5).map((hotspot) => (
                <button key={String(hotspot.id)} type="button" onClick={() => setSelectedNode(String(hotspot.id))} className="flex w-full items-center justify-between gap-3 rounded-lg border border-white/[0.08] bg-black/[0.24] p-3 text-left">
                  <span className="truncate font-mono text-sm text-white/[0.72]">{String(hotspot.label ?? hotspot.id)}</span>
                  <span className="text-xs text-amber-100">{String(hotspot.pressure ?? "0")}</span>
                </button>
              ))}
            </CardContent>
          </Card>

          <Card className="glass-panel">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Network className="h-4 w-4" />
                Topology
              </CardTitle>
              <CardDescription>Framework, monorepo, and deployment intelligence</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {((analysis.architecture.topology?.framework_analyzers as Array<Record<string, unknown>> | undefined) ?? []).slice(0, 6).map((item) => (
                <div key={String(item.framework)} className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
                  <div className="text-sm font-medium text-white">{String(item.framework)}</div>
                  <div className="mt-2 text-xs leading-5 text-white/[0.5]">
                    {Object.entries(item)
                      .filter(([key]) => key !== "framework")
                      .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.length : String(value)}`)
                      .join(" | ")}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
