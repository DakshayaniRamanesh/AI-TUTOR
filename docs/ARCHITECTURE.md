# Architecture & Design Specification

## Subsystems

### 1. Multi-Agent Pipeline (LangGraph)
- **DocumentEmbedderAgent**: Extracts text from PDF documents using `pypdf`, validates page count constraints (<= 20 pages), chunks into ~500-token segments, and indexes them into Qdrant.
- **StoryAgent**: Queries Qdrant vector database using the user's prompt, formats a structured script detailing visual scenes, equations, and voiceover text, and generates content via Gemini LLM.
- **ValidatorAgent**: Analyzes the script for pedagogical clarity, topic coverage, and Manim feasibility. Returns feedback or triggers script revisions.
- **CodeGenAgent**: Converts script scenes into valid Manim code (`Scene` subclasses). Retries with build error traces if CI dry-run fails.
- **RendererAgent**: Invokes Manim executable on Modal GPU server to render 1080p MP4 animations.
- **UploaderAgent**: Transfers output MP4s to DigitalOcean Spaces S3-compatible storage and logs metadata to Firestore.

### 2. CI/CD Validation Harness
Before committing to full GPU rendering, generated Python code passes through 3 validation stages:
1. Syntax check (`py_compile`)
2. Module import check
3. Manim scene graph dry-run (`manim render --dry_run`)

### 3. Annotation & Stream-Copy Stitching System
- Captures drawn canvas highlights (normalized vectors) + current frame timestamp + user question.
- Perform multimodal vector retrieval against Qdrant. Fallback to web search (Tavily) if similarity score is low.
- Render isolated Manim clip for the answer.
- Concat with original video via FFmpeg stream-copy (`ffmpeg -f concat -i list.txt -c copy output.mp4`) without re-encoding existing video segments.

### 4. Next.js Frontend
- Custom HTML5 Video Player synchronized with a transparent HTML5 `<canvas>` drawing layer.
- Support for freehand drawing, centroid calculation, timestamp tagging, and batch queueing.
- Real-time updates via Server-Sent Events (SSE) / Polling.
