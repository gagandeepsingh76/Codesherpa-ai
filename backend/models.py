from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


Confidence = Literal["low", "medium", "high"]


class RepoAnalyzeRequest(BaseModel):
    repo_url: HttpUrl
    use_cache: bool = False


class ChatRequest(BaseModel):
    repo_id: str
    message: str = Field(min_length=1, max_length=4000)


class TimelineEvent(BaseModel):
    id: str
    timestamp: datetime
    agent: str
    title: str
    detail: str
    status: Literal["queued", "running", "completed", "failed"] = "completed"
    confidence: Confidence = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImportantFile(BaseModel):
    path: str
    reason: str
    role: str
    confidence: Confidence


class FolderInsight(BaseModel):
    path: str
    role: str
    description: str
    file_count: int
    confidence: Confidence


class ArchitectureNode(BaseModel):
    id: str
    label: str
    type: Literal["frontend", "backend", "shared", "data", "infra", "docs", "tests", "config", "package"]
    description: str
    confidence: Confidence


class ArchitectureEdge(BaseModel):
    source: str
    target: str
    label: str
    confidence: Confidence


class ArchitectureMap(BaseModel):
    summary: str
    boundaries: list[str]
    nodes: list[ArchitectureNode]
    edges: list[ArchitectureEdge]
    dependency_flow: list[str]
    confidence: Confidence


class OnboardingStep(BaseModel):
    title: str
    description: str
    files: list[str]
    difficulty: Literal["easy", "medium", "hard"]
    estimate: str


class ContributorTask(BaseModel):
    title: str
    why: str
    files: list[str]
    difficulty: Literal["easy", "medium", "hard"]


class GoodFirstIssue(BaseModel):
    title: str
    rationale: str
    files: list[str]
    labels: list[str]
    difficulty: Literal["easy", "medium", "hard"]
    estimated_time: str
    confidence: Confidence


class ContributionPath(BaseModel):
    name: str
    outcome: str
    steps: list[str]
    files: list[str]
    difficulty: Literal["easy", "medium", "hard"]


class ContributorPlan(BaseModel):
    roadmap: list[OnboardingStep]
    beginner_files: list[ImportantFile]
    recommended_tasks: list[ContributorTask]
    good_first_issues: list[GoodFirstIssue] = Field(default_factory=list)
    contribution_paths: list[ContributionPath] = Field(default_factory=list)
    learning_sequence: list[str]
    confidence: Confidence


class ComplexityScore(BaseModel):
    score: int = Field(ge=0, le=100)
    level: Literal["approachable", "moderate", "complex", "advanced"]
    summary: str
    drivers: list[str]


class RiskInsight(BaseModel):
    title: str
    severity: Literal["low", "medium", "high"]
    evidence: list[str]
    recommendation: str
    confidence: Confidence


class OwnershipArea(BaseModel):
    area: str
    owner_hint: str
    paths: list[str]
    responsibilities: list[str]
    confidence: Confidence


class DependencyInsight(BaseModel):
    ecosystem: str
    signal: str
    dependencies: list[str]
    risk: Literal["low", "medium", "high"]
    recommendation: str


class RepositoryIntelligence(BaseModel):
    complexity: ComplexityScore
    risks: list[RiskInsight]
    ownership: list[OwnershipArea]
    dependency_insights: list[DependencyInsight]
    good_first_issues: list[GoodFirstIssue]
    contribution_paths: list[ContributionPath]
    architecture_brief: str
    demo_headline: str
    confidence: Confidence


class RepositorySummary(BaseModel):
    repo_id: str
    repo_url: str
    name: str
    default_branch: str | None = None
    description: str
    languages: dict[str, int]
    frameworks: list[str]
    entry_points: list[str]
    package_managers: list[str]
    important_files: list[ImportantFile]
    folders: list[FolderInsight]
    recommendations: list[str]
    confidence: Confidence


class AnalysisResult(BaseModel):
    repo_id: str
    repo_url: str
    analyzed_at: datetime
    summary: RepositorySummary
    architecture: ArchitectureMap
    contributor_plan: ContributorPlan
    intelligence: RepositoryIntelligence
    timeline: list[TimelineEvent]
    agent_manifest: dict[str, Any]


class ChatResponse(BaseModel):
    repo_id: str
    answer: str
    cited_files: list[str]
    confidence: Confidence
    remembered: bool = True


class RepositoryScan(BaseModel):
    repo_id: str
    repo_url: str
    name: str
    path: str
    default_branch: str | None
    files: list[str]
    languages: dict[str, int]
    manifests: dict[str, Any]
    frameworks: list[str]
    package_managers: list[str]
    entry_points: list[str]
    important_files: list[ImportantFile]
    folders: list[FolderInsight]
    readme_excerpt: str | None = None
    confidence: Confidence
