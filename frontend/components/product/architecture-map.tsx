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

type GraphNode = ArchitectureNode & {
  parent?: string;
  cluster?: boolean;
  clusterKey?: string;
  clusterChildren?: ArchitectureNode[];
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

type ClusterDefinition = {
  key: string;
  label: string;
  type: ArchitectureNode["type"];
  role: string;
  description: string;
  group: string;
};

const WIDTH = 1240;
const HEIGHT = 760;
const LANE_PADDING = 76;

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

const clusterDefinitions: Record<string, ClusterDefinition> = {
  "cluster:infrastructure": {
    key: "cluster:infrastructure",
    label: "Infrastructure",
    type: "infra",
    role: "collapsed deployment/config cluster",
    description: "Hosting, CI, container, and deployment configuration grouped to reduce graph noise.",
    group: "infrastructure",
  },
  "cluster:manifests": {
    key: "cluster:manifests",
    label: "Manifests",
    type: "config",
    role: "collapsed dependency manifest cluster",
    description: "Package, lockfile, and runtime manifest signals grouped as configuration evidence.",
    group: "infrastructure",
  },
  "cluster:configs": {
    key: "cluster:configs",
    label: "Configs",
    type: "config",
    role: "collapsed configuration cluster",
    description: "Framework and tool configuration grouped behind one support node.",
    group: "infrastructure",
  },
  "cluster:tests": {
    key: "cluster:tests",
    label: "Tests",
    type: "tests",
    role: "collapsed validation cluster",
    description: "Test suites and validation assets grouped as supporting evidence.",
    group: "testing",
  },
  "cluster:docs": {
    key: "cluster:docs",
    label: "Docs",
    type: "docs",
    role: "collapsed documentation cluster",
    description: "Documentation and onboarding material grouped outside the runtime path.",
    group: "docs",
  },
};

const laneX: Record<string, number> = {
  frontend: 170,
  shared: 450,
  backend: 730,
  infrastructure: 1010,
  testing: 520,
  docs: 220,
};

const laneLabels: Array<{ key: string; label: string; x: number; width: number }> = [
  { key: "frontend", label: "Frontend", x: 36, width: 250 },
  { key: "shared", label: "Shared/Core", x: 316, width: 250 },
  { key: "backend", label: "Backend/API", x: 596, width: 250 },
  { key: "infrastructure", label: "Infra/Deploy", x: 876, width: 320 },
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

function clusterKeyForNode(node: ArchitectureNode, mode: ArchitectureViewMode) {
  const normalized = node.id.toLowerCase();
  if (mode === "file") return null;
  if (node.id === "deployment") return null;
  if (node.id === "manifest" || normalized.includes("package-lock") || normalized.includes("pnpm-lock")) return "cluster:manifests";
  if (node.type === "docs") return "cluster:docs";
  if (node.type === "tests") return "cluster:tests";
  if (node.type === "config") return "cluster:configs";
  if (node.type === "infra" && mode !== "infrastructure") return "cluster:infrastructure";
  return null;
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
  if (node.visualRank === "primary") return { width: 202, height: 108 };
  if (node.visualRank === "secondary") return { width: 184, height: 96 };
  if (node.visualRank === "supporting") return { width: 158, height: 84 };
  return { width: 132, height: 70 };
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
      ? "border-teal-300/38 bg-teal-300/12 text-teal-50"
      : node.type === "backend"
        ? "border-amber-300/38 bg-amber-300/12 text-amber-50"
        : node.type === "shared"
          ? "border-violet-300/32 bg-violet-300/10 text-violet-50"
          : node.type === "data"
            ? "border-blue-300/32 bg-blue-300/10 text-blue-50"
            : node.type === "infra"
              ? "border-rose-300/30 bg-rose-300/10 text-rose-50"
              : node.type === "tests"
                ? "border-emerald-300/25 bg-emerald-300/8 text-emerald-50"
                : node.type === "docs"
                  ? "border-sky-300/22 bg-sky-300/8 text-sky-50"
                  : node.type === "config"
                    ? "border-zinc-300/18 bg-zinc-300/7 text-zinc-100"
                    : "border-white/[0.14] bg-white/[0.07] text-white";
  const rank =
    node.visualRank === "primary"
      ? "shadow-[0_0_34px_rgba(45,212,191,0.13)]"
      : node.visualRank === "muted"
        ? "opacity-72"
        : "shadow-panel";
  const state = active ? "ring-2 ring-white/50" : matched ? "ring-2 ring-teal-200/70" : "";
  return cn(base, rank, state);
}

function edgeColor(edge: GraphEdge, active: boolean) {
  if (active) return "rgba(255,255,255,0.95)";
  if (edge.kind === "deployment") return "rgba(251,113,133,0.78)";
  if (edge.kind === "import" && edge.runtimeCritical) return "rgba(45,212,191,0.82)";
  if (edge.kind === "import") return "rgba(125,211,252,0.62)";
  if (edge.kind === "asset") return "rgba(56,189,248,0.54)";
  if (edge.kind === "manifest") return "rgba(161,161,170,0.36)";
  if (edge.kind === "semantic") return "rgba(196,181,253,0.42)";
  return "rgba(255,255,255,0.46)";
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

function buildViewModel(
  analysis: AnalysisResult,
  mode: ArchitectureViewMode,
  expandedNodes: Set<string>,
  expandedClusters: Set<string>,
  query: string,
  expansions: Record<string, ExpansionPayload>,
  hotspots: Map<string, number>,
) {
  const baseNodes: GraphNode[] = analysis.architecture.nodes.map((node) => {
    const importance = nodeImportance(node, hotspots);
    return { ...node, importance, visualRank: visualRank(importance) };
  });
  const nodeMap = new Map<string, GraphNode>(baseNodes.map((node) => [node.id, node]));
  const sourceNodes = [...baseNodes];
  const sourceEdges: ArchitectureEdge[] = analysis.architecture.edges.map((edge) => ({ ...edge, source: String(edge.source), target: String(edge.target) }));

  for (const parentId of expandedNodes) {
    const expansion = expansions[parentId];
    const parent = nodeMap.get(parentId);
    if (!parent || !expansion?.nodes) continue;
    for (const child of expansion.nodes) {
      if (nodeMap.has(child.id)) continue;
      const childImportance = nodeImportance({ ...parent, ...child, id: child.id, label: child.label, type: child.type, description: `${child.file_count ?? 1} files`, confidence: child.confidence ?? parent.confidence }, hotspots);
      const graphNode: GraphNode = {
        id: child.id,
        label: child.label,
        type: child.type,
        description: `${child.file_count ?? 1} files under ${parentId}`,
        confidence: child.confidence ?? parent.confidence ?? "medium",
        role: child.role ?? "file group",
        framework: child.framework ?? parent.framework,
        entrypoint: child.entrypoint ?? false,
        dependency_count: 0,
        ownership_score: parent.ownership_score ?? 0,
        runtime_classification: parent.runtime_classification,
        group: parent.group ?? child.type,
        metadata: { file_count: child.file_count ?? 1, files: child.files ?? [] },
        parent: parentId,
        file_count: child.file_count,
        importance: Math.max(2, childImportance - 1.4),
        visualRank: visualRank(Math.max(2, childImportance - 1.4)),
      };
      nodeMap.set(child.id, graphNode);
      sourceNodes.push(graphNode);
    }
    for (const edge of expansion.edges ?? []) {
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

  const clusterChildren = new Map<string, GraphNode[]>();
  const nodeAlias = new Map<string, string>();
  const visibleNodeMap = new Map<string, GraphNode>();

  for (const node of sourceNodes) {
    const clusterKey = clusterKeyForNode(node, mode);
    if (clusterKey && !expandedClusters.has(clusterKey)) {
      nodeAlias.set(node.id, clusterKey);
      clusterChildren.set(clusterKey, [...(clusterChildren.get(clusterKey) ?? []), node]);
      continue;
    }
    nodeAlias.set(node.id, node.id);
    visibleNodeMap.set(node.id, node);
  }

  for (const [clusterKey, children] of clusterChildren) {
    const definition = clusterDefinitions[clusterKey];
    if (!definition || !children.length) continue;
    const importance = Math.max(1.8, Math.min(4.8, 1.4 + children.length * 0.34 + Math.max(...children.map((node) => node.importance)) * 0.22));
    visibleNodeMap.set(clusterKey, {
      id: clusterKey,
      label: definition.label,
      type: definition.type,
      description: definition.description,
      confidence: "medium",
      role: definition.role,
      entrypoint: false,
      dependency_count: children.reduce((sum, node) => sum + numberFrom(node.dependency_count), 0),
      ownership_score: 0,
      runtime_classification: "supporting evidence",
      group: definition.group,
      metadata: { file_count: children.length, files: children.map((node) => node.id) },
      cluster: true,
      clusterKey,
      clusterChildren: children,
      file_count: children.length,
      importance,
      visualRank: visualRank(importance),
    });
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
  edges = edges.sort((a, b) => b.importance - a.importance).slice(0, mode === "file" ? 96 : 56);
  const connectedIds = new Set(edges.flatMap((edge) => [edge.source, edge.target]));
  const semanticMatches = semanticMatchIds(analysis, sourceNodes, query);
  const queryLower = query.trim().toLowerCase();
  const textMatches = new Set<string>();

  if (queryLower) {
    for (const node of visibleNodeMap.values()) {
      const files = stringArray(node.metadata?.files).join(" ");
      const haystack = `${node.id} ${node.label} ${node.role ?? ""} ${node.description} ${node.framework ?? ""} ${node.runtime_classification ?? ""} ${files}`.toLowerCase();
      if (haystack.includes(queryLower)) textMatches.add(node.id);
      for (const child of node.clusterChildren ?? []) {
        if (`${child.id} ${child.label} ${child.role ?? ""}`.toLowerCase().includes(queryLower) || semanticMatches.has(child.id)) textMatches.add(node.id);
      }
    }
    for (const sourceId of semanticMatches) {
      const alias = nodeAlias.get(sourceId);
      if (alias) textMatches.add(alias);
    }
  }

  if (queryLower && textMatches.size) {
    const keep = new Set(textMatches);
    edges.forEach((edge) => {
      if (textMatches.has(edge.source) || textMatches.has(edge.target)) {
        keep.add(edge.source);
        keep.add(edge.target);
      }
    });
    edges = edges.filter((edge) => keep.has(edge.source) && keep.has(edge.target));
    connectedIds.clear();
    edges.forEach((edge) => {
      connectedIds.add(edge.source);
      connectedIds.add(edge.target);
    });
    textMatches.forEach((id) => connectedIds.add(id));
  }

  const pinned = new Set(["src", "app", "frontend", "backend", "root", "apps", "packages", "deployment"]);
  let nodes = Array.from(visibleNodeMap.values()).filter(
    (node) => connectedIds.has(node.id) || node.cluster || node.entrypoint || pinned.has(node.id) || node.importance >= (mode === "runtime" ? 4.2 : 3.4) || expandedNodes.has(node.id) || textMatches.has(node.id),
  );
  nodes = nodes.sort((a, b) => b.importance - a.importance).slice(0, mode === "file" ? 72 : 44);
  const nodeIds = new Set(nodes.map((node) => node.id));
  edges = edges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target));

  return { nodes, edges, matchedIds: textMatches };
}

function domainSort(node: GraphNode, mode: ArchitectureViewMode) {
  const group = nodeGroup(node, mode);
  const order = ["frontend", "shared", "backend", "infrastructure", "testing", "docs", "config", "package"];
  return order.indexOf(group) === -1 ? 99 : order.indexOf(group);
}

function deterministicLayout(nodes: GraphNode[], mode: ArchitectureViewMode): PositionedNode[] {
  const grouped = new Map<string, GraphNode[]>();
  for (const node of nodes) {
    const group = nodeGroup(node, mode);
    grouped.set(group, [...(grouped.get(group) ?? []), node]);
  }
  const positioned: PositionedNode[] = [];
  for (const [group, groupNodes] of grouped) {
    const sorted = [...groupNodes].sort((a, b) => b.importance - a.importance || a.id.localeCompare(b.id));
    const x =
      mode === "ownership"
        ? 150 + Math.max(0, domainSort(sorted[0], mode)) * 145
        : laneX[group] ?? (group === "testing" ? 560 : group === "docs" ? 260 : laneX.shared);
    const totalHeight = sorted.reduce((sum, node) => sum + nodeSize(node).height, 0);
    const gap = Math.max(24, Math.min(58, (HEIGHT - LANE_PADDING * 2 - totalHeight) / Math.max(1, sorted.length - 1)));
    let y = Math.max(96, HEIGHT / 2 - (totalHeight + gap * (sorted.length - 1)) / 2);
    sorted.forEach((node) => {
      const size = nodeSize(node);
      positioned.push({ ...node, ...size, x, y: y + size.height / 2 });
      y += size.height + gap;
    });
  }
  return positioned;
}

async function computeElkLayout(nodes: GraphNode[], edges: GraphEdge[], mode: ArchitectureViewMode): Promise<PositionedNode[]> {
  const { default: ELK } = await import("elkjs/lib/elk.bundled.js");
  const elk = new ELK();
  const graph = await elk.layout({
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.spacing.nodeNode": mode === "file" ? "34" : "46",
      "elk.layered.spacing.nodeNodeBetweenLayers": mode === "file" ? "72" : "112",
      "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
      "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
    },
    children: nodes.map((node) => {
      const size = nodeSize(node);
      return { id: node.id, width: size.width, height: size.height };
    }),
    edges: edges.map((edge, index) => ({ id: `${edge.source}-${edge.target}-${index}`, sources: [edge.source], targets: [edge.target] })),
  });
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const result: PositionedNode[] = [];
  for (const child of (graph.children as Array<Record<string, unknown>> | undefined) ?? []) {
    const id = child.id;
    if (typeof id !== "string") continue;
    const node = byId.get(id);
    if (!node) continue;
    const size = nodeSize(node);
    result.push({
      ...node,
      ...size,
      x: numberFrom(child.x) + size.width / 2,
      y: numberFrom(child.y) + size.height / 2,
    });
  }
  return centerLayout(nodes.map((node) => result.find((item) => item.id === node.id) ?? { ...node, ...nodeSize(node), x: 100, y: 100 }));
}

function centerLayout(nodes: PositionedNode[]) {
  if (!nodes.length) return nodes;
  const minX = Math.min(...nodes.map((node) => node.x - node.width / 2));
  const maxX = Math.max(...nodes.map((node) => node.x + node.width / 2));
  const minY = Math.min(...nodes.map((node) => node.y - node.height / 2));
  const maxY = Math.max(...nodes.map((node) => node.y + node.height / 2));
  const offsetX = WIDTH / 2 - (minX + maxX) / 2;
  const offsetY = HEIGHT / 2 - (minY + maxY) / 2;
  return nodes.map((node) => ({
    ...node,
    x: Math.max(node.width / 2 + 26, Math.min(WIDTH - node.width / 2 - 26, node.x + offsetX)),
    y: Math.max(node.height / 2 + 58, Math.min(HEIGHT - node.height / 2 - 36, node.y + offsetY)),
  }));
}

function edgePath(edge: PositionedEdge, routeMode: EdgeRouteMode) {
  const source = edge.sourceNode;
  const target = edge.targetNode;
  const leftToRight = source.x <= target.x;
  const sx = source.x + (leftToRight ? source.width / 2 - 4 : -source.width / 2 + 4);
  const sy = source.y;
  const tx = target.x + (leftToRight ? -target.width / 2 + 4 : target.width / 2 - 4);
  const ty = target.y;
  const mx = sx + (tx - sx) / 2;
  if (routeMode === "bundled") {
    const bundleY = (sy + ty) / 2;
    const bend = Math.max(48, Math.abs(tx - sx) * 0.34);
    return `M ${sx} ${sy} C ${sx + (leftToRight ? bend : -bend)} ${bundleY}, ${tx - (leftToRight ? bend : -bend)} ${bundleY}, ${tx} ${ty}`;
  }
  return `M ${sx} ${sy} L ${mx} ${sy} L ${mx} ${ty} L ${tx} ${ty}`;
}

function focusNeighborhood(edges: PositionedEdge[], activeNode: string | null, matchedIds: Set<string>, query: string) {
  const nodes = new Set<string>();
  const edgeKeys = new Set<string>();
  if (query.trim() && matchedIds.size) {
    matchedIds.forEach((id) => nodes.add(id));
  }
  if (!activeNode && nodes.size === 0) return { nodes, edgeKeys };
  if (activeNode) nodes.add(activeNode);
  for (let depth = 0; depth < 2; depth += 1) {
    for (const edge of edges) {
      const source = edge.sourceNode.id;
      const target = edge.targetNode.id;
      if (nodes.has(source) || nodes.has(target)) {
        nodes.add(source);
        nodes.add(target);
      }
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
  if (matched || node.visualRank === "primary") return { title: true, meta: level !== "overview", description: level === "deep" };
  if (node.visualRank === "secondary") return { title: true, meta: level !== "overview", description: false };
  if (node.visualRank === "supporting") return { title: level !== "overview", meta: false, description: false };
  return { title: level === "deep", meta: false, description: false };
}

export function ArchitectureMapView() {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [viewMode, setViewMode] = useState<ArchitectureViewMode>("runtime");
  const [routeMode, setRouteMode] = useState<EdgeRouteMode>("orthogonal");
  const [query, setQuery] = useState("");
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [expandedClusters, setExpandedClusters] = useState<Set<string>>(new Set());
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedEdgeKey, setSelectedEdgeKey] = useState<string | null>(null);
  const [positions, setPositions] = useState<PositionedNode[]>([]);
  const [transform, setTransform] = useState<ZoomTransform>(zoomIdentity);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const viewportRef = useRef<SVGGElement | null>(null);
  const zoomRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null);

  useEffect(() => {
    setAnalysis(loadAnalysis());
  }, []);

  const expansions = useMemo(() => (analysis ? expansionMap(analysis) : {}), [analysis]);
  const hotspots = useMemo(() => (analysis ? hotspotMap(analysis) : new Map<string, number>()), [analysis]);
  const warnings = useMemo(() => (analysis ? riskWarnings(analysis) : []), [analysis]);
  const currentDetail = detailLevel(transform.k);

  const graph = useMemo(() => {
    if (!analysis) return null;
    return buildViewModel(analysis, viewMode, expandedNodes, expandedClusters, query, expansions, hotspots);
  }, [analysis, expandedClusters, expandedNodes, expansions, hotspots, query, viewMode]);

  useEffect(() => {
    if (!graph) return;
    let cancelled = false;
    const currentGraph = graph;
    async function runLayout() {
      const next = viewMode === "dependency" || viewMode === "file" ? await computeElkLayout(currentGraph.nodes, currentGraph.edges, viewMode) : deterministicLayout(currentGraph.nodes, viewMode);
      if (!cancelled) setPositions(next);
    }
    runLayout().catch(() => {
      if (!cancelled) setPositions(deterministicLayout(currentGraph.nodes, viewMode));
    });
    return () => {
      cancelled = true;
    };
  }, [graph, viewMode]);

  useEffect(() => {
    if (!svgRef.current || zoomRef.current) return;
    const behavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.42, 2.6])
      .on("zoom", (event: { transform: ZoomTransform }) => {
        setTransform(event.transform);
        select(viewportRef.current).attr("transform", event.transform.toString());
      });
    zoomRef.current = behavior;
    select(svgRef.current).call(behavior as unknown as (selection: Selection<SVGSVGElement, unknown, null, undefined>) => void);
  }, []);

  const positionById = useMemo(() => new Map(positions.map((node) => [node.id, node])), [positions]);
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

  const active = useMemo(() => focusNeighborhood(renderedEdges, hoveredNode ?? selectedNode, graph?.matchedIds ?? new Set(), query), [graph?.matchedIds, hoveredNode, query, renderedEdges, selectedNode]);

  if (!analysis || !graph) {
    return null;
  }

  const selectedNodeData = selectedNode ? positions.find((node) => node.id === selectedNode) : null;
  const selectedExpansion = selectedNode ? expansions[selectedNode] : null;
  const riskScore = numberFrom(analysis.architecture.risk_analysis?.score, 0);
  const graphMetrics = analysis.architecture.graph_metrics;
  const deploymentFiles = Array.isArray(analysis.code_intelligence.deployment.files) ? analysis.code_intelligence.deployment.files.filter((file): file is string => typeof file === "string") : [];
  const collapsedClusters = Array.from(new Set(graph.nodes.filter((node) => node.cluster).map((node) => node.clusterKey).filter(Boolean) as string[]));
  const flowItems = [
    { label: "Frontend", value: analysis.architecture.nodes.filter((node) => node.type === "frontend").slice(0, 3).map((node) => node.label).join(", ") || "not detected" },
    { label: "Shared/Core", value: analysis.architecture.nodes.filter((node) => node.type === "shared" || node.type === "data").slice(0, 3).map((node) => node.label).join(", ") || "not detected" },
    { label: "Backend/API", value: analysis.architecture.nodes.filter((node) => node.type === "backend").slice(0, 3).map((node) => node.label).join(", ") || "not detected" },
    { label: "Deployment", value: deploymentFiles.slice(0, 3).join(", ") || analysis.architecture.nodes.filter((node) => node.id === "deployment" || node.type === "infra").slice(0, 3).map((node) => node.label).join(", ") || "not detected" },
  ];

  function toggleNode(node: PositionedNode) {
    setSelectedNode(node.id);
    if (node.clusterKey) {
      setExpandedClusters((current) => {
        const next = new Set(current);
        if (next.has(node.clusterKey!)) next.delete(node.clusterKey!);
        else next.add(node.clusterKey!);
        return next;
      });
      return;
    }
    if (expansions[node.id]?.nodes?.length) {
      setExpandedNodes((current) => {
        const next = new Set(current);
        if (next.has(node.id)) next.delete(node.id);
        else next.add(node.id);
        return next;
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
            <Badge variant="neutral">{graph.nodes.length} visible nodes</Badge>
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

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_390px]">
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
              {collapsedClusters.map((clusterKey) => {
                const definition = clusterDefinitions[clusterKey];
                if (!definition) return null;
                return (
                  <button
                    key={clusterKey}
                    type="button"
                    onClick={() =>
                      setExpandedClusters((current) => {
                        const next = new Set(current);
                        if (next.has(clusterKey)) next.delete(clusterKey);
                        else next.add(clusterKey);
                        return next;
                      })
                    }
                    className="rounded-md border border-white/[0.08] bg-black/[0.22] px-2.5 py-1 text-xs text-white/[0.58] transition hover:border-teal-300/25 hover:text-white"
                  >
                    {definition.label}
                  </button>
                );
              })}
              <Badge variant="neutral">{currentDetail} detail</Badge>
              <Badge variant="neutral">{graph.edges.length} visible edges</Badge>
            </div>
          </div>

          <div className="glass-panel relative overflow-hidden rounded-lg">
            <svg ref={svgRef} className="h-[780px] w-full touch-none select-none" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Layered architecture intelligence graph">
              <defs>
                <marker id="graph-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(255,255,255,0.68)" />
                </marker>
                <filter id="node-glow" x="-45%" y="-45%" width="190%" height="190%">
                  <feGaussianBlur stdDeviation="8" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>
              <g>
                {laneLabels.map((lane) => (
                  <g key={lane.key}>
                    <rect x={lane.x} y="22" width={lane.width} height={HEIGHT - 44} rx="12" fill="rgba(255,255,255,0.025)" stroke="rgba(255,255,255,0.04)" />
                    <text x={lane.x + 14} y="48" className="fill-white/[0.26] text-[11px] uppercase tracking-[0.18em]">
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
                  const strokeWidth = Math.max(1, Math.min(7, edge.runtimeCritical ? 1.8 + edge.importance * 0.36 : 0.8 + edge.importance * 0.22));
                  const midpoint = { x: (edge.sourceNode.x + edge.targetNode.x) / 2, y: (edge.sourceNode.y + edge.targetNode.y) / 2 };
                  const showEdgeLabel = activeEdge || selectedEdgeKey === key;
                  return (
                    <g
                      key={key}
                      className={cn("transition-opacity duration-200", muted && "opacity-12")}
                      onMouseEnter={() => setSelectedEdgeKey(key)}
                      onMouseLeave={() => setSelectedEdgeKey(null)}
                    >
                      <motion.path
                        d={edgePath(edge, routeMode)}
                        stroke={edgeColor(edge, activeEdge)}
                        strokeWidth={activeEdge ? strokeWidth + 1.1 : strokeWidth}
                        strokeOpacity={edge.kind === "manifest" ? 0.38 : edge.importance < 3 ? 0.36 : 0.86}
                        markerEnd="url(#graph-arrow)"
                        fill="none"
                        initial={{ pathLength: 0, opacity: 0 }}
                        animate={{ pathLength: 1, opacity: 1 }}
                        transition={{ duration: 0.58, delay: Math.min(0.26, index * 0.01) }}
                      />
                      {edge.runtimeCritical && currentDetail !== "overview" ? (
                        <circle r={activeEdge ? 4 : 2.6} fill={edgeColor(edge, activeEdge)} opacity={muted ? 0 : 0.9}>
                          <animateMotion dur={`${Math.max(2.6, 8.5 - edge.importance * 0.42)}s`} repeatCount="indefinite" path={edgePath(edge, routeMode)} />
                        </circle>
                      ) : null}
                      {showEdgeLabel ? (
                        <text x={midpoint.x} y={midpoint.y - 9} textAnchor="middle" className="pointer-events-none fill-white/[0.7] text-[11px]">
                          {edge.aggregated ? `${edge.label} (${edge.aggregateCount})` : edge.label}
                        </text>
                      ) : null}
                    </g>
                  );
                })}

                {positions.map((node) => {
                  const Icon = iconByType[node.type] ?? Box;
                  const activeNode = active.nodes.has(node.id) || selectedNode === node.id;
                  const muted = active.nodes.size > 0 && !activeNode;
                  const matched = graph.matchedIds.has(node.id);
                  const expandable = Boolean(node.clusterKey || expansions[node.id]?.nodes?.length);
                  const expanded = node.clusterKey ? expandedClusters.has(node.clusterKey) : expandedNodes.has(node.id);
                  const text = visibleNodeText(node, currentDetail, matched);
                  return (
                    <foreignObject
                      key={node.id}
                      x={node.x - node.width / 2}
                      y={node.y - node.height / 2}
                      width={node.width}
                      height={node.height + 24}
                      className={cn("overflow-visible transition-opacity duration-200", muted && "opacity-22")}
                    >
                      <motion.button
                        type="button"
                        onClick={() => toggleNode(node)}
                        onMouseEnter={() => setHoveredNode(node.id)}
                        onMouseLeave={() => setHoveredNode(null)}
                        whileHover={{ scale: 1.018 }}
                        className={cn("h-full w-full rounded-lg border p-3 text-left backdrop-blur", nodeColor(node, activeNode, matched))}
                        style={{ filter: node.visualRank === "primary" ? "url(#node-glow)" : undefined }}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex min-w-0 items-center gap-2">
                            <Icon className={cn("shrink-0", node.visualRank === "primary" ? "h-5 w-5" : "h-4 w-4")} />
                            {text.title ? <span className={cn("truncate font-mono", node.visualRank === "primary" ? "text-base" : "text-sm")}>{node.label}</span> : null}
                          </div>
                          {expandable ? expanded ? <ChevronDown className="h-4 w-4 shrink-0" /> : <ChevronRight className="h-4 w-4 shrink-0" /> : <span className="font-mono text-[10px] text-white/[0.46]">{node.dependency_count ?? 0}</span>}
                        </div>
                        {text.meta ? (
                          <div className="mt-2 flex flex-wrap gap-1">
                            <span className="rounded border border-white/[0.1] px-1.5 py-0.5 text-[10px] uppercase text-white/[0.54]">{node.cluster ? `${node.file_count ?? 0} items` : node.group ?? node.type}</span>
                            {node.entrypoint ? <span className="rounded border border-white/[0.1] px-1.5 py-0.5 text-[10px] uppercase text-white/[0.54]">entry</span> : null}
                            {node.visualRank === "primary" ? <span className="rounded border border-teal-300/20 px-1.5 py-0.5 text-[10px] uppercase text-teal-100">runtime</span> : null}
                          </div>
                        ) : null}
                        {text.description ? <p className="mt-2 line-clamp-2 text-xs leading-5 text-white/[0.58]">{node.role ?? node.description}</p> : null}
                      </motion.button>
                    </foreignObject>
                  );
                })}
              </g>
            </svg>

            <div className="pointer-events-none absolute bottom-4 left-4 rounded-lg border border-white/[0.08] bg-black/60 p-2 backdrop-blur">
              <svg className="h-24 w-44" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="xMidYMid meet" aria-hidden>
                {renderedEdges.slice(0, 80).map((edge, index) => (
                  <line key={`${edge.sourceNode.id}-${edge.targetNode.id}-${index}`} x1={edge.sourceNode.x} y1={edge.sourceNode.y} x2={edge.targetNode.x} y2={edge.targetNode.y} stroke={edgeColor(edge, false)} strokeWidth="6" opacity="0.26" />
                ))}
                {positions.map((node) => (
                  <circle key={node.id} cx={node.x} cy={node.y} r={node.visualRank === "primary" ? 15 : node.cluster ? 12 : 9} fill="rgba(255,255,255,0.75)" />
                ))}
                <rect
                  x={Math.max(0, -transform.x / transform.k)}
                  y={Math.max(0, -transform.y / transform.k)}
                  width={WIDTH / transform.k}
                  height={HEIGHT / transform.k}
                  fill="none"
                  stroke="rgba(45,212,191,0.9)"
                  strokeWidth="8"
                />
              </svg>
            </div>
          </div>
        </div>

        <div className="space-y-6">
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
                ["nodes", graph.nodes.length],
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
