# Performance Optimizations

This document details the architectural and algorithmic optimizations implemented in the Kestrel media generation and rendering pipeline.

---

## Quick Reference

| # | Optimization | Primary Module | Performance Impact | Compute Impact |
|---|---|---|---|---|
| 1 | **GPU Accelerated Rendering (OpenGL)** | `renderer_agent.py` | Up to 2x faster scene rendering | Utilizes idle GPU silicon on Modal A10G |
| 2 | **Hardware Video Encoding (NVENC)** | `renderer_agent.py` | 3–5x faster post-encode | Offloads CPU; automatic fallback to `libx264` |
| 3 | **Stage 4 CI Frame-0 Smoke Test** | `backend/ci/pipeline.py` | Catches bad LaTeX in ~10s | Saves 2–5 minutes of GPU compute per failure |
| 4 | **Selective Text() vs. MathTex()** | `codegen_agent.py` | 30–50% faster non-math render | Drastically reduces TeX Live compilation overhead |
| 5 | **Vetted Scene Template Library** | `scene_templates.py` | First-pass success &gt;90% | Eliminates LLM code-generation retries |
| 6 | **Cross-Student Video Cache** | `qdrant_store.py` | Instant playback on repeat queries | Zero GPU cost for recurring curriculum questions |
| 7 | **Server-Sent Events (SSE)** | `modal_app.py`, `local_server.py` | Sub-100ms UI latency | Replaces 60+ repeated HTTP polling queries |

---

## 1. GPU Accelerated Rendering (OpenGL) & NVENC Hardware Encoding

**Module:** `backend/video_generation/agents/renderer_agent.py`

### 1.1 The Bottleneck
Manim's default rendering engine relies on Cairo, which is strictly single-threaded and CPU-bound. When deploying to GPU instances (such as Modal's NVIDIA A10G), Cairo left GPU cores completely idle. Furthermore, raw Manim output was uncompressed and unoptimized for streaming.

### 1.2 Implementation
The rendering pipeline implements a multi-tier hardware acceleration strategy:

1. **OpenGL Scene Graph Traversal**: Invokes Manim with `--renderer=opengl`, delegating vertex transformations and shader operations directly to the GPU context. If an OpenGL display context cannot be initialized, it falls back to Cairo automatically.
2. **NVENC Hardware Encoding**: Post-processes rendered frames using FFmpeg's `h264_nvenc` encoder instead of software `libx264`:
   ```python
   # Detect encoder availability at initialization
   ffmpeg_check = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
   has_nvenc = "h264_nvenc" in ffmpeg_check.stdout

   encoder = "h264_nvenc" if has_nvenc else "libx264"
   encode_cmd = [
       "ffmpeg", "-y", "-i", raw_mp4,
       "-c:v", encoder,
       "-preset", "fast",
       "-pix_fmt", "yuv420p",
       "-movflags", "+faststart",
       output_path
   ]
   ```
3. **Streaming Flags**: Applies `-pix_fmt yuv420p` for cross-platform color support and `-movflags +faststart` to move the atom metadata (`moov`) to the beginning of the file, allowing playback to begin before the file has completely finished downloading.

---

## 2. Stage 4 CI Frame-0 Smoke Test

**Module:** `backend/ci/pipeline.py`

### 2.1 The Bottleneck
Standard syntax and import verification caught static parsing failures but missed runtime scene construction exceptions, such as:
- Malformed LaTeX strings inside `MathTex(r"\undefined{symbol}")`
- Incompatible `.animate` transform method targets
- Late-binding variable reference errors

These bugs passed preliminary checks and failed several minutes into a full 1080p GPU render.

### 2.2 Implementation
`CIPipelineHarness` implements a 4-stage sequential verification:

```
Code Input ──> [Stage 1: py_compile] ──> [Stage 2: Python Import] ──> [Stage 3: Manim --dry_run] ──> [Stage 4: Low-res Frame-0 Smoke Render]
```

