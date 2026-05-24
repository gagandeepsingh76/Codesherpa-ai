from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Awaitable, Callable

from backend.agents.architecture_mapping import ArchitectureMappingAgent
from backend.agents.documentation import DocumentationAgent
from backend.agents.issue_debugging import IssueDebuggingAgent
from backend.agents.onboarding import OnboardingAgent
from backend.agents.repository_analysis import RepositoryAnalysisAgent
from backend.agents.repository_intelligence import RepositoryIntelligenceAgent
from backend.models import (
    AnalysisResult,
    ArchitectureMap,
    ArchitectureNode,
    ChatResponse,
    ComplexityScore,
    ContributorPlan,
    RepositoryCodeIntelligence,
    RepositoryIntelligence,
    RepositoryScan,
    TimelineEvent,
)
from backend.services.git_service import GitService
from backend.services.gitagent_registry import GitAgentRegistry
from backend.services.code_intelligence import CodeIntelligenceWork, RepositoryCodeIntelligenceBuilder, RepositorySemanticRetriever
from backend.services.llm_service import LLMService
from backend.services.memory_store import MemoryStore
from backend.services.repository_scanner import RepositoryScanner
from backend.services.timeline import TimelineEmitter, TimelineRecorder
from backend.utils.ids import stable_repo_id


AnalysisEmitter = Callable[[str, AnalysisResult], Awaitable[None] | None]

ARCHITECTURE_TIMEOUT_SECONDS = 18
CLONE_TIMEOUT_SECONDS = 45
DEEP_INTELLIGENCE_TIMEOUT_SECONDS = 22
SCAN_TIMEOUT_SECONDS = 10
SYMBOL_TIMEOUT_SECONDS = 24
MAX_DEPENDENCY_GRAPH_SOURCE_FILES = 1800
MAX_SYMBOL_SOURCE_FILES = 1600
SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".css", ".scss", ".sass", ".html", ".md", ".mdx"}
CODE_SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}


