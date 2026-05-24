from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.agents.architecture_mapping import ArchitectureMappingAgent
from backend.models import ArchitectureMap
from backend.services.repository_scanner import RepositoryScanner


class DependencyGraphIntegrationTests(unittest.TestCase):
    def analyze(self, files: dict[str, str]) -> ArchitectureMap:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative_path, content in files.items():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            scan = RepositoryScanner().scan("https://example.com/test/repo", root, "main")
            self.last_scan = scan
            return ArchitectureMappingAgent().run(scan)

    @staticmethod
    def edge_exists(architecture: ArchitectureMap, source: str, target: str, kind: str | None = None) -> bool:
        return any(
            edge.source == source
            and edge.target == target
            and (kind is None or edge.kind == kind)
            for edge in architecture.edges
        )

    def test_next_monorepo_connects_imports_assets_and_deployment(self) -> None:
        architecture = self.analyze(
            {
                "package.json": '{"dependencies":{"next":"15.0.0","react":"19.0.0"},"devDependencies":{"tailwindcss":"3.4.0"}}',
                "tsconfig.json": '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["./*"]}}}',
                "next.config.mjs": "export default {};",
                "tailwind.config.ts": "export default {};",
                "app/page.tsx": 'import Header from "@/components/header"; const Server = import("../lib/server"); export default function Page(){ return <img src="/logo.svg" /> }',
                "components/header.tsx": "export default function Header(){ return null; }",
                "lib/server.ts": "export const runtime = 'edge';",
                "public/logo.svg": "<svg />",
                ".github/workflows/ci.yml": "name: ci",
                "vercel.json": '{"buildCommand":"next build"}',
            }
        )

        self.assertIn("Next.js", self.last_scan.frameworks)
        self.assertIn("React", self.last_scan.frameworks)
        self.assertIn("Tailwind CSS", self.last_scan.frameworks)
        self.assertEqual(architecture.confidence, "high")
        self.assertTrue(self.edge_exists(architecture, "app", "components", "import"))
        self.assertTrue(self.edge_exists(architecture, "app", "lib", "import"))
        self.assertTrue(self.edge_exists(architecture, "public", "app", "asset"))
        self.assertTrue(self.edge_exists(architecture, ".github", "deployment", "deployment"))
        self.assertTrue(self.edge_exists(architecture, "deployment", "app", "deployment"))

    def test_fastapi_backend_resolves_python_imports_and_render_flow(self) -> None:
        architecture = self.analyze(
            {
                "requirements.txt": "fastapi==0.110.3\npydantic==2.7.4\n",
                "backend/main.py": "from fastapi import FastAPI\nfrom backend.api.routes import router\napp = FastAPI()\n",
                "backend/api/routes.py": "from shared.models import Thing\nrouter = object()\n",
                "shared/models.py": "class Thing: pass\n",
                "render.yaml": "services:\n  - type: web\n    startCommand: uvicorn main:app\n",
            }
        )

        self.assertIn("FastAPI", self.last_scan.frameworks)
        backend = next(node for node in architecture.nodes if node.id == "backend")
        self.assertEqual(backend.framework, "FastAPI")
        self.assertTrue(backend.entrypoint)
        self.assertTrue(self.edge_exists(architecture, "backend", "shared", "import"))
        self.assertTrue(self.edge_exists(architecture, "render.yaml", "deployment", "deployment"))
        self.assertTrue(self.edge_exists(architecture, "deployment", "backend", "deployment"))

    def test_react_vite_connects_public_assets_to_source_runtime(self) -> None:
        architecture = self.analyze(
            {
                "package.json": '{"dependencies":{"@vitejs/plugin-react":"latest","react":"19.0.0","vite":"5.0.0"}}',
                "vite.config.ts": "export default {};",
                "src/main.tsx": 'import App from "./App"; import "./style.css";',
                "src/App.tsx": 'export default function App(){ return <img src="/logo.svg" /> }',
                "src/style.css": ".app { color: white; }",
                "public/logo.svg": "<svg />",
            }
        )

        self.assertIn("React", self.last_scan.frameworks)
        self.assertIn("Vite", self.last_scan.frameworks)
        src = next(node for node in architecture.nodes if node.id == "src")
        self.assertEqual(src.type, "frontend")
        self.assertTrue(self.edge_exists(architecture, "public", "src", "asset"))

    def test_mixed_frontend_backend_repo_creates_cross_boundary_import_edge(self) -> None:
        architecture = self.analyze(
            {
                "package.json": '{"dependencies":{"next":"15.0.0","react":"19.0.0"}}',
                "frontend/tsconfig.json": '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["./*"]}}}',
                "frontend/app/page.tsx": 'import { getIssues } from "../../backend/api/client"; import Widget from "@/components/widget"; export default function Page(){ return <Widget /> }',
                "frontend/components/widget.tsx": "export default function Widget(){ return null; }",
                "backend/api/client.ts": "export function getIssues(){ return []; }",
                "backend/main.py": "print('api')\n",
            }
        )

        self.assertTrue(self.edge_exists(architecture, "frontend", "backend", "import"))
        edge = next(edge for edge in architecture.edges if edge.source == "frontend" and edge.target == "backend")
        self.assertGreaterEqual(edge.weight, 1)
        self.assertTrue(edge.reasons)


if __name__ == "__main__":
    unittest.main()
