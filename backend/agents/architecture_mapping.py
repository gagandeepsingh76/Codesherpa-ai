from __future__ import annotations

from backend.models import ArchitectureMap, RepositoryScan
from backend.services.dependency_graph import RepositoryDependencyGraph


class ArchitectureMappingAgent:
    name = "Architecture Mapping Agent"

    def __init__(self) -> None:
        self.graph = RepositoryDependencyGraph()

    def run(self, scan: RepositoryScan) -> ArchitectureMap:
        return self.graph.analyze(scan)
