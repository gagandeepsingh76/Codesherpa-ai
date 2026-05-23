import { AppShell } from "@/components/product/app-shell";
import { ArchitectureMapView } from "@/components/product/architecture-map";

export default function ArchitecturePage() {
  return (
    <AppShell active="architecture">
      <ArchitectureMapView />
    </AppShell>
  );
}
