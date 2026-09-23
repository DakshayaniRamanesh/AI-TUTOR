from app.services.reasoning.math_parser import parse_math
import sympy

def test_parse_expression_implicit_mul():
    result = parse_math("2x + 6")
    assert result.is_valid is True
    assert result.is_equation is False
    assert result.expr == sympy.parse_expr("2*x + 6", evaluate=False)

def test_parse_equation():
    result = parse_math("2x = 4")
    assert result.is_valid is True
    assert result.is_equation is True
    assert result.lhs == sympy.parse_expr("2*x", evaluate=False)
    assert result.rhs == sympy.parse_expr("4", evaluate=False)

def test_parse_malformed():
    result = parse_math("2x = = 4")
    assert result.is_valid is False
    assert "Multiple or malformed" in result.error_message

def test_parse_injection_protection():
    result = parse_math("__import__('os').system('ls')")
    assert result.is_valid is False
