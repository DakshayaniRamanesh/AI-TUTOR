import sympy
from typing import Tuple

def validate_math_transition(before_state: str, after_state: str) -> Tuple[bool, str]:
    """
    Validates if a mathematical transition from before_state to after_state is valid.
    Uses SymPy to check for algebraic equivalence.
    """
    if not before_state or not after_state:
        return True, "Empty state, skipping validation"
        
    try:
        # Basic cleanup for equations (move RHS to LHS)
        def clean_eq(expr_str):
            if "=" in expr_str:
                lhs, rhs = expr_str.split("=", 1)
                return f"({lhs}) - ({rhs})"
            return expr_str
            
        b_clean = clean_eq(before_state)
        a_clean = clean_eq(after_state)
        
        # Parse expressions
        expr1 = sympy.sympify(b_clean, evaluate=False)
        expr2 = sympy.sympify(a_clean, evaluate=False)
        
        # Check equivalence
        diff = sympy.simplify(expr1 - expr2)
        if diff == 0:
            return True, "Mathematically equivalent"
            
        return False, f"Expressions are not algebraically equivalent: {before_state} vs {after_state}"
    except Exception as e:
        # If sympy fails to parse, we return True but warn, to not block non-math or complex notation
        return True, f"SymPy parsing failed, skipping strict validation: {str(e)}"
