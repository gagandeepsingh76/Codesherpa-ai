"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, FileCode2, GitPullRequestArrow, Route, Timer, TrendingUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ContributionPathCards, GoodFirstIssueList } from "@/components/product/intelligence-panel";
import { loadAnalysis } from "@/lib/api";
import type { AnalysisResult } from "@/lib/types";

export function ContributorPanel() {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);

  useEffect(() => {
    setAnalysis(loadAnalysis());
  }, []);

  if (!analysis) {
    return null;
  }

  return (
    <div className="space-y-6">
      <section className="glass-panel rounded-lg p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Badge variant="amber" className="mb-3">
              contributor mode
            </Badge>
            <h1 className="max-w-3xl text-3xl font-semibold text-white sm:text-5xl">A first-week roadmap for {analysis.summary.name}</h1>
            <p className="mt-4 max-w-3xl text-base leading-7 text-white/[0.62]">
              The Onboarding Agent turns repository structure into a sequenced learning path, beginner files, and scoped contribution ideas.
            </p>
          </div>
          <Badge>{analysis.contributor_plan.confidence} confidence</Badge>
        </div>
      </section>

      <section className="space-y-6">
        <div className="glass-panel rounded-lg p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-white">Suggested Contribution Paths</div>
              <p className="mt-1 text-sm text-white/[0.48]">Three demo-friendly lanes from safe onboarding to scoped implementation.</p>
            </div>
            <Badge variant="neutral">{analysis.intelligence.complexity.level} repo</Badge>
          </div>
        </div>
        <ContributionPathCards intelligence={analysis.intelligence} />
      </section>

      <section className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Route className="h-5 w-5 text-teal-200" />
              Learning Sequence
            </CardTitle>
            <CardDescription>Ordered for contributor momentum</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="relative space-y-4">
              <div className="absolute left-[19px] top-5 h-full w-px bg-gradient-to-b from-teal-300/70 to-transparent" />
              {analysis.contributor_plan.roadmap.map((step, index) => (
                <motion.div
                  key={`${step.title}-${index}`}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, delay: index * 0.08 }}
                  className="relative flex gap-4"
                >
                  <div className="z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-teal-300/25 bg-black text-sm font-semibold text-teal-100">
                    {index + 1}
                  </div>
                  <div className="flex-1 rounded-lg border border-white/[0.08] bg-black/[0.24] p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <h2 className="text-base font-semibold text-white">{step.title}</h2>
                      <div className="flex items-center gap-2">
                        <Badge variant={step.difficulty === "easy" ? "default" : "amber"}>{step.difficulty}</Badge>
                        <Badge variant="neutral" className="gap-1">
                          <Timer className="h-3 w-3" />
                          {step.estimate}
                        </Badge>
                      </div>
                    </div>
                    <p className="mt-2 text-sm leading-7 text-white/[0.62]">{step.description}</p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {step.files.map((file, fileIndex) => (
                        <Badge key={`${file}-${fileIndex}`} variant="neutral" className="gap-1">
                          <FileCode2 className="h-3 w-3" />
                          {file}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="glass-panel">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-amber-200" />
                Beginner Files
              </CardTitle>
              <CardDescription>Useful low-friction starting points</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {analysis.contributor_plan.beginner_files.map((file, index) => (
                <div key={`${file.path}-${index}`} className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="truncate font-mono text-sm text-white">{file.path}</div>
                    <Badge variant="neutral">{file.role}</Badge>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-white/[0.48]">{file.reason}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="glass-panel">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GitPullRequestArrow className="h-5 w-5 text-teal-200" />
                First Tasks
              </CardTitle>
              <CardDescription>Scoped contribution ideas</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {analysis.contributor_plan.recommended_tasks.map((task, index) => (
                <div key={`${task.title}-${index}`} className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
                  <div className="flex items-start gap-3">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-teal-200" />
                    <div>
                      <div className="text-sm font-medium text-white">{task.title}</div>
                      <p className="mt-1 text-xs leading-5 text-white/[0.48]">{task.why}</p>
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </section>

      <GoodFirstIssueList intelligence={analysis.intelligence} />
    </div>
  );
}
