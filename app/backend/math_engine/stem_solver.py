import os
import re
import time
import requests
from dotenv import load_dotenv
import sympy as sp
import numpy as np
import matplotlib.pyplot as plt

load_dotenv()
load_dotenv("backend/.env")
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "backend", ".env"))

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PLOTS_DIR = os.path.join(_BASE_DIR, "storage_data", "plots")

SUPERSCRIPTS = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
    '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
    'n': 'ⁿ', 'x': 'ˣ', 'y': 'ʸ'
}

def to_pretty_math(expr_str: str) -> str:
    s = str(expr_str)
    def repl(m):
        return "".join(SUPERSCRIPTS.get(c, c) for c in m.group(1))
    s = re.sub(r'\*\*([0-9nxy+-]+)', repl, s)
    s = re.sub(r'\^([0-9nxy+-]+)', repl, s)
    s = re.sub(r'(?<=[a-zA-Z0-9)])\*(?=[a-zA-Z()])', '', s)
    s = s.replace('*', '')
    return s

def clean_math_query(q: str) -> str:
    """
    Preprocesses natural language math input into clean SymPy expression string.
    """
    s = q.strip().rstrip(',.?!;=')
    s = re.sub(r'[\?=\s]+$', '', s)
    
    s = re.sub(r'^(evaluate|calculate|compute|find|solve|what is)\s+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^(the\s+)?(integral|derivative|diff|antiderivative)\s+(of\s+)?', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s*d[xyt]\b', '', s, flags=re.IGNORECASE)
    s = s.strip()
    
    if s.startswith('f') and len(s) > 1 and s[1].isdigit():
        s = s[1:]
        
    s = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', s)
    s = re.sub(r'(\d)\(', r'\1*(', s)
    s = s.replace('^', '**')
    return s

def should_generate_graph(raw_question: str, clean_expr_str: str) -> bool:
    """
    Determines if a graph plot is relevant for the query.
    Simple arithmetic (addition, numbers, basic constants) will NOT generate graphs.
    """
    q_lower = raw_question.lower()
    
    # Do NOT generate graphs for plain numbers or simple arithmetic without variables
    clean_no_ops = re.sub(r'[\d\s\+\-\*/\.\(\)]', '', clean_expr_str)
    if not clean_no_ops: # Pure arithmetic e.g. 12 + 13 or 25
        return False

    # Generate graphs for explicit plot requests or calculus/function variables
    if any(k in q_lower for k in ['plot', 'graph', 'draw', 'curve', 'visualize']):
        return True
    if any(k in q_lower for k in ['differentiate', 'derivative', 'diff', 'd/dx', 'integrate', 'integral', '∫', 'limit']):
        return True
        
    has_func_var = any(v in clean_expr_str for v in ['x', 'y', 't'])
    return has_func_var

def generate_function_plot(expression_str: str, title: str = "Function Graph") -> str:
    """
    Generates a beautifully styled, notebook-themed function graph.
    """
    os.makedirs(PLOTS_DIR, exist_ok=True)
    plot_path = os.path.join(PLOTS_DIR, f"plot_{int(time.time()*1000)}.png")

    try:
        x_sym = sp.symbols('x')
        parsed = sp.sympify(expression_str)
        func = sp.lambdify(x_sym, parsed, 'numpy')

        x_vals = np.linspace(-4, 4, 300)
        y_vals = func(x_vals)

        if np.isscalar(y_vals):
            y_vals = np.full_like(x_vals, y_vals)

        fig, ax = plt.subplots(figsize=(6, 3.5), facecolor='#fcfbf7')
        ax.set_facecolor('#fcfbf7')

        pretty_label = to_pretty_math(expression_str)
        ax.plot(x_vals, y_vals, label=f"f(x) = {pretty_label}", color='#007aff', linewidth=2.5)

        try:
            diff_expr = sp.diff(parsed, x_sym)
            diff_func = sp.lambdify(x_sym, diff_expr, 'numpy')
            dy_vals = diff_func(x_vals)
            if np.isscalar(dy_vals):
                dy_vals = np.full_like(x_vals, dy_vals)
            pretty_diff = to_pretty_math(diff_expr)
            ax.plot(x_vals, dy_vals, label=f"f'(x) = {pretty_diff}", color='#ff2d55', linewidth=1.8, linestyle='--')
        except Exception:
            pass

        ax.grid(True, linestyle=':', alpha=0.6, color='#c7c7cc')
        ax.axhline(0, color='#333333', linewidth=1)
        ax.axvline(0, color='#333333', linewidth=1)
        ax.legend(frameon=True, facecolor='#ffffff', edgecolor='#d1d1d6', fontsize=9)
        ax.set_title(title, fontsize=11, fontweight='bold', color='#1c1c1e', pad=8)
        
        y_valid = y_vals[np.isfinite(y_vals)]
        if len(y_valid) > 0:
            ymin, ymax = np.min(y_valid), np.max(y_valid)
            margin = max(1.0, (ymax - ymin) * 0.1)
            ax.set_ylim(max(-50, ymin - margin), min(50, ymax + margin))

        plt.tight_layout()
        plt.savefig(plot_path, dpi=140)
        plt.close(fig)
        return plot_path
    except Exception as err:
        print(f"[PlotGen] Notice: {err}")
        return ""

def is_simple_math_query(q_raw: str) -> bool:
    """
    Checks if a query is a direct arithmetic / simple math expression like 2+2=? or 15*8.
    """
    q = q_raw.strip().lower()
    q_clean = re.sub(r'^(what\s+is|evaluate|calculate|solve|compute|\s)+', '', q, flags=re.IGNORECASE)
    q_clean = re.sub(r'[\?=\s]', '', q_clean)
    if not q_clean:
        return False
    return bool(re.match(r'^[\d\+\-\*/\.\(\)\^\%]+$', q_clean))

def get_gemini_ai_answer(question: str, mode: str = "study") -> dict:
    """
    Calls Groq (Llama 3.3 70B) or Google Gemini AI LLM model to get answer based on active mode (Classroom vs Study).
    - Classroom Mode: Direct straight answer only, no elaboration or step-by-step breakdown.
    - Study Mode: Concise hints AND elaborate step-by-step solution with rich LaTeX & Markdown.
    """
    groq_key = os.getenv("GROQ_API_KEY")
    gemini_key = os.getenv("GOOGLE_API_KEY")

    if mode == "classroom":
        prompt = (
            f"You are Kestrel AI Tutor operating in CLASSROOM MODE.\n"
            f"For the student question below, provide ONLY the direct, straightforward final answer.\n"
            f"DO NOT elaborate, DO NOT explain, DO NOT provide step-by-step solutions or background text.\n"
            f"Give ONLY the straight direct answer concisely in 1 sentence or direct value.\n\n"
            f"Question: {question}\n\n"
            f"Format strictly as:\n"
            f"Answer: <straight direct answer>"
        )
    else:
        prompt = (
            f"You are Kestrel AI Tutor, an advanced STEM study notebook assistant operating in STUDY MODE.\n"
            f"For the student question/formula below, provide a clear, accurate, and comprehensive explanation with formatted LaTeX math/chemical formulas (e.g. $C_6H_6$, $x^2$, etc.) and Markdown headers.\n\n"
            f"Question: {question}\n\n"
            f"Strictly format your response as:\n"
            f"[HINTS]\n"
            f"• Key Point 1: ...\n"
            f"• Key Point 2: ...\n\n"
            f"[FULL_SOLUTION]\n"
            f"### {question}\n\n"
            f"**1. Core Concept & Overview**\n"
            f"...\n\n"
            f"**2. Formula, Structure & Proof**\n"
            f"...\n\n"
            f"**3. Key Properties & Calculations**\n"
            f"...\n"
        )

    # 1. Primary: Groq Llama 3.3 70B (Fast sub-second response)
    if groq_key:
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1200
                },
                timeout=4.0
            )
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"].strip()
                if text:
                    text_pretty = to_pretty_math(text)
                    if mode == "classroom":
                        return {"hints": text_pretty, "full_solution": text_pretty, "is_direct_math": True}
                    if "[HINTS]" in text_pretty and "[FULL_SOLUTION]" in text_pretty:
                        parts = text_pretty.split("[FULL_SOLUTION]")
                        hints = parts[0].replace("[HINTS]", "").strip()
                        full_sol = parts[1].strip()
                        return {"hints": hints, "full_solution": full_sol}
                    else:
                        lines = [l for l in text_pretty.split("\n") if l.strip()]
                        short_hints = "\n".join(lines[:3])
                        return {"hints": short_hints, "full_solution": text_pretty}
        except Exception as e:
            print(f"[LLM] Groq Notice: {e}")

    # 2. Secondary: Google Gemini models
    if gemini_key:
        models = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-flash-latest"]
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        for model in models:
            try:
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
                resp = requests.post(api_url, json=payload, timeout=3.5)
                if resp.status_code == 200:
                    result_json = resp.json()
                    text = result_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if text:
                        text_pretty = to_pretty_math(text)
                        if mode == "classroom":
                            return {"hints": text_pretty, "full_solution": text_pretty, "is_direct_math": True}
                        if "[HINTS]" in text_pretty and "[FULL_SOLUTION]" in text_pretty:
                            parts = text_pretty.split("[FULL_SOLUTION]")
                            hints = parts[0].replace("[HINTS]", "").strip()
                            full_sol = parts[1].strip()
                            return {"hints": hints, "full_solution": full_sol}
                        else:
                            lines = [l for l in text_pretty.split("\n") if l.strip()]
                            short_hints = "\n".join(lines[:3])
                            return {"hints": short_hints, "full_solution": text_pretty}
            except Exception:
                continue

    return {}

