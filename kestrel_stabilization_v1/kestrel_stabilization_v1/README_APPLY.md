# Kestrel Stabilization v1

Reviewed against `DakshayaniRamanesh/AI-TUTOR` main at commit:

`ae8198bf664fe0cc55f20a32962c2a5b946d5a52` (`Code Simplified 2`)

This is a **stabilization patch**, not another architecture rewrite. It targets the regressions that currently prevent LaTeX/video generation and the biggest whiteboard lag amplifiers.

## Before applying

```bash
git checkout main
git pull
git status
```

The working tree must be clean.

Create your own safety branch first:

```bash
git switch -c rescue/kestrel-before-stabilization
```

Copy this entire `kestrel_stabilization_v1` folder into the repository root, then run:

```bash
python kestrel_stabilization_v1/kestrel_stabilize.py --check
```

If the reviewed base matches, apply and run focused tests:

```bash
python kestrel_stabilization_v1/kestrel_stabilize.py --apply --test
```

The patcher stores timestamped backups under `.git/kestrel_rescue_backup_*`, so they stay outside the working tree and cannot be committed accidentally.

## Install dependencies after applying

```bash
pip install -r requirements.txt
```

### Tectonic is an external runtime dependency

The previous refactor removed the tracked `tectonic.exe`, which is good repository hygiene but it did not provide a replacement installation mechanism. Install Tectonic separately and make it available on `PATH`, **or** set:

```text
TECTONIC_BIN=<absolute path to tectonic executable>
```

The patch intentionally does not auto-download or execute a binary.

## Environment configuration

The patch restores consistent defaults:

```text
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
BACKEND_URL=http://127.0.0.1:8000
```

Modal defaults match the current `backend/modal_app.py` app name, but explicit deployment URLs are still preferable:

```text
MODAL_VIDEO_GENERATE_URL=...
MODAL_VIDEO_STATUS_URL=...
MODAL_LATEX_GENERATE_URL=...
MODAL_LATEX_STATUS_URL=...
MODAL_ANNOTATE_URL=...
```

If using Groq:

```text
GROQ_API_KEY=...
```

If Groq is unavailable, the patched LaTeX structurer can fall back to Gemini using `GOOGLE_API_KEY`.

## What v1 fixes

### LaTeX

- desktop client now sends JSON matching the new FastAPI Pydantic contract;
- removes broken Modal URL `.replace('/generate', ...)` logic;
- preserves study/classroom mode across cloud fallback;
- removes fake LaTeX job IDs;
- polls the backend that accepted the job;
- adds missing `groq` dependency to local + Modal runtime;
- decodes base64 image data to bytes before Gemini vision;
- adds Gemini text fallback for DocumentIR structuring;
- returns editable LaTeX code through Modal status;
- detects Tectonic from `TECTONIC_BIN`, legacy local binary, or `PATH`;
- bounds Tectonic compilation to 180 seconds and 2 compile attempts.

### Video

- removes fake video job IDs;
- remembers whether local or Modal accepted a job and polls that endpoint;
- compiles **all SceneSpecs into one MainScene**;
- renderer renders exactly that MainScene rather than independent scene classes + fragile FFmpeg concatenation;
- removes the fatal undefined `_VIDEOS_DIR` reference;
- removes redundant low-quality render before production render (CI already smoke-renders);
- structured whiteboard CI failure no longer silently switches to arbitrary legacy LLM Python;
- fixes Storyboard normalization so `AskQuestion`, `RevealRule`, nested term IDs, `HighlightTerm`, and `MapTerms` survive;
- missing transform reasons are rejected instead of becoming `Direct transition`.

### Whiteboard performance

- changes QGraphicsView from `FullViewportUpdate` to `BoundingRectViewportUpdate`;
- updates lasso drawing incrementally instead of rebuilding the whole path every mouse move;
- caps stale/recent ink bookkeeping;
- increases autosave debounce from 1.0s to 2.5s;
- stops rebuilding the whole Notebooks panel on every autosave;
- saves board JSON compactly and atomically;
- removes the one-off `fix_items.py` migration script with a hard-coded developer path.

### Truthful preview

The HTML LaTeX preview remains an approximation in v1. The UI is relabeled so it no longer claims to be a true compiled PDF preview. A real background-compiled preview should be a separate follow-up after generation is stable.

## Focused verification

Automated:

```bash
python -m compileall -q app backend
pytest -q tests/test_stabilization_contracts.py tests/test_whiteboard_video_foundations.py backend/tests/test_video_pipeline.py
```

Manual local backend:

```bash
python -m uvicorn backend.local_server:app --host 127.0.0.1 --port 8000
```

Then verify:

1. Draw a small equation, select it, Generate LaTeX.
2. Confirm the request appears in backend logs and does not return HTTP 422.
3. Confirm transcription -> structure -> template -> Tectonic stages occur.
4. Draw/select whiteboard content and Generate Video.
5. Confirm `scene_compile` creates `MainScene`, CI passes it, renderer produces one MP4.
6. Open a large notebook, draw continuously and lasso a large region; compare interaction latency.

## Deliberately not solved in v1

Do **not** re-expand scope until local LaTeX/video smoke tests pass. These remain for v2:

- complete `material_id` migration and cache isolation audit;
- true PDF page preview in a background worker;
- fully asynchronous notebook serialization;
- cloud artifact hosting when DigitalOcean Spaces is unavailable;
- typed math-transition validation (`VALID/INVALID/UNKNOWN`);
- removal of the remaining legacy StoryAgent/CodeGen path for non-whiteboard requests;
- scene-level caching/rendering (after MainScene is stable);
- AppData migration for notebook/runtime storage;
- deeper dead-code deletion after import/reference analysis.
