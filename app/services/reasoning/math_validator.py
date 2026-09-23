import sympy
from shared.contracts.reasoning import ValidationResult, ValidationVerdict
from app.services.reasoning.math_parser import ParsedMath

def validate_transition(previous: ParsedMath, current: ParsedMath, step_id: str = "dummy_id") -> ValidationResult:
    if not previous.is_valid or not current.is_valid:
        return ValidationResult(
            step_id=step_id,
            verdict=ValidationVerdict.UNKNOWN,
            explanation="One or both expressions could not be parsed safely."
        )

    try:
        # Both are pure expressions
        if not previous.is_equation and not current.is_equation:
            diff = sympy.simplify(previous.expr - current.expr)
            if diff == 0:
                return ValidationResult(step_id=step_id, verdict=ValidationVerdict.VALID, explanation="Expressions are equivalent.")
            return ValidationResult(step_id=step_id, verdict=ValidationVerdict.INVALID, explanation="Expressions are not equivalent.")

        # Both are equations
        if previous.is_equation and current.is_equation:
            # Reconstruct Eq objects to be safe
            eq_prev = sympy.Eq(previous.lhs, previous.rhs)
            eq_curr = sympy.Eq(current.lhs, current.rhs)
            
            # Numeric statements without variables (e.g. 4 = 4)
            symbols_prev = eq_prev.free_symbols
            symbols_curr = eq_curr.free_symbols
            all_symbols = symbols_prev.union(symbols_curr)
            
            if len(all_symbols) == 0:
                if eq_prev == eq_curr or (sympy.simplify(previous.lhs - previous.rhs) == 0 and sympy.simplify(current.lhs - current.rhs) == 0):
                    return ValidationResult(step_id=step_id, verdict=ValidationVerdict.VALID, explanation="Numeric statements are equivalent.")
                return ValidationResult(step_id=step_id, verdict=ValidationVerdict.INVALID, explanation="Numeric statements are not equivalent.")

            # Single variable equations
            if len(all_symbols) == 1:
                var = list(all_symbols)[0]
                sol_prev = sympy.solveset(eq_prev, var, domain=sympy.S.Reals)
                sol_curr = sympy.solveset(eq_curr, var, domain=sympy.S.Reals)
                
                if sol_prev == sol_curr:
                    return ValidationResult(step_id=step_id, verdict=ValidationVerdict.VALID, explanation="Solution sets are identical.")
                else:
                    return ValidationResult(
                        step_id=step_id,
                        verdict=ValidationVerdict.INVALID, 
                        explanation=f"Solution sets differ. Previous: {sol_prev}, Current: {sol_curr}"
                    )
            
            return ValidationResult(
                step_id=step_id,
                verdict=ValidationVerdict.UNKNOWN, 
                explanation="Multi-variable equations are not fully supported yet."
            )

        # Mismatch (expression vs equation)
        return ValidationResult(
            step_id=step_id,
            verdict=ValidationVerdict.INVALID,
            explanation="Cannot compare an expression directly to an equation."
        )

    except NotImplementedError:
        return ValidationResult(step_id=step_id, verdict=ValidationVerdict.UNKNOWN, explanation="SymPy cannot solve this equation.")
    except Exception as e:
        return ValidationResult(step_id=step_id, verdict=ValidationVerdict.UNKNOWN, explanation=f"Validation failed: {str(e)}")
