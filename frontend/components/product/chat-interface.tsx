"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Bot, CornerDownLeft, FileCode2, Loader2, MessageSquare, User } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { loadAnalysis, sendChat } from "@/lib/api";
import type { AnalysisResult, ChatResponse } from "@/lib/types";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  citations?: string[];
  confidence?: string;
};

const prompts = [
  "How authentication works?",
  "Where are API routes?",
  "Explain state management",
  "Suggest good first issues",
  "What is the complexity and risk profile?",
  "How should a beginner start?",
];

export function ChatInterface() {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("How should a beginner start?");
  const [isSending, setIsSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const loaded = loadAnalysis();
    setAnalysis(loaded);
    setMessages([
      {
        role: "assistant",
        content: `Repository memory is loaded for ${loaded.summary.name}. Ask about architecture, APIs, onboarding, dependencies, or contribution paths.`,
        citations: loaded.summary.entry_points.slice(0, 3),
        confidence: "high",
      },
    ]);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function submit(message = input) {
    if (!analysis || !message.trim()) return;
    setIsSending(true);
    setMessages((current) => [...current, { role: "user", content: message }]);
    setInput("");
    try {
      const response: ChatResponse = await sendChat(analysis.repo_id, message);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.answer,
          citations: response.cited_files,
          confidence: response.confidence,
        },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  if (!analysis) {
    return null;
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <section className="glass-panel flex min-h-[740px] flex-col overflow-hidden rounded-lg">
        <div className="border-b border-white/10 px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-teal-300/20 bg-teal-300/10">
                <MessageSquare className="h-4 w-4 text-teal-200" />
              </div>
              <div>
                <h1 className="text-base font-semibold text-white">Repository Chat</h1>
                <p className="text-xs text-white/[0.48]">{analysis.summary.name}</p>
              </div>
            </div>
            <Badge variant="neutral">memory-backed</Badge>
          </div>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {messages.map((message, index) => (
            <motion.div
              key={`${message.role}-${index}`}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
              className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {message.role === "assistant" ? (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-teal-300/20 bg-teal-300/10">
                  <Bot className="h-4 w-4 text-teal-200" />
                </div>
              ) : null}
              <div className={`max-w-[780px] rounded-lg border p-4 ${message.role === "user" ? "border-amber-300/20 bg-amber-300/10" : "border-white/10 bg-black/[0.26]"}`}>
                <div className="whitespace-pre-wrap text-sm leading-7 text-white/[0.72]">{message.content}</div>
                {message.citations?.length ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {message.citations.map((file, fileIndex) => (
                      <Badge key={`${file}-${fileIndex}`} variant="neutral" className="gap-1">
                        <FileCode2 className="h-3 w-3" />
                        {file}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </div>
              {message.role === "user" ? (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-amber-300/20 bg-amber-300/10">
                  <User className="h-4 w-4 text-amber-200" />
                </div>
              ) : null}
            </motion.div>
          ))}
          {isSending ? (
            <div className="flex items-center gap-3 text-sm text-white/[0.48]">
              <Loader2 className="h-4 w-4 animate-spin text-teal-200" />
              CodeSherpa is grounding the answer in repository memory
              <span className="animate-cursor">_</span>
            </div>
          ) : null}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-white/10 p-4">
          <div className="flex flex-col gap-3">
            <Textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                void submit();
              }
            }} />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap gap-2">
                {prompts.slice(0, 3).map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => setInput(prompt)}
                    className="rounded-md border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-xs text-white/[0.56] transition hover:bg-white/[0.08] hover:text-white"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
              <Button onClick={() => void submit()} disabled={isSending || !input.trim()}>
                {isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CornerDownLeft className="h-4 w-4" />}
                Send
              </Button>
            </div>
          </div>
        </div>
      </section>

      <aside className="space-y-6">
        <div className="glass-panel rounded-lg p-5">
          <Badge variant="amber" className="mb-4">
            suggested questions
          </Badge>
          <div className="space-y-2">
            {prompts.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => void submit(prompt)}
                className="w-full rounded-lg border border-white/[0.08] bg-black/[0.24] px-3 py-3 text-left text-sm text-white/[0.62] transition hover:border-teal-300/25 hover:bg-teal-300/10 hover:text-white"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
        <div className="glass-panel rounded-lg p-5">
          <div className="text-sm font-semibold text-white">Repository Context</div>
          <div className="mt-4 space-y-3">
            {analysis.summary.important_files.slice(0, 6).map((file, index) => (
              <div key={`${file.path}-${index}`} className="rounded-lg border border-white/[0.08] bg-black/[0.24] p-3">
                <div className="font-mono text-xs text-white">{file.path}</div>
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-white/[0.46]">{file.reason}</p>
              </div>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}