Stage 4 renders only the very first frame at low quality (`-ql -s`):
```python
smoke_cmd = [
    "manim", "render", "-ql", "-s",
    "--media_dir", temp_smoke_dir,
    file_path, scene_name
]
result = subprocess.run(smoke_cmd, capture_output=True, text=True, timeout=60)
```
This forces Manim to construct all Mobjects, compile LaTeX formulas, and bind textures. If Stage 4 fails, execution halts in ~10 seconds and returns compiler diagnostics to `CodeGenAgent` for immediate repair.

---

## 3. Selective Text() vs. MathTex()

**Module:** `backend/video_generation/agents/codegen_agent.py`

### 3.1 The Bottleneck
LaTeX compilation via TeX Live is the single most CPU-intensive step within Manim. Earlier implementations wrapped all on-screen prose in `MathTex()`, triggering TeX engine invocations even for plain English titles and descriptive labels.

### 3.2 Implementation
`CodeGenAgent` enforces strict typing rules in prompts and templates:
- **`Text()`**: Mandatory for all titles, narrative statements, bullet lists, and labels. Rendered instantly via Pango/Cairo typography without TeX compilation.
- **`MathTex()`**: Reserved strictly for mathematical equations, scientific units, and symbolic formulas.

```python
# Optimal:
title = Text("Newton's Second Law of Motion", font_size=36)
formula = MathTex(r"\vec{F} = m \vec{a}", font_size=48)

# Sub-optimal (triggers TeX Live overhead):
title = MathTex(r"\text{Newton's Second Law of Motion}")
```

For non-mathematical subjects (biology, history, programming), this reduces rendering duration by **30% to 50%**.

---

## 4. Vetted Scene Template Library

**Module:** `backend/video_generation/scene_templates.py`

### 4.1 The Bottleneck
Unconstrained LLM code generation produces syntax and scene-graph errors in approximately 30% of initial attempts, resulting in repeated CI failure and retry loops.

### 4.2 Implementation
`SceneTemplateLibrary` provides five pre-compiled, parameter-validated Manim scene templates:

| Template | Intended Domain | Characteristics |
| :--- | :--- | :--- |
| `concept_explainer` | General science, humanities, CS | Uses `Text()` exclusively; zero LaTeX compile overhead. |
| `math_explainer` | Calculus, linear algebra, physics | Integrates coordinate systems and `MathTex` formulas. |
| `process_flow` | Algorithms, state machines, pipelines | Structured sequence of nodes interconnected with directional arrows. |
| `comparison` | Comparative analysis, trade-offs | Split-screen two-column comparative layout. |
| `matrix_transform` | Vector calculus, machine learning | Grid transformation and matrix-vector operations. |

The pipeline attempts template parameter injection first. If the prompt does not match template heuristics or fails, it falls back to free-generation.

---

## 5. Cross-Student Video Cache

**Module:** `backend/workspace/qdrant_store.py`

### 5.1 The Bottleneck
In educational cohorts, multiple students frequently submit identical or semantically equivalent questions against the same reference material, causing duplicate GPU rendering runs.

### 5.2 Implementation
A dedicated Qdrant collection (`manim-video-cache`) indexes completed video artifacts:

1. **Content Hash (Exact Match)**: Computes a SHA-256 digest of normalized prompt text and the first 2,000 characters of the source document:
   ```python
   content_hash = QdrantRAGStore.compute_content_hash(document_text, user_prompt)
   ```
2. **Semantic Similarity (Near-Duplicate Match)**: Compares prompt embeddings using cosine similarity with a threshold &ge; 0.92 within the same document context.
3. **Short-Circuit Execution**: If a cache hit occurs, the pipeline bypasses code generation and rendering, returning the existing video URL in under 50 milliseconds.

---

## 6. Server-Sent Events (SSE) Status Streaming

**Module:** `backend/local_server.py`, `backend/modal_app.py`

### 6.1 The Bottleneck
Traditional HTTP polling (`GET /status/{job_id}` every 1–2 seconds) produces ~60 unnecessary HTTP requests per generation job and introduces up to 2 seconds of latency between agent phase transitions.

### 6.2 Implementation
The `/stream_status` endpoint exposes an `EventStream` (`text/event-stream`):
- Pushes state delta updates immediately upon agent completion.
- Replaces repeated request overhead with a single persistent HTTP connection.
- Reduces UI state update latency to sub-100ms while maintaining fallback polling support.
