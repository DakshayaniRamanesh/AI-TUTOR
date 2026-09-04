import os
import re
import time
from typing import Optional, Dict, Any, List, Union, Tuple
import requests
from typing import Optional, Dict, Any, List, Tuple
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

CHEMISTRY_KNOWLEDGE_BASE = {
    "phenolphthalein": {
        "title": "Phenolphthalein Indicator",
        "formula": r"\text{C}_{20}\text{H}_{14}\text{O}_4",
        "molar_mass": "318.32 g/mol",
        "type": "Acid-Base Indicator",
        "ph_range": "pH 8.2 – 10.0",
        "color_change": "Colorless (Acid/Neutral) ↔ Pink/Magenta (Base)",
        "structure": "Triarylmethane dye (phthalide core with two phenolic rings)"
    },
    "phenopthaline": {
        "title": "Phenolphthalein Indicator",
        "formula": r"\text{C}_{20}\text{H}_{14}\text{O}_4",
        "molar_mass": "318.32 g/mol",
        "type": "Acid-Base Indicator",
        "ph_range": "pH 8.2 – 10.0",
        "color_change": "Colorless (Acid/Neutral) ↔ Pink/Magenta (Base)",
        "structure": "Triarylmethane dye (phthalide core with two phenolic rings)"
    },
    "methyl orange": {
        "title": "Methyl Orange Indicator",
        "formula": r"\text{C}_{14}\text{H}_{14}\text{N}_3\text{NaO}_3\text{S}",
        "molar_mass": "327.33 g/mol",
        "type": "Acid-Base Indicator",
        "ph_range": "pH 3.1 – 4.4",
        "color_change": "Red (Acid) ↔ Yellow (Base)",
        "structure": "Azo dye compound"
    },
    "litmus": {
        "title": "Litmus Indicator",
        "formula": r"\text{C}_9\text{H}_{10}\text{O}_5",
        "type": "Natural pH Indicator",
        "ph_range": "pH 4.5 – 8.3",
        "color_change": "Red (Acid) ↔ Blue (Base)",
        "structure": "Lichen-extracted natural indicator"
    },
    "benzene": {
        "title": "Benzene",
        "formula": r"\text{C}_6\text{H}_6",
        "molar_mass": "78.11 g/mol",
        "type": "Aromatic Hydrocarbon",
        "structure": "Planar hexagonal ring with 6 delocalized π-electrons"
    },
    "water": {
        "title": "Water",
        "formula": r"\text{H}_2\text{O}",
        "molar_mass": "18.02 g/mol",
        "type": "Universal Solvent",
        "structure": "Bent polar molecule (104.5° bond angle)"
    },
    "methane": {
        "title": "Methane",
        "formula": r"\text{CH}_4",
        "molar_mass": "16.04 g/mol",
        "type": "Simplest Alkane Hydrocarbon",
        "structure": "Tetrahedral geometry (109.5° bond angle)"
    },
    "carbon dioxide": {
        "title": "Carbon Dioxide",
        "formula": r"\text{CO}_2",
        "molar_mass": "44.01 g/mol",
        "type": "Inorganic Oxide Gas",
        "structure": "Linear non-polar molecule (O=C=O, 180° bond angle)"
    },
    "ethanol": {
        "title": "Ethanol (Ethyl Alcohol)",
        "formula": r"\text{C}_2\text{H}_5\text{OH}",
        "molar_mass": "46.07 g/mol",
        "type": "Primary Alcohol",
        "structure": "CH3-CH2-OH aliphatic chain"
    },
    "sulfuric acid": {
        "title": "Sulfuric Acid",
        "formula": r"\text{H}_2\text{SO}_4",
        "molar_mass": "98.08 g/mol",
        "type": "Strong Mineral Acid",
        "structure": "Diprotic tetrahedral sulfur oxyacid"
    },
    "hydrochloric acid": {
        "title": "Hydrochloric Acid",
        "formula": r"\text{HCl}",
        "molar_mass": "36.46 g/mol",
        "type": "Strong Monoprotic Acid",
        "structure": "Hydrogen chloride in aqueous solution"
    },
    "nitric acid": {
        "title": "Nitric Acid",
        "formula": r"\text{HNO}_3",
        "molar_mass": "63.01 g/mol",
        "type": "Strong Oxidizing Acid",
        "structure": "Planar nitrate oxyacid"
    },
    "acetic acid": {
        "title": "Acetic Acid (Ethanoic Acid)",
        "formula": r"\text{CH}_3\text{COOH}",
        "molar_mass": "60.05 g/mol",
        "type": "Carboxylic Acid (Vinegar)",
        "structure": "Methyl group bonded to carboxyl group"
    },
    "glucose": {
        "title": "Glucose",
        "formula": r"\text{C}_6\text{H}_{12}\text{O}_6",
        "molar_mass": "180.16 g/mol",
        "type": "Monosaccharide Hexose Sugar",
        "structure": "Pyranose 6-membered cyclic ring"
    },
    "ammonia": {
        "title": "Ammonia",
        "formula": r"\text{NH}_3",
        "molar_mass": "17.03 g/mol",
        "type": "Pungent Alkaline Gas",
        "structure": "Trigonal pyramidal molecule with lone pair (107°)"
    },
    "sodium hydroxide": {
        "title": "Sodium Hydroxide (Caustic Soda)",
        "formula": r"\text{NaOH}",
        "molar_mass": "39.997 g/mol",
        "type": "Strong Base / Alkali",
        "structure": "Ionic lattice of Na+ and OH- ions"
    },
    "sodium chloride": {
        "title": "Sodium Chloride (Table Salt)",
        "formula": r"\text{NaCl}",
        "molar_mass": "58.44 g/mol",
        "type": "Ionic Salt",
        "structure": "Face-centered cubic (FCC) crystal lattice"
    },
    "hydrogen peroxide": {
        "title": "Hydrogen Peroxide",
        "formula": r"\text{H}_2\text{O}_2",
        "molar_mass": "34.01 g/mol",
        "type": "Strong Oxidizing Agent",
        "structure": "Non-planar skewed open-book conformation"
    },
    "acetone": {
        "title": "Acetone (Propanone)",
        "formula": r"\text{C}_3\text{H}_6\text{O}",
        "molar_mass": "58.08 g/mol",
        "type": "Simplest Ketone",
        "structure": "Carbonyl group bonded to two methyl groups"
    },
    "aspirin": {
        "title": "Aspirin (Acetylsalicylic Acid)",
        "formula": r"\text{C}_9\text{H}_8\text{O}_4",
        "molar_mass": "180.16 g/mol",
        "type": "Analgesic & Anti-inflammatory NSAID",
        "structure": "Salicylic acid derivative with acetyl group"
    },
    "caffeine": {
        "title": "Caffeine",
        "formula": r"\text{C}_8\text{H}_{10}\text{N}_4\text{O}_2",
        "molar_mass": "194.19 g/mol",
        "type": "Xanthine Alkaloid Stimulant",
        "structure": "Purine base derivative with methyl substituents"
    },
    "sucrose": {
        "title": "Sucrose (Table Sugar)",
        "formula": r"\text{C}_{12}\text{H}_{22}\text{O}_{11}",
        "molar_mass": "342.30 g/mol",
        "type": "Disaccharide Sugar (Glucose + Fructose)",
        "structure": "Glycosidic bond between glucose and fructose"
    },
    "citric acid": {
        "title": "Citric Acid",
        "formula": r"\text{C}_6\text{H}_8\text{O}_7",
        "molar_mass": "192.12 g/mol",
        "type": "Weak Organic Tricarboxylic Acid",
        "structure": "Three carboxyl (-COOH) and one hydroxyl (-OH) group"
    },
    "sodium bicarbonate": {
        "title": "Sodium Bicarbonate (Baking Soda)",
        "formula": r"\text{NaHCO}_3",
        "molar_mass": "84.01 g/mol",
        "type": "Amphoteric Sodium Salt",
        "structure": "Sodium cation and bicarbonate anion"
    },
    "baking soda": {
        "title": "Baking Soda (Sodium Bicarbonate)",
        "formula": r"\text{NaHCO}_3",
        "molar_mass": "84.01 g/mol",
        "type": "Leavening Agent / Base",
        "structure": "NaHCO3 crystal powder"
    },
    "potassium permanganate": {
        "title": "Potassium Permanganate",
        "formula": r"\text{KMnO}_4",
        "molar_mass": "158.03 g/mol",
        "type": "Strong Oxidizing Agent (Purple Crystals)",
        "structure": "K+ and tetrahedral MnO4- ions"
    },
    "copper sulfate": {
        "title": "Copper(II) Sulfate",
        "formula": r"\text{CuSO}_4",
        "molar_mass": "159.61 g/mol",
        "type": "Inorganic Salt (Blue Vitriol when hydrated)",
        "structure": "Cu2+ and SO4(2-) ionic crystal"
    },
    "phenol": {
        "title": "Phenol (Carbolic Acid)",
        "formula": r"\text{C}_6\text{H}_5\text{OH}",
        "molar_mass": "94.11 g/mol",
        "type": "Aromatic Hydroxy Compound",
        "structure": "Hydroxyl group directly attached to benzene ring"
    },
    "aniline": {
        "title": "Aniline",
        "formula": r"\text{C}_6\text{H}_5\text{NH}_2",
        "molar_mass": "93.13 g/mol",
        "type": "Primary Aromatic Amine",
        "structure": "Amino group bonded to benzene ring"
    },
    "toluene": {
        "title": "Toluene (Methylbenzene)",
        "formula": r"\text{C}_7\text{H}_8",
        "molar_mass": "92.14 g/mol",
        "type": "Aromatic Hydrocarbon",
        "structure": "Methyl group attached to benzene ring"
    },
    "methanol": {
        "title": "Methanol (Wood Alcohol)",
        "formula": r"\text{CH}_3\text{OH}",
        "molar_mass": "32.04 g/mol",
        "type": "Simplest Alcohol",
        "structure": "Methyl group bonded to hydroxyl group"
    },
    "chloroform": {
        "title": "Chloroform (Trichloromethane)",
        "formula": r"\text{CHCl}_3",
        "molar_mass": "119.38 g/mol",
        "type": "Trihalomethane Anesthetic / Solvent",
        "structure": "Carbon bonded to one H and three Cl atoms"
    },
    "bromothymol blue": {
        "title": "Bromothymol Blue Indicator",
        "formula": r"\text{C}_{27}\text{H}_{28}\text{Br}_2\text{O}_5\text{S}",
        "type": "pH Indicator",
        "ph_range": "pH 6.0 – 7.6",
        "color_change": "Yellow (Acid) ↔ Green (Neutral) ↔ Blue (Base)"
    },
    "thymol blue": {
        "title": "Thymol Blue Indicator",
        "formula": r"\text{C}_{27}\text{H}_{30}\text{O}_5\text{S}",
        "type": "Dual-Range pH Indicator",
        "ph_range": "pH 1.2–2.8 (Red→Yellow) & 8.0–9.6 (Yellow→Blue)",
        "color_change": "Red ↔ Yellow ↔ Blue"
    }
}

