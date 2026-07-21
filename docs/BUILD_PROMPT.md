# Manim AI Video Generator — Build Prompt Specification

## System Overview
The Manim AI Video Generator is an AI-powered system that accepts a PDF document and a user prompt to generate a rendered Manim explainer video. Additionally, users can annotate rendered videos by drawing highlights over specific frames, attaching questions/comments, and requesting extended explanations. The system processes these annotations via RAG and web search fallbacks, generates new Manim animation clips, and stitches them seamlessly into the original video using stream-copy ffmpeg techniques.

## Core Features
1. **PDF Ingestion & Embeddings**: Extract text, chunk, and embed into Qdrant vector database using Google Gemini embeddings.
2. **Multi-Agent Video Pipeline (LangGraph)**:
   - `DocumentEmbedderAgent`: Parse PDF and upload chunks to Qdrant.
   - `StoryAgent`: Craft pedagogical narrative script based on query and document context.
   - `ValidatorAgent`: Evaluate script quality and completeness.
   - `CodeGenAgent`: Generate executable Python Manim `Scene` code with error-retry capabilities.
   - `RendererAgent`: Render Manim scenes to MP4 on Modal GPU containers.
   - `UploaderAgent`: Save assets to DigitalOcean Spaces & update job metadata in Firestore.
3. **CI/CD Dry-Run Pipeline**: Pre-execution syntax, import, and scene-graph dry-run checks before full GPU rendering.
4. **Interactive Canvas & Extended Explanation**:
   - Frame capture + drawn annotation overlay.
   - Dynamic clip generation via RAG lookup or Tavily web search fallback.
   - Lossless video stitching (ffmpeg stream-copy concat).
5. **Modern Web Frontend**:
   - Next.js 15 app with custom glassmorphism design system.
   - Canvas drawing overlay with normalized coordinate capture.
   - Real-time progress updates and timeline scrubber with annotation markers.