def solve_stem_question(question: str, mode: str = "study") -> dict:
    """
    Evaluates questions using Gemini AI LLM and SymPy symbolic solver.
    Modes:
    - "classroom": Straight-to-the-point direct answer only (no elaboration/waiting).
    - "study": Complete step-by-step solution with hints and core concepts.
    """
    q_raw = question.strip()
    q_clean = clean_math_query(q_raw)
    x, y, z, t = sp.symbols('x y z t')
    plot_path = ""

    # Check question tags for calculus operations
    is_integral = any(k in q_raw.lower() for k in ['integral', 'integrate', '∫'])
    is_derivative = any(k in q_raw.lower() for k in ['derivative', 'differentiate', 'diff', 'd/dx'])
    is_limit = any(k in q_raw.lower() for k in ['limit', 'lim'])

    # 1. Simple direct math (e.g. 2+2=?, 15 * 8, 100/5) -> return ONLY final direct answer
    if is_simple_math_query(q_raw):
        try:
            parsed = sp.sympify(q_clean)
            simplified = sp.simplify(parsed)
            pretty_r = to_pretty_math(simplified)
            ans_text = f"Answer: {pretty_r}"
            return {
                "is_direct_math": True,
                "hints": ans_text,
                "full_solution": ans_text,
                "solution": ans_text,
                "plot_path": ""
            }
        except Exception:
            pass

    # 2. Try Gemini AI LLM for AI answer according to mode
    ai_data = get_gemini_ai_answer(q_raw, mode=mode)
    
    # Check if a function plot is relevant
    if should_generate_graph(q_raw, q_clean):
        try:
            parsed = sp.sympify(q_clean)
            pretty_p = to_pretty_math(parsed)
            plot_path = generate_function_plot(str(parsed), title=f"Graph: f(x) = {pretty_p}")
        except Exception:
            pass

    if ai_data:
        hints = ai_data.get("hints", "")
        full_sol = ai_data.get("full_solution", "")
        if mode == "classroom":
            ans = full_sol or hints
            if not ans.startswith("Answer:") and not ans.startswith("Ans:"):
                ans = f"Answer: {ans}"
            return {
                "is_direct_math": True,
                "hints": ans,
                "full_solution": ans,
                "solution": ans,
                "plot_path": plot_path
            }
        return {
            "is_direct_math": False,
            "hints": hints,
            "full_solution": full_sol,
            "solution": full_sol,
            "plot_path": plot_path
        }

    # Check if user explicitly asked to elaborate/explain/show steps
    wants_elaborate = (mode == "study") or any(k in q_raw.lower() for k in ['elaborate', 'explain', 'steps', 'step by step', 'detail', 'how to', 'why'])

    try:
        if is_integral:
            parsed_expr = sp.sympify(q_clean)
            result = sp.integrate(parsed_expr, x)
            pretty_p = to_pretty_math(parsed_expr)
            pretty_r = to_pretty_math(result)
            
            if not plot_path and should_generate_graph(q_raw, q_clean):
                plot_path = generate_function_plot(str(parsed_expr), title=f"Integrand Graph: f(x) = {pretty_p}")
            
            if not wants_elaborate or mode == "classroom":
                ans_text = f"Answer: ∫ {pretty_p} dx = {pretty_r} + C"
                return {"is_direct_math": True, "hints": ans_text, "full_solution": ans_text, "solution": ans_text, "plot_path": plot_path}

            solution = (
                f"1. ▤ Core Concept & Integrand\n"
                f"Identify f(x) = {pretty_p}\n\n"
                f"2. ✦ Step-by-Step Integration\n"
                f"Apply integration rules & anti-differentiation:\n"
                f"∫ {pretty_p} dx = {pretty_r} + C\n\n"
                f"3. ◈ Final Answer\n"
                f"∫ {pretty_p} dx = {pretty_r} + C"
            )
            return {"hints": solution, "solution": solution, "plot_path": plot_path}
            
        elif is_derivative:
            parsed_expr = sp.sympify(q_clean)
            result = sp.diff(parsed_expr, x)
            pretty_p = to_pretty_math(parsed_expr)
            pretty_r = to_pretty_math(result)
            
            if not plot_path and should_generate_graph(q_raw, q_clean):
                plot_path = generate_function_plot(str(parsed_expr), title=f"Function & Derivative: {pretty_p}")
            
            if not wants_elaborate or mode == "classroom":
                ans_text = f"Answer: d/dx({pretty_p}) = {pretty_r}"
                return {"is_direct_math": True, "hints": ans_text, "full_solution": ans_text, "solution": ans_text, "plot_path": plot_path}

            solution = (
                f"1. ▤ Core Concept & Function\n"
                f"Identify f(x) = {pretty_p}\n\n"
                f"2. ✦ Step-by-Step Differentiation\n"
                f"Apply differentiation rules:\n"
                f"f'(x) = {pretty_r}\n\n"
                f"3. ◈ Final Answer\n"
                f"f'(x) = {pretty_r}"
            )
            return {"hints": solution, "solution": solution, "plot_path": plot_path}

        elif is_limit:
            target_val = 0
            expr_str = q_clean
            if 'as x->' in expr_str:
                parts = expr_str.split('as x->')
                expr_str = parts[0]
                target_val = sp.sympify(parts[1])
            parsed_expr = sp.sympify(expr_str if expr_str else 'sin(x)/x')
            result = sp.limit(parsed_expr, x, target_val)
            pretty_p = to_pretty_math(parsed_expr)
            pretty_r = to_pretty_math(result)
            
            if not plot_path and should_generate_graph(q_raw, q_clean):
                plot_path = generate_function_plot(str(parsed_expr), title=f"Limit Graph: {pretty_p}")
            
            if mode == "classroom":
                ans_text = f"Answer: lim_{{x→{target_val}}} {pretty_p} = {pretty_r}"
                return {"is_direct_math": True, "hints": ans_text, "full_solution": ans_text, "solution": ans_text, "plot_path": plot_path}

            solution = (
                f"1. ▤ Core Concept & Limit Definition\n"
                f"Evaluate limit of f(x) = {pretty_p} as x → {target_val}\n\n"
                f"2. ✦ Step-by-Step Evaluation\n"
                f"Apply limit laws and algebraic simplification.\n\n"
                f"3. ◈ Final Answer\n"
                f"lim_{{x→{target_val}}} {pretty_p} = {pretty_r}"
            )
            return {"hints": solution, "solution": solution, "plot_path": plot_path}

        # General SymPy evaluation fallback (Arithmetic, Algebra, Constants)
        parsed = sp.sympify(q_clean)
        simplified = sp.simplify(parsed)
        pretty_p = to_pretty_math(parsed)
        pretty_r = to_pretty_math(simplified)
        
        if not plot_path and should_generate_graph(q_raw, q_clean):
            plot_path = generate_function_plot(str(parsed), title=f"Function Graph: {pretty_p}")
            
        if not wants_elaborate or mode == "classroom":
            ans_text = f"Answer: {pretty_p} = {pretty_r}"
            return {"is_direct_math": True, "hints": ans_text, "full_solution": ans_text, "solution": ans_text, "plot_path": plot_path}

        solution = (
            f"1. ▤ Core Concept\n"
            f"Evaluate mathematical expression: {pretty_p}\n\n"
            f"2. ✦ Step-by-Step Simplification\n"
            f"Simplifying terms yields: {pretty_r}\n\n"
            f"3. ◈ Final Answer\n"
            f"{pretty_p} = {pretty_r}"
        )
        return {"hints": solution, "solution": solution, "plot_path": plot_path}

    except Exception:
        if mode == "classroom":
            ans_text = f"Answer: {q_raw}"
            return {"is_direct_math": True, "hints": ans_text, "full_solution": ans_text, "solution": ans_text, "plot_path": plot_path}

        solution = (
            f"1. ▤ Question Overview\n"
            f"Topic: {q_raw}\n\n"
            f"2. ✦ Structured Analysis\n"
            f"• Identify core variables and relationships.\n"
            f"• Apply foundational laws & definitions.\n\n"
            f"3. ◈ Summary & Key Takeaway\n"
            f"For detailed AI study explanations, ensure GOOGLE_API_KEY is connected."
        )
        return {"hints": solution, "solution": solution, "plot_path": plot_path}

from PyQt6.QtCore import QThread, pyqtSignal

class StemSolverWorker(QThread):
    finished = pyqtSignal(str, dict)

    def __init__(self, question: str, mode: str = "study", parent=None):
        super().__init__(parent)
        self.question = question
        self.mode = mode

    def run(self):
        res = solve_stem_question(self.question, mode=self.mode)
        self.finished.emit(self.question, res)

