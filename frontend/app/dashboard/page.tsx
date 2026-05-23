import { AppShell } from "@/components/product/app-shell";
import { RepositoryDashboard } from "@/components/product/repository-dashboard";

export default function DashboardPage() {
  return (
    <AppShell active="dashboard">
      <RepositoryDashboard />
    </AppShell>
  );
}
