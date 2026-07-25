/**
 * Open-Source Client-Side Git Engine for GitNote VCS
 * Implements a pure JS Git DAG (Blobs, Trees, Commits, Staging Index, Branches, Diffs)
 */

class GitEngine {
  constructor() {
    this.repoName = 'ai-tutor-notes';
    this.currentBranch = 'main';
    this.branches = {}; // name -> commitHash
    this.tags = {}; // name -> commitHash
    this.commits = {}; // hash -> CommitObject
    this.head = null; // commitHash

    // Working directory and staging area
    this.workingDirectory = {}; // filename -> content
    this.stagingIndex = {}; // filename -> content

    this.listeners = [];
  }

  onChange(callback) {
    this.listeners.push(callback);
  }

  notify() {
    this.saveToStorage();
    this.listeners.forEach(cb => cb());
  }

  // Generate SHA-1 style truncated hash
  generateHash() {
    return Math.random().toString(36).substring(2, 9) + Math.random().toString(36).substring(2, 9);
  }

  // Initialize or restore repository
  init() {
    const saved = localStorage.getItem('GITNOTE_VCS_REPO_STATE');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        this.currentBranch = parsed.currentBranch || 'main';
        this.branches = parsed.branches || {};
        this.tags = parsed.tags || {};
        this.commits = parsed.commits || {};
        this.head = parsed.head || null;
        this.workingDirectory = parsed.workingDirectory || {};
        this.stagingIndex = parsed.stagingIndex || {};
        if (Object.keys(this.workingDirectory).length > 0) return;
      } catch (e) {
        console.warn('Failed to parse stored Git repo state, re-initializing sample repo', e);
      }
    }

    // Seed realistic sample Git note repository
    this.seedSampleRepository();
  }

  saveToStorage() {
    const data = {
      currentBranch: this.currentBranch,
      branches: this.branches,
      tags: this.tags,
      commits: this.commits,
      head: this.head,
      workingDirectory: this.workingDirectory,
      stagingIndex: this.stagingIndex
    };
    localStorage.setItem('GITNOTE_VCS_REPO_STATE', JSON.stringify(data));
  }

  seedSampleRepository() {
    this.commits = {};
    this.branches = {};
    this.tags = {};

    // Initial Note 1: physics_notes.md
    const file1_v1 = `# Physics & Quantum Mechanics Notes

## 1. Classical Physics vs Quantum Physics
Classical mechanics describes the behavior of macroscopic objects. Quantum mechanics describes nature at the scale of atoms and subatomic particles.

- **Planck's Law**: $E = h \\nu$
- **Speed of Light**: $c = 3.00 \\times 10^8 \\text{ m/s}$

## 2. Key Questions
- How does wave-particle duality manifest in double-slit experiments?
`;

    // Commit 1: Initial repository commit
    const hash1 = '7a9f2b1';
    this.commits[hash1] = {
      hash: hash1,
      parents: [],
      author: 'Dakshayani <dakshayani@ai-tutor.edu>',
      timestamp: new Date(Date.now() - 86400000 * 3).toISOString(),
      message: 'Initial commit: Add physics notes foundation',
      tree: {
        'physics_notes.md': file1_v1,
        'ai_tutor_roadmap.md': `# AI Tutor Platform Architecture

## Features
- Automated summarizer
- STEM problem solver
- Interactive notebook with Git version control
`
      }
    };

    // Commit 2: Add Quantum Superposition
    const file1_v2 = file1_v1 + `
## 3. Quantum Superposition
Quantum superposition is a fundamental principle of quantum mechanics. It states that any two (or more) quantum states can be added together ("superposed") and the result will be another valid quantum state.

\`\`\`python
# Quantum state representation snippet
import numpy as np

psi = (1 / np.sqrt(2)) * np.array([1, 1]) # |+> state
print("Quantum superposition state vector:", psi)
\`\`\`
`;

    const hash2 = '3c8e9f4';
    this.commits[hash2] = {
      hash: hash2,
      parents: [hash1],
      author: 'Dakshayani <dakshayani@ai-tutor.edu>',
      timestamp: new Date(Date.now() - 86400000 * 2).toISOString(),
      message: 'Add quantum superposition theory & python code snippet',
      tree: {
        'physics_notes.md': file1_v2,
        'ai_tutor_roadmap.md': `# AI Tutor Platform Architecture

## Features
- Automated summarizer
- STEM problem solver
- Interactive notebook with Git version control
- Offline Git DAG history browser
`
      }
    };

    // Branch creation: feature/calculus
    const hash3 = 'e4b11c9';
    this.commits[hash3] = {
      hash: hash3,
      parents: [hash2],
      author: 'Dakshayani <dakshayani@ai-tutor.edu>',
      timestamp: new Date(Date.now() - 86400000 * 1).toISOString(),
      message: 'Draft calculus & derivatives cheat sheet',
      tree: {
        'physics_notes.md': file1_v2,
        'ai_tutor_roadmap.md': `# AI Tutor Platform Architecture

## Features
- Automated summarizer
- STEM problem solver
- Interactive notebook with Git version control
- Offline Git DAG history browser
`,
        'calculus_derivatives.md': `# Calculus & Derivatives Reference

## Standard Rules
1. Power Rule: $\\frac{d}{dx}[x^n] = n x^{n-1}$
2. Product Rule: $\\frac{d}{dx}[u \\cdot v] = u'v + uv'$
3. Chain Rule: $\\frac{d}{dx}[f(g(x))] = f'(g(x)) \\cdot g'(x)$
`
      }
    };

    // Setup refs
    this.branches['main'] = hash2;
    this.branches['feature/calculus'] = hash3;
    this.tags['v1.0.0'] = hash2;

    this.currentBranch = 'main';
    this.head = hash2;

    // Copy HEAD tree into working directory
    const headCommit = this.commits[this.head];
    this.workingDirectory = JSON.parse(JSON.stringify(headCommit.tree));

    // Simulate uncommitted edit in working directory for live demonstration
    this.workingDirectory['physics_notes.md'] += `\n## 4. Heisenberg Uncertainty Principle\nIt is impossible to measure simultaneously both the position and momentum of a particle:\n$$\\Delta x \\cdot \\Delta p \\ge \\frac{\\hbar}{2}$$\n`;
    
    // Copy main into staging index
    this.stagingIndex = JSON.parse(JSON.stringify(headCommit.tree));

    this.saveToStorage();
  }

  // File Operations in Working Tree
  getFileList() {
    const allFiles = new Set([
      ...Object.keys(this.workingDirectory),
      ...Object.keys(this.stagingIndex),
      ...(this.head && this.commits[this.head] ? Object.keys(this.commits[this.head].tree) : [])
    ]);
    return Array.from(allFiles).sort();
  }

  getFileContent(filename) {
    return this.workingDirectory[filename] || '';
  }

  updateFileContent(filename, content) {
    this.workingDirectory[filename] = content;
    this.notify();
  }

  createFile(filename) {
    if (!filename.endsWith('.md')) filename += '.md';
    if (!this.workingDirectory[filename]) {
      this.workingDirectory[filename] = `# ${filename.replace('.md', '')}\n\nStart typing your note content...`;
      this.notify();
    }
    return filename;
  }

  // Get Git Status of Files (M, A, D, U, Clean)
  getFileGitStatus(filename) {
    const headTree = (this.head && this.commits[this.head]) ? this.commits[this.head].tree : {};
    const inHead = filename in headTree;
    const inIndex = filename in this.stagingIndex;
    const inWork = filename in this.workingDirectory;

    const headContent = headTree[filename] || null;
    const indexContent = this.stagingIndex[filename] || null;
    const workContent = this.workingDirectory[filename] || null;

    if (inIndex && indexContent !== headContent) {
      return { code: 'S', name: 'Staged', label: 'Staged for commit' };
    }

    if (!inHead && inWork) {
      return { code: 'U', name: 'Untracked', label: 'Untracked file' };
    }

    if (inHead && !inWork) {
      return { code: 'D', name: 'Deleted', label: 'Deleted' };
    }

    if (inWork && headContent !== workContent) {
      return { code: 'M', name: 'Modified', label: 'Modified in working tree' };
    }

    return { code: '', name: 'Clean', label: 'Unmodified' };
  }

  // Git Staging Operations
  stageFile(filename) {
    if (filename in this.workingDirectory) {
      this.stagingIndex[filename] = this.workingDirectory[filename];
    } else {
      delete this.stagingIndex[filename]; // deleted file staged
    }
    this.notify();
  }

  unstageFile(filename) {
    const headTree = (this.head && this.commits[this.head]) ? this.commits[this.head].tree : {};
    if (filename in headTree) {
      this.stagingIndex[filename] = headTree[filename];
    } else {
      delete this.stagingIndex[filename];
    }
    this.notify();
  }

  stageAll() {
    this.getFileList().forEach(fn => this.stageFile(fn));
  }

  unstageAll() {
    this.getFileList().forEach(fn => this.unstageFile(fn));
  }

  discardChanges(filename) {
    const headTree = (this.head && this.commits[this.head]) ? this.commits[this.head].tree : {};
    if (filename in headTree) {
      this.workingDirectory[filename] = headTree[filename];
      this.stagingIndex[filename] = headTree[filename];
    } else {
      delete this.workingDirectory[filename];
      delete this.stagingIndex[filename];
    }
    this.notify();
  }

  // Git Commit
  commit(message, amend = false) {
    if (!message || message.trim() === '') {
      throw new Error('Commit message cannot be empty.');
    }

    let newHash = this.generateHash();
    let parents = [this.head];

    if (amend && this.head && this.commits[this.head]) {
      const lastCommit = this.commits[this.head];
      parents = lastCommit.parents;
      newHash = this.head; // overwrite
    }

    const newCommit = {
      hash: newHash,
      parents: parents,
      author: 'Dakshayani <dakshayani@ai-tutor.edu>',
      timestamp: new Date().toISOString(),
      message: message.trim(),
      tree: JSON.parse(JSON.stringify(this.stagingIndex))
    };

    this.commits[newHash] = newCommit;
    this.head = newHash;
    this.branches[this.currentBranch] = newHash;

    // Working directory becomes synchronized with commit tree
    this.workingDirectory = JSON.parse(JSON.stringify(this.stagingIndex));

    this.notify();
    return newCommit;
  }

  // Git Branching & Checkout
  createBranch(branchName, startPoint = 'HEAD') {
    if (!branchName || branchName.trim() === '') throw new Error('Branch name required.');
    const targetHash = startPoint === 'HEAD' ? this.head : (this.branches[startPoint] || startPoint);
    this.branches[branchName] = targetHash;
    this.notify();
  }

  switchBranch(branchName) {
    if (!this.branches[branchName]) throw new Error(`Branch ${branchName} does not exist.`);
    this.currentBranch = branchName;
    this.head = this.branches[branchName];

    // Load commit tree into working directory & staging area
    const headCommit = this.commits[this.head];
    if (headCommit) {
      this.workingDirectory = JSON.parse(JSON.stringify(headCommit.tree));
      this.stagingIndex = JSON.parse(JSON.stringify(headCommit.tree));
    }
    this.notify();
  }

  createTag(tagName, message = '') {
    if (!tagName) throw new Error('Tag name required.');
    this.tags[tagName] = this.head;
    this.notify();
  }

  // Compute Line-by-Line Diffs
  getLineDiff(oldText = '', newText = '') {
    if (typeof Diff !== 'undefined' && Diff.diffLines) {
      const changes = Diff.diffLines(oldText, newText);
      const lines = [];
      let oldNum = 1;
      let newNum = 1;
      let additions = 0;
      let deletions = 0;

      changes.forEach(change => {
        const lineArray = change.value.replace(/\n$/, '').split('\n');
        lineArray.forEach(text => {
          if (change.added) {
            lines.push({ type: 'add', text, oldNum: null, newNum: newNum++ });
            additions++;
          } else if (change.removed) {
            lines.push({ type: 'del', text, oldNum: oldNum++, newNum: null });
            deletions++;
          } else {
            lines.push({ type: 'same', text, oldNum: oldNum++, newNum: newNum++ });
          }
        });
      });

      return { additions, deletions, lines };
    }

    // Fallback simple line diff
    const oldLines = oldText.split('\n');
    const newLines = newText.split('\n');
    const lines = [];
    const max = Math.max(oldLines.length, newLines.length);

    let additions = 0, deletions = 0;
    for (let i = 0; i < max; i++) {
      const o = oldLines[i];
      const n = newLines[i];
      if (o === n) {
        lines.push({ type: 'same', text: o || '', oldNum: i+1, newNum: i+1 });
      } else {
        if (o !== undefined) { lines.push({ type: 'del', text: o, oldNum: i+1, newNum: null }); deletions++; }
        if (n !== undefined) { lines.push({ type: 'add', text: n, oldNum: null, newNum: i+1 }); additions++; }
      }
    }
    return { additions, deletions, lines };
  }

  // Get Commit Trajectory / Log
  getCommitLog() {
    const list = Object.values(this.commits);
    return list.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }
}

// Global instance
window.gitEngine = new GitEngine();
