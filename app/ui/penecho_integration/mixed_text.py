"""
Mixed Text & LaTeX Math Formula Parser & QGraphicsItem for AI-TUTOR.
Ported from penecho/public/mixed-text.js.

Provides:
1. Fast tokenizer for mixed Markdown (bold, italic, inline code) and LaTeX math formulas
   (both delimited: $..$, $$..$$, \\(..\\), \\[..\\] and bare TeX: \\frac, \\sqrt, \\sum, \\alpha, \\sin, etc.).
2. Balanced delimiter scanner.
3. PenechoMixedTextItem: Interactive PyQt6 QGraphicsItem rendering rich text with math
   notation, card styling, editable source on double-click, and full serialization.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsTextItem, QStyleOptionGraphicsItem,
    QWidget, QInputDialog, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QBrush, QFont, QTextDocument,
    QTextOption, QPainterPath
)
from PyQt6.QtCore import Qt, QRectF, QPointF

NAMED_TEX_COMMANDS = {
    "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta", "eta",
    "theta", "vartheta", "iota", "kappa", "lambda", "mu", "nu", "xi", "pi",
    "varpi", "rho", "varrho", "sigma", "tau", "upsilon", "phi", "varphi", "chi",
    "psi", "omega", "Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma",
    "Upsilon", "Phi", "Psi", "Omega", "sum", "prod", "coprod", "int", "iint",
    "iiint", "oint", "lim", "sin", "cos", "tan", "cot", "sec", "csc", "arcsin",
    "arccos", "arctan", "log", "ln", "exp", "min", "max", "det", "infty",
    "partial", "nabla", "forall", "exists", "neg", "pm", "mp", "times", "div",
    "cdot", "le", "leq", "ge", "geq", "ne", "neq", "approx", "equiv", "to",
    "rightarrow", "leftarrow", "Rightarrow", "Leftarrow", "leftrightarrow",
    "vec", "hat", "bar", "overline", "underline", "dot", "ddot", "mathbf",
    "mathrm", "mathit", "mathbb", "mathcal", "operatorname", "text"
}

# Unicode fallback symbols for common LaTeX expressions
TEX_UNICODE_MAP = {
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ", r"\epsilon": "ε",
    r"\zeta": "ζ", r"\eta": "η", r"\theta": "θ", r"\lambda": "λ", r"\mu": "μ",
    r"\nu": "ν", r"\xi": "ξ", r"\pi": "π", r"\rho": "ρ", r"\sigma": "σ",
    r"\tau": "τ", r"\phi": "φ", r"\chi": "χ", r"\psi": "ψ", r"\omega": "ω",
    r"\Gamma": "Γ", r"\Delta": "Δ", r"\Theta": "Θ", r"\Lambda": "Λ", r"\Pi": "Π",
    r"\Sigma": "Σ", r"\Omega": "Ω", r"\infty": "∞", r"\partial": "∂", r"\nabla": "∇",
    r"\pm": "±", r"\times": "×", r"\div": "÷", r"\cdot": "·", r"\leq": "≤",
    r"\le": "≤", r"\geq": "≥", r"\ge": "≥", r"\neq": "≠", r"\ne": "≠",
    r"\approx": "≈", r"\to": "→", r"\rightarrow": "→", r"\leftarrow": "←",
    r"\Rightarrow": "⇒", r"\sum": "∑", r"\prod": "∏", r"\int": "∫", r"\sqrt": "√",
}


def _is_escaped(source: str, index: int) -> bool:
    slashes = 0
    at = index - 1
    while at >= 0 and source[at] == "\\":
        slashes += 1
        at -= 1
    return slashes % 2 == 1


def _find_closing(source: str, marker: str, from_idx: int) -> int:
    idx = from_idx
    while True:
        idx = source.find(marker, idx)
        if idx < 0:
            return -1
        if not _is_escaped(source, idx):
            return idx
        idx += len(marker)


def _read_balanced(source: str, index: int, open_ch: str, close_ch: str) -> int:
    if index >= len(source) or source[index] != open_ch:
        return -1
    depth = 0
    for at in range(index, len(source)):
        if _is_escaped(source, at):
            continue
        if source[at] == open_ch:
            depth += 1
        elif source[at] == close_ch:
            depth -= 1
            if depth == 0:
                return at + 1
    return -1


def _read_script_target(source: str, index: int) -> int:
    if index < len(source) and source[index] == "{":
        return _read_balanced(source, index, "{", "}")
    if index < len(source) and source[index].isalnum():
        return index + 1
    return -1


def _read_scripts(source: str, index: int) -> Tuple[int, int]:
    at = index
    count = 0
    while at < len(source) and source[at] in ("_", "^"):
        end = _read_script_target(source, at + 1)
        if end < 0:
            break
        at = end
        count += 1
    return at, count


def _boundary(source: str, index: int) -> bool:
    if index < 0 or index >= len(source):
        return True
    return not (source[index].isalnum() or source[index] == "_")


def _bare_math_at(source: str, index: int) -> Optional[Dict[str, Any]]:
    if _is_escaped(source, index) or not _boundary(source, index - 1):
        return None
    end = -1
    if source.startswith(r"\frac", index):
        at = index + 5
        while at < len(source) and source[at].isspace():
            at += 1
        at = _read_balanced(source, at, "{", "}")
        if at < 0:
            return None
        while at < len(source) and source[at].isspace():
            at += 1
        end = _read_balanced(source, at, "{", "}")
    elif source.startswith(r"\sqrt", index):
        at = index + 5
        while at < len(source) and source[at].isspace():
            at += 1
        if at < len(source) and source[at] == "[":
            at = _read_balanced(source, at, "[", "]")
            if at < 0:
                return None
            while at < len(source) and source[at].isspace():
                at += 1
        end = _read_balanced(source, at, "{", "}")
    elif source[index] == "\\":
        cmd_match = re.match(r"^\\([A-Za-z]+)", source[index:])
        if not cmd_match or cmd_match.group(1) not in NAMED_TEX_COMMANDS:
            return None
        at = index + len(cmd_match.group(0))
        while at < len(source) and source[at].isspace():
            at += 1
        if at < len(source) and source[at] == "[":
            at = _read_balanced(source, at, "[", "]")
            if at < 0:
                return None
        for _ in range(4):
            if at < len(source) and source[at] == "{":
                at = _read_balanced(source, at, "{", "}")
                if at < 0:
                    return None
            else:
                break
        at, _ = _read_scripts(source, at)
        end = at
        if end < len(source) and source[end] == "(":
            grouped = _read_balanced(source, end, "(", ")")
            if grouped > 0:
                end = grouped
    elif source[index].isalpha():
        at, count = _read_scripts(source, index + 1)
        if count == 0:
            return None
        end = at

    if end < 0 or not _boundary(source, end):
        return None
    raw_tex = source[index:end]
    return {"type": "math", "tex": raw_tex, "raw": raw_tex, "end": end, "display": False}


def _explicit_math_at(source: str, index: int) -> Optional[Dict[str, Any]]:
    open_marker = None
    close_marker = None
    display = False

    if source.startswith("$$", index) and not _is_escaped(source, index):
        open_marker = close_marker = "$$"
        display = True
    elif source.startswith("$", index) and not _is_escaped(source, index):
        open_marker = close_marker = "$"
    elif source.startswith(r"\(", index) and not _is_escaped(source, index):
        open_marker = r"\("
        close_marker = r"\)"
    elif source.startswith(r"\[", index) and not _is_escaped(source, index):
        open_marker = r"\["
        close_marker = r"\]"
        display = True
    else:
        return None

    closing = _find_closing(source, close_marker, index + len(open_marker))
    if closing < 0:
        return {"type": "literal-rest", "raw": source[index:], "end": len(source)}
    
    tex = source[index + len(open_marker):closing]
    if not tex.strip():
        return {"type": "text", "text": source[index:closing + len(close_marker)], "end": closing + len(close_marker)}
    if open_marker == "$" and (tex[0].isspace() or tex[-1].isspace()):
        return None
    return {"type": "math", "tex": tex, "raw": source[index:closing + len(close_marker)], "end": closing + len(close_marker), "display": display}


def _markdown_at(source: str, index: int) -> Optional[Dict[str, Any]]:
    if _is_escaped(source, index):
        return None
    if source[index] == "`":
        closing = _find_closing(source, "`", index + 1)
        if closing < 0:
            return {"type": "literal-rest", "raw": source[index:], "end": len(source)}
        return {"type": "code", "content": source[index + 1:closing], "end": closing + 1}
    for marker, style in [("**", "bold"), ("__", "bold"), ("*", "italic"), ("_", "italic")]:
        if not source.startswith(marker, index):
            continue
        closing = _find_closing(source, marker, index + len(marker))
        if closing < 0:
            return {"type": "literal-rest", "raw": source[index:], "end": len(source)}
        content = source[index + len(marker):closing]
        end = closing + len(marker)
        if closing > index + len(marker) and _boundary(source, index - 1) and _boundary(source, end) and not content[0].isspace() and not content[-1].isspace():
            return {"type": "styled", "style": style, "content": content, "end": end}
    return None


def parse_mixed_text(source: str) -> List[Dict[str, Any]]:
    """
    Parses a string into structured mixed text tokens: text, styled (bold/italic), code, and math.
    """
    tokens = []
    index = 0
    length = len(source)
    buffer = []

    def flush():
        if buffer:
            tokens.append({"type": "text", "text": "".join(buffer)})
            buffer.clear()

    while index < length:
        exp_math = _explicit_math_at(source, index)
        if exp_math:
            flush()
            tokens.append(exp_math)
            index = exp_math["end"]
            continue

        md = _markdown_at(source, index)
        if md:
            flush()
            tokens.append(md)
            index = md["end"]
            continue

        bare_math = _bare_math_at(source, index)
        if bare_math:
            flush()
            tokens.append(bare_math)
            index = bare_math["end"]
            continue

        buffer.append(source[index])
        index += 1

    flush()
    return tokens


def mixed_tokens_to_html(tokens: List[Dict[str, Any]]) -> str:
    """
    Converts tokens into natural handwritten ink HTML for QTextDocument.
    """
    html_parts = []
    for tok in tokens:
        ttype = tok.get("type")
        if ttype == "text":
            escaped = tok.get("text", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
            html_parts.append(escaped)
        elif ttype == "styled":
            style = tok.get("style", "bold")
            content = tok.get("content", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if style == "bold":
                html_parts.append(f"<b style='font-weight: 700; color: #0f172a;'>{content}</b>")
            elif style == "italic":
                html_parts.append(f"<i>{content}</i>")
        elif ttype == "code":
            content = tok.get("content", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_parts.append(f"<span style='font-family: monospace; color: #2563eb;'>{content}</span>")
        elif ttype == "math":
            tex = tok.get("tex", "")
            # Convert known symbols to unicode
            rendered_tex = tex
            for k, v in TEX_UNICODE_MAP.items():
                rendered_tex = rendered_tex.replace(k, v)
            # Clean up TeX text macros & formatting
            rendered_tex = re.sub(r"\\text\{([^}]+)\}", r"\1", rendered_tex)
            rendered_tex = re.sub(r"\\mathrm\{([^}]+)\}", r"\1", rendered_tex)
            rendered_tex = re.sub(r"\\mathbf\{([^}]+)\}", r"<b>\1</b>", rendered_tex)
            rendered_tex = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"(\1 / \2)", rendered_tex)
            rendered_tex = re.sub(r"\\sqrt\{([^}]+)\}", r"√(\1)", rendered_tex)
            rendered_tex = re.sub(r"_\{([^}]+)\}", r"<sub>\1</sub>", rendered_tex)
            rendered_tex = re.sub(r"\^\{([^}]+)\}", r"<sup>\1</sup>", rendered_tex)
            rendered_tex = re.sub(r"_([0-9a-zA-Z])", r"<sub>\1</sub>", rendered_tex)
            rendered_tex = re.sub(r"\^([0-9a-zA-Z])", r"<sup>\1</sup>", rendered_tex)
            
            is_display = tok.get("display", False)
            if is_display:
                html_parts.append(f"<div style='text-align: center; color: #1d4ed8; margin: 6px 0; font-family: \"Segoe Print\", \"Segoe Script\", \"Cambria Math\", cursive;'>{rendered_tex}</div>")
            else:
                html_parts.append(f"<span style='color: #1d4ed8; font-family: \"Segoe Print\", \"Segoe Script\", \"Cambria Math\", cursive;'>{rendered_tex}</span>")
        elif ttype == "literal-rest":
            escaped = tok.get("raw", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
            html_parts.append(escaped)

    return "".join(html_parts)


class PenechoMixedTextItem(QGraphicsItem):
    """
    QGraphicsItem that renders handwritten ink responses and equations directly on the canvas.
    Renders with authentic handwritten typography with transparent background.
    """

    def __init__(self, raw_text: str = "", font_size: int = 17, width: float = 340.0, is_ink_mode: bool = True, parent=None):
        super().__init__(parent)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self._raw_text = raw_text or "Type text: **E = mc²**"
        self._font_size = font_size
        self._card_width = max(180.0, width)
        self._is_ink_mode = is_ink_mode
        self._text_color = QColor("#1e293b")

        self._doc = QTextDocument()
        self._update_document()

    def _update_document(self):
        from ...backend.math_engine.latex_formatter import format_math_to_html
        html_body = format_math_to_html(self._raw_text)
        html = f"""
        <div style='font-family: "Segoe Print", "Ink Free", "Caveat", "Segoe Script", "Comic Sans MS", cursive, sans-serif;
                    font-size: {self._font_size}px; line-height: 1.6; color: {self._text_color.name()};'>
            {html_body}
        </div>
        """
        font = QFont("Segoe Print", self._font_size)
        font.setStyleHint(QFont.StyleHint.Cursive)
        self._doc.setDefaultFont(font)
        self._doc.setTextWidth(self._card_width)
        self._doc.setHtml(html)

    def boundingRect(self) -> QRectF:
        doc_height = self._doc.size().height()
        return QRectF(0, 0, self._card_width, max(40.0, doc_height + 10))

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.boundingRect()

        # When selected or hovered, show subtle natural dashed ink guide
        if self.isSelected():
            path = QPainterPath()
            path.addRoundedRect(rect.adjusted(-4, -4, 4, 4), 6, 6)
            painter.setPen(QPen(QColor(59, 130, 246, 160), 1.2, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(QColor(59, 130, 246, 12)))
            painter.drawPath(path)

        # Render handwritten document content directly on canvas
        self._doc.drawContents(painter, QRectF(0, 0, self._card_width, rect.height()))

        painter.restore()

    def mouseDoubleClickEvent(self, event):
        new_text, ok = QInputDialog.getMultiLineText(
            None,
            "Edit Mixed Text & LaTeX",
            "Enter Markdown & LaTeX (e.g. $f(x) = \\frac{1}{x}$, **bold**, `code`):",
            self._raw_text
        )
        if ok and new_text.strip():
            self.prepareGeometryChange()
            self._raw_text = new_text
            self._update_document()
            self.update()
        event.accept()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "PenechoMixedTextItem",
            "x": self.pos().x(),
            "y": self.pos().y(),
            "z_value": self.zValue(),
            "raw_text": self._raw_text,
            "font_size": self._font_size,
            "card_width": self._card_width
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PenechoMixedTextItem":
        item = cls(
            raw_text=data.get("raw_text", ""),
            font_size=int(data.get("font_size", 15)),
            width=float(data.get("card_width", 320.0))
        )
        return item
