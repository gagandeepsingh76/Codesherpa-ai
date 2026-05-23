from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from backend.agents.architecture_mapping import ArchitectureMappingAgent
from backend.agents.documentation import DocumentationAgent
from backend.agents.issue_debugging import IssueDebuggingAgent
from backend.agents.onboarding import OnboardingAgent
from backend.agents.repository_analysis import RepositoryAnalysisAgent
from backend.agents.repository_intelligence import RepositoryIntelligenceAgent
from backend.models import AnalysisResult, ChatResponse, RepositoryScan, TimelineEvent
from backend.services.git_service import GitService
from backend.services.gitagent_registry import GitAgentRegistry
from backend.services.llm_service import LLMService
from backend.services.memory_store import MemoryStore
from backend.services.repository_scanner import RepositoryScanner
from backend.services.timeline import TimelineEmitter, TimelineRecorder
from backend.utils.ids import stable_repo_id


class RepositoryUnderstandingWorkflow:
    def __init__(self) -> None:
        self.registry = GitAgentRegistry()
        self.git = GitService()
        self.scanner = RepositoryScanner()
        self.memory = MemoryStore()
        self.llm = LLMService(self.registry)
        self.repository_agent = RepositoryAnalysisAgent()
        self.architecture_agent = ArchitectureMappingAgent()
        self.onboarding_agent = OnboardingAgent()
        self.issue_agent = IssueDebuggingAgent()
        self.documentation_agent = DocumentationAgent()
        self.intelligence_agent = RepositoryIntelligenceAgent()

    async def run(self, repo_url: str, emitter: TimelineEmitter | None = None, use_cache: bool = False) -> AnalysisResult:
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
            if cached and cached.get("intelligence"):
                await timeline.add(
                    "GitAgent Memory",
                    "Cached repository intelligence restored",
                    "Reused persisted architecture, contributor, risk, and good-first-issue memory for a fast repeat demo.",
                    confidence="high",
                )
                result = AnalysisResult.model_validate(cached)
                result.timeline = timeline.events + result.timeline
                return result

        await timeline.add(
            self.repository_agent.name,
            "Repository Analysis Agent initialized",
            "Preparing isolated checkout and repository scanner.",
            status="running",
            confidence="high",
        )

        repo_path = await self.git.clone_or_update(repo_url)
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
        )

        scan = await asyncio.to_thread(self.scanner.scan, repo_url, repo_path, default_branch)
        await timeline.add(
            self.repository_agent.name,
            "Scanning repository structure",
            f"Indexed {len(scan.files)} files across {len(scan.folders)} top-level areas.",
            confidence=scan.confidence,
            metadata={"languages": scan.languages, "frameworks": scan.frameworks},
        )

        summary = self.repository_agent.run(scan)
        await timeline.add(
            self.repository_agent.name,
            "Identifying important files",
            f"Ranked {len(summary.important_files)} important files and {len(summary.entry_points)} entry points.",
            confidence=summary.confidence,
        )

        await timeline.add(
            self.architecture_agent.name,
            "Architecture Mapping Agent initialized",
            "Converting scan evidence into an architecture graph.",
            status="running",
            confidence="high",
        )
        architecture = self.architecture_agent.run(scan)
        await timeline.add(
            self.architecture_agent.name,
            "Building dependency graph",
            f"Generated {len(architecture.nodes)} nodes and {len(architecture.edges)} relationship edges.",
            confidence=architecture.confidence,
        )
        await timeline.add(
            self.architecture_agent.name,
            "Detecting system boundaries",
            "Classified frontend, backend, shared, tests, docs, and infrastructure areas.",
            confidence=architecture.confidence,
        )

        await timeline.add(
            self.onboarding_agent.name,
            "Onboarding Agent initialized",
            "Building a contributor-first learning sequence.",
            status="running",
            confidence="high",
        )
        contributor_plan = self.onboarding_agent.run(scan)
        await timeline.add(
            self.onboarding_agent.name,
            "Generating onboarding guide",
            f"Created {len(contributor_plan.roadmap)} roadmap steps and {len(contributor_plan.recommended_tasks)} first tasks.",
            confidence=contributor_plan.confidence,
        )

        await timeline.add(
            self.intelligence_agent.name,
            "Repository Intelligence Agent initialized",
            "Scoring complexity, mapping ownership, and generating contribution opportunities.",
            status="running",
            confidence="high",
        )
        intelligence = self.intelligence_agent.run(scan, architecture)
        contributor_plan.good_first_issues = intelligence.good_first_issues
        contributor_plan.contribution_paths = intelligence.contribution_paths
        await timeline.add(
            self.intelligence_agent.name,
            "Good first issues generated",
            f"Created {len(intelligence.good_first_issues)} scoped issues and {len(intelligence.contribution_paths)} contribution paths.",
            confidence=intelligence.confidence,
        )
        await timeline.add(
            self.intelligence_agent.name,
            "Complexity and risk model completed",
            f"Complexity scored {intelligence.complexity.score}/100 with {len(intelligence.risks)} risk insights.",
            confidence=intelligence.confidence,
            metadata={"complexity": intelligence.complexity.model_dump(mode="json")},
        )

        await timeline.add(
            self.documentation_agent.name,
            "Documentation Agent initialized",
            "Preparing durable repository explanation and documentation recommendations.",
            status="running",
            confidence="high",
        )
        summary.recommendations = list(
            dict.fromkeys(summary.recommendations + self.documentation_agent.recommendations(scan, architecture))
        )[:6]
        await timeline.add(
            self.documentation_agent.name,
            "Contributor analysis completed",
            "Repository summary, architecture map, onboarding plan, and memory payload are ready.",
            confidence="high",
        )

        result = AnalysisResult(
            repo_id=repo_id,
            repo_url=repo_url,
            analyzed_at=datetime.now(timezone.utc),
            summary=summary,
            architecture=architecture,
            contributor_plan=contributor_plan,
            intelligence=intelligence,
            timeline=timeline.events,
            agent_manifest=self._manifest_public_payload(),
        )
        self.memory.save_analysis(result)
        await timeline.add(
            "GitAgent Memory",
            "Persistent memory updated",
            "Stored compact repository facts, architecture summary, contributor notes, and timeline events.",
            confidence="high",
        )
        result.timeline = timeline.events
        self.memory.save_analysis(result)
        return result

    async def chat(self, repo_id: str, message: str) -> ChatResponse:
        analysis = self.memory.get_analysis(repo_id)
        if not analysis:
            return ChatResponse(
                repo_id=repo_id,
                answer="I do not have memory for that repository yet. Run an analysis first so I can answer with repository context.",
                cited_files=[],
                confidence="low",
            )

        llm_answer = await self.llm.answer_with_context(message, self._compact_context(analysis))
        if llm_answer:
            cited = self._extract_citations(llm_answer, analysis)
            response = ChatResponse(repo_id=repo_id, answer=llm_answer, cited_files=cited, confidence="high")
            self.memory.remember_question(repo_id, message, response)
            return response

        response = self._heuristic_chat(repo_id, message, analysis)
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

    def repo_summary(self, repo_id: str) -> dict[str, Any] | None:
        analysis = self.memory.get_analysis(repo_id)
        return analysis.get("summary") if analysis else None

    def _manifest_public_payload(self) -> dict[str, Any]:
        manifest = self.registry.manifest.copy()
        return {
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "skills": manifest.get("skills", []),
            "tools": manifest.get("tools", []),
            "workflow": manifest.get("workflow", {}),
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
        return [path for path in known_files if path and path in answer][:8]


def sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"
