<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&height=220&text=CodeSherpa%20AI&fontAlign=50&fontAlignY=40&color=0:0A0D12,55:14B8A6,100:F59E0B&fontColor=FFFFFF&fontSize=60" alt="CodeSherpa AI banner" />
</p>

<p align="center">
  <strong>Understand any repository in minutes.</strong>
</p>

<p align="center">
  <img alt="GitAgent native" src="https://img.shields.io/badge/GitAgent-native-14b8a6?style=for-the-badge" />
  <img alt="Next.js 15" src="https://img.shields.io/badge/Next.js-15-ffffff?style=for-the-badge&logo=nextdotjs&logoColor=black" />
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-async-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img alt="OpenAI" src="https://img.shields.io/badge/OpenAI-ready-111827?style=for-the-badge&logo=openai&logoColor=white" />
</p>

---

# CodeSherpa AI

A production-ready AI-powered Repository Intelligence & Architecture Analysis platform built using Next.js, React, TypeScript, FastAPI, Python, and advanced graph intelligence systems.

CodeSherpa AI enables developers, contributors, and engineering teams to deeply understand repositories through AI-powered architecture mapping, grounded semantic retrieval, repository onboarding intelligence, dependency analysis, and interactive runtime visualization.

---

# Live Demo

## Live Application

https://codesherpa-ai.vercel.app/

## Backend API

https://codesherpa-ai-3.onrender.com

## Health Endpoint

https://codesherpa-ai-3.onrender.com/health

## GitHub Repository

https://github.com/gagandeepsingh76/Codesherpa-ai

---

# Product Preview

<p align="center">
  <img width="1365" height="626" alt="image" src="https://github.com/user-attachments/assets/dd47d8aa-b533-4938-b925-ba643a3a9c3e" />
</p>

---

# System Architecture

```mermaid
flowchart LR
  UI[Next.js Frontend] --> API[FastAPI Backend]
  API --> Agents[GitAgent Agents]
  Agents --> Graph[Architecture Intelligence]
  Agents --> Memory[Semantic Memory]
  API --> Chat[Grounded Repository Chat]
  Chat --> OpenAI[OpenAI SDK]
```

---

# Application Interface

## Repository Intelligence Dashboard

<p align="center">
<img width="620" height="486" alt="image" src="https://github.com/user-attachments/assets/dfdc8cc5-1099-4550-a5f0-9b4da81137a0" />
</p>

---

## Interactive Architecture Visualization

<p align="center">
<img width="1158" height="394" alt="image" src="https://github.com/user-attachments/assets/aba17906-075e-4848-af00-39874990b0da" />
<img width="1187" height="578" alt="image" src="https://github.com/user-attachments/assets/ebc0bb13-fc77-4d99-b4bd-39184a21324a" />
</p>

---

## Grounded AI Repository Chat

<p align="center">
<img width="1341" height="624" alt="image" src="https://github.com/user-attachments/assets/50ac5289-fe64-4f09-a081-ec06ea453497" />
</p>

---

## AI Agent Timeline

<p align="center">
<img width="639" height="541" alt="image" src="https://github.com/user-attachments/assets/69930f63-966b-4a05-a0aa-f16cf83f696a" />
</p>

---

# Problem

Open-source onboarding is slow because repository knowledge is scattered across source folders, stale documentation, tests, manifests, and maintainer intuition.

Developers frequently struggle with:

- Where should I start?
- Which files matter most?
- What is the architecture flow?
- How risky is this change?
- Which contribution is beginner friendly?

CodeSherpa compresses this discovery workflow into an AI-native repository intelligence experience.

---

# Key Features

## AI Repository Intelligence

- Semantic Repository Understanding
- Grounded Code Retrieval
- Runtime-aware Analysis
- Symbol Extraction Engine
- Repository Memory System
- Contextual Architecture Reasoning

---

## Interactive Architecture Intelligence

- Layered Architecture Visualization
- Runtime Dependency Mapping
- Infrastructure Clustering
- Progressive Drilldown
- Signal-first Graph Rendering
- Focus & Search Modes

---

## Grounded AI Repository Chat

- File-aware Responses
- Route-aware Intelligence
- Authentication Flow Detection
- State Management Detection
- Runtime Architecture Reasoning
- Semantic Retrieval-backed Answers

---

## Contributor Intelligence