class RepositoryUnderstandingWorkflow:
    def __init__(self) -> None:
        self.registry = GitAgentRegistry()
        self.git = GitService()
        self.scanner = RepositoryScanner()
        self.memory = MemoryStore()
        self.llm = LLMService(self.registry)
        self.repository_agent = RepositoryAnalysisAgent()
        self.architecture_agent = ArchitectureMappingAgent()
        self.code_intelligence = RepositoryCodeIntelligenceBuilder()
        self.retriever = RepositorySemanticRetriever()
        self.onboarding_agent = OnboardingAgent()
        self.issue_agent = IssueDebuggingAgent()
        self.documentation_agent = DocumentationAgent()
        self.intelligence_agent = RepositoryIntelligenceAgent()

    async def run(
        self,
        repo_url: str,
        emitter: TimelineEmitter | None = None,
        use_cache: bool = False,
        result_emitter: AnalysisEmitter | None = None,
    ) -> AnalysisResult:
        repo_id = stable_repo_id(repo_url)
        timeline = TimelineRecorder(repo_id, emitter)

        await timeline.add(
            "GitAgent Runtime",
            "CodeSherpa GitAgent initialized",
            "Loaded agent.yaml, SOUL.md, RULES.md, skills, tools, and workflow definitions.",
            confidence="high",
            metadata={"skills": self.registry.manifest.get("skills", [])},
        )

        if use_cache:
            cached = self.memory.get_analysis_by_url(repo_url)
            if cached:
                await timeline.add(
                    "GitAgent Memory",
                    "Cached repository intelligence restored",
                    "Reused persisted repository memory immediately instead of repeating a full clone, graph build, and semantic pass.",
                    confidence="high" if cached.get("code_intelligence", {}).get("semantic_memory") else "medium",
                )
                result = AnalysisResult.model_validate(cached)
                result.timeline = timeline.events + result.timeline
                result.agent_manifest = self._manifest_public_payload(
                    "cached",
                    cache_status="hit",
                    deep_status="ready" if result.code_intelligence.semantic_memory else "metadata",
                )
                await self._emit_result("cached", result, result_emitter)
                return result

        await timeline.add(
            self.repository_agent.name,
            "Fast repository analysis started",
            "Preparing an isolated shallow checkout, manifest scan, and root-only dashboard shell.",
            status="running",
            confidence="high",
            metadata={"phase": "phase1-fast"},
        )

        repo_path = await self._with_timeout(
            self.git.clone_or_update(repo_url),
            CLONE_TIMEOUT_SECONDS,
            "Repository checkout timed out before analysis could start.",
        )
        await timeline.add(
            self.repository_agent.name,
            "Cloning repository",
            f"Repository materialized at {repo_path}. No repository code was executed.",
            confidence="high",
        )

        default_branch = await self.git.default_branch(repo_path)
        await timeline.add(
            self.repository_agent.name,
            "Detecting frameworks",
            "Reading manifests and canonical config files.",
            status="running",
            confidence="medium",
            metadata={"phase": "phase1-fast"},
        )

        scan = await self._with_timeout(
            asyncio.to_thread(self.scanner.scan, repo_url, repo_path, default_branch),
            SCAN_TIMEOUT_SECONDS,
            "Repository scan timed out while indexing manifests and top-level files.",
        )
        await timeline.add(
            self.repository_agent.name,
            "Scanning repository structure",
            f"Indexed {len(scan.files)} files across {len(scan.folders)} top-level areas.",
            confidence=scan.confidence,
            metadata={"languages": scan.languages, "frameworks": scan.frameworks, "phase": "phase1-fast"},
        )
        if len(scan.files) >= self.scanner.max_files:
            await timeline.add(
                "Repository Safeguards",
                "Large repository cap applied",
                f"Initial scan capped at {self.scanner.max_files:,} files so the dashboard stays responsive.",
                confidence="medium",
                metadata={"phase": "phase1-fast", "max_files": self.scanner.max_files},
            )

        summary = self.repository_agent.run(scan)
        await timeline.add(
            self.repository_agent.name,
            "Identifying important files",
            f"Ranked {len(summary.important_files)} important files and {len(summary.entry_points)} entry points.",
            confidence=summary.confidence,
            metadata={"phase": "phase1-fast"},
        )

        architecture = self._root_architecture(scan)
        contributor_plan = self._shell_contributor_plan(scan)
        intelligence = self._shell_intelligence(scan, architecture)
        code_intelligence = self._shell_code_intelligence(scan)
        phase1_result = self._analysis_result(
            repo_id,
            repo_url,
            summary,
            architecture,
            contributor_plan,
            intelligence,
            code_intelligence,
            timeline,
            phase="phase1",
            deep_status="queued",
        )
        await timeline.add(
            "Dashboard Runtime",
            "Dashboard shell ready",
            "Real repository metadata, framework signals, manifests, and architecture roots are ready while deeper intelligence streams in.",
            confidence="high",
            metadata={"phase": "phase1-fast"},
        )
        phase1_result.timeline = list(timeline.events)
        await self._emit_result("phase1", phase1_result, result_emitter)

        source_file_count = self._source_file_count(scan)
        await timeline.add(
            self.architecture_agent.name,
            "Architecture relationships queued",
            "Building dependency relationships after the dashboard shell is already visible.",
            status="running",
            confidence="high",
            metadata={"phase": "phase2-background", "source_files": source_file_count},
        )
        if source_file_count > MAX_DEPENDENCY_GRAPH_SOURCE_FILES:
            await timeline.add(
                "Repository Safeguards",
                "Dependency graph sampled",
                (
                    f"{source_file_count:,} source-like files were detected. "
                    "CodeSherpa kept the initial architecture-root graph to avoid blocking the dashboard."
                ),
                confidence="medium",
                metadata={"phase": "phase2-background", "source_files": source_file_count},
            )
        else:
            try:
                mapped_architecture = await self._with_timeout(
                    asyncio.to_thread(self.architecture_agent.run, scan),
                    ARCHITECTURE_TIMEOUT_SECONDS,
                    "Dependency graph analysis exceeded the background budget.",
                )
                if mapped_architecture.nodes:
                    architecture = mapped_architecture
                else:
                    architecture.graph_metrics["background_graph_empty"] = True
                await timeline.add(
                    self.architecture_agent.name,
                    "Building dependency graph",
                    f"Generated {len(architecture.nodes)} nodes and {len(architecture.edges)} relationship edges.",
                    confidence=architecture.confidence,
                    metadata={"phase": "phase2-background"},
                )
            except Exception as exc:
                await timeline.add(
                    self.architecture_agent.name,
                    "Dependency graph deferred",
                    f"{exc} The root architecture map remains available.",
                    status="failed",
                    confidence="medium",
                    metadata={"phase": "phase2-background"},
                )
        await timeline.add(
            self.architecture_agent.name,
            "Detecting system boundaries",
            "Classified frontend, backend, shared, tests, docs, and infrastructure areas.",
            confidence=architecture.confidence,
            metadata={"phase": "phase2-background"},
        )

        code_work: CodeIntelligenceWork | None = None
        await timeline.add(
            "Symbol Intelligence Engine",
            "Extracting route and symbol intelligence",
            "Parsing code for concrete symbols, runtime entry points, and API route definitions in the background.",
            status="running",
            confidence="high",
            metadata={"phase": "phase2-background", "source_files": self._code_source_file_count(scan)},
        )
        try:
            code_intelligence, code_work = await self._with_timeout(
                asyncio.to_thread(self.code_intelligence.analyze_symbols, scan, architecture, MAX_SYMBOL_SOURCE_FILES),
                SYMBOL_TIMEOUT_SECONDS,
                "Symbol and route extraction exceeded the background budget.",
            )
        except Exception as exc:
            await timeline.add(
                "Symbol Intelligence Engine",
                "Symbol extraction deferred",
                f"{exc} Semantic memory can be rebuilt on a later cached run.",
                status="failed",
                confidence="medium",
                metadata={"phase": "phase2-background"},
            )
        await timeline.add(
            "Symbol Intelligence Engine",
            "Routes and symbols indexed",
            (
                f"Indexed {len(code_intelligence.symbols)} symbols and {len(code_intelligence.routes)} routes. "
                "Semantic memory and reasoning run lazily next."
            ),
            confidence=code_intelligence.confidence,
            metadata={**code_intelligence.retrieval_stats, "phase": "phase2-background"},
        )
        phase2_result = self._analysis_result(
            repo_id,
            repo_url,
            summary,
            architecture,
            contributor_plan,
            intelligence,
            code_intelligence,
            timeline,
            phase="phase2",
            deep_status="running",
        )
        await self._emit_result("phase2", phase2_result, result_emitter)

        await timeline.add(
            self.onboarding_agent.name,
            "Deep repository intelligence queued",
            "Building contributor guidance, semantic memory, auth/state reasoning, and risk signals after first render.",
            status="running",
            confidence="high",
            metadata={"phase": "phase3-deep"},
        )
        contributor_plan = await asyncio.to_thread(self.onboarding_agent.run, scan)
        await timeline.add(
            self.onboarding_agent.name,
            "Generating onboarding guide",
            f"Created {len(contributor_plan.roadmap)} roadmap steps and {len(contributor_plan.recommended_tasks)} first tasks.",
            confidence=contributor_plan.confidence,
            metadata={"phase": "phase3-deep"},
        )

        if code_work:
            try:
                code_intelligence = await self._with_timeout(
                    asyncio.to_thread(self.code_intelligence.finalize, scan, architecture, code_work),
                    DEEP_INTELLIGENCE_TIMEOUT_SECONDS,
                    "Semantic memory analysis exceeded the lazy deep-analysis budget.",
                )
                await timeline.add(
                    "Symbol Intelligence Engine",
                    "Semantic repository memory built",
                    (
                        f"Indexed {len(code_intelligence.semantic_memory)} grounded memory items with "
                        f"{len(code_intelligence.auth.files)} auth file signals and {len(code_intelligence.state.libraries)} state libraries."
                    ),
                    confidence=code_intelligence.confidence,
                    metadata=code_intelligence.retrieval_stats,
                )
            except Exception as exc:
                await timeline.add(
                    "Symbol Intelligence Engine",
                    "Semantic repository memory deferred",
                    f"{exc} Route and symbol intelligence remain available.",
                    status="failed",
                    confidence="medium",
                    metadata={"phase": "phase3-deep"},
                )

        await timeline.add(
            self.intelligence_agent.name,
            "Repository Intelligence Agent running",
            "Scoring complexity, mapping ownership, and generating contribution opportunities.",
            status="running",
            confidence="high",
            metadata={"phase": "phase3-deep"},
        )
        intelligence = await asyncio.to_thread(self.intelligence_agent.run, scan, architecture)
        contributor_plan.good_first_issues = intelligence.good_first_issues
        contributor_plan.contribution_paths = intelligence.contribution_paths
        await timeline.add(
            self.intelligence_agent.name,
            "Good first issues generated",
            f"Created {len(intelligence.good_first_issues)} scoped issues and {len(intelligence.contribution_paths)} contribution paths.",
            confidence=intelligence.confidence,
            metadata={"phase": "phase3-deep"},
        )
        await timeline.add(
            self.intelligence_agent.name,
            "Complexity and risk model completed",
            f"Complexity scored {intelligence.complexity.score}/100 with {len(intelligence.risks)} risk insights.",
            confidence=intelligence.confidence,
            metadata={"complexity": intelligence.complexity.model_dump(mode="json"), "phase": "phase3-deep"},
        )

        await timeline.add(
            self.documentation_agent.name,
            "Documentation Agent initialized",
            "Preparing durable repository explanation and documentation recommendations.",
            status="running",
            confidence="high",
            metadata={"phase": "phase3-deep"},
        )
        summary.recommendations = list(
            dict.fromkeys(summary.recommendations + self.documentation_agent.recommendations(scan, architecture))
        )[:6]
        await timeline.add(
            self.documentation_agent.name,
            "Contributor analysis completed",
            "Repository summary, architecture map, onboarding plan, and memory payload are ready.",
            confidence="high",
            metadata={"phase": "phase3-deep"},
        )

        result = self._analysis_result(
            repo_id,
            repo_url,
            summary,
            architecture,
            contributor_plan,
            intelligence,
            code_intelligence,
            timeline,
            phase="complete",
            deep_status="ready" if code_intelligence.semantic_memory else "partial",
        )
        self.memory.save_analysis(result)
        await timeline.add(
            "GitAgent Memory",
            "Persistent memory updated",
            "Stored compact repository facts, architecture summary, contributor notes, and timeline events.",
            confidence="high",
            metadata={"phase": "complete"},
        )
        result.timeline = timeline.events
        result.agent_manifest = self._manifest_public_payload(
            "complete",
            cache_status="stored",
            deep_status="ready" if code_intelligence.semantic_memory else "partial",
        )
        self.memory.save_analysis(result)
        return result

    async def _with_timeout(self, awaitable: Awaitable[Any], seconds: int, message: str) -> Any:
        try:
            return await asyncio.wait_for(awaitable, timeout=seconds)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(message) from exc

    async def _emit_result(
        self,
        stage: str,
        result: AnalysisResult,
        result_emitter: AnalysisEmitter | None,
    ) -> None:
        if not result_emitter:
            return
        maybe = result_emitter(stage, result)
        if maybe is not None:
            await maybe

    def _analysis_result(
        self,
        repo_id: str,
        repo_url: str,
        summary: Any,
        architecture: ArchitectureMap,
        contributor_plan: ContributorPlan,
        intelligence: RepositoryIntelligence,
        code_intelligence: RepositoryCodeIntelligence,
        timeline: TimelineRecorder,
        *,
        phase: str,
        deep_status: str,
    ) -> AnalysisResult:
        return AnalysisResult(
            repo_id=repo_id,
            repo_url=repo_url,
            analyzed_at=datetime.now(timezone.utc),
            summary=summary,
            architecture=architecture,
            contributor_plan=contributor_plan,
            intelligence=intelligence,
            code_intelligence=code_intelligence,
            timeline=list(timeline.events),
            agent_manifest=self._manifest_public_payload(phase, deep_status=deep_status),
        )

    def _root_architecture(self, scan: RepositoryScan) -> ArchitectureMap:
        nodes = [
            ArchitectureNode(
                id=folder.path,
                label=folder.path,
                type=self._node_type_for_role(folder.role),
                description=folder.description,
                confidence=folder.confidence,
                role=folder.role,
                framework=scan.frameworks[0] if scan.frameworks and folder.role in {"frontend", "backend", "shared"} else None,
                entrypoint=any(entry == folder.path or entry.startswith(f"{folder.path}/") for entry in scan.entry_points),
                dependency_count=0,
                ownership_score=round(min(0.95, 0.25 + folder.file_count / max(1, len(scan.files))), 2),
                runtime_classification="architecture root",
                group=folder.role,
                metadata={"file_count": folder.file_count, "analysis_phase": "roots"},
            )
            for folder in scan.folders[:12]
        ]
        if scan.manifests:
            nodes.append(
                ArchitectureNode(
                    id="manifests",
                    label="manifests",
                    type="config",
                    description="Dependency manifests and framework configuration detected during the fast scan.",
                    confidence="high",
                    role="configuration",
                    dependency_count=0,
                    ownership_score=0.35,
                    runtime_classification="configuration",
                    group="config",
                    metadata={"files": sorted(scan.manifests)[:10], "analysis_phase": "roots"},
                )
            )
        deployment_files = self._deployment_files(scan)
        if deployment_files:
            nodes.append(
                ArchitectureNode(
                    id="deployment",
                    label="deployment",
                    type="infra",
                    description="Deployment, CI, or runtime operation files detected in the repository root scan.",
                    confidence="medium",
                    role="deployment",
                    dependency_count=0,
                    ownership_score=0.3,
                    runtime_classification="operations",
                    group="infra",
                    metadata={"files": deployment_files[:10], "analysis_phase": "roots"},
                )
            )
        if not nodes:
            nodes.append(
                ArchitectureNode(
                    id="repository",
                    label=scan.name,
                    type="package",
                    description="Repository root detected. More structure will appear as analysis progresses.",
                    confidence=scan.confidence,
                    role="repository",
                    metadata={"analysis_phase": "roots"},
                )
            )

        frameworks = ", ".join(scan.frameworks[:4]) if scan.frameworks else "framework detection is still sparse"
        boundaries = [
            f"{folder.path} is a {folder.role} root with {folder.file_count} indexed files."
            for folder in scan.folders[:5]
        ]
        dependency_flow = [
            "Fast phase renders architecture roots only.",
            "Dependency relationships, symbols, routes, and semantic memory stream after first render.",
        ]
        if scan.entry_points:
            dependency_flow.append(f"Runtime entry-point scan starts at {', '.join(scan.entry_points[:3])}.")
        return ArchitectureMap(
            summary=(
                f"Fast scan found {len(scan.files)} files across {len(scan.folders)} top-level areas. "
                f"Detected stack signal: {frameworks}. Relationship mapping is running in the background."
            ),
            boundaries=boundaries or ["Repository roots are being inferred from manifests and top-level files."],
            nodes=nodes,
            edges=[],
            dependency_flow=dependency_flow,
            confidence=scan.confidence,
            framework_signals=[f"{framework}: manifest or config signal" for framework in scan.frameworks[:8]],
            graph_metrics={
                "analysis_phase": "roots",
                "nodes": len(nodes),
                "edges": 0,
                "files_indexed": len(scan.files),
                "manifest_count": len(scan.manifests),
            },
            topology={"analysis_phase": "roots", "root_count": len(nodes)},
        )

    def _shell_contributor_plan(self, scan: RepositoryScan) -> ContributorPlan:
        return ContributorPlan(
            roadmap=[],
            beginner_files=scan.important_files[:6],
            recommended_tasks=[],
            good_first_issues=[],
            contribution_paths=[],
            learning_sequence=["Fast scan", "Architecture roots", "Dependency graph", "Semantic memory", "Contributor intelligence"],
            confidence="medium" if scan.files else "low",
        )

    def _shell_intelligence(self, scan: RepositoryScan, architecture: ArchitectureMap) -> RepositoryIntelligence:
        score = min(100, max(4 if scan.files else 0, int(len(scan.files) / 45) + len(scan.frameworks) * 4 + len(scan.folders) * 2))
        if score < 25:
            level = "approachable"
        elif score < 50:
            level = "moderate"
        elif score < 75:
            level = "complex"
        else:
            level = "advanced"
        return RepositoryIntelligence(
            complexity=ComplexityScore(
                score=score,
                level=level,
                summary="Initial complexity estimate from manifests, languages, and top-level roots. Deep scoring is still running.",
                drivers=[
                    f"{len(scan.files)} indexed files",
                    f"{len(scan.languages)} language families",
                    f"{len(scan.frameworks)} framework signals",
                    f"{len(architecture.nodes)} architecture roots",
                ],
            ),
            risks=[],
            ownership=[],
            dependency_insights=[],
            good_first_issues=[],
            contribution_paths=[],
            architecture_brief=architecture.summary,
            demo_headline=f"Fast-mapped {scan.name} into repository roots and manifest signals.",
            confidence="medium" if scan.files else "low",
        )

    def _shell_code_intelligence(self, scan: RepositoryScan) -> RepositoryCodeIntelligence:
        return RepositoryCodeIntelligence(
            runtime={
                "entry_points": scan.entry_points[:20],
                "frameworks": scan.frameworks,
                "analysis_phase": "metadata",
            },
            deployment={
                "files": self._deployment_files(scan),
                "targets": [],
                "manifests": {},
                "analysis_phase": "metadata",
            },
            retrieval_stats={
                "source_files_analyzed": 0,
                "symbols_indexed": 0,
                "routes_indexed": 0,
                "memory_items": 0,
                "analysis_phase": "metadata",
            },
            confidence="low",
        )

    @staticmethod
    def _node_type_for_role(role: str) -> str:
        role_map = {
            "frontend": "frontend",
            "backend": "backend",
            "shared": "shared",
            "data": "data",
            "infra": "infra",
            "docs": "docs",
            "tests": "tests",
            "config": "config",
            "manifest": "config",
            "application": "shared",
        }
        return role_map.get(role, "package")

    @staticmethod
    def _deployment_files(scan: RepositoryScan) -> list[str]:
        names = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml", "render.yaml", "render.yml", "vercel.json"}
        return [
            file
            for file in scan.files
            if PurePosixPath(file).name in names or file.startswith(".github/workflows/")
        ][:16]

    @staticmethod
    def _source_file_count(scan: RepositoryScan) -> int:
        return sum(1 for file in scan.files if PurePosixPath(file).suffix.lower() in SOURCE_EXTENSIONS)

    @staticmethod
    def _code_source_file_count(scan: RepositoryScan) -> int:
        return sum(1 for file in scan.files if PurePosixPath(file).suffix.lower() in CODE_SOURCE_EXTENSIONS)

    async def chat(self, repo_id: str, message: str) -> ChatResponse:
        analysis = self.memory.get_analysis(repo_id)
        if not analysis:
            return ChatResponse(
                repo_id=repo_id,
                answer="I do not have memory for that repository yet. Run an analysis first so I can answer with repository context.",
                cited_files=[],
                confidence="low",
            )

        if not analysis.get("code_intelligence", {}).get("semantic_memory"):
            response = ChatResponse(
                repo_id=repo_id,
                answer=(
                    "This repository memory was created before symbol intelligence was available. "
                    "Re-run analysis so I can answer from exact files, symbols, routes, middleware, providers, and runtime relationships."
                ),
                cited_files=[],
                confidence="low",
            )
            self.memory.remember_question(repo_id, message, response)
            return response

        retrieval_context = self.retriever.build_context(message, analysis)
        llm_answer = await self.llm.answer_with_context(message, retrieval_context)
        if llm_answer:
            cited = self._extract_citations(llm_answer, analysis)
            cited_symbols = self._extract_symbol_citations(llm_answer, analysis)
            cited_routes = self._extract_route_citations(llm_answer, analysis)
            response = ChatResponse(
                repo_id=repo_id,
                answer=llm_answer,
                cited_files=cited,
                cited_symbols=cited_symbols,
                cited_routes=cited_routes,
                context_items=[
                    item
                    for item in retrieval_context.get("retrieved_items", [])[:6]
                ],
                confidence="high",
            )
            self.memory.remember_question(repo_id, message, response)
            return response

        response = self.retriever.answer(repo_id, message, analysis)
        self.memory.remember_question(repo_id, message, response)
        return response

    def timeline(self, repo_id: str) -> list[TimelineEvent]:
        analysis = self.memory.get_analysis(repo_id)
        if not analysis:
            return []
        return [TimelineEvent.model_validate(event) for event in analysis.get("timeline", [])]

    def architecture(self, repo_id: str) -> dict[str, Any] | None:
        analysis = self.memory.get_analysis(repo_id)
        return analysis.get("architecture") if analysis else None

    def onboarding(self, repo_id: str) -> dict[str, Any] | None:
        analysis = self.memory.get_analysis(repo_id)
        return analysis.get("contributor_plan") if analysis else None

    def intelligence(self, repo_id: str) -> dict[str, Any] | None:
        analysis = self.memory.get_analysis(repo_id)
        return analysis.get("intelligence") if analysis else None

    def code_intelligence_payload(self, repo_id: str) -> dict[str, Any] | None:
        analysis = self.memory.get_analysis(repo_id)
        return analysis.get("code_intelligence") if analysis else None

    def repo_summary(self, repo_id: str) -> dict[str, Any] | None:
        analysis = self.memory.get_analysis(repo_id)
        return analysis.get("summary") if analysis else None

    def _manifest_public_payload(
        self,
        phase: str = "complete",
        *,
        cache_status: str = "miss",
        deep_status: str = "ready",
    ) -> dict[str, Any]:
        manifest = self.registry.manifest.copy()
        workflow = dict(manifest.get("workflow") or {})
        workflow.update(
            {
                "analysis_phase": phase,
                "cache_status": cache_status,
                "deep_status": deep_status,
                "progressive_intelligence": True,
            }
        )
        return {
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "skills": manifest.get("skills", []),
            "tools": manifest.get("tools", []),
            "workflow": workflow,
            "agents": list((manifest.get("agents") or {}).keys()),
        }

    @staticmethod
    def _compact_context(analysis: dict[str, Any]) -> dict[str, Any]:
        summary = analysis.get("summary", {})
        architecture = analysis.get("architecture", {})
        contributor = analysis.get("contributor_plan", {})
        return {
            "repo_url": analysis.get("repo_url"),
            "summary": {
                "name": summary.get("name"),
                "description": summary.get("description"),
                "frameworks": summary.get("frameworks"),
                "entry_points": summary.get("entry_points"),
                "important_files": summary.get("important_files"),
                "folders": summary.get("folders"),
            },
            "architecture": {
                "summary": architecture.get("summary"),
                "boundaries": architecture.get("boundaries"),
                "dependency_flow": architecture.get("dependency_flow"),
                "graph_metrics": architecture.get("graph_metrics"),
            },
            "code_intelligence": {
                "routes": analysis.get("code_intelligence", {}).get("routes", [])[:40],
                "auth": analysis.get("code_intelligence", {}).get("auth", {}),
                "state": analysis.get("code_intelligence", {}).get("state", {}),
                "runtime": analysis.get("code_intelligence", {}).get("runtime", {}),
            },
            "contributor_plan": contributor,
            "intelligence": analysis.get("intelligence", {}),
        }

    def _heuristic_chat(self, repo_id: str, message: str, analysis: dict[str, Any]) -> ChatResponse:
        context = self._compact_context(analysis)
        summary = context["summary"]
        architecture = context["architecture"]
        lower = message.lower()
        cited_files: list[str] = []

        important_files = summary.get("important_files") or []
        entry_points = summary.get("entry_points") or []
        folders = summary.get("folders") or []

        def cite(paths: list[str]) -> None:
            for path in paths:
                if path and path not in cited_files:
                    cited_files.append(path)

        if "auth" in lower or "login" in lower or "session" in lower:
            matches = [item["path"] for item in important_files if item.get("role") == "auth" or "auth" in item.get("path", "").lower()]
            cite(matches or entry_points[:3])
            answer = self._answer_block(
                "Authentication",
                "I did not find enough direct auth evidence to claim the full auth flow. Start with the cited middleware/auth-like files if present, then trace imports into API or app entry points.",
                context,
                cited_files,
            )
            return ChatResponse(repo_id=repo_id, answer=answer, cited_files=cited_files, confidence="medium" if cited_files else "low")

        if "api" in lower or "route" in lower or "endpoint" in lower:
            matches = [item["path"] for item in important_files if item.get("role") == "api"]
            api_folders = [folder["path"] for folder in folders if folder.get("role") == "backend"]
            cite(matches + api_folders + entry_points[:3])
            answer = self._answer_block(
                "API routes",
                "The API surface should be inspected through the cited API files or backend folders, then cross-checked against entry points and manifests.",
                context,
                cited_files,
            )
            return ChatResponse(repo_id=repo_id, answer=answer, cited_files=cited_files, confidence="medium" if cited_files else "low")

        if "state" in lower or "management" in lower:
            cite(entry_points[:3] + [folder["path"] for folder in folders if folder.get("role") in {"frontend", "shared"}][:3])
            answer = self._answer_block(
                "State management",
                "State management was not conclusively detected from manifests alone. Inspect the frontend and shared source areas for providers, stores, hooks, or context modules.",
                context,
                cited_files,
            )
            return ChatResponse(repo_id=repo_id, answer=answer, cited_files=cited_files, confidence="medium")

        if "database" in lower or "db" in lower or "schema" in lower:
            matches = [item["path"] for item in important_files if item.get("role") == "data" or "schema" in item.get("path", "").lower()]
            cite(matches + [folder["path"] for folder in folders if folder.get("role") == "data"])
            answer = self._answer_block(
                "Database configuration",
                "Database evidence is based on schema/model files and dependency manifests. If no schema files are cited, inspect manifests for ORM packages and search source folders for database clients.",
                context,
                cited_files,
            )
            return ChatResponse(repo_id=repo_id, answer=answer, cited_files=cited_files, confidence="medium" if cited_files else "low")

        if "beginner" in lower or "start" in lower or "onboard" in lower:
            contributor = context["contributor_plan"]
            roadmap = contributor.get("roadmap", [])
            cite([file for step in roadmap[:2] for file in step.get("files", [])])
            answer = "A beginner should follow this sequence:\n\n" + "\n".join(
                f"{index + 1}. {step.get('title')}: {step.get('description')}" for index, step in enumerate(roadmap[:4])
            )
            return ChatResponse(repo_id=repo_id, answer=answer, cited_files=cited_files, confidence=contributor.get("confidence", "medium"))

        if "good first" in lower or "issue" in lower or "contribution" in lower:
            intelligence = context.get("intelligence", {})
            issues = intelligence.get("good_first_issues", [])
            cite([file for issue in issues[:3] for file in issue.get("files", [])])
            answer = "Good first issue candidates:\n\n" + "\n".join(
                f"{index + 1}. {issue.get('title')}: {issue.get('rationale')}" for index, issue in enumerate(issues[:4])
            )
            return ChatResponse(repo_id=repo_id, answer=answer, cited_files=cited_files, confidence=intelligence.get("confidence", "medium"))

        if "complex" in lower or "risk" in lower or "ownership" in lower:
            intelligence = context.get("intelligence", {})
            complexity = intelligence.get("complexity", {})
            risks = intelligence.get("risks", [])
            ownership = intelligence.get("ownership", [])
            cite([path for area in ownership[:3] for path in area.get("paths", [])])
            risk_lines = [f"- {risk.get('title')} ({risk.get('severity')}): {risk.get('recommendation')}" for risk in risks[:4]]
            answer = "\n".join(
                [
                    "## Repository intelligence",
                    f"Complexity: {complexity.get('score', 'n/a')}/100, {complexity.get('level', 'unknown')}.",
                    complexity.get("summary", ""),
                    "",
                    "Risk insights:",
                    *(risk_lines or ["- No major deterministic risk signals were detected."]),
                ]
            )
            return ChatResponse(repo_id=repo_id, answer=answer, cited_files=cited_files, confidence=intelligence.get("confidence", "medium"))

        cite(entry_points[:4] + [item["path"] for item in important_files[:4]])
        answer = self._answer_block(
            "Project structure",
            architecture.get("summary") or summary.get("description") or "The repository is best understood from its entry points, manifests, and top-level source folders.",
            context,
            cited_files,
        )
        return ChatResponse(repo_id=repo_id, answer=answer, cited_files=cited_files, confidence=architecture.get("confidence", "medium"))

    @staticmethod
    def _answer_block(title: str, guidance: str, context: dict[str, Any], cited_files: list[str]) -> str:
        frameworks = context["summary"].get("frameworks") or []
        flow = context["architecture"].get("dependency_flow") or []
        lines = [
            f"## {title}",
            guidance,
            "",
            f"Detected stack: {', '.join(frameworks) if frameworks else 'not enough manifest evidence'}",
        ]
        if flow:
            lines.extend(["", "Repository flow:"] + [f"- {item}" for item in flow[:3]])
        if cited_files:
            lines.extend(["", "Start with:"] + [f"- `{path}`" for path in cited_files[:6]])
        return "\n".join(lines)

    @staticmethod
    def _extract_citations(answer: str, analysis: dict[str, Any]) -> list[str]:
        known_files = {
            item.get("path")
            for item in analysis.get("summary", {}).get("important_files", [])
            if isinstance(item, dict)
        }
        known_files.update(analysis.get("summary", {}).get("entry_points", []))
        known_files.update(
            symbol.get("file")
            for symbol in analysis.get("code_intelligence", {}).get("symbols", [])
            if isinstance(symbol, dict)
        )
        known_files.update(
            route.get("file")
            for route in analysis.get("code_intelligence", {}).get("routes", [])
            if isinstance(route, dict)
        )
        known_files.update(
            item.get("file")
            for item in analysis.get("code_intelligence", {}).get("semantic_memory", [])
            if isinstance(item, dict)
        )
        return [path for path in known_files if path and path in answer][:8]

    @staticmethod
    def _extract_symbol_citations(answer: str, analysis: dict[str, Any]) -> list[str]:
        symbols = analysis.get("code_intelligence", {}).get("symbols", [])
        cited = []
        for symbol in symbols:
            if not isinstance(symbol, dict):
                continue
            name = symbol.get("name")
            symbol_id = symbol.get("id")
            if name and symbol_id and name in answer:
                cited.append(symbol_id)
        return list(dict.fromkeys(cited))[:12]

    @staticmethod
    def _extract_route_citations(answer: str, analysis: dict[str, Any]) -> list[str]:
        routes = analysis.get("code_intelligence", {}).get("routes", [])
        cited = []
        for route in routes:
            if not isinstance(route, dict):
                continue
            label = f"{route.get('method')} {route.get('path')}"
            if route.get("method") and route.get("path") and label in answer:
                cited.append(label)
        return list(dict.fromkeys(cited))[:12]


def sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"
