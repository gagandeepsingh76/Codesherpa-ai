export type Confidence = "low" | "medium" | "high";

export type TimelineEvent = {
  id: string;
  timestamp: string;
  agent: string;
  title: string;
  detail: string;
  status: "queued" | "running" | "completed" | "failed";
  confidence: Confidence;
  metadata?: Record<string, unknown>;
};

export type ImportantFile = {
  path: string;
  reason: string;
  role: string;
  confidence: Confidence;
};

export type FolderInsight = {
  path: string;
  role: string;
  description: string;
  file_count: number;
  confidence: Confidence;
};

export type ArchitectureNode = {
  id: string;
  label: string;
  type: "frontend" | "backend" | "shared" | "data" | "infra" | "docs" | "tests" | "config" | "package";
  description: string;
  confidence: Confidence;
  role?: string | null;
  framework?: string | null;
  entrypoint?: boolean;
  dependency_count?: number;
  ownership_score?: number;
  runtime_classification?: string | null;
  group?: string | null;
  x?: number | null;
  y?: number | null;
  metadata?: Record<string, unknown>;
};

export type ArchitectureEdge = {
  source: string;
  target: string;
  label: string;
  confidence: Confidence;
  weight?: number;
  kind?: "import" | "asset" | "deployment" | "manifest" | "semantic" | "dependency" | string;
  reasons?: string[];
  files?: string[];
  metadata?: Record<string, unknown>;
};

export type ArchitectureMap = {
  summary: string;
  boundaries: string[];
  nodes: ArchitectureNode[];
  edges: ArchitectureEdge[];
  dependency_flow: string[];
  confidence: Confidence;
  framework_signals?: string[];
  graph_metrics?: Record<string, unknown>;
  file_graph?: Record<string, unknown>;
  risk_analysis?: Record<string, unknown>;
  hotspots?: Array<Record<string, unknown>>;
  topology?: Record<string, unknown>;
  evolution?: Record<string, unknown>;
};

export type OnboardingStep = {
  title: string;
  description: string;
  files: string[];
  difficulty: "easy" | "medium" | "hard";
  estimate: string;
};

export type ContributorTask = {
  title: string;
  why: string;
  files: string[];
  difficulty: "easy" | "medium" | "hard";
};

export type GoodFirstIssue = {
  title: string;
  rationale: string;
  files: string[];
  labels: string[];
  difficulty: "easy" | "medium" | "hard";
  estimated_time: string;
  confidence: Confidence;
};

export type ContributionPath = {
  name: string;
  outcome: string;
  steps: string[];
  files: string[];
  difficulty: "easy" | "medium" | "hard";
};

export type ContributorPlan = {
  roadmap: OnboardingStep[];
  beginner_files: ImportantFile[];
  recommended_tasks: ContributorTask[];
  good_first_issues: GoodFirstIssue[];
  contribution_paths: ContributionPath[];
  learning_sequence: string[];
  confidence: Confidence;
};

export type ComplexityScore = {
  score: number;
  level: "approachable" | "moderate" | "complex" | "advanced";
  summary: string;
  drivers: string[];
};

export type RiskInsight = {
  title: string;
  severity: "low" | "medium" | "high";
  evidence: string[];
  recommendation: string;
  confidence: Confidence;
};

export type OwnershipArea = {
  area: string;
  owner_hint: string;
  paths: string[];
  responsibilities: string[];
  confidence: Confidence;
};

export type DependencyInsight = {
  ecosystem: string;
  signal: string;
  dependencies: string[];
  risk: "low" | "medium" | "high";
  recommendation: string;
};

export type RepositoryIntelligence = {
  complexity: ComplexityScore;
  risks: RiskInsight[];
  ownership: OwnershipArea[];
  dependency_insights: DependencyInsight[];
  good_first_issues: GoodFirstIssue[];
  contribution_paths: ContributionPath[];
  architecture_brief: string;
  demo_headline: string;
  confidence: Confidence;
};

export type CodeSymbol = {
  id: string;
  name: string;
  type: string;
  file: string;
  line?: number | null;
  end_line?: number | null;
  language: string;
  runtime_role?: string | null;
  signature?: string | null;
  imports: string[];
  used_by: string[];
  calls: string[];
  decorators: string[];
  metadata?: Record<string, unknown>;
};

export type RouteEndpoint = {
  id: string;
  method: string;
  path: string;
  file: string;
  line?: number | null;
  framework: string;
  controller?: string | null;
  middleware: string[];
  auth_required: boolean;
  dependencies: string[];
  symbols: string[];
  metadata?: Record<string, unknown>;
};

export type AuthFlow = {
  strategies: string[];
  files: string[];
  login_routes: RouteEndpoint[];
  token_issuers: string[];
  validators: string[];
  protected_routes: RouteEndpoint[];
  role_enforcement: string[];
  session_persistence: string[];
  explanation: string;
  confidence: Confidence;
};

export type StateFlow = {
  libraries: string[];
  stores: CodeSymbol[];
  providers: CodeSymbol[];
  hooks: CodeSymbol[];
  cache_layers: CodeSymbol[];
  shared_state_boundaries: string[];
  relationships: Array<Record<string, unknown>>;
  explanation: string;
  confidence: Confidence;
};

export type SemanticMemoryItem = {
  id: string;
  type: string;
  title: string;
  file?: string | null;
  line?: number | null;
  symbol?: string | null;
  route?: string | null;
  summary: string;
  keywords: string[];
  importance: number;
  relations: string[];
  metadata?: Record<string, unknown>;
};

export type RepositoryCodeIntelligence = {
  symbols: CodeSymbol[];
  symbol_graph: Record<string, unknown>;
  routes: RouteEndpoint[];
  auth: AuthFlow;
  state: StateFlow;
  runtime: Record<string, unknown>;
  deployment: Record<string, unknown>;
  semantic_memory: SemanticMemoryItem[];
  retrieval_stats: Record<string, unknown>;
  confidence: Confidence;
};

export type RepositorySummary = {
  repo_id: string;
  repo_url: string;
  name: string;
  default_branch?: string | null;
  description: string;
  languages: Record<string, number>;
  frameworks: string[];
  entry_points: string[];
  package_managers: string[];
  important_files: ImportantFile[];
  folders: FolderInsight[];
  recommendations: string[];
  confidence: Confidence;
};

export type AnalysisResult = {
  repo_id: string;
  repo_url: string;
  analyzed_at: string;
  summary: RepositorySummary;
  architecture: ArchitectureMap;
  contributor_plan: ContributorPlan;
  intelligence: RepositoryIntelligence;
  code_intelligence: RepositoryCodeIntelligence;
  timeline: TimelineEvent[];
  agent_manifest: {
    name: string;
    version: string;
    skills: string[];
    tools: string[];
    workflow: Record<string, unknown>;
    agents: string[];
  };
};

export type ChatResponse = {
  repo_id: string;
  answer: string;
  cited_files: string[];
  cited_symbols: string[];
  cited_routes: string[];
  context_items: SemanticMemoryItem[];
  confidence: Confidence;
  remembered: boolean;
};
