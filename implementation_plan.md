# Manim AI Video Generator — Implementation Plan

## Overview

Build an AI-powered platform that turns a user-uploaded PDF + text prompt into a fully rendered Manim explainer video, with an interactive canvas annotation system that lets users highlight regions of the video and request deeper explanations — which are generated and stitched in without re-rendering the whole video.

The system has two major flows:
1. **GENERATE** — PDF upload → multi-agent pipeline → rendered `.mp4` playable in browser
2. **ANNOTATE** — canvas highlight + question → RAG/web-search context → new Manim clip → stitched into original video via stream-copy

---

## User Review Required

> [!IMPORTANT]
> **LLM Provider Choice**: The spec references both Anthropic Claude and OpenAI. I'll default to **Google Gemini** (since you already need Gemini for embeddings) for the LLM agent calls as well, using `langchain-google-genai`. This keeps dependencies minimal. Please confirm or specify a different provider.

> [!IMPORTANT]
> **Web Search Tool**: The `ResearchAgent` requires a web-search backend. The spec doesn't specify which. I'll use **Tavily** (native LangChain integration, easiest to configure) as a fallback. You'll need a `TAVILY_API_KEY`. Alternatively I can use Google Search API or SerpAPI.

> [!WARNING]
> **Modal + Qdrant + DO Spaces + Firebase require real accounts and API keys** — the code will be fully wired but you'll need to supply credentials in `.env` files before running. All the required variable names are documented in `DEVELOPER_GUIDE.md`.

> [!NOTE]
> **Manim rendering on Modal** will require a GPU-enabled Modal account tier. The CI dry-run step can run on CPU. The frontend and backend proxy work fully without Modal in local dev mode (`modal serve`).

---

## Open Questions

> [!IMPORTANT]
> 1. **Authentication**: Should the MVP include any user auth (NextAuth, Clerk, etc.) or is it fully open (no login)?  
>    *Default plan: No auth in MVP — add a note about adding an API key header before production.*
>
> 2. **Polling vs. WebSockets**: Should `/status` polling be simple HTTP polling from the frontend, or should I implement Server-Sent Events (SSE) for real-time progress updates?  
>    *Default plan: SSE from the Next.js API route, which connects to Modal's streaming response.*
>
> 3. **LLM Provider**: Gemini (default, already needed for embeddings) or Anthropic/OpenAI?
>
> 4. **Web Search**: Tavily (default) or another provider for the ResearchAgent fallback?

---

## Proposed Changes

### Repository Structure

```
d:\ai tutor\
├── docs/
│   ├── BUILD_PROMPT.md
│   ├── README.md
│   ├── ARCHITECTURE.md
│   ├── DEVELOPER_GUIDE.md
│   └── API_REFERENCE.md
├── frontend/                    # Next.js 15 app
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx             # Main UI: upload + player + canvas
│   │   ├── globals.css
│   │   └── api/
│   │       ├── generate/route.ts
│   │       ├── annotate/route.ts
│   │       └── status/[jobId]/route.ts
│   ├── components/
│   │   ├── UploadForm.tsx
│   │   ├── VideoPlayer.tsx
│   │   ├── AnnotationCanvas.tsx
│   │   ├── CommentBox.tsx
│   │   └── TimelineScrubber.tsx
│   ├── lib/
│   │   └── api.ts               # Client-side fetch helpers
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.ts
│   └── .env.local.example
├── backend/                     # Modal Python backend
│   ├── modal_app.py             # App entry + HTTP endpoints
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── graph.py             # LangGraph StateGraph definition
│   │   ├── models.py            # VideoJob dataclass
│   │   └── agents/
│   │       ├── __init__.py
│   │       ├── document_embedder.py
│   │       ├── story_agent.py
│   │       ├── validator_agent.py
│   │       ├── codegen_agent.py
│   │       ├── renderer_agent.py
│   │       └── uploader_agent.py
│   ├── annotation/
│   │   ├── __init__.py
│   │   ├── handler.py           # AnnotationHandler
│   │   └── stitcher.py          # ffmpeg stream-copy stitching
│   ├── rag/
│   │   ├── __init__.py
│   │   └── qdrant_store.py      # Qdrant + Gemini embeddings wrapper
│   ├── ci/
│   │   ├── __init__.py
│   │   └── pipeline.py          # Manim dry-run validation harness
│   ├── requirements.txt
│   └── .env.example
└── .gitignore
```

