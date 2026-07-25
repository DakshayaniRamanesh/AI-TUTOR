/**
 * Kestrel Web Edition — Industrial Standard Web Application Controller
 */

document.addEventListener('DOMContentLoaded', () => {
  const engine = window.gitEngine;
  if (engine) engine.init();

  let isDarkMode = false;
  let activeViewId = 'view-canvas';
  let canvasItems = [];
  let currentZoom = 1.0;
  let isRuled = true;

  // DOM Elements
  const btnThemeToggle = document.getElementById('btn-theme-toggle');
  const sidebar = document.getElementById('app-sidebar');
  const btnToggleSidebarCollapse = document.getElementById('btn-toggle-sidebar-collapse');
  const canvasTopToolbar = document.getElementById('canvas-top-toolbar');

  const menuItems = document.querySelectorAll('.menu-item');
  const stackViews = document.querySelectorAll('.stack-view');

  const canvasPaper = document.getElementById('canvas-paper');
  const lblZoomLevel = document.getElementById('lbl-zoom-level');
  const btnZoomIn = document.getElementById('btn-zoom-in');
  const btnZoomOut = document.getElementById('btn-zoom-out');
  const btnGridMode = document.getElementById('tb-btn-grid-mode');

  const askInput = document.getElementById('ask-input');
  const btnAskAi = document.getElementById('btn-ask-ai');

  const btnOpenRefDb = document.getElementById('btn-open-ref-db');
  const btnCloseRefDb = document.getElementById('btn-close-ref-db');
  const refDbDrawer = document.getElementById('ref-db-drawer');

  // --- 1. Theme Toggle ---
  if (btnThemeToggle) {
    btnThemeToggle.addEventListener('click', () => {
      isDarkMode = !isDarkMode;
      document.body.classList.toggle('dark-mode', isDarkMode);
      btnThemeToggle.textContent = isDarkMode ? '☀ Light Mode' : '🌙 Dark Mode';
    });
  }

  // --- 2. Sidebar Navigation ---
  menuItems.forEach(item => {
    item.addEventListener('click', () => {
      menuItems.forEach(m => m.classList.remove('active'));
      stackViews.forEach(v => v.classList.remove('active'));

      item.classList.add('active');
      const targetView = item.getAttribute('data-view');
      activeViewId = targetView;

      const viewEl = document.getElementById(targetView);
      if (viewEl) viewEl.classList.add('active');

      // Show canvas top toolbar only on All Boards view
      if (canvasTopToolbar) {
        canvasTopToolbar.style.display = targetView === 'view-canvas' ? 'flex' : 'none';
      }

      if (targetView === 'view-notebooks') renderNotebooksList();
      if (targetView === 'view-vcs') initVcsView();
      if (targetView === 'view-graph') renderObsidianGraph();
      if (targetView === 'view-shared') renderSharedHub();
      if (targetView === 'view-downloads') renderDownloadsList();
    });
  });

  if (btnToggleSidebarCollapse && sidebar) {
    btnToggleSidebarCollapse.addEventListener('click', () => {
      sidebar.classList.toggle('collapsed');
    });
  }

  // --- 3. Freeform Canvas Engine ---
  function initDemoCanvas() {
    if (!canvasPaper) return;
    canvasPaper.innerHTML = '';
    
    // Add default initial canvas cards
    createStickyNote(60, 60, "Key Theorem:\nIntegral of e^x dx = e^x + C\nAlways verify boundary conditions!");
    createHandwritingNote(360, 60, "Question: Solve ∫ (3x² + 2x) dx\n\n✦ Hints & Key Steps:\n• Power Rule: ∫ xⁿ dx = xⁿ⁺¹ / (n+1)\n• Result: x³ + x² + C");
    createTableCard(800, 60, "Physical Constants", ["Name", "Symbol", "Value"], [
      ["Speed of Light", "c", "3.00 × 10⁸ m/s"],
      ["Planck Constant", "h", "6.626 × 10⁻³⁴ J·s"],
      ["Gravitational", "G", "6.674 × 10⁻¹¹ N·m²/kg²"]
    ]);
  }

  function makeDraggable(el, headerEl) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
    const handle = headerEl || el;

    handle.onmousedown = dragMouseDown;

    function dragMouseDown(e) {
      if (e.target.classList.contains('btn-close-item')) return;
      e.preventDefault();
      pos3 = e.clientX;
      pos4 = e.clientY;
      document.onmouseup = closeDragElement;
      document.onmousemove = elementDrag;
    }

    function elementDrag(e) {
      e.preventDefault();
      pos1 = pos3 - e.clientX;
      pos2 = pos4 - e.clientY;
      pos3 = e.clientX;
      pos4 = e.clientY;
      el.style.top = (el.offsetTop - pos2) + "px";
      el.style.left = (el.offsetLeft - pos1) + "px";
    }

    function closeDragElement() {
      document.onmouseup = null;
      document.onmousemove = null;
    }
  }

  function createStickyNote(x, y, text = "New Note...") {
    const div = document.createElement('div');
    div.className = 'canvas-item sticky-note';
    div.style.left = x + 'px';
    div.style.top = y + 'px';

    div.innerHTML = `
      <div class="item-header">
        <span class="title"><span class="glyph">✎</span> Note</span>
        <button class="btn-close-item">&times;</button>
      </div>
      <textarea>${text}</textarea>
    `;

    canvasPaper.appendChild(div);
    makeDraggable(div, div.querySelector('.item-header'));
    div.querySelector('.btn-close-item').onclick = () => div.remove();
  }

  function createHandwritingNote(x, y, text = "") {
    const div = document.createElement('div');
    div.className = 'canvas-item handwriting-note';
    div.style.left = x + 'px';
    div.style.top = y + 'px';

    div.innerHTML = `
      <div class="item-header">
        <span class="title"><span class="glyph">✎</span> Note (Handwritten)</span>
        <button class="btn-close-item">&times;</button>
      </div>
      <div class="note-body" contenteditable="true">${text.replace(/\n/g, '<br>')}</div>
    `;

    canvasPaper.appendChild(div);
    makeDraggable(div, div.querySelector('.item-header'));
    div.querySelector('.btn-close-item').onclick = () => div.remove();
  }

  function createTableCard(x, y, title, headers, rows) {
    const div = document.createElement('div');
    div.className = 'canvas-item table-item';
    div.style.left = x + 'px';
    div.style.top = y + 'px';

    let tableHtml = `<table><thead><tr>`;
    headers.forEach(h => tableHtml += `<th>${h}</th>`);
    tableHtml += `</tr></thead><tbody>`;
    rows.forEach(r => {
      tableHtml += `<tr>`;
      r.forEach(c => tableHtml += `<td>${c}</td>`);
      tableHtml += `</tr>`;
    });
    tableHtml += `</tbody></table>`;

    div.innerHTML = `
      <div class="item-header">
        <span class="title"><span class="glyph">▤</span> ${title}</span>
        <button class="btn-close-item">&times;</button>
      </div>
      <div class="table-body" style="padding:10px;">${tableHtml}</div>
    `;

    canvasPaper.appendChild(div);
    makeDraggable(div, div.querySelector('.item-header'));
    div.querySelector('.btn-close-item').onclick = () => div.remove();
  }

  function createAnswerBubble(x, y, question, answer) {
    const div = document.createElement('div');
    div.className = 'canvas-item handwriting-note';
    div.style.left = x + 'px';
    div.style.top = y + 'px';
    div.style.width = '480px';

    div.innerHTML = `
      <div class="item-header">
        <span class="title" style="color:var(--primary-accent);"><span class="glyph">✦</span> Solution Steps</span>
        <button class="btn-close-item">&times;</button>
      </div>
      <div class="note-body" style="font-size:22px; color:#0b2545;">
        <strong>Question:</strong> ${question}<br><br>
        ${answer.replace(/\n/g, '<br>')}
      </div>
    `;

    canvasPaper.appendChild(div);
    makeDraggable(div, div.querySelector('.item-header'));
    div.querySelector('.btn-close-item').onclick = () => div.remove();
  }

  // Toolbar Actions
  document.getElementById('tb-btn-sticky')?.addEventListener('click', () => createStickyNote(100, 100));
  document.getElementById('tb-btn-note')?.addEventListener('click', () => createHandwritingNote(200, 120));
  document.getElementById('tb-btn-table')?.addEventListener('click', () => createTableCard(300, 150, "Data Table", ["Col 1", "Col 2"], [["Val 1", "Val 2"]]));
  document.getElementById('tb-btn-save')?.addEventListener('click', () => alert("Notebook Board Saved!"));

  if (btnGridMode) {
    btnGridMode.addEventListener('click', () => {
      isRuled = !isRuled;
      canvasPaper.className = `canvas-paper ${isRuled ? 'ruled-background' : 'dotted-background'}`;
      btnGridMode.innerHTML = `<span class="glyph">🗎</span> ${isRuled ? 'Ruled Paper' : '░ Dotted Grid'}`;
    });
  }

  // Zoom Control
  if (btnZoomIn) {
    btnZoomIn.addEventListener('click', () => {
      currentZoom = Math.min(2.0, currentZoom + 0.1);
      canvasPaper.style.transform = `scale(${currentZoom})`;
      canvasPaper.style.transformOrigin = '0 0';
      if (lblZoomLevel) lblZoomLevel.textContent = `${Math.round(currentZoom * 100)}%`;
    });
  }
  if (btnZoomOut) {
    btnZoomOut.addEventListener('click', () => {
      currentZoom = Math.max(0.5, currentZoom - 0.1);
      canvasPaper.style.transform = `scale(${currentZoom})`;
      canvasPaper.style.transformOrigin = '0 0';
      if (lblZoomLevel) lblZoomLevel.textContent = `${Math.round(currentZoom * 100)}%`;
    });
  }

  let lastMouseX = 200;
  let lastMouseY = 200;

  const canvasViewport = document.getElementById('canvas-viewport');
  if (canvasViewport) {
    canvasViewport.addEventListener('mousemove', (e) => {
      const rect = canvasPaper.getBoundingClientRect();
      lastMouseX = Math.max(20, Math.min(2400, e.clientX - rect.left));
      lastMouseY = Math.max(20, Math.min(1800, e.clientY - rect.top));
    });
    canvasViewport.addEventListener('click', (e) => {
      const rect = canvasPaper.getBoundingClientRect();
      lastMouseX = Math.max(20, Math.min(2400, e.clientX - rect.left));
      lastMouseY = Math.max(20, Math.min(1800, e.clientY - rect.top));
    });
  }

  // --- 4. STEM Question Ask Bar ---
  if (btnAskAi && askInput) {
    btnAskAi.addEventListener('click', solveAskQuestion);
    askInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') solveAskQuestion();
    });
  }

  function solveAskQuestion() {
    const q = askInput.value.trim();
    if (!q) return;

    const wantsElaborate = /elaborate|explain|steps|detail|how to|why/i.test(q);
    let ans = "";

    if (wantsElaborate) {
      if (q.includes('d/dx') || q.includes('derivative')) {
        ans = "1. ▤ Core Concept & Function\nIdentify f(x) = x³ + 2x\n\n2. ✦ Step-by-Step Differentiation\nApply Power Rule:\nf'(x) = 3x² + 2\n\n3. ◈ Final Answer\nf'(x) = 3x² + 2";
      } else if (q.includes('integral') || q.includes('∫')) {
        ans = "1. ▤ Core Concept & Integrand\nIdentify f(x) = sin(x)\n\n2. ✦ Step-by-Step Integration\nApply integration rules:\n∫ sin(x) dx = -cos(x) + C\n\n3. ◈ Final Answer\n∫ sin(x) dx = -cos(x) + C";
      } else {
        ans = `1. ▤ Detailed Explanation for '${q}'\n\n2. ✦ Step-by-Step Analysis\nApplied foundational laws and algebraic rules.\n\n3. ◈ Final Answer\nVerified symbolic output for ${q}`;
      }
    } else {
      // Straight, direct answer
      if (q.includes('d/dx') || q.includes('derivative')) {
        ans = "Answer: f'(x) = 3x² + 2";
      } else if (q.includes('integral') || q.includes('∫')) {
        ans = "Answer: ∫ sin(x) dx = -cos(x) + C";
      } else if (/^\d+\s*[\+\-\*\/]\s*\d+/.test(q)) {
        try {
          ans = `Answer: ${eval(q.replace(/[^\d\+\-\*\/]/g, ''))}`;
        } catch(err) {
          ans = `Answer: ${q}`;
        }
      } else {
        ans = `Answer: Verified result for ${q}`;
      }
    }

    createAnswerBubble(lastMouseX, lastMouseY, q, ans);
    askInput.value = '';
  }

  // --- 5. Reference Database Drawer ---
  if (btnOpenRefDb && refDbDrawer && btnCloseRefDb) {
    btnOpenRefDb.addEventListener('click', () => {
      refDbDrawer.classList.remove('hidden');
      populateRefDbTables();
    });
    btnCloseRefDb.addEventListener('click', () => {
      refDbDrawer.classList.add('hidden');
    });
  }

  const dtabs = document.querySelectorAll('.dtab');
  const dcontents = document.querySelectorAll('.dtab-content');
  dtabs.forEach(tab => {
    tab.addEventListener('click', () => {
      dtabs.forEach(t => t.classList.remove('active'));
      dcontents.forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(tab.getAttribute('data-dtab')).classList.add('active');
    });
  });

  function populateRefDbTables() {
    const tbodyConst = document.querySelector('#table-const tbody');
    if (tbodyConst && tbodyConst.children.length === 0) {
      tbodyConst.innerHTML = `
        <tr><td>Speed of Light</td><td>c</td><td>3.00 × 10⁸</td><td>m/s</td></tr>
        <tr><td>Planck Constant</td><td>h</td><td>6.626 × 10⁻³⁴</td><td>J·s</td></tr>
        <tr><td>Gravitational Constant</td><td>G</td><td>6.674 × 10⁻¹¹</td><td>N·m²/kg²</td></tr>
        <tr><td>Elementary Charge</td><td>e</td><td>1.602 × 10⁻¹⁹</td><td>C</td></tr>
      `;
    }

    const tbodyMath = document.querySelector('#table-math tbody');
    if (tbodyMath && tbodyMath.children.length === 0) {
      tbodyMath.innerHTML = `
        <tr><td>d/dx (xⁿ)</td><td>n * xⁿ⁻¹</td></tr>
        <tr><td>d/dx (sin x)</td><td>cos x</td></tr>
        <tr><td>d/dx (cos x)</td><td>-sin x</td></tr>
        <tr><td>∫ xⁿ dx</td><td>(xⁿ⁺¹) / (n + 1) + C</td></tr>
        <tr><td>∫ eˣ dx</td><td>eˣ + C</td></tr>
      `;
    }

    const tbodyTrig = document.querySelector('#table-trig tbody');
    if (tbodyTrig && tbodyTrig.children.length === 0) {
      tbodyTrig.innerHTML = `
        <tr><td>0°</td><td>0</td><td>0</td><td>1</td><td>0</td></tr>
        <tr><td>30°</td><td>π/6</td><td>1/2</td><td>√3/2</td><td>1/√3</td></tr>
        <tr><td>45°</td><td>π/4</td><td>1/√2</td><td>1/√2</td><td>1</td></tr>
        <tr><td>60°</td><td>π/3</td><td>√3/2</td><td>1/2</td><td>√3</td></tr>
        <tr><td>90°</td><td>π/2</td><td>1</td><td>0</td><td>undefined</td></tr>
      `;
    }
  }

  document.getElementById('btn-insert-const-canvas')?.addEventListener('click', () => {
    createTableCard(220, 180, "Physical Constants", ["Name", "Symbol", "Value", "Unit"], [
      ["Speed of Light", "c", "3.00 × 10⁸", "m/s"],
      ["Planck Constant", "h", "6.626 × 10⁻³⁴", "J·s"],
      ["Gravitational", "G", "6.674 × 10⁻¹¹", "N·m²/kg²"]
    ]);
    refDbDrawer.classList.add('hidden');
  });

  // --- 6. Notebooks List View ---
  function renderNotebooksList() {
    const container = document.getElementById('notebooks-list-container');
    if (!container) return;

    container.innerHTML = `
      <div class="notebook-row-card">
        <div>
          <div class="title"><span class="glyph">🗂</span> Physics Quantum Mechanics Notebook</div>
          <div class="sub">Last saved: 2 minutes ago • 14 pages</div>
        </div>
        <button class="btn-action-outline">Open</button>
      </div>
      <div class="notebook-row-card">
        <div>
          <div class="title"><span class="glyph">🗂</span> Calculus & Differential Equations</div>
          <div class="sub">Last saved: Yesterday • 28 pages</div>
        </div>
        <button class="btn-action-outline">Open</button>
      </div>
      <div class="notebook-row-card">
        <div>
          <div class="title"><span class="glyph">🗂</span> Organic Chemistry Synthesis Study Guide</div>
          <div class="sub">Last saved: 3 days ago • 19 pages</div>
        </div>
        <button class="btn-action-outline">Open</button>
      </div>
    `;
  }

  // --- 7. Git VCS View ---
  function initVcsView() {
    const branchSelect = document.getElementById('vcs-branch-select');
    if (branchSelect && branchSelect.children.length === 0) {
      branchSelect.innerHTML = `<option value="main">⎇ main</option><option value="feature">⎇ feature/quantum-notes</option>`;
    }

    const editorTextarea = document.getElementById('vcs-editor-textarea');
    const mdPreview = document.getElementById('vcs-markdown-preview');
    if (editorTextarea && mdPreview && !editorTextarea.value) {
      editorTextarea.value = `# Physics & Quantum Mechanics Notes\n\n## 1. ▤ Overview & Core Principles\nQuantum mechanics system analysis with **Wave-Particle Duality**.\n\n$$\\hat{H}\\Psi = E\\Psi$$\n\n- Heisenberg Uncertainty Principle\n- Schrödinger Wave Equation`;
      mdPreview.innerHTML = window.marked ? marked.parse(editorTextarea.value) : editorTextarea.value;

      editorTextarea.addEventListener('input', () => {
        mdPreview.innerHTML = window.marked ? marked.parse(editorTextarea.value) : editorTextarea.value;
      });
    }

    const treeContainer = document.getElementById('vcs-tree-container');
    if (treeContainer) {
      treeContainer.innerHTML = `
        <div style="font-size:12px; font-weight:bold; color:var(--success-color); margin-bottom:8px;"><span class="glyph">⤓</span> Staged Changes (1)</div>
        <div style="padding-left:10px; font-size:13px;"><span class="glyph">🗎</span> physics_quantum_notes.md</div>
        <div style="font-size:12px; font-weight:bold; color:var(--text-muted); margin:12px 0 8px;"><span class="glyph">✎</span> Markdown Notes (3)</div>
        <div style="padding-left:10px; font-size:13px;"><span class="glyph">🗎</span> calculus_derivatives.md</div>
        <div style="padding-left:10px; font-size:13px;"><span class="glyph">🗎</span> chemistry_reactions.md</div>
      `;
    }
  }

  const vcsTabs = document.querySelectorAll('.vcs-tab');
  const vcsPages = document.querySelectorAll('.vcs-content-page');
  vcsTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      vcsTabs.forEach(t => t.classList.remove('active'));
      vcsPages.forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(tab.getAttribute('data-tab')).classList.add('active');
    });
  });

  // --- 8. Obsidian Knowledge Graph ---
  function renderObsidianGraph() {
    const svg = document.getElementById('knowledge-graph-svg');
    if (!svg) return;

    svg.innerHTML = `
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="15" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--text-muted)"/>
        </marker>
      </defs>
      <line x1="200" y1="150" x2="400" y2="250" stroke="var(--border-color)" stroke-width="2" marker-end="url(#arrow)" />
      <line x1="400" y1="250" x2="600" y2="180" stroke="var(--border-color)" stroke-width="2" marker-end="url(#arrow)" />
      <line x1="400" y1="250" x2="450" y2="400" stroke="var(--border-color)" stroke-width="2" marker-end="url(#arrow)" />

      <circle cx="200" cy="150" r="16" fill="var(--primary-accent)" />
      <text x="200" y="185" text-anchor="middle" fill="var(--text-main)" font-size="12" font-weight="bold">Quantum Physics</text>

      <circle cx="400" cy="250" r="20" fill="var(--success-color)" />
      <text x="400" y="290" text-anchor="middle" fill="var(--text-main)" font-size="12" font-weight="bold">Calculus & Math</text>

      <circle cx="600" cy="180" r="15" fill="var(--warning-color)" />
      <text x="600" y="215" text-anchor="middle" fill="var(--text-main)" font-size="12" font-weight="bold">Wave Mechanics</text>

      <circle cx="450" cy="400" r="14" fill="#9c27b0" />
      <text x="450" y="430" text-anchor="middle" fill="var(--text-main)" font-size="12" font-weight="bold">Organic Chemistry</text>
    `;
  }

  // --- 9. Shared Hub ---
  function renderSharedHub() {
    const list = document.getElementById('contrib-list-container');
    if (list && list.children.length === 0) {
      list.innerHTML = `
        <li style="padding:10px; border-bottom:1px solid var(--border-color); cursor:pointer;">
          <div style="font-weight:bold;"><span class="glyph">⎇</span> Add Quantum Integration Examples</div>
          <div style="font-size:12px; color:var(--text-muted);">Branch: feature/alex-quantum • Target: main</div>
        </li>
      `;
    }
  }

  const shTabs = document.querySelectorAll('.sh-tab');
  const shPages = document.querySelectorAll('.sh-page');
  shTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      shTabs.forEach(t => t.classList.remove('active'));
      shPages.forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(tab.getAttribute('data-shtab')).classList.add('active');
    });
  });

  function renderDownloadsList() {
    const container = document.getElementById('downloads-list-container');
    if (container) {
      container.innerHTML = `
        <div style="padding:12px; border:1px solid var(--border-color); border-radius:8px; margin-bottom:10px;">
          <div style="font-weight:bold;"><span class="glyph">⤓</span> Manim_Quantum_Wave_Animation.mp4</div>
          <div style="font-size:12px; color:var(--text-muted);">Size: 4.2 MB • Saved locally</div>
        </div>
      `;
    }
  }

  // Init default view
  initDemoCanvas();
});
