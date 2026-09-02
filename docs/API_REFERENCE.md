# API Reference

The Kestrel backend exposes a REST API via FastAPI for video generation, LaTeX typesetting, media streaming, and system diagnostics.

The default local base URL is:
```
http://localhost:8000
```
When deployed to Modal, endpoints are hosted under your Modal environment subdomain.

---

## 1. Video Generation Endpoints

### 1.1 `POST /generate`
Submits a text prompt and an optional PDF file to initiate the video generation pipeline or document study notes generation.

- **URL**: `/generate`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`

#### Request Parameters (Form Fields)

| Field | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `prompt` | `string` | Yes | &mdash; | Natural language description of the lesson or animation to generate. |
| `pdf` | `file` (binary) | No | `None` | Source educational document (PDF format, maximum 20 pages). |
| `page_range` | `string` | No | `""` | Comma-separated or hyphenated page range to process (e.g. `"1-5"` or `"3,7"`). |
| `emphasis_note` | `string` | No | `""` | Additional pedagogical guidance or specific emphasis for the script generator. |
| `output_type` | `string` | No | `"video"` | Target output format: `"video"` (Manim MP4) or `"notes"` (LaTeX study notes PDF). |
| `subject_id` | `string` | No | `""` | Optional UUID of the subject to associate generated media with. |

#### Response (`200 OK`)

```json
{
  "job_id": "job_a1b2c3d4",
  "status": "processing",
  "message": "Video generation pipeline started for uploaded document."
}
```

#### Side Effects
- Allocates a new `VideoJob` instance in memory / database.
- Writes uploaded PDF to a temporary file on disk.
- Spawns asynchronous worker `run_job_background`.

---

### 1.2 `GET /status/{job_id}`
Retrieves the execution status, progress, and artifact URLs for an active or completed video generation job.

- **URL**: `/status/{job_id}`
- **Method**: `GET`

#### Path Parameters

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `job_id` | `string` | Yes | Unique job identifier returned by `POST /generate`. |

#### Response (`200 OK`)

```json
{
  "job_id": "job_a1b2c3d4",
  "status": "done",
  "step": "uploader",
  "progress_percentage": 100,
  "video_url": "http://localhost:8000/video/job_a1b2c3d4_encoded.mp4",
  "video_local_path": "C:\\Users\\...\\job_a1b2c3d4_encoded.mp4",
  "error_message": null,
  "version": 1,
  "story_script": "Scene 1: Newton's First Law..."
}
```

#### Status Values

| Status | Description |
| :--- | :--- |
| `pending` | Job is queued and waiting for worker initialization. |
| `processing` | Job is actively running through pipeline agents. |
| `done` | Pipeline completed successfully; `video_url` is available. |
| `error` | Pipeline encountered an unrecoverable failure; see `error_message`. |

#### Error Responses
- `404 Not Found`:
  ```json
  {
    "error": "Job not found"
  }
  ```

---

### 1.3 `POST /annotate`
Submits drawn canvas highlights and questions referencing a specific video frame, generating an appended explanation clip stitched via FFmpeg.

- **URL**: `/annotate`
- **Method**: `POST`
- **Content-Type**: `application/json`

#### Request Body Schema

```json
{
  "job_id": "job_a1b2c3d4",
  "annotations": [
    {
      "timestamp": 14.5,
      "frame_image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
      "paths": [
        {
          "points": [[0.25, 0.40], [0.28, 0.42], [0.35, 0.50]],
          "stroke_color": "#ef4444",
          "stroke_width": 3
        }
      ],
      "comment": "Why does the acceleration vector point toward the center here?"
    }
  ]
}
```

#### Path & Annotation Fields

| Field | Type | Description |
| :--- | :--- | :--- |
| `job_id` | `string` | Parent job identifier. |
| `annotations[].timestamp` | `float` | Playback position (seconds) where the video was paused. |
| `annotations[].frame_image`| `string` | Base64 PNG composite of the paused frame and student drawing. |
| `annotations[].paths` | `array` | Normalized coordinate paths (`[0.0, 1.0]`) drawn on canvas. |
| `annotations[].comment` | `string` | User's question or clarification request. |

#### Response (`200 OK`)

```json
{
  "job_id": "job_a1b2c3d4",
  "status": "updated",
  "version": 2,
  "video_url": "http://localhost:8000/video/job_a1b2c3d4_v2.mp4"
}
```

#### Side Effects
- Queries Qdrant RAG store with fallback to Tavily search.
- Generates a new Manim explanation clip (`AnnotationScene`).
- Stitches the new clip to the original video using `ffmpeg -f concat -c copy` without re-encoding existing frames.

---

### 1.4 `GET /video/{filename}`
Streams a generated MP4 animation.

- **URL**: `/video/{filename}`
- **Method**: `GET`, `HEAD`

#### Path Parameters

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `filename` | `string` | Yes | Target video filename (e.g. `job_a1b2c3d4_encoded.mp4`). |

#### Response
- Status: `200 OK`
- Header: `Content-Type: video/mp4`
- Body: Binary video stream.

---

## 2. LaTeX and Typesetting Endpoints

### 2.1 `POST /generate_latex`
Transforms handwriting or drawn canvas work into a compiled LaTeX document.

- **URL**: `/generate_latex`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`

#### Request Parameters (Form Fields)

