"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, BrainCircuit, FileCode2, FolderTree, GitBranch, Loader2, Play, Sparkles } from "lucide-react";

import { TimelinePanel } from "@/components/product/timeline-panel";
import { StatStrip } from "@/components/product/stat-strip";
import { ComplexityMeter, GoodFirstIssueList, OwnershipMap, RiskRadar } from "@/components/product/intelligence-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { analyzeRepository, loadAnalysis } from "@/lib/api";
import { demoTimeline } from "@/lib/demo-data";
import type { AnalysisResult, TimelineEvent } from "@/lib/types";

export function RepositoryDashboard() {
  const [repoUrl, setRepoUrl] = useState("https://github.com/vercel/next.js");
  const [analysis, setAnalysis] = useState<AnalysisResult>(() => loadAnalysis());
  const [events, setEvents] = useState<TimelineEvent[]>(analysis.timeline);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const topLanguages = useMemo(
    () =>
      Object.entries(analysis.summary.languages)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5),
    [analysis.summary.languages],
  );

  async function handleAnalyze() {
    setIsAnalyzing(true);
    setError(null);
    setEvents([]);
    try {
      const result = await analyzeRepository(repoUrl, (event) => {
        setEvents((current) => [...current.filter((item) => item.id !== event.id), event].slice(-14));
      });
      setAnalysis(result);
      setEvents(result.timeline);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Analysis failed. Showing demo analysis.");
      setEvents(demoTimeline);
    } finally {
      setIsAnalyzing(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-6 lg:grid-cols-[1fr_420px]">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45 }}
          className="glass-panel rounded-lg p-5 sm:p-6"
        >
          <div className="flex flex-col gap-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <Badge variant="amber" className="mb-3">
                  autonomous repository workflow
                </Badge>
                <h1 className="max-w-3xl text-3xl font-semibold tracking-normal text-white sm:text-5xl">
                  Repository intelligence, streamed as agents work.
                </h1>
                <p className="mt-4 max-w-2xl text-base leading-7 text-white/[0.62]">
                  CodeSherpa clones, scans, maps, explains, and remembers a repository through a GitAgent-native workflow.
                </p>
              </div>
              <div className="rounded-lg border border-teal-300/20 bg-teal-300/10 px-3 py-2 font-mono text-xs text-teal-100">
                {analysis.repo_id}
              </div>
            </div>

            <div className="flex flex-col gap-3 rounded-lg border border-white/10 bg-black/[0.24] p-3 sm:flex-row">
              <Input value={repoUrl} onChange={(event) => setRepoUrl(event.target.value)} aria-label="GitHub repository URL" />
              <Button onClick={handleAnalyze} disabled={isAnalyzing} className="sm:w-[156px]">
                {isAnalyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                Analyze
              </Button>
            </div>
            {error ? <div className="rounded-lg border border-red-300/20 bg-red-300/10 px-4 py-3 text-sm text-red-100">{error}</div> : null}

            <StatStrip analysis={analysis} />
          </div>
        </motion.div>

        <TimelinePanel events={events} compact />
      </section>

      <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <ComplexityMeter intelligence={analysis.intelligence} />
        <Card className="glass-panel overflow-hidden">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-amber-200" />
              Repository Intelligence Brief
            </CardTitle>
            <CardDescription>Competition-grade onboarding signals generated from the scan</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-7 text-white/[0.68]">{analysis.intelligence.architecture_brief}</p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
                <div className="text-2xl font-semibold text-white">{analysis.intelligence.good_first_issues.length}</div>
                <div className="mt-1 text-xs text-white/[0.44]">good-first issues</div>
              </div>
              <div className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
                <div className="text-2xl font-semibold text-white">{analysis.intelligence.ownership.length}</div>
                <div className="mt-1 text-xs text-white/[0.44]">ownership surfaces</div>
              </div>
              <div className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
                <div className="text-2xl font-semibold text-white">{analysis.intelligence.risks.length}</div>
                <div className="mt-1 text-xs text-white/[0.44]">risk signals</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BrainCircuit className="h-5 w-5 text-teal-200" />
              Architecture Summary
            </CardTitle>
            <CardDescription>{analysis.summary.name}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {isAnalyzing ? (
              <div className="space-y-3">
                <Skeleton className="h-5 w-4/5" />
                <Skeleton className="h-5 w-3/5" />
                <Skeleton className="h-5 w-5/6" />
              </div>
            ) : (
              <p className="text-sm leading-7 text-white/[0.68]">{analysis.architecture.summary}</p>
            )}
            <div className="flex flex-wrap gap-2">
              {analysis.summary.frameworks.map((framework, index) => (
                <Badge key={`${framework}-${index}`}>{framework}</Badge>
              ))}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {analysis.architecture.boundaries.slice(0, 4).map((boundary, index) => (
                <div key={`${boundary}-${index}`} className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3 text-sm leading-6 text-white/[0.62]">
                  {boundary}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FolderTree className="h-5 w-5 text-amber-200" />
              Repository Explorer
            </CardTitle>
            <CardDescription>Top-level areas detected by the scanner</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="folders">
              <TabsList>
                <TabsTrigger value="folders">Folders</TabsTrigger>
                <TabsTrigger value="files">Important Files</TabsTrigger>
                <TabsTrigger value="flow">Flow</TabsTrigger>
              </TabsList>
              <TabsContent value="folders" className="space-y-3">
                {analysis.summary.folders.slice(0, 7).map((folder, index) => (
                  <div key={`${folder.path}-${index}`} className="flex items-start justify-between gap-3 rounded-lg border border-white/[0.08] bg-black/[0.22] p-3">
                    <div>
                      <div className="font-mono text-sm text-white">{folder.path}</div>
                      <p className="mt-1 text-xs leading-5 text-white/[0.48]">{folder.description}</p>
                    </div>
                    <Badge variant="neutral">{folder.role}</Badge>
                  </div>
                ))}
              </TabsContent>
              <TabsContent value="files" className="space-y-3">
                {analysis.summary.important_files.slice(0, 8).map((file, index) => (
                  <div key={`${file.path}-${index}`} className="rounded-lg border border-white/[0.08] bg-black/[0.22] p-3">
                    <div className="flex items-center gap-2 font-mono text-sm text-white">
                      <FileCode2 className="h-4 w-4 text-teal-200" />
                      {file.path}
                    </div>
                    <p className="mt-2 text-xs leading-5 text-white/[0.48]">{file.reason}</p>
                  </div>
                ))}
              </TabsContent>
              <TabsContent value="flow" className="space-y-3">
                {analysis.architecture.dependency_flow.map((flow, index) => (
                  <div key={`${flow}-${index}`} className="flex gap-3 rounded-lg border border-white/[0.08] bg-black/[0.22] p-3 text-sm text-white/[0.62]">
                    <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-amber-200" />
                    {flow}
                  </div>
                ))}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        <Card className="glass-panel lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="h-5 w-5 text-teal-200" />
              Onboarding Insights
            </CardTitle>
            <CardDescription>Generated by the Onboarding Agent</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            {analysis.contributor_plan.roadmap.map((step, index) => (
              <div key={`${step.title}-${index}`} className="rounded-lg border border-white/[0.08] bg-black/[0.22] p-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono text-xs text-teal-200">0{index + 1}</span>
                  <Badge variant={step.difficulty === "easy" ? "default" : "amber"}>{step.difficulty}</Badge>
                </div>
                <h3 className="mt-3 text-sm font-semibold text-white">{step.title}</h3>
                <p className="mt-2 text-sm leading-6 text-white/[0.54]">{step.description}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-amber-200" />
              Recommendations
            </CardTitle>
            <CardDescription>High-signal next actions</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {analysis.summary.recommendations.map((recommendation, index) => (
              <div key={`${recommendation}-${index}`} className="rounded-lg border border-white/[0.08] bg-black/[0.22] p-3 text-sm leading-6 text-white/[0.62]">
                {recommendation}
              </div>
            ))}
            <div className="pt-2">
              <div className="text-xs font-medium uppercase tracking-[0.16em] text-white/[0.34]">Language profile</div>
              <div className="mt-3 space-y-2">
                {topLanguages.map(([language, count]) => (
                  <div key={language}>
                    <div className="flex justify-between text-xs text-white/[0.58]">
                      <span>{language}</span>
                      <span>{count}</span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/[0.08]">
                      <div
                        className="h-full rounded-full bg-teal-300"
                        style={{ width: `${Math.max(8, (count / Math.max(1, topLanguages[0]?.[1] ?? 1)) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1fr_420px]">
        <GoodFirstIssueList intelligence={analysis.intelligence} />
        <RiskRadar intelligence={analysis.intelligence} />
      </section>

      <OwnershipMap intelligence={analysis.intelligence} />
    </div>
  );
}