---

### Component 1: Documentation

#### [NEW] docs/BUILD_PROMPT.md, docs/README.md, docs/ARCHITECTURE.md, docs/DEVELOPER_GUIDE.md, docs/API_REFERENCE.md
Copy the provided spec content verbatim into `docs/`.

---

### Component 2: Backend — Data Models & Config

#### [NEW] backend/pipeline/models.py
- `VideoJob` dataclass — the LangGraph shared state object
- `AnnotationEvent` dataclass
- Status enums: `processing | done | error`
- All fields from the spec's class diagram

---

### Component 3: Backend — RAG Layer

#### [NEW] backend/rag/qdrant_store.py
- `QdrantRAGStore` class
- `EmbeddingsClient` wrapping `google-generativeai` text+multimodal embedding API
- `upsert(chunks, job_id)` — stores chunks scoped by `job_id` as a Qdrant payload filter
- `search(query, top_k, job_id)` — filtered vector search
- `create_collection_if_needed()` — idempotent setup

---

### Component 4: Backend — Agent Pipeline

#### [NEW] backend/pipeline/agents/document_embedder.py
- PDF text extraction using `pypdf`
- Page count validation (reject > 20 pages with `INVALID_PDF`)
- Chunk into ~500-token segments
- Call `QdrantRAGStore.upsert()`

#### [NEW] backend/pipeline/agents/story_agent.py
- RAG-query Qdrant with the user prompt
- Build a structured story/narrative script prompt
- Call Gemini via LangChain `ChatGoogleGenerativeAI`
- Return `VideoJob` with `story_script` set

#### [NEW] backend/pipeline/agents/validator_agent.py
- Score the script for quality/coverage
- Set `needs_revision = True/False` on `VideoJob`
- Track `revision_count`; after 2 revisions, approve regardless

#### [NEW] backend/pipeline/agents/codegen_agent.py
- Translate `story_script` into valid Manim Python `Scene` subclass code
- On retry: include `build_error_trace` in the prompt so LLM can fix specific errors
- Track `retry_count`; after 3 failures, set `status = "error"`

#### [NEW] backend/pipeline/agents/renderer_agent.py
- Write Manim code to a temp `.py` file on Modal's ephemeral storage
- Execute `manim render scene.py SceneName -o /output/video.mp4`
- Return path to rendered `.mp4`

#### [NEW] backend/pipeline/agents/uploader_agent.py
- Upload `.mp4` to DigitalOcean Spaces via `boto3`
- Save job metadata to Firestore
- Set `video_url` on `VideoJob`

---

### Component 5: Backend — CI Pipeline

#### [NEW] backend/ci/pipeline.py
- Write code to `/tmp/scene_{job_id}.py`
- `python -m py_compile` syntax check
- `python -c "import scene_..."` import check
- `manim render --dry_run scene.py SceneName` scene graph validation
- Return `(passed: bool, error_trace: str)`

---

### Component 6: Backend — LangGraph Graph

#### [NEW] backend/pipeline/graph.py
- `StateGraph(VideoJob)` with all agent nodes
- Conditional edges:
  - `validate → story` (if `needs_revision` and `revision_count < 2`)
  - `ci → codegen` (if `has_build_error` and `retry_count < 3`)
- Delta checkpointing configured
- `build_graph()` factory function

---

### Component 7: Backend — Annotation System

#### [NEW] backend/annotation/handler.py
- `AnnotationHandler` class
- For each annotation: embed frame+comment with Gemini vision embedding
- Vector search in Qdrant against job's collection
- If no relevant chunks: invoke `ResearchAgent` (Tavily web search via LangChain)
- Invoke `codegen_agent` to generate standalone `AnnotationScene`
- Invoke CI dry-run on each new clip
- Invoke `renderer_agent` for each new clip

#### [NEW] backend/annotation/stitcher.py
- Sort annotation clips by timestamp
- Build ffmpeg concat filter: stream-copy original segments, insert new clips
- Output versioned final video (e.g. `{job_id}-v{version}.mp4`)
- No re-encoding of original content

