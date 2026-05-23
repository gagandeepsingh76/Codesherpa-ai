from __future__ import annotations

from backend.models import ArchitectureEdge, ArchitectureMap, ArchitectureNode, RepositoryScan


class ArchitectureMappingAgent:
    name = "Architecture Mapping Agent"

    def run(self, scan: RepositoryScan) -> ArchitectureMap:
        nodes = self._nodes(scan)
        edges = self._edges(scan, nodes)
        boundaries = self._boundaries(nodes, scan.frameworks)
        dependency_flow = self._dependency_flow(scan, nodes)
        summary = self._summary(scan, nodes)
        confidence = "high" if scan.frameworks and scan.entry_points else "medium"
        return ArchitectureMap(
            summary=summary,
            boundaries=boundaries,
            nodes=nodes,
            edges=edges,
            dependency_flow=dependency_flow,
            confidence=confidence,
        )

    @staticmethod
    def _nodes(scan: RepositoryScan) -> list[ArchitectureNode]:
        nodes: list[ArchitectureNode] = []
        for folder in scan.folders[:10]:
            node_type = folder.role if folder.role in {"frontend", "backend", "shared", "data", "infra", "docs", "tests"} else "package"
            nodes.append(
                ArchitectureNode(
                    id=folder.path,
                    label=folder.path,
                    type=node_type,  # type: ignore[arg-type]
                    description=folder.description,
                    confidence=folder.confidence,
                )
            )

        if scan.manifests and "manifest" not in {node.id for node in nodes}:
            nodes.append(
                ArchitectureNode(
                    id="manifest",
                    label="manifests",
                    type="config",
                    description="Dependency and runtime configuration source.",
                    confidence="high",
                )
            )
        return nodes[:12]

    @staticmethod
    def _edges(scan: RepositoryScan, nodes: list[ArchitectureNode]) -> list[ArchitectureEdge]:
        ids = [node.id for node in nodes]
        edges: list[ArchitectureEdge] = []
        if "manifest" in ids:
            for node in nodes:
                if node.id != "manifest" and node.type in {"frontend", "backend", "shared", "package"}:
                    edges.append(ArchitectureEdge(source="manifest", target=node.id, label="configures", confidence="medium"))
        frontends = [node.id for node in nodes if node.type == "frontend"]
        backends = [node.id for node in nodes if node.type == "backend"]
        shared = [node.id for node in nodes if node.type == "shared"]
        tests = [node.id for node in nodes if node.type == "tests"]
        for frontend in frontends:
            for target in shared[:2]:
                edges.append(ArchitectureEdge(source=frontend, target=target, label="uses", confidence="medium"))
            for backend in backends[:1]:
                edges.append(ArchitectureEdge(source=frontend, target=backend, label="calls", confidence="low"))
        for backend in backends:
            for target in shared[:2]:
                edges.append(ArchitectureEdge(source=backend, target=target, label="uses", confidence="medium"))
        for test in tests:
            for target in (frontends + backends + shared)[:2]:
                edges.append(ArchitectureEdge(source=test, target=target, label="validates", confidence="medium"))
        return edges[:18]

    @staticmethod
    def _boundaries(nodes: list[ArchitectureNode], frameworks: list[str]) -> list[str]:
        boundaries: list[str] = []
        if any(node.type == "frontend" for node in nodes):
            boundaries.append("Frontend boundary detected from UI/app folders and framework signals.")
        if any(node.type == "backend" for node in nodes):
            boundaries.append("Backend or API boundary detected from server/API folders.")
        if any(node.type == "shared" for node in nodes):
            boundaries.append("Shared implementation boundary contains reusable source or package code.")
        if "Next.js App Router" in frameworks:
            boundaries.append("Next.js App Router suggests route-level UI and server behavior may live together under `app/`.")
        if not boundaries:
            boundaries.append("Architecture boundaries are inferred mostly from top-level folders; inspect entry points for certainty.")
        return boundaries

    @staticmethod
    def _dependency_flow(scan: RepositoryScan, nodes: list[ArchitectureNode]) -> list[str]:
        flow: list[str] = []
        if scan.package_managers:
            flow.append(f"Dependencies enter through {', '.join(scan.package_managers)} manifests.")
        if scan.entry_points:
            flow.append(f"Runtime exploration should start at {', '.join(scan.entry_points[:3])}.")
        source_nodes = [node.label for node in nodes if node.type in {"frontend", "backend", "shared", "package"}]
        if source_nodes:
            flow.append(f"Primary source areas: {', '.join(source_nodes[:5])}.")
        test_nodes = [node.label for node in nodes if node.type == "tests"]
        if test_nodes:
            flow.append(f"Validation appears under {', '.join(test_nodes[:3])}.")
        return flow

    @staticmethod
    def _summary(scan: RepositoryScan, nodes: list[ArchitectureNode]) -> str:
        frameworks = ", ".join(scan.frameworks[:4]) if scan.frameworks else "the detected language stack"
        source_areas = ", ".join(node.label for node in nodes if node.type in {"frontend", "backend", "shared", "package"}) or "top-level source folders"
        return f"The repository is organized around {frameworks}. The main implementation surface appears in {source_areas}, with configuration and dependency signals coming from the detected manifests."
