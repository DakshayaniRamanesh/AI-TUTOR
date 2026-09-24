# Kestrel demo rescue patch

Verified target: `DakshayaniRamanesh/AI-TUTOR` at commit `bfdabef720a9aeb52e5f6658a18f78f5d64a4094`.

## Apply

From your AI-TUTOR repository root on Windows PowerShell:

```powershell
python path\to\kestrel_demo_rescue.py .
```

The script refuses to guess. If an expected code block is different, it aborts. Before editing a file it copies the original into `.kestrel_rescue_backup/<timestamp>/...`.

Do **not** use `--force` unless your current HEAD is intentionally different from the verified commit and you understand that only exact-block matches will be touched.

## Start the demo stack

Use the project's normal virtual environment. Start the local backend on the configuration the current code expects:

```powershell
python -m uvicorn backend.local_server:app --host 127.0.0.1 --port 8000
```

In a second terminal launch Kestrel using your normal entrypoint.

## 10-minute smoke test before presenting

1. Open Kestrel and create/open a subject.
2. Create a subject notebook, draw a simple equation such as `2x + 2 = 6`, invoke Feather, then write `2x = 4`. The first line should be captured without a fake green verification; the next transition can be checked.
3. Open a different notebook and verify old Feather output does not jump into it.
4. Save a blank/scratch notebook, close/reopen it, and verify it loads without session/foreign-key errors.
5. Upload/open a PDF under a subject, ask a question, and click a citation. It should open the material using its stored file path and call `go_to_page`, not the removed `load_document/jump_to_page` methods.
6. Select canvas content and run LaTeX conversion. The former `GroupSelectionBox` / `RemoteCursor` import crash is removed.
7. From PDF study mode request video/notes. PDF path, page range, emphasis and output type now travel through the request contract; `/generate` constructs `VideoJob(user_prompt=...)` instead of the invalid `prompt=` argument.
8. Ask a subject-material question after ingestion. Vector hits now retain chunk/material IDs, preventing all vector results from collapsing into the `None` fusion key.
9. Open the knowledge graph and move a node. The query side now reads the same `graph_layout` table written by the layout service.
10. Watch both terminals for tracebacks. If an external AI key/provider, Manim/Tectonic/FFmpeg, or Qdrant service is unavailable, that is environment/runtime availability rather than one of the repaired code mismatches.

## What this patch does *not* claim

This is a high-confidence demo rescue for source defects verified in the pinned `main` commit. It cannot guarantee cloud API availability, model/provider credentials, local Manim/Tectonic/FFmpeg installation, or your existing SQLite/Alembic state without running on your machine. The installer runs `py_compile` over every file it modifies so it will not silently leave a syntax-broken tree.
