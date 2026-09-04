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

def user_asked_for_explanation(q: str) -> bool:
    """
    Returns True only if the user explicitly requested an explanation or step-by-step breakdown.
    """
    q_lower = q.lower()
    keywords = [
        "explain", "explanation", "why", "how", "steps", "step by step",
        "show work", "show steps", "elaborate", "detail", "details", "derive", "derivation", "proof", "prove"
    ]
    return any(k in q_lower for k in keywords)

def clean_ai_response(text: str) -> str:
    """
    Strips internal thinking processes, reasoning monologue, and planning blocks emitted by reasoning LLMs.
    """
    if not text:
        return ""
    # 1. Strip <think>...</think>
    text = re.sub(r'(?is)<think>.*?</think>', '', text).strip()

    # 2. Check if model produced a thinking process with a "Draft:" or final answer section
    if re.search(r'(?i)\bdraft\s*:', text):
        parts = re.split(r'(?i)\bdraft\s*:\s*\n*', text, maxsplit=1)
        draft_body = parts[1]
        # Remove trailing constraints checks e.g. "4. Check Constraints:"
        draft_clean = re.split(r'(?i)\n+\s*\d+\.\s*(?:check\s+constraints|verification|review)', draft_body)[0]
        text = draft_clean.strip()
    else:
        # Strip thinking process headers up to Question: or Answer:
        patterns = [
            r"(?is)here'?s a thinking process\s*:.*?(?=(?:question\s*:|answer\s*:|###|\$\$|\Z))",
            r"(?is)thinking process\s*:.*?(?=(?:question\s*:|answer\s*:|###|\$\$|\Z))",
            r"(?is)\b1\.\s*analyze user input\s*:.*?(?=(?:question\s*:|answer\s*:|###|\$\$|\Z))"
        ]
        for p in patterns:
            text = re.sub(p, '', text).strip()

    text = re.sub(r'(?i)^draft\s*:\s*\n*', '', text).strip()
    text = re.sub(r"(?is)here'?s a thinking process.*$", '', text).strip()
    return text.strip()

