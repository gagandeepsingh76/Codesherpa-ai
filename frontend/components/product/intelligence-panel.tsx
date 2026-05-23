"use client";

import { AlertTriangle, Compass, FilePlus2, Gauge, ShieldCheck, UsersRound } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { RepositoryIntelligence } from "@/lib/types";
import { cn } from "@/lib/utils";

function severityVariant(severity: "low" | "medium" | "high") {
  if (severity === "high") return "red";
  if (severity === "medium") return "amber";
  return "neutral";
}

export function ComplexityMeter({ intelligence }: { intelligence: RepositoryIntelligence }) {
  const score = intelligence.complexity.score;
  return (
    <Card className="glass-panel overflow-hidden">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Gauge className="h-5 w-5 text-teal-200" />
          Complexity Score
        </CardTitle>
        <CardDescription>Evidence-weighted onboarding difficulty</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-5">
          <div
            className="grid h-28 w-28 shrink-0 place-items-center rounded-full"
            style={{ background: `conic-gradient(#2dd4bf ${score * 3.6}deg, rgba(255,255,255,0.08) 0deg)` }}
          >
            <div className="grid h-20 w-20 place-items-center rounded-full bg-[#080b10]">
              <div className="text-center">
                <div className="text-2xl font-semibold text-white">{score}</div>
                <div className="text-[10px] uppercase tracking-[0.18em] text-white/[0.38]">/100</div>
              </div>
            </div>
          </div>
          <div className="min-w-0">
            <Badge variant={score > 70 ? "amber" : "default"}>{intelligence.complexity.level}</Badge>
            <p className="mt-3 text-sm leading-6 text-white/[0.62]">{intelligence.complexity.summary}</p>
          </div>
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          {intelligence.complexity.drivers.slice(0, 5).map((driver, index) => (
            <Badge key={`${driver}-${index}`} variant="neutral">
              {driver}
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export function RiskRadar({ intelligence }: { intelligence: RepositoryIntelligence }) {
  return (
    <Card className="glass-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-200" />
          Dependency & Risk Radar
        </CardTitle>
        <CardDescription>Signals that may slow contributor onboarding</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {intelligence.risks.length ? (
          intelligence.risks.slice(0, 4).map((risk, index) => (
            <div key={`${risk.title}-${index}`} className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-medium text-white">{risk.title}</div>
                <Badge variant={severityVariant(risk.severity)}>{risk.severity}</Badge>
              </div>
              <p className="mt-2 text-xs leading-5 text-white/[0.52]">{risk.recommendation}</p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {risk.evidence.slice(0, 4).map((item, evidenceIndex) => (
                  <span key={`${item}-${evidenceIndex}`} className="rounded-md bg-white/[0.06] px-2 py-1 font-mono text-[11px] text-white/[0.42]">
                    {item}
                  </span>
                ))}
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-lg border border-teal-300/[0.16] bg-teal-300/[0.08] p-4 text-sm leading-6 text-teal-50/[0.74]">
            <ShieldCheck className="mb-3 h-5 w-5 text-teal-200" />
            No major deterministic onboarding risks were detected. The agent will keep risk confidence conservative until deeper file reads are added.
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function OwnershipMap({ intelligence }: { intelligence: RepositoryIntelligence }) {
  return (
    <Card className="glass-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <UsersRound className="h-5 w-5 text-teal-200" />
          Smart Ownership Map
        </CardTitle>
        <CardDescription>Responsibility hints without inventing maintainers</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        {intelligence.ownership.length ? (
          intelligence.ownership.slice(0, 6).map((area, index) => (
            <div key={`${area.area}-${index}`} className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-medium text-white">{area.area}</div>
                  <p className="mt-1 text-xs leading-5 text-white/[0.46]">{area.owner_hint}</p>
                </div>
                <Badge variant="neutral">{area.confidence}</Badge>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {area.paths.map((path, pathIndex) => (
                  <span key={`${path}-${pathIndex}`} className="rounded-md bg-white/[0.06] px-2 py-1 font-mono text-[11px] text-white/[0.48]">
                    {path}
                  </span>
                ))}
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-lg border border-dashed border-white/[0.12] bg-white/[0.03] p-5 text-sm leading-6 text-white/[0.52] sm:col-span-2">
            Ownership surfaces appear once the scanner detects top-level folders. For single-file repositories, CodeSherpa keeps ownership confidence low instead of inventing teams.
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function GoodFirstIssueList({ intelligence, className }: { intelligence: RepositoryIntelligence; className?: string }) {
  return (
    <Card className={cn("glass-panel", className)}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FilePlus2 className="h-5 w-5 text-amber-200" />
          AI-Generated Good First Issues
        </CardTitle>
        <CardDescription>Scoped opportunities grounded in detected files</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {intelligence.good_first_issues.map((issue, index) => (
          <div key={`${issue.title}-${index}`} className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-white">{issue.title}</h3>
                <p className="mt-2 text-sm leading-6 text-white/[0.56]">{issue.rationale}</p>
              </div>
              <Badge variant={issue.difficulty === "easy" ? "default" : "amber"}>{issue.estimated_time}</Badge>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {issue.labels.map((label, labelIndex) => (
                <Badge key={`${label}-${labelIndex}`} variant="neutral">
                  {label}
                </Badge>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {issue.files.map((file, fileIndex) => (
                <span key={`${file}-${fileIndex}`} className="rounded-md bg-white/[0.06] px-2 py-1 font-mono text-[11px] text-white/[0.48]">
                  {file}
                </span>
              ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export function ContributionPathCards({ intelligence }: { intelligence: RepositoryIntelligence }) {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {intelligence.contribution_paths.map((path, index) => (
        <div key={`${path.name}-${index}`} className="glass-panel rounded-lg p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-teal-300/20 bg-teal-300/10">
              <Compass className="h-4 w-4 text-teal-200" />
            </div>
            <span className="font-mono text-xs text-white/[0.34]">path 0{index + 1}</span>
          </div>
          <h3 className="mt-4 text-base font-semibold text-white">{path.name}</h3>
          <p className="mt-2 text-sm leading-6 text-white/[0.54]">{path.outcome}</p>
          <div className="mt-4 space-y-2">
            {path.steps.slice(0, 4).map((step, stepIndex) => (
              <div key={`${step}-${stepIndex}`} className="flex gap-2 text-xs leading-5 text-white/[0.52]">
                <span className="font-mono text-teal-200">{stepIndex + 1}</span>
                <span>{step}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
