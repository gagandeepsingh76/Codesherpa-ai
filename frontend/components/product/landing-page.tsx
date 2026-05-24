"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Bot, BrainCircuit, GitBranch, Map, MemoryStick, Radio, Route, ShieldCheck, Sparkles } from "lucide-react";

import { TimelinePanel } from "@/components/product/timeline-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { demoAnalysis, demoTimeline } from "@/lib/demo-data";

const features = [
  {
    icon: GitBranch,
    title: "Repository Analysis Agent",
    description: "Scans structure, manifests, frameworks, entry points, and important files.",
  },
  {
    icon: Map,
    title: "Architecture Mapping Agent",
    description: "Turns folders and dependencies into a navigable system map.",
  },
  {
    icon: Route,
    title: "Contributor Mode",
    description: "Generates beginner files, first tasks, and learning sequence.",
  },
  {
    icon: MemoryStick,
    title: "Persistent Memory",
    description: "Remembers analyzed repositories, questions, summaries, and guidance.",
  },
];

export function LandingPage() {
  return (
    <main className="min-h-screen overflow-hidden">
      <div className="pointer-events-none fixed inset-0 premium-grid opacity-45" />
      <section className="relative mx-auto grid min-h-screen w-full max-w-7xl gap-10 px-4 pb-10 pt-5 sm:px-6 lg:grid-cols-[1fr_460px] lg:px-8">
        <div className="flex flex-col">
          <header className="glass-panel flex items-center justify-between rounded-lg px-4 py-3">
            <Link href="/" className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-teal-300/20 bg-teal-300/10">
                <Bot className="h-5 w-5 text-teal-200" />
              </div>
              <div>
                <div className="text-sm font-semibold text-white">CodeSherpa AI</div>
                <div className="text-xs text-white/[0.48]">GitAgent-powered repo intelligence</div>
              </div>
            </Link>
            <Button asChild size="sm" variant="secondary">
              <Link href="/dashboard">Open Console</Link>
            </Button>
          </header>

          <div className="flex flex-1 flex-col justify-center py-16 lg:py-0">
            <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.55 }}>
              <Badge variant="amber" className="mb-5">
                autonomous GitAgent OS for repositories
              </Badge>
              <h1 className="max-w-4xl text-5xl font-semibold leading-[1.02] tracking-normal text-white sm:text-7xl">
                CodeSherpa AI
              </h1>
              <p className="mt-5 max-w-2xl text-xl leading-8 text-white/[0.68]">Understand any repository in minutes.</p>
              <p className="mt-4 max-w-3xl text-base leading-8 text-white/[0.58]">
                An AI onboarding and contribution copilot for open-source repositories. Paste a GitHub URL and watch specialized agents clone, scan, map, score, explain, and remember the codebase through a live cinematic workflow.
              </p>

              <div className="mt-8 max-w-2xl rounded-lg border border-white/10 bg-black/[0.24] p-3">
                <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-center">
                  <Input readOnly placeholder="Enter your GitHub repository link..." aria-label="Repository URL preview" className="flex-1 placeholder:text-white/[0.30]" />
                  <Button asChild className="w-full shrink-0 sm:w-[168px]">
                    <Link href="/dashboard">
                      Analyze repo
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </Button>
                </div>
                <div className="mt-2 px-1 text-xs text-white/[0.42]">Example: github.com/user/repository</div>
              </div>

              <div className="mt-8 flex flex-wrap gap-3">
                {["agent.yaml", "SOUL.md", "RULES.md", "skills/", "memory/", "workflows/"].map((item) => (
                  <Badge key={item} variant="neutral">
                    {item}
                  </Badge>
                ))}
              </div>
            </motion.div>
          </div>
        </div>

        <div className="flex items-center pb-8 lg:pb-0">
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.65, delay: 0.1 }}
            className="w-full space-y-5"
          >
            <TimelinePanel events={demoTimeline} compact />
            <div className="glass-panel rounded-lg p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-mono text-xs uppercase tracking-[0.16em] text-white/[0.38]">architecture graph</div>
                  <div className="mt-1 text-sm font-medium text-white">{demoAnalysis.summary.name}</div>
                </div>
                <Badge>{demoAnalysis.architecture.confidence} confidence</Badge>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-3">
                {demoAnalysis.architecture.nodes.slice(0, 6).map((node) => (
                  <div key={node.id} className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
                    <div className="h-1.5 w-8 rounded-full bg-teal-300/70" />
                    <div className="mt-3 truncate font-mono text-xs text-white">{node.label}</div>
                    <div className="mt-1 truncate text-[11px] text-white/[0.38]">{node.type}</div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      <section className="relative mx-auto w-full max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {features.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 18 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-80px" }}
                transition={{ duration: 0.35, delay: index * 0.05 }}
                className="glass-panel rounded-lg p-5"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-teal-300/20 bg-teal-300/10">
                  <Icon className="h-5 w-5 text-teal-200" />
                </div>
                <h2 className="mt-5 text-base font-semibold text-white">{feature.title}</h2>
                <p className="mt-3 text-sm leading-6 text-white/[0.52]">{feature.description}</p>
              </motion.div>
            );
          })}
        </div>
      </section>

      <section className="relative mx-auto grid w-full max-w-7xl gap-6 px-4 pb-20 sm:px-6 lg:grid-cols-3 lg:px-8">
        <div className="glass-panel rounded-lg p-5">
          <Radio className="h-5 w-5 text-amber-200" />
          <h2 className="mt-4 text-lg font-semibold text-white">Live workflow telemetry</h2>
          <p className="mt-2 text-sm leading-6 text-white/[0.54]">Every autonomous step becomes observable, from clone to contributor roadmap.</p>
        </div>
        <div className="glass-panel rounded-lg p-5">
          <BrainCircuit className="h-5 w-5 text-teal-200" />
          <h2 className="mt-4 text-lg font-semibold text-white">Repository-specific chat</h2>
          <p className="mt-2 text-sm leading-6 text-white/[0.54]">Answers are grounded in remembered analysis, cited files, and confidence levels.</p>
        </div>
        <div className="glass-panel rounded-lg p-5">
          <ShieldCheck className="h-5 w-5 text-emerald-200" />
          <h2 className="mt-4 text-lg font-semibold text-white">Read-only by design</h2>
          <p className="mt-2 text-sm leading-6 text-white/[0.54]">The scanner clones and reads repositories without executing or modifying project code.</p>
        </div>
        <div className="glass-panel rounded-lg p-5 lg:col-span-3">
          <div className="grid gap-4 md:grid-cols-4">
            {[
              ["Complexity scoring", "Quantifies onboarding difficulty from deterministic repo signals."],
              ["Good-first issues", "Generates scoped contribution ideas grounded in detected files."],
              ["Ownership mapping", "Groups folders into responsibility surfaces without inventing maintainers."],
              ["Risk radar", "Highlights docs, test, dependency, and CI risks that slow contributors."],
            ].map(([title, description]) => (
              <div key={title} className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-4">
                <div className="text-sm font-semibold text-white">{title}</div>
                <p className="mt-2 text-xs leading-5 text-white/[0.46]">{description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="pointer-events-none fixed bottom-6 right-6 hidden rounded-lg border border-white/10 bg-black/55 px-3 py-2 font-mono text-xs text-white/[0.44] backdrop-blur md:block">
        <Sparkles className="mr-2 inline h-3.5 w-3.5 text-teal-200" />
        codesherpa.agent.ready
        <span className="animate-cursor">_</span>
      </div>
    </main>
  );
}
