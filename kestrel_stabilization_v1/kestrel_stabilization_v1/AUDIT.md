# AI-TUTOR Rescue Audit — 2026-09-04

## Executive diagnosis

The Antigravity change set did not fail because the project needs more agents or more architecture. It failed because several new components were only **half-migrated**: client/server contracts changed on one side, runtime dependencies were removed without replacement, SceneSpec compiler/CI/renderer implemented incompatible scene models, and UI persistence/repaint work was added on the main Qt thread.

The safest recovery is to restore one coherent local path first, then reintroduce cloud/data improvements incrementally.

## P0 — Why LaTeX currently fails

### 1. Desktop and FastAPI now speak different protocols

`app/backend/math_engine/latex_client.py` still sends local `/generate_latex` as form data. `backend/local_server.py` was refactored to require a JSON Pydantic request body. The local request therefore fails validation before the pipeline starts.

### 2. Modal fallback URL derivation is still wrong

The LaTeX client tries to derive cloud LaTeX endpoints by replacing `/generate` in a Modal URL whose endpoint name is in the hostname. That replacement does not produce the LaTeX endpoint.

### 3. Fresh installs do not contain Groq

`LatexStructureAgent` errors when the `groq` package is unavailable, but the current backend requirements and Modal image do not install it.

### 4. Tectonic was removed without a runtime installation path

The refactor untracked/deleted `tectonic.exe`, while both `/compile_pdf` and `TectonicCompileAgent` still rely on a local binary or `tectonic` on PATH. On a Windows machine that previously relied on the repository executable, PDF compilation now fails.

### 5. Modal LaTeX result is incomplete

The cloud worker/status response returns PDF bytes but not the editable `final_tex_code`/structured source expected by the desktop workflow.

## P0 — Why video currently fails

### 1. Renderer contains an unconditional NameError

`RendererAgent.run()` constructs `persistent_path = os.path.join(_VIDEOS_DIR, ...)`, but `_VIDEOS_DIR` is not defined/imported in the module. A render that reaches this point is turned into an error.

### 2. Scene compiler and CI still contradict each other

For multiple SceneSpecs, `SceneCompileAgent` emits separate `Scene_<id>` classes and no `MainScene`. CI Stage 0 still requires `class MainScene`. Multi-scene structured lessons therefore fail CI by construction.

### 3. Renderer introduced a second incompatible scene model

Renderer now renders each separate Scene class and concatenates the clips, while CI validates MainScene. The pipeline therefore has no single scene contract.

### 4. Structured whiteboard failure falls into legacy arbitrary Python

`graph.py` routes deterministic SceneSpec CI failures to `CodeGenAgent`. This hides the real compiler/contract bug and can replace a grounded structured lesson with unrelated free-form Python.

### 5. Storyboard validation deletes the important teaching actions

`StoryboardPlannerAgent._normalize_scenes()` only accepts actions whose target is a top-level object ID. Targetless `AskQuestion`/`RevealRule` actions are discarded, and nested term IDs are not valid targets. Missing transform reasons are replaced with `Direct transition`.

### 6. Video submission still creates fake jobs

The desktop returns a generated job ID after both local and Modal submission fail. Its worker then polls localhost, so the UI can display a long-running job that never existed.

## P0/P1 — Why the whiteboard lags

### 1. Full viewport repaint on every graphics update

`CanvasView` uses `FullViewportUpdate`. Every small ink/path/item update can repaint the complete viewport, including the grid, text, widgets, images and strokes.

### 2. Lasso drawing is O(n²) per gesture

On each mouse move the current code creates a fresh `QPainterPath` and replays every lasso point collected so far. Long lassos become progressively more expensive.

### 3. Autosave performs expensive work on the UI thread

One second after a scene mutation the main Qt thread serializes the entire scene, rewrites the full notebook JSON, updates the notebook index, and refreshes/rebuilds the Notebooks panel. The pause becomes very visible as notebook size grows.

### 4. Recent ink bookkeeping can grow during the notebook lifetime

The list used by AI-on-ink can accumulate many stroke objects. Later AI requests filter/render an increasingly large set unless the list is pruned/consumed.

## Redundant / misleading code introduced or preserved

- `fix_items.py` is a one-off source rewriting script with a hard-coded developer Windows path; the item-id migration has already been applied.
- `backend/config.py` added a new source of Modal URLs but the LaTeX client ignored it and the defaults did not match `modal.App("manim-app")`.
- `ArtifactStore.get_url()` reintroduced a hard-coded `localhost:8000` source of truth.
- CI smoke-render + renderer low-quality validation + renderer production rendering repeated expensive Manim work.
- The LaTeX editor still called its regex/HTML representation a PDF live preview even though export used a different Tectonic rendering path.
- The backend test suite still expected MathTex to be banned even after CI was modified to allow it.

## Rescue principle

Do not attempt material ingestion, true PDF preview, scene-level caching, AppData migration, annotation architecture and dead-code cleanup in the same recovery commit. First get these three invariants green:

1. Local LaTeX request -> actual compiled PDF.
2. Whiteboard SceneSpec[] -> one validated MainScene -> one playable MP4.
3. Drawing/lasso/autosave does not cause avoidable full-canvas work.

Only then continue architectural cleanup.
