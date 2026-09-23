from app.services.reasoning.math_parser import parse_math
from app.services.reasoning.math_validator import validate_transition
from shared.contracts.reasoning import ValidationVerdict

def test_validate_equivalent_expressions():
    prev = parse_math("2x + 6")
    curr = parse_math("2*(x + 3)")
    res = validate_transition(prev, curr)
    assert res.verdict == ValidationVerdict.VALID

def test_validate_non_equivalent_expressions():
    prev = parse_math("2x + 6")
    curr = parse_math("2x + 5")
    res = validate_transition(prev, curr)
    assert res.verdict == ValidationVerdict.INVALID

def test_validate_equivalent_equations():
    prev = parse_math("2x = 4")
    curr = parse_math("x = 2")
    res = validate_transition(prev, curr)
    assert res.verdict == ValidationVerdict.VALID

def test_validate_incorrect_equation_step():
    prev = parse_math("2x = 4")
    curr = parse_math("x = 3")
    res = validate_transition(prev, curr)
    assert res.verdict == ValidationVerdict.INVALID

def test_validate_parser_failure():
    prev = parse_math("2x = 4")
    curr = parse_math("x = = = 2")
    res = validate_transition(prev, curr)
    assert res.verdict == ValidationVerdict.UNKNOWN

def test_validate_squaring_both_sides_extraneous():
    # x = 3 -> solution set {3}
    # x^2 = 9 -> solution set {-3, 3}
    # Because the sets are not identical, it correctly flags it as invalid.
    prev = parse_math("x = 3")
    curr = parse_math("x^2 = 9")
    res = validate_transition(prev, curr)
    assert res.verdict == ValidationVerdict.INVALID

def test_validate_multivariable_unknown():
    prev = parse_math("x + y = 2")
    curr = parse_math("x = 2 - y")
    res = validate_transition(prev, curr)
    assert res.verdict == ValidationVerdict.UNKNOWN
