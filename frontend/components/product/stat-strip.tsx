import { Badge } from "@/components/ui/badge";
import type { AnalysisResult } from "@/lib/types";

export function StatStrip({ analysis }: { analysis: AnalysisResult }) {
  const languageTotal = Object.values(analysis.summary.languages).reduce((sum, count) => sum + count, 0);
  const stats = [
    { label: "Files mapped", value: languageTotal.toLocaleString() },
    { label: "Frameworks", value: analysis.summary.frameworks.length.toString() },
    { label: "Complexity", value: `${analysis.intelligence.complexity.score}/100` },
    { label: "Good-first issues", value: analysis.intelligence.good_first_issues.length.toString() },
  ];
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat) => (
        <div key={stat.label} className="glass-panel rounded-lg px-4 py-4">
          <div className="text-xs text-white/[0.44]">{stat.label}</div>
          <div className="mt-2 flex items-end justify-between">
            <div className="text-2xl font-semibold text-white">{stat.value}</div>
            <Badge variant="neutral">live</Badge>
          </div>
        </div>
      ))}
    </div>
  );
}