def get_local_stem_answer(question: str, mode: str = "study") -> Optional[dict]:
    """
    Checks built-in comprehensive STEM & chemistry knowledge base for instant 0ms offline response.
    """
    q_lower = question.lower()
    for key, data in CHEMISTRY_KNOWLEDGE_BASE.items():
        if key in q_lower:
            title = data["title"]
            formula = data["formula"]
            molar = data.get("molar_mass", "")
            ctype = data.get("type", "")
            ph_rng = data.get("ph_range", "")
            color_chg = data.get("color_change", "")
            struct = data.get("structure", "")

            if mode == "classroom":
                ans = f"Answer: {title} formula is ${formula}$"
                return {"is_direct_math": True, "hints": ans, "full_solution": ans, "solution": ans, "plot_path": ""}

            lines = [f"### {title}"]
            lines.append(f"$${formula}$$")
            lines.append(f"• **Formula:** ${formula}$")
            if molar:
                lines.append(f"• **Molar Mass:** {molar}")
            if ph_rng:
                lines.append(f"• **pH Range:** {ph_rng}")
            if color_chg:
                lines.append(f"• **Color Transition:** {color_chg}")
            if ctype:
                lines.append(f"• **Type:** {ctype}")
            if struct:
                lines.append(f"• **Structure:** {struct}")

            full_sol = "\n".join(lines)
            hints = f"• Compound: {title}\n• Formula: ${formula}$"
            return {"hints": hints, "full_solution": full_sol, "solution": full_sol, "plot_path": ""}

    return None

