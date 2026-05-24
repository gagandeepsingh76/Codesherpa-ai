from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.services.code_intelligence import RepositoryCodeIntelligenceBuilder, RepositorySemanticRetriever
from backend.services.repository_scanner import RepositoryScanner
from backend.agents.architecture_mapping import ArchitectureMappingAgent


class CodeIntelligenceTests(unittest.TestCase):
    def analyze(self, files: dict[str, str]):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative_path, content in files.items():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            scan = RepositoryScanner().scan("https://example.com/acme/app", root, "main")
            architecture = ArchitectureMappingAgent().run(scan)
            code = RepositoryCodeIntelligenceBuilder().analyze(scan, architecture)
            return scan, architecture, code

    def test_express_jwt_auth_routes_state_and_semantic_memory(self) -> None:
        _, architecture, code = self.analyze(
            {
                "package.json": '{"dependencies":{"express":"4.18.0","jsonwebtoken":"9.0.0","zustand":"4.5.0","react":"19.0.0"}}',
                "backend/routes/v1/auth.js": 'const { login } = require("../../controllers/authController"); router.post("/api/login", login);',
                "backend/routes/v1/issues.js": 'const { authMiddleware } = require("../../middleware/auth"); const issueController = require("../../controllers/issueController"); router.post("/api/issues", authMiddleware, issueController.createIssue);',
                "backend/middleware/auth.js": 'const jwt = require("jsonwebtoken"); function authMiddleware(req,res,next){ jwt.verify(req.headers.authorization, process.env.JWT_SECRET); next(); } module.exports = { authMiddleware };',
                "backend/controllers/authController.js": 'const jwt = require("jsonwebtoken"); function login(req,res){ return jwt.sign({ id: "1" }, process.env.JWT_SECRET); } module.exports = { login };',
                "backend/controllers/issueController.js": 'exports.createIssue = function createIssue(req,res){ return res.json({ ok: true }); };',
                "src/store/useIssueStore.ts": 'import { create } from "zustand"; export const useIssueStore = create((set) => ({ issues: [] }));',
                "src/providers/AuthProvider.tsx": 'import { createContext, useContext } from "react"; export const AuthProvider = ({ children }) => children; export function useAuth(){ return useContext(createContext(null)); }',
            }
        )

        symbol_types = {symbol.type for symbol in code.symbols}
        route_labels = {f"{route.method} {route.path}" for route in code.routes}

        self.assertIn("middleware", symbol_types)
        self.assertIn("store", symbol_types)
        self.assertIn("hook", symbol_types)
        self.assertIn("POST /api/login", route_labels)
        self.assertIn("POST /api/issues", route_labels)
        self.assertIn("JWT", code.auth.strategies)
        self.assertTrue(code.auth.protected_routes)
        self.assertIn("Zustand", code.state.libraries)
        self.assertTrue(code.semantic_memory)
        self.assertGreaterEqual(architecture.graph_metrics["internal_import_edges"], 1)

    def test_fastapi_routes_schemas_and_grounded_auth_chat(self) -> None:
        _, _, code = self.analyze(
            {
                "requirements.txt": "fastapi==0.110.3\npython-jose==3.3.0\npydantic==2.7.4\n",
                "backend/api/routes.py": (
                    "from fastapi import APIRouter, Depends\n"
                    "from pydantic import BaseModel\n"
                    "from backend.auth import get_current_user, create_access_token\n"
                    "router = APIRouter()\n"
                    "class LoginRequest(BaseModel):\n    email: str\n"
                    "@router.post('/token')\n"
                    "def login(payload: LoginRequest):\n    return create_access_token({'sub': payload.email})\n"
                    "@router.get('/issues', dependencies=[Depends(get_current_user)])\n"
                    "def list_issues():\n    return []\n"
                ),
                "backend/auth.py": (
                    "from jose import jwt\n"
                    "import os\n"
                    "def create_access_token(data):\n    return jwt.encode(data, os.getenv('JWT_SECRET'))\n"
                    "def get_current_user():\n    return jwt.decode('token', os.getenv('JWT_SECRET'))\n"
                ),
            }
        )

        analysis = {
            "repo_id": "repo",
            "repo_url": "https://example.com/acme/app",
            "summary": {"entry_points": [], "important_files": []},
            "architecture": {"summary": "", "dependency_flow": [], "graph_metrics": {}},
            "contributor_plan": {"confidence": "medium", "roadmap": []},
            "intelligence": {},
            "code_intelligence": code.model_dump(mode="json"),
        }
        response = RepositorySemanticRetriever().answer("repo", "How auth works?", analysis)
        route_labels = {f"{route.method} {route.path}" for route in code.routes}

        self.assertIn("POST /token", route_labels)
        self.assertIn("GET /issues", route_labels)
        self.assertTrue(any(symbol.type == "schema" and symbol.name == "LoginRequest" for symbol in code.symbols))
        self.assertIn("JWT", code.auth.strategies)
        self.assertIn("backend/auth.py", response.cited_files)
        self.assertIn(response.confidence, {"medium", "high"})


if __name__ == "__main__":
    unittest.main()
