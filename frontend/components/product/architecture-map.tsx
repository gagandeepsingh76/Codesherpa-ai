"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Box, Database, FileText, GitFork, Layers3, Server, Shield, TestTube2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ComplexityMeter } from "@/components/product/intelligence-panel";
import { loadAnalysis } from "@/lib/api";
import type { AnalysisResult, ArchitectureNode } from "@/lib/types";
import { cn } from "@/lib/utils";

const iconByType = {
  frontend: Layers3,
  backend: Server,
  shared: GitFork,
  data: Database,
  infra: Shield,
  docs: FileText,
  tests: TestTube2,
  config: Box,
  package: Box,
};

const positions = [
  { x: 12, y: 14 },
  { x: 58, y: 12 },
  { x: 36, y: 38 },
  { x: 10, y: 62 },
  { x: 62, y: 62 },
  { x: 78, y: 36 },
  { x: 34, y: 74 },
  { x: 4, y: 38 },
  { x: 74, y: 78 },
  { x: 48, y: 84 },
  { x: 22, y: 86 },
  { x: 84, y: 12 },
];

function nodeColor(type: ArchitectureNode["type"]) {
  if (type === "frontend") return "border-teal-300/30 bg-teal-300/10 text-teal-100";
  if (type === "backend") return "border-amber-300/30 bg-amber-300/10 text-amber-100";
  if (type === "tests") return "border-emerald-300/25 bg-emerald-300/10 text-emerald-100";
  if (type === "docs") return "border-sky-300/25 bg-sky-300/10 text-sky-100";
  if (type === "infra") return "border-rose-300/25 bg-rose-300/10 text-rose-100";
  return "border-white/[0.12] bg-white/[0.06] text-white";
}

export function ArchitectureMapView() {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);

  useEffect(() => {
    setAnalysis(loadAnalysis());
  }, []);

  if (!analysis) {
    return null;
  }

  const nodes = analysis.architecture.nodes.slice(0, 12);
  const positionById = Object.fromEntries(nodes.map((node, index) => [node.id, positions[index] ?? positions[0]]));

  return (
    <div className="space-y-6">
      <section className="glass-panel rounded-lg p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Badge variant="amber" className="mb-3">
              architecture visualization
            </Badge>
            <h1 className="max-w-3xl text-3xl font-semibold text-white sm:text-5xl">Interactive system map for {analysis.summary.name}</h1>
            <p className="mt-4 max-w-3xl text-base leading-7 text-white/[0.62]">{analysis.architecture.summary}</p>
          </div>
          <Badge>{analysis.architecture.confidence} confidence</Badge>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="glass-panel relative min-h-[640px] overflow-hidden rounded-lg p-5">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(45,212,191,0.08),transparent_32rem)]" />
          <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
            {analysis.architecture.edges.map((edge, index) => {
              const source = positionById[edge.source];
              const target = positionById[edge.target];
              if (!source || !target) return null;
              return (
                <motion.path
                  key={`${edge.source}-${edge.target}-${index}`}
                  d={`M ${source.x + 8} ${source.y + 4} C ${source.x + 20} ${source.y}, ${target.x - 6} ${target.y}, ${target.x + 8} ${target.y + 4}`}
                  stroke="rgba(45, 212, 191, 0.34)"
                  strokeWidth="0.24"
                  fill="none"
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: 1, opacity: 1 }}
                  transition={{ duration: 0.8, delay: index * 0.08 }}
                />
              );
            })}
          </svg>
          <div className="relative h-[600px]">
            {nodes.map((node, index) => {
              const Icon = iconByType[node.type] ?? Box;
              const position = positions[index] ?? positions[0];
              return (
                <motion.div
                  key={`${node.id}-${index}`}
                  initial={{ opacity: 0, scale: 0.92, y: 12 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: index * 0.06 }}
                  className={cn("absolute w-[180px] rounded-lg border p-3 shadow-panel backdrop-blur", nodeColor(node.type))}
                  style={{ left: `${position.x}%`, top: `${position.y}%` }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2">
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="truncate font-mono text-sm">{node.label}</span>
                    </div>
                    <span className="h-2 w-2 shrink-0 rounded-full bg-current opacity-70" />
                  </div>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-white/[0.54]">{node.description}</p>
                </motion.div>
              );
            })}
          </div>
        </div>

        <div className="space-y-6">
          <ComplexityMeter intelligence={analysis.intelligence} />

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
              <CardTitle>Dependency Flow</CardTitle>
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