| Field | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `image_b64` | `string` | Yes | &mdash; | Base64-encoded image buffer of the canvas/handwriting. |
| `template_type` | `string` | No | `"Homework"` | Template type: `"Homework"`, `"Assignment"`, `"Research Paper"`, or `"Lecture Slides"`. |
| `mode` | `string` | No | `"study"` | Operational mode: `"study"`, `"exam"`, or `"notes"`. |
| `classroom_action` | `string` | No | `"Solve Question"` | Action prompt: `"Solve Question"`, `"Format Notes"`, etc. |

#### Response (`200 OK`)

```json
{
  "job_id": "latex_9f8e7d6c",
  "status": "processing",
  "message": "LaTeX generation pipeline started."
}
```

---

### 2.2 `GET /latex_status/{job_id}`
Retrieves the compilation status and output artifacts for a LaTeX generation job.

- **URL**: `/latex_status/{job_id}`
- **Method**: `GET`

#### Response (`200 OK`)

```json
{
  "job_id": "latex_9f8e7d6c",
  "status": "done",
  "step": "completed",
  "progress_percentage": 100,
  "pdf_url": "http://localhost:8000/pdf/latex_9f8e7d6c.pdf",
  "latex_code": "\\documentclass{article}\\n\\begin{document}...",
  "raw_transcription": "Formula: E = mc^2",
  "structured_latex": "\\begin{equation}\\nE = mc^2\\n\\end{equation}",
  "error_message": null
}
```

---

### 2.3 `POST /compile_pdf`
Compiles an arbitrary LaTeX code string directly into a PDF using Tectonic.

- **URL**: `/compile_pdf`
- **Method**: `POST`
- **Content-Type**: `application/json`

#### Request Body Schema

```json
{
  "latex_code": "\\documentclass{article}\n\\begin{document}\nHello World\n\\end{document}"
}
```

#### Response (`200 OK`)

```json
{
  "status": "ok",
  "pdf_b64": "JVBERi0xLjUKJcfsj6IKNCAwIG9iai..."
}
```

#### Error Response (`500 Internal Server Error`)

```json
{
  "status": "error",
  "message": "Compilation failed: ! LaTeX Error: Undefined control sequence."
}
```

---

### 2.4 `GET /pdf/{filename}`
Streams a compiled PDF document.

- **URL**: `/pdf/{filename}`
- **Method**: `GET`, `HEAD`

#### Response
- Status: `200 OK`
- Header: `Content-Type: application/pdf`
- Body: Binary PDF stream.

---

## 3. Diagnostic Endpoints

Used by the desktop client settings panel to verify external credentials and local tool availability.

### 3.1 `GET /api/diagnostics/groq`
Tests connection to the Groq API and validates the configured `GROQ_API_KEY`.

- **URL**: `/api/diagnostics/groq`
- **Method**: `GET`

#### Responses
- `200 OK`:
  ```json
  {
    "status": "ok",
    "message": "Groq connected"
  }
  ```
- `400 Bad Request` (Missing/Placeholder Key):
  ```json
  {
    "status": "error",
    "message": "GROQ_API_KEY is not configured (placeholder detected in backend/.env)"
  }
  ```
- `500 Internal Server Error` (Invalid Key / Network Failure):
  ```json
  {
    "status": "error",
    "message": "Error code: 401 - {'error': {'message': 'Invalid API Key'}}"
  }
  ```

---

### 3.2 `GET /api/diagnostics/gemini`
Tests connection to the Google Gemini API, cycling through fallback models (`gemini-2.0-flash`, `gemini-1.5-flash`).

- **URL**: `/api/diagnostics/gemini`
- **Method**: `GET`

#### Responses
- `200 OK`:
  ```json
  {
    "status": "ok",
    "message": "Gemini connected (gemini-2.0-flash)"
  }
  ```
- `400 Bad Request` (Missing/Placeholder Key):
  ```json
  {
    "status": "error",
    "message": "GOOGLE_API_KEY is not configured (placeholder detected in backend/.env)"
  }
  ```

---

### 3.3 `GET /api/diagnostics/tectonic`
Verifies the presence and execution of the Tectonic XeTeX binary (`tectonic.exe`). If missing, attempts automatic binary acquisition.

- **URL**: `/api/diagnostics/tectonic`
- **Method**: `GET`

#### Responses
- `200 OK`:
  ```json
  {
    "status": "ok",
    "message": "Tectonic found"
  }
  ```
- `500 Internal Server Error`:
  ```json
  {
    "status": "error",
    "message": "Tectonic binary not found"
  }
  ```

---

## 4. Streaming Endpoints

### 4.1 `GET /stream_status` (Modal Serverless)
Provides real-time pipeline status via Server-Sent Events (SSE).

- **URL**: `/stream_status?job_id={job_id}`
- **Method**: `GET`
- **Header**: `Accept: text/event-stream`

#### Event Stream Output

```
data: {"job_id": "job_a1b2c3d4", "status": "processing", "step": "story_agent", "progress_percentage": 25}

data: {"job_id": "job_a1b2c3d4", "status": "processing", "step": "codegen_agent", "progress_percentage": 50}

data: {"job_id": "job_a1b2c3d4", "status": "done", "step": "uploader", "progress_percentage": 100, "video_url": "https://..."}
```
