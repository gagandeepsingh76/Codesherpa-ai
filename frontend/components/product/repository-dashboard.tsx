"use client";

import { useMemo, useState } from "react";
import type {
  ChangeEvent,
  KeyboardEvent,
  MouseEvent,
} from "react";
import { motion } from "framer-motion";
import {
  ArrowRight,
  BrainCircuit,
  FileCode2,
  FolderTree,
  GitBranch,
  Loader2,
  Play,
  Sparkles,
} from "lucide-react";

import { TimelinePanel } from "@/components/product/timeline-panel";
import { StatStrip } from "@/components/product/stat-strip";
import {
  ComplexityMeter,
  GoodFirstIssueList,
  OwnershipMap,
  RiskRadar,
} from "@/components/product/intelligence-panel";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";

import {
  analysisPhase,
  analyzeRepository,
  createPendingAnalysis,
  loadAnalysis,
  normalizeRepositoryUrl,
} from "@/lib/api";

import { demoTimeline } from "@/lib/demo-data";

import type {
  AnalysisResult,
  TimelineEvent,
} from "@/lib/types";

export function RepositoryDashboard() {
  const [repoUrl, setRepoUrl] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisResult>(() =>
    loadAnalysis(),
  );

  const [events, setEvents] = useState<TimelineEvent[]>(
    analysis.timeline,
  );

  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const phase = analysisPhase(analysis);

  const isProgressing =
    isAnalyzing &&
    phase !== "complete" &&
    phase !== "cached";

  const deepStatus =
    typeof analysis.agent_manifest.workflow.deep_status ===
      "string"
      ? analysis.agent_manifest.workflow.deep_status
      : "ready";

  const isDeepLoading =
    isAnalyzing &&
    phase !== "cached" &&
    deepStatus !== "ready";

  const canAnalyze =
    repoUrl.trim().length > 0 && !isAnalyzing;

  const topLanguages = useMemo(
    () =>
      Object.entries(analysis.summary.languages)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5),
    [analysis.summary.languages],
  );

  async function handleAnalyze() {
    if (isAnalyzing) {
      return;
    }

    const normalizedRepoUrl =
      normalizeRepositoryUrl(repoUrl);

    if (!normalizedRepoUrl) {
      setError(
        "Enter a GitHub repository link to start analysis.",
      );
      return;
    }

    const pending =
      createPendingAnalysis(normalizedRepoUrl);

    setAnalysis(pending);
    setIsAnalyzing(true);
    setError(null);
    setEvents(pending.timeline);

    try {
      const result = await analyzeRepository(
        normalizedRepoUrl,
        (event) => {
          setEvents((current) =>
            [
              ...current.filter(
                (item) => item.id !== event.id,
              ),
              event,
            ].slice(-14),
          );
        },
        (partial) => {
          setAnalysis(partial);
          setEvents(partial.timeline.slice(-14));
        },
      );

      setAnalysis(result);
      setEvents(result.timeline);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Analysis failed. Showing demo analysis.",
      );

      setEvents(demoTimeline);
    } finally {
      setIsAnalyzing(false);
    }
  }

  function handleRepoUrlChange(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    setRepoUrl(event.currentTarget.value);
  }

  function handleRepoUrlKeyDown(
    event: KeyboardEvent<HTMLInputElement>,
  ) {
    if (event.key !== "Enter") {
      return;
    }

    event.preventDefault();
    event.stopPropagation();

    if (!canAnalyze) {
      return;
    }

    void handleAnalyze();
  }

  function handleAnalyzeButtonClick(
    event: MouseEvent<HTMLButtonElement>,
  ) {
    event.preventDefault();
    event.stopPropagation();

    if (!canAnalyze) {
      return;
    }

    void handleAnalyze();
  }

  return (
    <div className="min-w-0 space-y-6">
      <section className="grid min-w-0 items-start gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(520px,1.05fr)] 2xl:grid-cols-[minmax(0,0.95fr)_minmax(600px,1.05fr)]">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45 }}
          className="glass-panel min-w-0 rounded-lg p-5 sm:p-6"
        >
          <div className="flex flex-col gap-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <Badge
                  variant="amber"
                  className="mb-3"
                >
                  autonomous repository workflow
                </Badge>

                <h1 className="max-w-3xl text-3xl font-semibold tracking-normal text-white sm:text-5xl">
                  Repository intelligence,
                  streamed as agents work.
                </h1>

                <p className="mt-4 max-w-2xl break-words text-base leading-7 text-white/[0.62]">
                  CodeSherpa clones, scans,
                  maps, explains, and remembers
                  a repository through a
                  GitAgent-native workflow.
                </p>
              </div>

              <div className="max-w-full rounded-lg border border-teal-300/20 bg-teal-300/10 px-3 py-2 font-mono text-xs text-teal-100">
                {analysis.repo_id}
              </div>
            </div>

            <div
              className="pointer-events-auto relative z-10 w-full rounded-lg border border-white/10 bg-black/[0.24] p-3 sm:p-4"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="grid min-w-0 gap-3 sm:grid-cols-[minmax(0,1fr)_188px] sm:items-start">
                <div className="min-w-0">
                  <Input
                    id="repository-url"
                    name="repository-url"
                    type="url"
                    inputMode="url"
                    autoCapitalize="none"
                    autoComplete="url"
                    autoCorrect="off"
                    spellCheck={false}
                    value={repoUrl}
                    onChange={handleRepoUrlChange}
                    onKeyDown={handleRepoUrlKeyDown}
                    placeholder="Enter your GitHub repository link..."
                    aria-label="GitHub repository URL"
                    className="h-12 w-full rounded-lg border border-white/10 bg-black/[0.38] px-4 text-sm text-white outline-none transition-all duration-200 placeholder:text-white/[0.32] focus:border-teal-300/60 focus:ring-2 focus:ring-teal-300/20"
                  />

                  <div className="mt-2 px-1 text-xs text-white/[0.42]">
                    Example: github.com/user/repository
                  </div>
                </div>

                <Button
                  type="button"
                  disabled={!canAnalyze}
                  aria-busy={isAnalyzing}
                  onClick={handleAnalyzeButtonClick}
                  className="h-12 w-full rounded-lg bg-teal-300 text-black transition-all duration-200 hover:bg-teal-200 disabled:opacity-60 sm:w-[188px]"
                >
                  {isAnalyzing ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    <>
                      <Play className="mr-2 h-4 w-4" />
                      Analyze Repository
                    </>
                  )}
                </Button>
              </div>
            </div>

            {error ? (
              <div className="rounded-lg border border-red-300/20 bg-red-300/10 px-4 py-3 text-sm text-red-100">
                {error}
              </div>
            ) : null}

            <StatStrip
              analysis={analysis}
              isLoading={isProgressing}
            />
          </div>
        </motion.div>

        <TimelinePanel
          events={events}
          compact
          layout="console"
        />
      </section>

      {/* KEEP REST OF YOUR FILE SAME */}
    </div>
  );
}
