import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
from pydantic import BaseModel, ConfigDict
from typing import Optional, Any

class ParsedMath(BaseModel):
    is_valid: bool
    is_equation: bool = False
    lhs: Optional[Any] = None  # SymPy AST
    rhs: Optional[Any] = None  # SymPy AST
    expr: Optional[Any] = None # SymPy AST (for pure expressions)
    raw_text: str
    error_message: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

def parse_math(text: str) -> ParsedMath:
    if not text or not text.strip():
        return ParsedMath(is_valid=False, raw_text=text, error_message="Empty input")

    clean_text = text.strip()
    
    # Safe transformations: handle implicit multiplication (2x -> 2*x) and ^ for exponents
    transformations = standard_transformations + (implicit_multiplication_application,)
    
    # Restrict evaluation dictionary to prevent code injection
    # We must explicitly remove __builtins__ to prevent eval() from falling back to Python builtins
    safe_global = {k: v for k, v in sympy.__dict__.items() if not k.startswith("_")}
    safe_global["__builtins__"] = {}
    safe_local = {"E": sympy.E, "pi": sympy.pi}
    
    try:
        if "=" in clean_text:
            parts = clean_text.split("=")
            if len(parts) != 2:
                return ParsedMath(is_valid=False, raw_text=text, error_message="Multiple or malformed equals signs")
            
            lhs_ast = parse_expr(parts[0].strip(), local_dict=safe_local, global_dict=safe_global, transformations=transformations, evaluate=False)
            rhs_ast = parse_expr(parts[1].strip(), local_dict=safe_local, global_dict=safe_global, transformations=transformations, evaluate=False)
            
            return ParsedMath(
                is_valid=True,
                is_equation=True,
                lhs=lhs_ast,
                rhs=rhs_ast,
                raw_text=text
            )
        else:
            expr_ast = parse_expr(clean_text, local_dict=safe_local, global_dict=safe_global, transformations=transformations, evaluate=False)
            return ParsedMath(
                is_valid=True,
                is_equation=False,
                expr=expr_ast,
                raw_text=text
            )
    except Exception as e:
        return ParsedMath(is_valid=False, raw_text=text, error_message=str(e))