def get_gemini_ai_answer(question: str, mode: str = "study") -> dict:
    """
    Calls Groq (Llama 3.3 70B) or Google Gemini AI LLM model to get answer based on active mode (Classroom vs Study).
    - Classroom Mode: Direct straight answer only, no elaboration or step-by-step breakdown.
    - Study Mode: Concise, clean, handwritten-style bullet points with rich LaTeX formulas.
    """
    # 0. Check instant local STEM knowledge base first (0ms latency, zero timeouts)
    local_ans = get_local_stem_answer(question, mode=mode)
    if local_ans:
        return local_ans

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
            f"You are a helpful AI tutor writing simple handwritten blackboard notes.\n"
            f"For the question below, provide a VERY SIMPLE, direct, and concise answer (max 3-4 short bullet points).\n"
            f"DO NOT write long essays, numbered section breakdowns, or boilerplate text.\n"
            f"Use clean math notation ($...$) for formulas.\n\n"
            f"Question: {question}\n\n"
            f"Format strictly as:\n"
            f"### <Topic or Title>\n"
            f"$$<Primary Formula if applicable>$$\n"
            f"• <Key point / Direct Definition / Formula>\n"
            f"• <Property / Calculation / Concise explanation>\n"
        )

    # 1. Primary: Groq Llama 3.3 70B (Fast sub-second response)
    if groq_key:
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}"},
                json={
                    "model": "qwen/qwen3.6-27b",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 600
                },
                timeout=2.5
            )
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"].strip()
                # Strip <think>...</think> from reasoning models (Qwen, etc.)
                import re as _re
                text = _re.sub(r'<think>.*?</think>', '', text, flags=_re.DOTALL).strip()
                if text:
                    text_pretty = to_pretty_math(text)
                    if mode == "classroom":
                        return {"hints": text_pretty, "full_solution": text_pretty, "is_direct_math": True}
                    lines = [l for l in text_pretty.split("\n") if l.strip()]
                    short_hints = "\n".join(lines[:2])
                    return {"hints": short_hints, "full_solution": text_pretty}
        except Exception:
            pass

    # 2. Secondary: Google Gemini models
    if gemini_key:
        models = ["gemini-flash-latest", "gemini-flash-lite-latest"]
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        for model in models:
            try:
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
                resp = requests.post(api_url, json=payload, timeout=8.0)
                if resp.status_code == 200:
                    result_json = resp.json()
                    text = result_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if text:
                        text_pretty = to_pretty_math(text)
                        if mode == "classroom":
                            return {"hints": text_pretty, "full_solution": text_pretty, "is_direct_math": True}
                        lines = [l for l in text_pretty.split("\n") if l.strip()]
                        short_hints = "\n".join(lines[:2])
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
        clean_title = re.sub(r'^(formula\s+for|what\s+is\s+the\s+formula\s+for|what\s+is|define|calculate|solve)\s+', '', q_raw, flags=re.IGNORECASE).strip().title()
        if mode == "classroom":
            ans_text = f"Answer: {clean_title or q_raw}"
            return {"is_direct_math": True, "hints": ans_text, "full_solution": ans_text, "solution": ans_text, "plot_path": plot_path}

        solution = (
            f"### {clean_title or q_raw}\n"
            f"• **Topic:** {q_raw}\n"
            f"• **Result:** Direct formulation & scientific definitions apply.\n"
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

