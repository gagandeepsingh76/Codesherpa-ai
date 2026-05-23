import Link from "next/link";
import { Bot, GitBranch, Map, MessageSquare, Route, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: GitBranch },
  { href: "/architecture", label: "Architecture", icon: Map },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/contributor", label: "Contributor", icon: Route },
];

export function AppShell({
  children,
  active,
}: {
  children: React.ReactNode;
  active?: "dashboard" | "architecture" | "chat" | "contributor";
}) {
  return (
    <main className="min-h-screen overflow-hidden">
      <div className="pointer-events-none fixed inset-0 premium-grid opacity-45" />
      <div className="relative mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
        <header className="glass-panel flex items-center justify-between rounded-lg px-4 py-3">
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-teal-300/20 bg-teal-300/10">
              <Bot className="h-5 w-5 text-teal-200" />
            </div>
            <div>
              <div className="text-sm font-semibold text-white">CodeSherpa AI</div>
              <div className="text-xs text-white/[0.48]">Understand any repository in minutes.</div>
            </div>
          </Link>
          <nav className="hidden items-center gap-1 md:flex">
            {navItems.map((item) => {
              const Icon = item.icon;
              const itemActive = active === item.href.replace("/", "");
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-white/[0.58] transition hover:bg-white/[0.07] hover:text-white",
                    itemActive && "bg-white/[0.09] text-white",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="flex items-center gap-2">
            <Badge variant="neutral" className="hidden sm:inline-flex">
              GitAgent native
            </Badge>
            <Button asChild size="sm" variant="secondary">
              <Link href="/dashboard">
                <Sparkles className="h-4 w-4" />
                Analyze
              </Link>
            </Button>
          </div>
        </header>
        {children}
      </div>
    </main>
  );
}