---

### Component 8: Backend — Modal App Entry Point

#### [NEW] backend/modal_app.py
- `modal.App("manim-app")`
- `manim_image` — Debian slim + Python + Manim + system deps (LaTeX, ffmpeg)
- `@app.function(gpu="A10G")` for `render_on_gpu`
- `@app.function()` for CI checks (CPU only)
- `@app.web_endpoint(method="POST")` for `/generate`
- `@app.web_endpoint(method="POST")` for `/annotate`
- `@app.web_endpoint(method="GET")` for `/status/{job_id}`

---

### Component 9: Frontend — Next.js App

#### [NEW] frontend/package.json
- Next.js 15, React 19, TypeScript
- No Tailwind (per guidelines) — Vanilla CSS
- `framer-motion` for micro-animations
- `react-hot-toast` for notifications

#### [NEW] frontend/app/globals.css
- CSS custom properties design system
- Dark-mode first, glassmorphism aesthetic
- Premium gradients, Inter/Outfit fonts from Google Fonts
- Smooth transitions on all interactive elements

#### [NEW] frontend/app/layout.tsx
- Root layout with meta tags, SEO, font imports

#### [NEW] frontend/app/page.tsx
- Two-phase UI:
  - **Phase 1**: Upload form + prompt input (before generation)
  - **Phase 2**: Video player + annotation canvas (after generation)
- SSE progress tracking during generation

#### [NEW] frontend/app/api/generate/route.ts
- Thin proxy: forward `multipart/form-data` to Modal `/generate`
- Never expose Modal URL to client

#### [NEW] frontend/app/api/annotate/route.ts
- Thin proxy: forward JSON to Modal `/annotate`

#### [NEW] frontend/app/api/status/[jobId]/route.ts
- Poll Modal `/status/{job_id}` and return JSON or SSE stream

---

### Component 10: Frontend — Components

#### [NEW] frontend/components/UploadForm.tsx
- Drag-and-drop PDF upload (with page count validation hint)
- Prompt textarea with character count
- Animated submit button with loading states
- Real-time progress bar during generation (SSE)

#### [NEW] frontend/components/VideoPlayer.tsx
- `<video>` element with `crossOrigin="anonymous"`
- `useRef` for imperative control (pause, seek, hot-swap src)
- Custom play/pause/seek controls
- Duration and current time display

#### [NEW] frontend/components/AnnotationCanvas.tsx
- Transparent canvas overlay on the video
- Pen tool: freehand path drawing on mousedown/mousemove/mouseup
- Path normalization (0-1 coords) for resolution independence
- Frame capture: composite video frame + drawn paths → base64 PNG
- Queue management: single submit vs. batch mode
- Visual indication of pending annotations

#### [NEW] frontend/components/CommentBox.tsx
- Floating popup at annotation centroid
- Textarea for question/comment
- "Submit Now" and "Add Another" buttons

#### [NEW] frontend/components/TimelineScrubber.tsx
- Custom video timeline bar
- Markers for pending annotations (colored dots)
- Markers for inserted annotation clips (different color)
- Click to seek

#### [NEW] frontend/lib/api.ts
- `generateVideo(formData)` — POST to `/api/generate`
- `submitAnnotations(jobId, annotations)` — POST to `/api/annotate`
- `pollStatus(jobId)` — SSE subscription to `/api/status/[jobId]`

---

## Verification Plan

### Automated Tests
- `cd backend && python -m pytest` — unit tests for CI pipeline, qdrant_store, models
- `cd frontend && npm run build` — TypeScript compilation check

### Manual Verification
1. Run `modal serve backend/modal_app.py` (requires Modal account)
2. Run `npm run dev` in `frontend/`
3. Upload a short 1-2 page PDF with a simple topic
4. Verify video appears within ~90s
5. Draw annotation, submit question
6. Verify updated video URL loads with stitched clip
7. Test batch annotation (queue 2, submit all)

### Mock Mode (for frontend-only development)
- The frontend API routes will accept a `?mock=true` query param that returns fixture JSON so the UI can be developed and previewed without a running Modal backend.