- Good-first Issue Suggestions
- Complexity Scoring
- Ownership Mapping
- Contributor Onboarding Guidance
- Learning Sequence Generation
- Risk-aware Recommendations

---

## Live AI Timeline Streaming

- Autonomous Repository Workflow
- Real-time Event Streaming
- Semantic Memory Updates
- Architecture Build Logs
- Runtime Execution Tracking

---

# Technology Stack

| Technology | Purpose |
|---|---|
| Next.js | Frontend Framework |
| React.js | UI Library |
| TypeScript | Type Safety |
| Tailwind CSS | Styling |
| FastAPI | Backend Framework |
| Python | Backend Runtime |
| D3.js | Interactive Graph Rendering |
| ELK.js | Graph Layout Engine |
| GitPython | Repository Cloning |
| OpenAI SDK | AI Enhancement |
| Render | Backend Deployment |
| Vercel | Frontend Deployment |

---

# Project Architecture

## Frontend (Vercel)

- Next.js App Router
- Interactive Architecture Graph
- Repository Dashboard
- AI Timeline
- Grounded Chat Interface
- Contributor Intelligence UI

---

## Backend (Render)

- FastAPI REST APIs
- Repository Intelligence Engine
- Semantic Retrieval Pipeline
- AST-based Code Analysis
- Dependency Graph Engine
- Runtime Architecture Mapping

---

## Intelligence Engine

### Core Systems

- Symbol Extraction Engine
- Dependency Graph Intelligence
- Repository Memory System
- Runtime Boundary Detection
- Authentication Detection
- Route Registry System

---

# AI Capabilities

| Capability | Description |
|---|---|
| Semantic Retrieval | Grounded repository understanding |
| Architecture Mapping | Runtime-aware graph intelligence |
| Repository Chat | Contextual code explanations |
| Dependency Analysis | Weighted relationship tracing |
| Auth Detection | JWT/RBAC discovery |
| Contributor Guidance | AI onboarding workflow |

---

# API Modules

## Repository Intelligence APIs

- Repository Analysis
- Architecture Mapping
- Dependency Graph Generation
- Semantic Memory Retrieval
- Contributor Insights

---

## AI Chat APIs

- Grounded Repository Chat
- Runtime Explanations
- Symbol Retrieval
- Architecture Reasoning
- File-aware Responses

---

# Environment Variables

## Frontend (.env)

```env
NEXT_PUBLIC_API_URL=https://codesherpa-ai-3.onrender.com
```

## Backend (.env)

```env
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
CODESHERPA_ALLOWED_ORIGINS=https://codesherpaai.vercel.app
PYTHON_ENV=production
```

---

# Local Setup

## 1. Clone Repository

```bash
git clone https://github.com/gagandeepsingh76/Codesherpa-ai.git
cd Codesherpa-ai
```

---

## 2. Install Dependencies

### Frontend

```bash
cd frontend
npm install
```

### Backend

```bash
cd backend
pip install -r requirements.txt
```

---

## 3. Setup Environment Variables

Create `.env` files for frontend and backend.

---

## 4. Run Frontend

```bash
cd frontend
npm run dev
```

---

## 5. Run Backend

```bash
cd backend
uvicorn main:app --reload
```

---

# Docker Setup

## Run Full Stack

```bash
docker compose up --build
```

---

# Product Surface

- Landing Page
- Repository Dashboard
- Architecture Visualization
- AI Timeline Panel
- Repository Chat
- Contributor Intelligence
- Dependency Intelligence
- Runtime Graph System

---

# Deployment Status

| Service | Status |
|---|---|
| Frontend | Live |
| Backend | Live |
| Repository Intelligence | Working |
| Architecture Visualization | Working |
| AI Chat | Working |
| Semantic Retrieval | Working |
| Timeline Streaming | Working |

---

# Future Improvements

- GitHub OAuth Integration
- Multi-repository Analysis
- Pull Request Intelligence
- ChromaDB Semantic Memory
- Exportable Architecture Reports
- Real-time Repository Monitoring
- AI-generated Contributor Tasks

---

# Author

## Gagandeep Singh

- Student Research Associate Intern at IIT Kanpur

---

# License

This project is created for educational, research, portfolio, and advanced AI developer tooling purposes.

Inspired by modern repository intelligence systems, architecture observability platforms, and AI-native developer experience tooling.
