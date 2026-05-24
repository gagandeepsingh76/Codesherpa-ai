import { Badge } from "@/components/ui/badge";
import type { AnalysisResult } from "@/lib/types";

export function StatStrip({ analysis, isLoading = false }: { analysis: AnalysisResult; isLoading?: boolean }) {
  const languageTotal = Object.values(analysis.summary.languages).reduce((sum, count) => sum + count, 0);
  const stats = [
    { label: "Files mapped", value: languageTotal.toLocaleString() },
    { label: "Frameworks", value: analysis.summary.frameworks.length.toString() },
    { label: "Complexity", value: `${analysis.intelligence.complexity.score}/100` },
    { label: "Good-first issues", value: analysis.intelligence.good_first_issues.length.toString() },
  ];
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {stats.map((stat) => (
        <div key={stat.label} className="glass-panel flex min-h-[116px] min-w-0 flex-col justify-between rounded-lg px-4 py-4">
          <div className="flex min-w-0 items-start justify-between gap-3">
            <div className="min-w-0 truncate text-xs text-white/[0.46]">{stat.label}</div>
            <Badge variant={isLoading ? "amber" : "neutral"} className="px-2 py-0.5 text-[10px]">
              {isLoading ? "streaming" : "live"}
            </Badge>
          </div>
          <div className="mt-4 min-w-0">
            <div className="break-words text-[1.35rem] font-semibold leading-none text-white sm:text-2xl">{stat.value}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
