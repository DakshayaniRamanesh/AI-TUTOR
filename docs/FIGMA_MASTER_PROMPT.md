# 🎨 Kestrel UI/UX — Master Figma Design & Competition Prototype Specification
> **Comprehensive Interactive UI Guide, Component State Matrix, Folder Hierarchy, Canvas Spec, and Direct Figma AI Prompt**
> *Targeted for Competition Showcase, Figma Auto-Layout Design, Prototyping & Design System Documentation*

---

## 📋 Table of Contents

1. [🚀 Direct Copy-Paste Prompt for Figma AI / UI Generators](#-direct-copy-paste-prompt-for-figma-ai--ui-generators)
2. [✨ Master Interactive State & Hover Effect Matrix](#-master-interactive-state--hover-effect-matrix)
3. [📂 Feature 2: Subject-to-Notebook Folder Drill-Down System](#-feature-2-subject-to-notebook-folder-drill-down-system)
4. [📐 Feature 3: Pixel-Perfect Canvas Board & Floating Toolbar Spec](#-feature-3-pixel-perfect-canvas-board--floating-toolbar-spec)
5. [🕸 Feature 4: Interactive Knowledge Graph Studio & Node Inspector](#-feature-4-interactive-knowledge-graph-studio--node-inspector)
6. [🎨 Figma Global Design Tokens (Color, Typography, Elevation & Radius)](#-figma-global-design-tokens)
7. [🎬 Competition Demo Flow & Interactive Prototyping Wiring](#-competition-demo-flow--interactive-prototyping-wiring)

---

## 🚀 Direct Copy-Paste Prompt for Figma AI / UI Generators

*You can copy and paste the prompt block below directly into Figma AI, Claude Artifacts, or design generation tools to generate the complete interface:*

```text
Design an ultra-premium, competition-ready desktop UI for "Kestrel" — an Intelligent Handwritten Notebook & STEM Learning Environment for A/L and university students (Maths, Physics, Chemistry).

Visual Identity:
- Theme: Warm Parchment Light Theme (#f5f2ec background, #faf8f4 card surfaces, #ede9e1 sunken formula boxes) with Dark Midnight Navy Sidebar (#0f1623).
- Primary Accent: Deep Academic Teal (#1e6b6b), Hover (#165858), Active/Light (#e8f4f4).
- Discipline Colors: Cobalt Mathematics (#2c5f8a), Violet Chemistry (#5a3e8a), Amber Exam/AI Pending (#8a5a1e), Emerald Success/Grounded (#1a6b3a).
- Typography: Plus Jakarta Sans for UI/controls (10px to 15px), Newsreader Serif for editorial headings (20px to 36px), JetBrains Mono for equations and code (10px to 12px).

Layout Structure (1440x900px Desktop Shell):
1. Top macOS Titlebar (34px height): Traffic light dots (#ff5f56, #ffbd2e, #27c93f), centered title "Kestrel · Handwritten Freeform Notebook", theme toggle on right.
2. Left Iconic Navy Sidebar (50px width, #0f1623): 34x34px icon buttons with tooltips for Home, Canvas, Subjects (Syllabus), PDF Study (RAG), Knowledge Graph, PDF Explainer, Git Version Control, Starred Boards.
3. Top Navigation Toolbar (44px height): Back chevron, Board title ("Kinematics & Reaction Kinetics · Board 1"), "Auto-Saved" emerald pill, 4-mode layout picker (Blank, Dotted, Ruled, Math Grid), Action buttons (Insert, Solve, LaTeX, Study), Primary Teal Save Button, Search/Undo/Settings icon buttons.

Required Screen Views:
- View 1 (Canvas Studio): 3-column interactive layout on a subtle dotted background.
  * Col 1: Draw-and-hold parametric shape snapping card (raw ghost stroke vs #1e6b6b snapped ellipse with 4 anchor handles) + Real-time Bézier handwriting neatening card (jitter wave vs smoothed spline) + 4096 pressure level specs.
  * Col 2: Human-in-the-Loop AI structural synthesis card (Amber border, 99.2% confidence badge, Phenol benzene ring SVG diagram, Accept/Dismiss buttons) + STEM 2D kinematic trajectory derivation card.
  * Col 3: Yellow sticky note (#fef6d6, border #f5e08a, -1deg tilt) with exam prep notes + Docked Floating Smart Pen Toolbar (48px pill, white bg, shadow-floating, containing Undo, Redo, active Teal Selection tool, Hand, Pen, Highlighter, Eraser, Sticky, Shapes, LaTeX Sigma, AI Sparkles).
- View 2 (Subjects & Notebook Folder Drill-Down):
  * Level 1: Curriculum overview cards for Combined Mathematics, Physics, Chemistry with unit badges, sync tags, and stats.
  * Level 2 (Drill-Down Folder View): Breadcrumbs (Subjects > Combined Mathematics > Unit 04: Calculus), grid of sub-folders (Unit 01 to 05), active folder displaying relative notebooks list (Limits & Multivariable Continuity, Integration by Parts, Polar Coord Transforms, Partial Derivatives) with sync indicators, past paper tags, and "New Notebook (+)" button.
- View 3 (PDF Study & Highlight-to-Ask AI):
  * Split view (1.15fr : 1fr). Left: Multivariable calculus exam paper with Question 5 highlighted in warm amber (rgba(255,215,50,0.16)) and floating animated "Ask Kestrel AI to Solve & Prove (⌘K)" popover. Right: Step-by-step LaTeX continuity proof with conclusion callout (A = 0) and "Insert to Board" button.
- View 4 (Knowledge Graph Studio):
  * Split view (1fr : 280px). Top control bar with discipline filter chips and search. Center: Interactive SVG concept topology with Central Hub (Multivariable Calculus Hub, r=44px) connected via colored vector arrows to Pure Maths cluster (Limits, Polar, Partial Derivs), Physics cluster (Gravitation, Heat Flow, Kinematics), and Chemistry cluster (Reaction Kinetics). Right: 280px Node Inspector sidebar showing active concept details, connected exam questions (Q5, Q6), confidence (99.4%), and deep-link buttons.
- View 5 (Collaborative Git Control):
  * Split view (280px : 1fr). Left: Source control sidebar with branch badge "main", commit message box, modified files list. Right: Tabs for Incoming PRs (Hamiltonian Mechanics notes review), Visual Diff (green additions / red deletions with LaTeX math), and linear commit history tree.

Ensure all interactive hover states, active pill highlights, 3px top card hover indicator lines, and smooth elevation shadows are explicitly rendered.
```

---

## ✨ Master Interactive State & Hover Effect Matrix

This matrix provides the exact color hex codes, border transitions, elevation changes, and CSS/Figma transform states for every interactive UI element.

### 1. Global Navigation & Toolbar Elements

| Element | Default Rest State | Hover State (Mouse Over) | Active / Selected State | Interaction Feel / Transition |
| :--- | :--- | :--- | :--- | :--- |
| **Sidebar Icon Button** (`.sidebar-icon-btn`) | `bg: transparent`<br>`color: #8fa3b8`<br>`border: 1px solid transparent`<br>`border-radius: 6px`<br>`size: 34x34px` | `bg: rgba(255,255,255,0.07)`<br>`color: #d0e4f0`<br>`transform: scale(1.05)` | `bg: #1e6b6b`<br>`color: #ffffff`<br>`box-shadow: 0 2px 8px rgba(30,107,107,0.50)` | `all 0.14s ease`<br>Smooth glow effect on dark navy background |
| **Back Chevron** (`.back-chevron`) | `color: #887e70`<br>`padding: 4px`<br>`border-radius: 3px` | `bg: #ede9e1`<br>`color: #1a1612`<br>`transform: translateX(-2px)` | `bg: #e0dcd4`<br>`color: #1a1612` | `all 0.12s ease`<br>Subtle directional nudge |
| **Layout Selector Pill** (`.layout-pill`) | `bg: transparent`<br>`color: #4a453c`<br>`font-weight: 500`<br>`padding: 3px 9px`<br>`font-size: 11px` | `bg: rgba(255,255,255,0.65)`<br>`color: #1a1612` | `bg: #ffffff`<br>`color: #1a1612`<br>`font-weight: 700`<br>`box-shadow: 0 1px 2px rgba(26,22,18,0.05)` | `all 0.12s ease`<br>Segmented control switch |
| **Toolbar Action Button** (`.tool-text-action`) | `bg: transparent`<br>`color: #4a453c`<br>`font-size: 12px`<br>`border-radius: 6px`<br>`padding: 4px 8px` | `bg: #ede9e1`<br>`color: #1a1612` | `bg: #e8f4f4`<br>`color: #1e6b6b`<br>`font-weight: 600` | `all 0.12s ease` |
| **Save Button** (`.btn-kestrel-save`) | `bg: #1e6b6b`<br>`color: #ffffff`<br>`font-weight: 700`<br>`font-size: 12px`<br>`padding: 5px 13px`<br>`border-radius: 6px`<br>`shadow: 0 1px 2px rgba(26,22,18,0.05)` | `bg: #165858`<br>`box-shadow: 0 4px 8px rgba(30,107,107,0.25)`<br>`transform: translateY(-1px)` | `bg: #114242`<br>`transform: translateY(0px)` | `all 0.14s ease`<br>Satisfying physical button press |
| **Top Icon Button** (`.btn-top-icon`) | `bg: transparent`<br>`border: 1px solid rgba(60,50,30,0.16)`<br>`color: #887e70`<br>`size: 28x28px`<br>`border-radius: 6px` | `bg: #ede9e1`<br>`color: #1a1612`<br>`border-color: rgba(60,50,30,0.28)` | `bg: #e8f4f4`<br>`color: #1e6b6b`<br>`border-color: #1e6b6b` | `all 0.12s ease` |
| **Theme Toggle Button** (`#themeToggle`) | `bg: transparent`<br>`border: 1px solid rgba(60,50,30,0.16)`<br>`color: #887e70`<br>`font-size: 10px`<br>`padding: 3px 8px` | `bg: #ede9e1`<br>`color: #1a1612`<br>`border-color: #1e6b6b` | `bg: #1e6b6b`<br>`color: #ffffff` | `all 0.12s ease` |

---

### 2. Canvas & Showcase Cards

| Element | Default Rest State | Hover State (Mouse Over) | Active / Clicked State | Interaction Feel / Transition |
| :--- | :--- | :--- | :--- | :--- |
| **Welcome Launch Card** (`.welcome-card-btn`) | `bg: #faf8f4`<br>`border: 1.5px solid rgba(60,50,30,0.16)`<br>`border-radius: 16px`<br>`shadow: 0 1px 3px rgba(26,22,18,0.08)`<br>`top bar (3px): opacity 0` | `border-color: #1e6b6b`<br>`transform: translateY(-3px)`<br>`shadow: 0 12px 24px rgba(26,22,18,0.10)`<br>`top bar (3px): opacity 1 (#1e6b6b)` | `transform: scale(0.985)`<br>`border-color: #165858` | `0.18s cubic-bezier(0.16, 1, 0.3, 1)`<br>Card lift with top accent reveal |
| **Floating Toolbar Button** (`.kestrel-tool-btn`) | `bg: transparent`<br>`color: #4a453c`<br>`size: 34x34px`<br>`border-radius: 50%` | `bg: #ede9e1`<br>`color: #1a1612`<br>`transform: scale(1.08)` | `bg: #1e6b6b`<br>`color: #ffffff`<br>`box-shadow: 0 2px 8px rgba(30,107,107,0.35)` | `all 0.12s ease`<br>Circular tool activation |
| **AI Accept Button** (`.btn-review-accept`) | `bg: #1a6b3a` (Emerald)<br>`color: #ffffff`<br>`font-weight: 700`<br>`border-radius: 3px`<br>`padding: 7px 10px` | `bg: #14552e`<br>`box-shadow: 0 3px 8px rgba(26,107,58,0.30)`<br>`transform: translateY(-1px)` | `bg: #0f3e22`<br>`transform: translateY(0px)` | `all 0.12s ease`<br>Positive confirmation |
| **AI Dismiss Button** (`.btn-review-dismiss`) | `bg: #faf8f4`<br>`border: 1px solid rgba(60,50,30,0.28)`<br>`color: #4a453c`<br>`border-radius: 3px`<br>`padding: 7px 10px` | `bg: #ede9e1`<br>`color: #8a2a1e` (Dark Red)<br>`border-color: #8a2a1e` | `bg: #fdf0ee`<br>`color: #8a2a1e` | `all 0.12s ease`<br>Safe dismissal affordance |
| **Sticky Note** (`.canvas-sticky`) | `bg: #fef6d6`<br>`border: 1px solid #f5e08a`<br>`color: #4a3800`<br>`shadow: 0 4px 8px rgba(26,22,18,0.08)`<br>`transform: rotate(-1deg)` | `shadow: 0 10px 20px rgba(160,124,16,0.15)`<br>`transform: rotate(0deg) translateY(-2px)` | `transform: scale(0.99)` | `all 0.15s ease`<br>Realistic paper note lift |

---

### 3. Knowledge Graph & RAG Elements

| Element | Default Rest State | Hover State (Mouse Over) | Active / Clicked State | Interaction Feel / Transition |
| :--- | :--- | :--- | :--- | :--- |
| **Graph Filter Chip** (`.graph-chip`) | `bg: #ede9e1`<br>`border: 1px solid rgba(60,50,30,0.16)`<br>`color: #4a453c`<br>`border-radius: 9999px`<br>`padding: 3px 9px`<br>`font-size: 11px` | `border-color: rgba(60,50,30,0.28)`<br>`color: #1a1612`<br>`bg: #e5e0d6` | `bg: #e8f4f4`<br>`border-color: #1e6b6b`<br>`color: #1e6b6b`<br>`font-weight: 700` | `all 0.12s ease`<br>Pill filter toggle |
| **Graph Node Circle** (`<circle>`) | `fill: var(--color-*)`<br>`stroke: #faf8f4 (3px)`<br>`cursor: pointer` | `stroke: #1a1612 (4px)`<br>`filter: drop-shadow(0 6px 16px rgba(0,0,0,0.25))` | `stroke: #1e6b6b (5px)`<br>`filter: drop-shadow(0 8px 20px rgba(30,107,107,0.45))` | `all 0.16s ease`<br>Node focus expansion |
| **Contextual AI Popover** (`.contextual-ai-popover`) | `bg: #1e6b6b`<br>`color: #ffffff`<br>`border-radius: 9999px`<br>`padding: 5px 12px`<br>`shadow: 0 4px 8px rgba(26,22,18,0.08)`<br>`animation: floatUp 2.2s infinite` | `bg: #165858`<br>`transform: scale(1.04) translateY(-2px)`<br>`box-shadow: 0 8px 16px rgba(30,107,107,0.30)` | `bg: #114242`<br>`transform: scale(0.98)` | `floatUp 2.2s alternate`<br>Inviting interactive spark |
| **PDF Upload Affordance** (`.pdf-upload-affordance`) | `border: 2px dashed rgba(60,50,30,0.28)`<br>`bg: #f5f2ec`<br>`color: #887e70`<br>`border-radius: 10px`<br>`padding: 18px` | `border-color: #1e6b6b`<br>`color: #1e6b6b`<br>`bg: #e8f4f4`<br>`transform: translateY(-1px)` | `border-color: #165858`<br>`bg: #d8ecec` | `all 0.15s ease`<br>Drag & drop highlight |

---

### 4. Collaborative Git & Starred Elements

| Element | Default Rest State | Hover State (Mouse Over) | Active / Selected State | Interaction Feel / Transition |
| :--- | :--- | :--- | :--- | :--- |
| **Git Tab Button** (`.git-tab-btn`) | `bg: transparent`<br>`color: #887e70`<br>`border-bottom: 2px solid transparent`<br>`font-size: 12px`<br>`height: 40px` | `color: #1a1612` | `color: #1e6b6b`<br>`border-bottom-color: #1e6b6b`<br>`font-weight: 700` | `color 0.12s ease`<br>Underline tab transition |
| **Git PR Card** (`.pr-card`) | `bg: #faf8f4`<br>`border: 1px solid rgba(60,50,30,0.16)`<br>`border-radius: 10px`<br>`padding: 14px 16px`<br>`shadow: 0 1px 2px rgba(26,22,18,0.05)` | `border-color: #1e6b6b`<br>`box-shadow: 0 4px 8px rgba(26,22,18,0.08)`<br>`transform: translateY(-1px)` | `border-color: #1e6b6b`<br>`bg: #e8f4f4` | `all 0.14s ease`<br>Collaborator item select |
| **Git File Item** (`.git-file-item`) | `bg: transparent`<br>`color: #4a453c`<br>`padding: 6px 8px`<br>`border-radius: 3px`<br>`font-size: 12px` | `bg: #ede9e1`<br>`color: #1a1612` | `bg: #e8f4f4`<br>`color: #1e6b6b`<br>`font-weight: 600` | `background 0.10s ease` |
| **Git Merge Button** (`.git-merge-btn`) | `bg: #1e6b6b`<br>`color: #ffffff`<br>`font-weight: 700`<br>`padding: 8px 18px`<br>`border-radius: 6px` | `bg: #165858`<br>`box-shadow: 0 4px 10px rgba(30,107,107,0.30)`<br>`transform: translateY(-1px)` | `bg: #114242`<br>`transform: translateY(0px)` | `all 0.13s ease` |
| **Starred Board Card** (`.fav-card`) | `bg: #faf8f4`<br>`border: 1px solid rgba(60,50,30,0.16)`<br>`border-radius: 10px`<br>`padding: 18px`<br>`shadow: 0 1px 3px rgba(26,22,18,0.08)` | `border-color: #1e6b6b`<br>`box-shadow: 0 8px 16px rgba(26,22,18,0.08)`<br>`transform: translateY(-2px)` | `bg: #e8f4f4`<br>`border-color: #1e6b6b` | `all 0.15s ease`<br>Bookmark card elevation |

---

## 📂 Feature 2: Subject-to-Notebook Folder Drill-Down System

When a user clicks on any Subject Course Card from the curriculum overview screen, Kestrel smoothly transitions into a nested **Folder & Notebook Drill-Down Workspace**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  BREADCRUMB:  Subjects  >  📐 Combined Mathematics  >  📁 Unit 04: Calculus & Limits   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  [+ New Notebook]   [↑ Import PDF Past Paper]   [🔍 Filter Notebooks...]  [● Synced]   │
├───────────────────────────────────────────────────────┬────────────────────────────────┤
│  CURRICULUM UNITS (FOLDERS)                           │  NOTEBOOKS IN UNIT 04 (BOARDS) │
│                                                       │                                │
│  📁 Unit 01: Pure Algebra & Polynomials   (4 boards)  │  📓 Board 1 (Active):          │
│  📁 Unit 02: Trigonometry & Complex Num   (6 boards)  │     "Limits & Multivariable    │
│  📁 Unit 03: Vectors & 3D Geometry        (3 boards)  │      Continuity (Exam Q5)"     │
│  📂 Unit 04: Calculus & Limits [OPEN]     (8 boards)──┼──►  Tags: #pure-maths #q5      │
│  📁 Unit 05: Applied Mechanics & Kinematics (5 boards)│     Last edit: 2h ago · Synced │
│                                                       │                                │
│                                                       │  📓 Board 2:                   │
│                                                       │     "Integration by Parts &    │
│                                                       │      Reduction Formulas"       │
│                                                       │     Tags: #calculus #unit4     │
│                                                       │                                │
│                                                       │  📓 Board 3:                   │
│                                                       │     "Polar Transforms &        │
│                                                       │      Jacobian Determinants"    │
└───────────────────────────────────────────────────────┴────────────────────────────────┘
```

### Drill-Down UI Component Specifications for Figma

#### 1. Breadcrumb Header Frame
- **Frame Height**: `38px`, Auto-layout horizontal, align center, gap `8px`.
- **Items**:
  - `Subjects` (Clickable text, `color: #887e70`, hover `color: #1e6b6b`).
  - Chevron `/` separator (`color: #b5ae9f`).
  - `Combined Mathematics` (Clickable text, `color: #4a453c`, `font-weight: 600`).
  - Chevron `/` separator (`color: #b5ae9f`).
  - `Unit 04: Calculus & Limits` (Active path, `color: #1a1612`, `font-weight: 700`, with folder icon `folder-open`).

#### 2. Folder List Pane (Left Column: `300px` width)
- **Folder Item Card (`.subject-folder-item`)**:
  - Dimensions: `width: 100%`, `padding: 10px 14px`, `border-radius: 6px`, `margin-bottom: 6px`.
  - Default: `bg: #faf8f4`, `border: 1px solid rgba(60,50,30,0.16)`, `color: #4a453c`.
  - Hover: `bg: #ede9e1`, `border-color: rgba(60,50,30,0.28)`, `color: #1a1612`.
  - Active/Open State: `bg: #e8f4f4`, `border: 1.5px solid #1e6b6b`, `color: #1e6b6b`, `font-weight: 700`.
  - Left Icon: Folder emoji/icon (`folder` or `folder-open` when active).
  - Right Badge: Board count (e.g. `8 boards`, `bg: rgba(30,107,107,0.12)`, `color: #1e6b6b`, `10px`, `border-radius: 9999px`).

#### 3. Notebook Cards Grid (Right Pane: `flex: 1`)
- **Grid Layout**: Auto-fill minmax `260px`, gap `16px`.
- **Notebook Board Card (`.notebook-entry-card`)**:
  - Dimensions: `min-height: 140px`, `padding: 16px`, `bg: #faf8f4`, `border: 1px solid rgba(60,50,30,0.16)`, `border-radius: 10px`.
  - Hover: `border-color: #1e6b6b`, `transform: translateY(-2px)`, `box-shadow: 0 8px 16px rgba(26,22,18,0.08)`.
  - Top Row: Subject Tag (`Maths · Calculus`, `#2c5f8a` on `#eaf2f9`) + Sync Dot (`● Synced`, `#1a6b3a`).
  - Title: Notebook title (e.g. *"Limits & Multivariable Continuity"*), `14px`, `font-weight: 700`.
  - Formula Snippet Preview Strip: `bg: #ede9e1`, `height: 32px`, `padding: 0 8px`, `font-family: JetBrains Mono`, `font-size: 11px`, `color: #4a453c`.
  - Bottom Meta: `Last edited 2h ago · 3 pages · 4 AI proofs`.

---

## 📐 Feature 3: Pixel-Perfect Canvas Board & Floating Toolbar Spec

*(Directly incorporating the user's reference image for the docked floating pill toolbar)*

```
  ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
  │  (↺)  (↻)  │  ( ↖ )  (✋)  (✏️)  (🖍️)  (🧽)  │  (📄)  (△□○)  ( ∑ )  ( ✨ )                        │
  └──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1. Floating Toolbar Exact Specifications (Matching User Image)

- **Container Dimensions**:
  - `height: 48px`, `min-width: 460px`, `border-radius: 9999px` (Full Pill).
  - `padding: 4px 14px`.
  - `background: #ffffff` (`var(--bg-elevated)`).
  - `border: 1px solid rgba(60, 50, 30, 0.18)`.
  - `box-shadow: 0 20px 32px rgba(26,22,18,0.16), 0 6px 12px rgba(26,22,18,0.10)` (`var(--shadow-floating)`).
  - Positioning: `position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); z-index: 200;`.
- **Inner Tool Organization**:
  1. **History Group**:
     - `Undo` icon button (`undo-2`, `14x14px`, color `#4a453c`).
     - `Redo` icon button (`redo-2`, `14x14px`, color `#4a453c`).
  2. **Separator 1**: Vertical line `1px width`, `20px height`, background `rgba(60,50,30,0.16)`.
  3. **Main Stylus & Interaction Group**:
     - **Pointer / Select Tool (Active in Image)**:
       - Circle container: `36x36px`, `border-radius: 50%`.
       - Background: `#1e6b6b` (Deep Academic Teal).
       - Icon: Arrow cursor (`mouse-pointer-2`, `15x15px`, color `#ffffff`).
       - Box Shadow: `0 3px 10px rgba(30,107,107,0.40)`.
     - `Hand / Pan` tool button (`hand`, `15x15px`, color `#4a453c`, hover bg `#ede9e1`).
     - `Smart Pen` tool button (`pen`, `15x15px`, color `#4a453c`).
     - `Highlighter` tool button (`highlighter`, `15x15px`, color `#4a453c`).
     - `Eraser` tool button (`eraser`, `15x15px`, color `#4a453c`).
  4. **Separator 2**: Vertical line `1px width`, `20px height`, background `rgba(60,50,30,0.16)`.
  5. **Insert & STEM Intelligence Group**:
     - `Sticky Note` tool button (`sticky-note` / `file-text`, `15x15px`, color `#4a453c`).
     - `Parametric Shapes` tool button (`shapes` / `triangle-square-circle`, `15x15px`, color `#4a453c`).
     - `LaTeX Formula Block` tool button (`sigma` $\Sigma$, `15x15px`, color `#4a453c`).
     - `AI Structural Generator` tool button (`sparkles` ✨, `15x15px`, color `#1e6b6b` Teal with subtle glow).

---

### 2. Canvas Background Pattern Matrix

Kestrel supports 4 real-time switchable background canvas grids:

1. **Blank Canvas (`.bg-pattern-blank`)**: Solid warm parchment `#f5f2ec`.
2. **Dotted Matrix Grid (`.bg-pattern-dots`)**:
   - Background color: `#f5f2ec`.
   - Pattern: Radial dots `circle, rgba(60,50,30,0.16) 1.2px, transparent 1.2px`.
   - Grid Pitch: `24px x 24px`.
3. **Ruled Notebook Paper (`.bg-pattern-ruled`)**:
   - Line separation: `28px height`.
   - Line styling: `1px solid rgba(60,50,30,0.10)`.
4. **Cartesian Math Grid (`.bg-pattern-grid`)**:
   - Grid pitch: `24px x 24px`.
   - Orthogonal lines: `1px solid rgba(60,50,30,0.10)`.

---

## 🕸 Feature 4: Interactive Knowledge Graph Studio & Node Inspector

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  FILTER: [All (18)]  [📐 Pure Calculus]  [⚡ Mechanics]  [🔥 Heat Flow]  [🧪 Kinetics]  │
├──────────────────────────────────────────────────────────────────┬─────────────────────┤
│  INTERACTIVE TOPOLOGY CANVAS (SVG 940x520)                       │  NODE INSPECTOR     │
│                                                                  │  (280px Width)      │
│          [Limits & Continuity (Q5)]                              │                     │
│                (r=32, Cobalt)                                    │  ACTIVE SELECTION:  │
│                       ▲                                          │  Limits & Multi-    │
│                       │ (path limits)                            │  variable Continuity│
│                       │                                          │  Unit 04 · Pure AL  │
│            ┌──────────┴──────────┐                               │                     │
│            │ MULTIVARIABLE       │───(potential field)──► [Grav] │  Core Concept:      │
│            │ CALCULUS HUB (∇)    │                        (r=32) │  Cancellation of    │
│            │ (r=44, Deep Teal)   │───(heat gradient)────► [Heat] │  factor (x-y) shows │
│            └──────────┬──────────┘                        (r=30) │  limit A = 0.       │
│                       │                                          │                     │
│                       ▼ (rate laws)                              │  Linked Questions:  │
│              [Reaction Kinetics]                                 │  Exam Q5, Exam Q6   │
│                 (r=32, Violet)                                   │                     │
│                                                                  │  Confidence: 99.4%  │
│                                                                  │  [Open Linked Board]│
└──────────────────────────────────────────────────────────────────┴─────────────────────┘
```

### Knowledge Graph Node & Vector Architecture

1. **Center Hub Node (Multivariable Calculus Hub)**:
   - Coordinates: `cx="470" cy="250"`.
   - Radius: `r="44px"`, Fill: `#1e6b6b` (Teal), Stroke: `#faf8f4` (`4px`), Outer dashed ring: `r="49px"` (`1.5px dashed #1e6b6b`).
   - Text: `Multivariable Calculus Hub` (`11px`, bold, white) + `f(x,y) · ∇` (`9px`, Mono).
2. **Pure Mathematics Cluster (Left)**:
   - **Limits & Continuity (Exam Q5)**: `cx="190" cy="130"`, `r="32px"`, Fill `#2c5f8a` (Cobalt), Text: `Limits & Continuity` / `Exam Q5 · A=0`.
   - **Polar Coordinate Transforms (Exam Q6)**: `cx="140" cy="250"`, `r="28px"`, Fill `#2c5f8a`, Text: `Polar Coord` / `(r, θ) · Q6`.
   - **Partial Derivatives & Gradient**: `cx="180" cy="390"`, `r="30px"`, Fill `#2c5f8a`, Text: `Partial Derivs` / `∂/∂x, ∂/∂y`.
   - **Single Variable (L'Hôpital)**: `cx="70" cy="120"`, `r="20px"`, Fill `#ede9e1`, Stroke `#887e70`.
3. **Physics & Field Cluster (Right)**:
   - **Gravitational Potential ($F = -\nabla V$)**: `cx="730" cy="110"`, `r="32px"`, Fill `#1e6b6b` (Teal), Text: `Gravitation` / `F = -∇V · Q7`.
   - **Fourier Heat Conduction ($H = -k\nabla T$)**: `cx="790" cy="230"`, `r="30px"`, Fill `#1e6b6b`, Text: `Heat Conduction` / `H = -k∇T · Q8`.
   - **Kinematics & Projectile Drag**: `cx="760" cy="380"`, `r="32px"`, Fill `#1e6b6b`, Text: `Kinematics` / `Trajectory & Drag`.
4. **Chemistry Kinetics Cluster (Bottom)**:
   - **Reaction Kinetics & Arrhenius $E_a$**: `cx="470" cy="440"`, `r="32px"`, Fill `#5a3e8a` (Violet), Text: `Reaction Kinetics` / `Arrhenius Ea`.

---

## 🎨 Figma Global Design Tokens

### Color Styles Table

| Style Name in Figma | Light Hex | Dark Hex | Role & Application |
| :--- | :--- | :--- | :--- |
| `Color/Base/Canvas` | `#f5f2ec` | `#181512` | Viewport and paper background |
| `Color/Base/Surface` | `#faf8f4` | `#1e1a16` | Card container background, toolbar fill |
| `Color/Base/Elevated`| `#ffffff` | `#261f19` | Floating toolbar pill, active segmented pill |
| `Color/Base/Sunken` | `#ede9e1` | `#13100d` | Inset formula boxes, code backgrounds |
| `Color/Base/Sidebar` | `#0f1623` | `#0f1623` | Left navigation bar |
| `Color/Accent/Teal` | `#1e6b6b` | `#2f9090` | Primary interactive elements, active tools |
| `Color/Accent/TealHover`| `#165858` | `#3aa8a8` | Button hover state |
| `Color/Accent/TealLight`| `#e8f4f4` | `rgba(47,144,144,0.14)`| Active list item background |
| `Color/Discipline/Maths`| `#2c5f8a` | `#5a9ec4` | Mathematics cards, equations, graph nodes |
| `Color/Discipline/Chem` | `#5a3e8a` | `#a07cd4` | Chemistry cards, molecular preview |
| `Color/Discipline/Exam` | `#8a5a1e` | `#c8903a` | Sticky notes, AI pending review, alerts |
| `Color/Discipline/Success`| `#1a6b3a`| `#3ab87a` | Auto-Saved, RAG Grounded, Accept button |

---

## 🎬 Competition Demo Flow & Interactive Prototyping Wiring

When setting up interactions in Figma prototype mode:

1. **Slide 1 (Welcome & Curriculum Launch)**:
   - Hover on `Freeform Scratchpad` $\to$ Top 3px teal line reveals, card lifts `-3px`.
   - Click `Freeform Scratchpad` $\to$ Navigate to **Canvas Studio**.
   - Click `My Subjects & Syllabus` $\to$ Navigate to **Subjects Folder Drill-Down**.
2. **Slide 2 (Canvas Studio & Intelligent Tools)**:
   - Click floating toolbar icons $\to$ Toggle active teal circle state.
   - Click layout picker pills (`Blank` / `Dotted` / `Ruled` / `Math Grid`) $\to$ Swap canvas background component variant.
   - Hover on AI Benzene Card $\to$ Reveal glowing confidence badge and green `[Accept]` / gray `[Dismiss]` hover colors.
3. **Slide 3 (Subject Drill-Down to Notebooks)**:
   - Click `Combined Mathematics` $\to$ Open `Unit 04: Calculus & Limits` folder.
   - Click `Limits & Continuity (Board 1)` $\to$ Navigate to **PDF Study & RAG Solver**.
4. **Slide 4 (PDF Study & Step-by-Step Proof)**:
   - Hover on Question 5 on the exam paper $\to$ Reveal yellow bounding box and floating `floatUp` popover pill.
   - Click `Ask Kestrel AI (⌘K)` $\to$ Animate in the step-by-step KaTeX LaTeX derivation cards and emerald `A = 0` conclusion callout.
5. **Slide 5 (Knowledge Graph Studio)**:
   - Click `Pure Calculus` chip $\to$ Filter and highlight mathematics nodes in cobalt.
   - Click `Limits & Continuity` node $\to$ Dynamically update the right-hand **Node Inspector Panel** with grounded theorem stats and confidence score ($99.4\%$).
6. **Slide 6 (Collaborative Git Version Control)**:
   - Click `Visual Diff` tab $\to$ Switch view to line-by-line diff showing green additions and red deletions.
   - Click `[Merge into main]` $\to$ Trigger emerald merge confirmation badge and update commit history tree.