def clean_math_query(q: str) -> str:
    """
    Preprocesses natural language math input into clean SymPy expression string.
    """
    s = q.strip().rstrip(',.?!;=')
    s = re.sub(r'[\?=\s]+$', '', s)
    
    # Strip trailing explanation requests e.g. "and explain", "with steps", "show work"
    s = re.sub(r'\s+(and\s+)?(please\s+)?(explain|show\s+steps?|steps?|with\s+steps?|in\s+detail|elaborate)\s*$', '', s, flags=re.IGNORECASE)
    # Strip leading explanation requests e.g. "explain how to integrate 5x"
    s = re.sub(r'^(please\s+)?(explain|show\s+steps?|steps?|elaborate)\s+(how\s+to\s+)?', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^(evaluate|calculate|compute|find|solve|what is|please)\s+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^(the\s+)?(integral|integrate|integration|derivative|differentiate|diff|antiderivative)\s+(of\s+)?', '', s, flags=re.IGNORECASE)
    
    # Differential stripping: dx, dy, dt, dz at end of expression (e.g. 5xdx, 5x dx)
    s = re.sub(r'[\s\*]*d[xytz]\b\s*$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'(?<=[a-zA-Z0-9\)])d[xytz]$', '', s, flags=re.IGNORECASE)
    
    # Derivative prefix stripping: d/dx(...)
    s = re.sub(r'^d/d[xytz]\s*\(?', '', s, flags=re.IGNORECASE)
    s = s.strip()
    if s.endswith(')') and '(' not in s:
        s = s[:-1].strip()
        
    if s.startswith('f') and len(s) > 1 and s[1].isdigit():
        s = s[1:]
        
    s = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', s)
    s = re.sub(r'(\d)\(', r'\1*(', s)
    s = s.replace('^', '**')
    return s.strip()

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
    asked_explain = user_asked_for_explanation(question)

    for key, data in CHEMISTRY_KNOWLEDGE_BASE.items():
        if key in q_lower:
            title = data["title"]
            formula = data["formula"]
            molar = data.get("molar_mass", "")
            ctype = data.get("type", "")
            ph_rng = data.get("ph_range", "")
            color_chg = data.get("color_change", "")
            struct = data.get("structure", "")

            short_sol = f"Question: {question}\nAnswer: {title} (${formula}$)"
            lines = [short_sol, "", "Explanation:"]
            if molar:
                lines.append(f"• Molar Mass: {molar}")
            if ctype:
                lines.append(f"• Type: {ctype}")
            if ph_rng:
                lines.append(f"• pH Range: {ph_rng}")
            if color_chg:
                lines.append(f"• Color Transition: {color_chg}")
            if struct:
                lines.append(f"• Structure: {struct}")
            full_sol = "\n".join(lines)

            if mode == "classroom":
                ans = f"Answer: {title} formula is ${formula}$"
                return {"is_direct_math": True, "hints": ans, "short_solution": ans, "full_solution": ans, "solution": ans, "plot_path": ""}

            return {
                "is_direct_math": not asked_explain,
                "hints": short_sol,
                "short_solution": short_sol,
                "full_solution": full_sol,
                "solution": full_sol if asked_explain else short_sol,
                "plot_path": ""
            }

    return None

def get_gemini_ai_answer(question: str, mode: str = "study") -> dict:
    """
    Calls Groq or Google Gemini AI LLM model to get answer based on active mode (Classroom vs Study).
    - Classroom Mode: Direct straight answer only.
    - Ask AI (Study Mode): Concise Question + Answer by default, with step-by-step explanation available on expand.
    """
    local_ans = get_local_stem_answer(question, mode=mode)
    if local_ans:
        return local_ans

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    gemini_key = (
        os.environ.get("GEMINI_API_KEY", "").strip() or
        os.environ.get("GOOGLE_API_KEY", "").strip()
    )

    asked_explain = user_asked_for_explanation(question)

    if mode == "classroom":
        prompt = (
            "You are a concise STEM solver for a classroom blackboard.\n"
            "CRITICAL: Do NOT output any thinking process, reasoning steps, or analysis.\n"
            "Output ONLY the direct answer.\n\n"
            f"Question: {question}\n\n"
            "Format strictly as:\n"
            "Answer: <direct answer>"
        )
    else:
        prompt = (
            "You are a helpful AI tutor in ASK AI.\n"
            "CRITICAL: Do NOT output any internal thinking process, reasoning steps, analysis, or monologue.\n"
            "Provide the question, direct answer, and then a clear, concise explanation with 2-3 bullet points.\n\n"
            f"Question: {question}\n\n"
            "Format strictly as:\n"
            f"Question: {question}\n"
            "Answer: <direct answer with clean math notation>\n\n"
            "Explanation:\n"
            "• <concise step or key point 1>\n"
            "• <concise step or key point 2>"
        )

    def _parse_ai_output(raw_output: str) -> dict:
        text_clean = clean_ai_response(raw_output)
        text_pretty = to_pretty_math(text_clean)
        if mode == "classroom":
            return {
                "hints": text_pretty,
                "short_solution": text_pretty,
                "full_solution": text_pretty,
                "solution": text_pretty,
                "is_direct_math": True
            }
        if "Explanation:" in text_pretty:
            parts = text_pretty.split("Explanation:", 1)
            short_sol = parts[0].strip()
            full_sol = text_pretty.strip()
        else:
            short_sol = text_pretty.strip()
            full_sol = text_pretty.strip()

        return {
            "hints": short_sol,
            "short_solution": short_sol,
            "full_solution": full_sol,
            "solution": full_sol if asked_explain else short_sol,
            "is_direct_math": not asked_explain
        }

    # 1. Primary: Groq (Fast sub-second response)
    if groq_key:
        for model in ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "qwen/qwen3.8-27b"]:
            try:
                resp = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                        "max_tokens": 500
                    },
                    timeout=3.0
                )
                if resp.status_code == 200:
                    text = resp.json()["choices"][0]["message"]["content"].strip()
                    parsed = _parse_ai_output(text)
                    if parsed.get("hints"):
                        return parsed
            except Exception:
                continue

    # 2. Secondary: Google Gemini models
    if gemini_key:
        models = ["gemini-flash-latest", "gemini-flash-lite-latest"]
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        for model in models:
            try:
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
                resp = requests.post(api_url, json=payload, timeout=6.0)
                if resp.status_code == 200:
                    result_json = resp.json()
                    text = result_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                    parsed = _parse_ai_output(text)
                    if parsed.get("hints"):
                        return parsed
            except Exception:
                continue

    return {}

