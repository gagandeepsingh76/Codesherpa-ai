"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  Box,
  Braces,
  Database,
  FileText,
  GitBranch,
  GitFork,
  Layers3,
  Network,
  Server,
  Shield,
  TestTube2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ComplexityMeter } from "@/components/product/intelligence-panel";
import { loadAnalysis } from "@/lib/api";
import type { AnalysisResult, ArchitectureEdge, ArchitectureNode } from "@/lib/types";
import { cn } from "@/lib/utils";

type GraphPoint = {
  x: number;
  y: number;
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

const fallbackPositions: GraphPoint[] = [
  { x: 18, y: 18 },
  { x: 48, y: 14 },
  { x: 72, y: 22 },
  { x: 34, y: 42 },
  { x: 62, y: 46 },
  { x: 84, y: 50 },
  { x: 18, y: 68 },
  { x: 48, y: 74 },
  { x: 74, y: 78 },
  { x: 8, y: 42 },
  { x: 88, y: 12 },
  { x: 30, y: 86 },
];

function nodeColor(type: ArchitectureNode["type"]) {
  if (type === "frontend") return "border-teal-300/35 bg-teal-300/12 text-teal-100";
  if (type === "backend") return "border-amber-300/35 bg-amber-300/12 text-amber-100";
  if (type === "shared") return "border-violet-300/30 bg-violet-300/10 text-violet-100";
  if (type === "data") return "border-blue-300/30 bg-blue-300/10 text-blue-100";
  if (type === "tests") return "border-emerald-300/30 bg-emerald-300/10 text-emerald-100";
  if (type === "docs") return "border-sky-300/30 bg-sky-300/10 text-sky-100";
  if (type === "infra") return "border-rose-300/30 bg-rose-300/10 text-rose-100";
  if (type === "config") return "border-zinc-300/25 bg-zinc-300/10 text-zinc-100";
  return "border-white/[0.14] bg-white/[0.07] text-white";
}

function edgeColor(edge: ArchitectureEdge) {
  if (edge.kind === "asset") return "rgba(56, 189, 248, 0.62)";
  if (edge.kind === "deployment") return "rgba(244, 114, 182, 0.62)";
  if (edge.kind === "manifest") return "rgba(161, 161, 170, 0.54)";
  if (edge.label.includes("validates")) return "rgba(52, 211, 153, 0.56)";
  return "rgba(45, 212, 191, 0.58)";
}

function positionFor(node: ArchitectureNode, index: number): GraphPoint {
  const fallback = fallbackPositions[index % fallbackPositions.length];
  return {
    x: typeof node.x === "number" ? node.x : fallback.x,
    y: typeof node.y === "number" ? node.y : fallback.y,
  };
}

function listFromUnknown(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function metricValue(metrics: Record<string, unknown> | undefined, key: string) {
  const value = metrics?.[key];
  return typeof value === "number" || typeof value === "string" ? value : "0";
}

function edgeTitle(edge: ArchitectureEdge) {
  const reasons = edge.reasons?.slice(0, 3).join("\n") ?? "";
  return `${edge.source} -> ${edge.target}\n${edge.label}\nweight ${edge.weight ?? 1}${reasons ? `\n${reasons}` : ""}`;
}

export function ArchitectureMapView() {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);

  useEffect(() => {
    setAnalysis(loadAnalysis());
  }, []);

  const graph = useMemo(() => {
    if (!analysis) {
      return null;
    }
    const nodes = analysis.architecture.nodes.slice(0, 36);
    const positionById = Object.fromEntries(nodes.map((node, index) => [node.id, positionFor(node, index)]));
    const visibleEdges = analysis.architecture.edges
      .filter((edge) => positionById[edge.source] && positionById[edge.target])
      .slice(0, 80);
    return { nodes, positionById, visibleEdges };
  }, [analysis]);

  if (!analysis || !graph) {
    return null;
  }

  const metrics = analysis.architecture.graph_metrics;

  return (
    <div className="space-y-6">
      <section className="glass-panel rounded-lg p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Badge variant="amber" className="mb-3">
              architecture graph
            </Badge>
            <h1 className="max-w-3xl text-3xl font-semibold text-white sm:text-5xl">Dependency map for {analysis.summary.name}</h1>
            <p className="mt-4 max-w-3xl text-base leading-7 text-white/[0.62]">{analysis.architecture.summary}</p>
          </div>
          <Badge>{analysis.architecture.confidence} confidence</Badge>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="glass-panel overflow-x-auto rounded-lg">
          <div className="relative h-[720px] min-w-[820px] overflow-hidden p-5">
            <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
              <defs>
                <marker id="graph-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(255,255,255,0.62)" />
                </marker>
              </defs>
              {graph.visibleEdges.map((edge, index) => {
                const source = graph.positionById[edge.source];
                const target = graph.positionById[edge.target];
                const bend = Math.max(6, Math.abs(target.x - source.x) * 0.38);
                const midpoint = { x: (source.x + target.x) / 2, y: (source.y + target.y) / 2 };
                const strokeWidth = Math.min(0.72, 0.18 + (edge.weight ?? 1) * 0.08);
                return (
                  <g key={`${edge.source}-${edge.target}-${edge.kind ?? "edge"}-${index}`}>
                    <title>{edgeTitle(edge)}</title>
                    <motion.path
                      d={`M ${source.x} ${source.y} C ${source.x + bend} ${source.y}, ${target.x - bend} ${target.y}, ${target.x} ${target.y}`}
                      stroke={edgeColor(edge)}
                      strokeWidth={strokeWidth}
                      markerEnd="url(#graph-arrow)"
                      fill="none"
                      initial={{ pathLength: 0, opacity: 0 }}
                      animate={{ pathLength: 1, opacity: 1 }}
                      transition={{ duration: 0.75, delay: index * 0.025 }}
                    />
                    <text x={midpoint.x} y={midpoint.y - 1.4} textAnchor="middle" className="fill-white/[0.48] text-[2.4px]">
                      {edge.label}
                    </text>
                  </g>
                );
              })}
            </svg>

            {graph.nodes.map((node, index) => {
              const Icon = iconByType[node.type] ?? Box;
              const position = graph.positionById[node.id];
              const signals = listFromUnknown(node.metadata?.signals);
              return (
                <motion.div
                  key={`${node.id}-${index}`}
                  title={[node.description, node.framework, node.runtime_classification, ...signals.slice(0, 3)].filter(Boolean).join("\n")}
                  initial={{ opacity: 0, scale: 0.92, y: 10 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: index * 0.035 }}
                  className={cn(
                    "absolute w-[176px] -translate-x-1/2 -translate-y-1/2 rounded-lg border p-3 shadow-panel backdrop-blur",
                    nodeColor(node.type),
                  )}
                  style={{ left: `${position.x}%`, top: `${position.y}%` }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2">
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="truncate font-mono text-sm">{node.label}</span>
                    </div>
                    <span className="font-mono text-[10px] text-white/[0.48]">{node.dependency_count ?? 0}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    <span className="rounded border border-white/[0.1] px-1.5 py-0.5 text-[10px] uppercase text-white/[0.52]">{node.group ?? node.type}</span>
                    {node.entrypoint ? <span className="rounded border border-white/[0.1] px-1.5 py-0.5 text-[10px] uppercase text-white/[0.52]">entry</span> : null}
                  </div>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-white/[0.58]">{node.role ?? node.description}</p>
                  {node.framework ? <p className="mt-1 truncate text-[11px] text-white/[0.42]">{node.framework}</p> : null}
                </motion.div>
              );
            })}
          </div>
        </div>

        <div className="space-y-6">
          <ComplexityMeter intelligence={analysis.intelligence} />

          <Card className="glass-panel">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-4 w-4" />
                Graph Evidence
              </CardTitle>
              <CardDescription>AST traces, manifest signals, and graph connectivity</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              {[
                ["imports", metricValue(metrics, "imports_resolved")],
                ["edges", metricValue(metrics, "edges")],
                ["nodes", metricValue(metrics, "nodes")],
                ["connected", `${metricValue(metrics, "connected_ratio")}`],
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
                <Network className="h-4 w-4" />
                Mini Map
              </CardTitle>
              <CardDescription>{graph.nodes.length} nodes, {graph.visibleEdges.length} visible edges</CardDescription>
            </CardHeader>
            <CardContent>
              <svg className="h-36 w-full rounded-lg border border-white/[0.08] bg-black/[0.24]" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
                {graph.visibleEdges.map((edge, index) => {
                  const source = graph.positionById[edge.source];
                  const target = graph.positionById[edge.target];
                  return <line key={`${edge.source}-${edge.target}-${index}`} x1={source.x} y1={source.y} x2={target.x} y2={target.y} stroke={edgeColor(edge)} strokeWidth="0.35" />;
                })}
                {graph.nodes.map((node, index) => {
                  const point = graph.positionById[node.id];
                  return <circle key={`${node.id}-${index}`} cx={point.x} cy={point.y} r={node.entrypoint ? 1.8 : 1.2} className="fill-white/80" />;
                })}
              </svg>
            </CardContent>
          </Card>

          <Card className="glass-panel">
            <CardHeader>
              <CardTitle>System Boundaries</CardTitle>
              <CardDescription>Evidence-weighted architecture calls</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {analysis.architecture.boundaries.map((boundary, index) => (
                <div key={`${boundary}-${index}`} className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3 text-sm leading-6 text-white/[0.62]">
                  {boundary}
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="glass-panel">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GitBranch className="h-4 w-4" />
                Dependency Flow
              </CardTitle>
              <CardDescription>How to traverse the codebase</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {analysis.architecture.dependency_flow.map((flow, index) => (
                <div key={`${flow}-${index}`} className="flex gap-3 rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
                  <span className="font-mono text-xs text-teal-200">0{index + 1}</span>
                  <p className="text-sm leading-6 text-white/[0.62]">{flow}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
