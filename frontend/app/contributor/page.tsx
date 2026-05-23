import { AppShell } from "@/components/product/app-shell";
import { ContributorPanel } from "@/components/product/contributor-panel";

export default function ContributorPage() {
  return (
    <AppShell active="contributor">
      <ContributorPanel />
    </AppShell>
  );
}