def solve_stem_question(question: str, mode: str = "study") -> dict:
    """
    Evaluates questions with SymPy symbolic solver and AI LLM.
    Format is strictly:
    - Classroom: Answer only
    - Study (Ask AI): Question and Answer only, with Explanation ONLY if requested.
    """
    q_raw = question.strip()
    q_clean = clean_math_query(q_raw)
    x, y, z, t = sp.symbols('x y z t')
    plot_path = ""
    asked_explain = user_asked_for_explanation(q_raw)

    # 1. Instant built-in chemistry/STEM database check (0ms)
    local_ans = get_local_stem_answer(q_raw, mode=mode)
    if local_ans:
        return local_ans

    # Check question tags for calculus operations
    is_integral = any(k in q_raw.lower() for k in ['integral', 'integrate', '∫'])
    is_derivative = any(k in q_raw.lower() for k in ['derivative', 'differentiate', 'diff', 'd/dx'])
    is_limit = any(k in q_raw.lower() for k in ['limit', 'lim'])
    has_eq = '=' in q_raw and not any(k in q_raw.lower() for k in ['limit', 'as x->'])
    is_simple = is_simple_math_query(q_raw)

    # Check if graph generation is relevant
    if should_generate_graph(q_raw, q_clean):
        try:
            parsed = sp.sympify(q_clean)
            pretty_p = to_pretty_math(parsed)
            plot_path = generate_function_plot(str(parsed), title=f"Graph: f(x) = {pretty_p}")
        except Exception:
            pass

    # 2. Try Exact SymPy Symbolic Solver FIRST for all Math / Calculus / Algebra
    try:
        if is_integral:
            parsed_expr = sp.sympify(q_clean)
            result = sp.integrate(parsed_expr, x)
            pretty_p = to_pretty_math(parsed_expr)
            pretty_r = to_pretty_math(result)

            if not plot_path and should_generate_graph(q_raw, q_clean):
                plot_path = generate_function_plot(str(parsed_expr), title=f"Integrand Graph: f(x) = {pretty_p}")

            short_text = f"Question: {q_raw}\nAnswer: ∫ {pretty_p} dx = {pretty_r} + C"
            full_text = (
                f"Question: {q_raw}\n"
                f"Answer: ∫ {pretty_p} dx = {pretty_r} + C\n\n"
                f"Explanation:\n"
                f"• Use the power rule of integration: ∫ xⁿ dx = (xⁿ⁺¹)/(n+1) + C\n"
                f"• Integrate {pretty_p}: ∫ {pretty_p} dx = {pretty_r} + C"
            )

            if mode == "classroom":
                ans_text = f"Answer: ∫ {pretty_p} dx = {pretty_r} + C"
                short_text = ans_text
            else:
                ans_text = full_text if asked_explain else short_text

            return {
                "is_direct_math": not asked_explain,
                "hints": short_text,
                "short_solution": short_text,
                "full_solution": full_text,
                "solution": ans_text,
                "plot_path": plot_path
            }

        elif is_derivative:
            parsed_expr = sp.sympify(q_clean)
            result = sp.diff(parsed_expr, x)
            pretty_p = to_pretty_math(parsed_expr)
            pretty_r = to_pretty_math(result)

            if not plot_path and should_generate_graph(q_raw, q_clean):
                plot_path = generate_function_plot(str(parsed_expr), title=f"Derivative Graph: f(x) = {pretty_p}")

            short_text = f"Question: {q_raw}\nAnswer: d/dx({pretty_p}) = {pretty_r}"
            full_text = (
                f"Question: {q_raw}\n"
                f"Answer: d/dx({pretty_p}) = {pretty_r}\n\n"
                f"Explanation:\n"
                f"• Apply the power rule of differentiation: d/dx(xⁿ) = n·xⁿ⁻¹\n"
                f"• Derivative of {pretty_p}: f'(x) = {pretty_r}"
            )

            if mode == "classroom":
                ans_text = f"Answer: d/dx({pretty_p}) = {pretty_r}"
                short_text = ans_text
            else:
                ans_text = full_text if asked_explain else short_text

            return {
                "is_direct_math": not asked_explain,
                "hints": short_text,
                "short_solution": short_text,
                "full_solution": full_text,
                "solution": ans_text,
                "plot_path": plot_path
            }

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

            short_text = f"Question: {q_raw}\nAnswer: lim_{{x→{target_val}}} {pretty_p} = {pretty_r}"
            full_text = (
                f"Question: {q_raw}\n"
                f"Answer: lim_{{x→{target_val}}} {pretty_p} = {pretty_r}\n\n"
                f"Explanation:\n"
                f"• Evaluate limit of {pretty_p} as x → {target_val}\n"
                f"• Result: {pretty_r}"
            )

            if mode == "classroom":
                ans_text = f"Answer: lim_{{x→{target_val}}} {pretty_p} = {pretty_r}"
                short_text = ans_text
            else:
                ans_text = full_text if asked_explain else short_text

            return {
                "is_direct_math": not asked_explain,
                "hints": short_text,
                "short_solution": short_text,
                "full_solution": full_text,
                "solution": ans_text,
                "plot_path": plot_path
            }

        elif has_eq:
            sides = q_raw.split('=')
            lhs = sp.sympify(clean_math_query(sides[0]))
            rhs = sp.sympify(clean_math_query(sides[1]))
            eq = sp.Eq(lhs, rhs)
            free_s = list(eq.free_symbols)
            var_sym = free_s[0] if free_s else x
            sols = sp.solve(eq, var_sym)
            sol_str = ", ".join(to_pretty_math(s) for s in sols)

            short_text = f"Question: {q_raw}\nAnswer: {var_sym} = {sol_str}"
            full_text = (
                f"Question: {q_raw}\n"
                f"Answer: {var_sym} = {sol_str}\n\n"
                f"Explanation:\n"
                f"• Balance equation: {clean_math_query(sides[0])} = {clean_math_query(sides[1])}\n"
                f"• Solve for {var_sym}: {sol_str}"
            )

            if mode == "classroom":
                ans_text = f"Answer: {var_sym} = {sol_str}"
                short_text = ans_text
            else:
                ans_text = full_text if asked_explain else short_text

            return {
                "is_direct_math": not asked_explain,
                "hints": short_text,
                "short_solution": short_text,
                "full_solution": full_text,
                "solution": ans_text,
                "plot_path": plot_path
            }

        elif is_simple:
            parsed = sp.sympify(q_clean)
            simplified = sp.simplify(parsed)
            pretty_r = to_pretty_math(simplified)
            short_text = f"Question: {q_raw}\nAnswer: {pretty_r}"
            full_text = f"Question: {q_raw}\nAnswer: {pretty_r}\n\nExplanation:\n• Evaluate expression: {to_pretty_math(parsed)} = {pretty_r}"

            if mode == "classroom":
                ans_text = f"Answer: {pretty_r}"
                short_text = ans_text
            else:
                ans_text = full_text if asked_explain else short_text

            return {
                "is_direct_math": not asked_explain,
                "hints": short_text,
                "short_solution": short_text,
                "full_solution": full_text,
                "solution": ans_text,
                "plot_path": ""
            }

    except Exception:
        pass

    # 3. Fall back to LLM (Groq / Gemini) for general queries or word problems
    ai_data = get_gemini_ai_answer(q_raw, mode=mode)
    if ai_data:
        ai_data["plot_path"] = plot_path
        return ai_data

    # 4. Final safety fallback
    clean_title = re.sub(r'^(formula\s+for|what\s+is\s+the\s+formula\s+for|what\s+is|define|calculate|solve)\s+', '', q_raw, flags=re.IGNORECASE).strip().title()
    short_text = f"Question: {q_raw}\nAnswer: {clean_title or q_raw}"
    full_text = f"Question: {q_raw}\nAnswer: {clean_title or q_raw}\n\nExplanation:\n• Direct definition applies to {q_raw}"
    if mode == "classroom":
        ans_text = f"Answer: {clean_title or q_raw}"
        short_text = ans_text
    else:
        ans_text = full_text if asked_explain else short_text

    return {
        "is_direct_math": not asked_explain,
        "hints": short_text,
        "short_solution": short_text,
        "full_solution": full_text,
        "solution": ans_text,
        "plot_path": plot_path
    }

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

