"""
Calculus and Algebra Math Reference Formulas & Tables
"""

TRIG_VALUES = [
    {"angle_deg": "0°", "angle_rad": "0", "sin": "0", "cos": "1", "tan": "0"},
    {"angle_deg": "30°", "angle_rad": "π/6", "sin": "1/2", "cos": "√3/2", "tan": "1/√3"},
    {"angle_deg": "45°", "angle_rad": "π/4", "sin": "√2/2", "cos": "√2/2", "tan": "1"},
    {"angle_deg": "60°", "angle_rad": "π/3", "sin": "√3/2", "cos": "1/2", "tan": "√3"},
    {"angle_deg": "90°", "angle_rad": "π/2", "sin": "1", "cos": "0", "tan": "Undefined"},
    {"angle_deg": "180°", "angle_rad": "π", "sin": "0", "cos": "-1", "tan": "0"},
    {"angle_deg": "270°", "angle_rad": "3π/2", "sin": "-1", "cos": "0", "tan": "Undefined"},
    {"angle_deg": "360°", "angle_rad": "2π", "sin": "0", "cos": "1", "tan": "0"},
]

DERIVATIVE_FORMULAS = [
    {"function": "c (constant)", "derivative": "0"},
    {"function": "x^n", "derivative": "n * x^(n-1)"},
    {"function": "e^x", "derivative": "e^x"},
    {"function": "a^x", "derivative": "a^x * ln(a)"},
    {"function": "ln(x)", "derivative": "1/x"},
    {"function": "sin(x)", "derivative": "cos(x)"},
    {"function": "cos(x)", "derivative": "-sin(x)"},
    {"function": "tan(x)", "derivative": "sec^2(x)"},
    {"function": "arctan(x)", "derivative": "1 / (1 + x^2)"},
    {"function": "Product Rule (u*v)", "derivative": "u'*v + u*v'"},
    {"function": "Quotient Rule (u/v)", "derivative": "(u'*v - u*v') / v^2"},
    {"function": "Chain Rule f(g(x))", "derivative": "f'(g(x)) * g'(x)"},
]

INTEGRAL_FORMULAS = [
    {"integrand": "x^n (n ≠ -1)", "integral": "x^(n+1) / (n+1) + C"},
    {"integrand": "1/x", "integral": "ln|x| + C"},
    {"integrand": "e^x", "integral": "e^x + C"},
    {"integrand": "sin(x)", "integral": "-cos(x) + C"},
    {"integrand": "cos(x)", "integral": "sin(x) + C"},
    {"integrand": "sec^2(x)", "integral": "tan(x) + C"},
    {"integrand": "1 / (1 + x^2)", "integral": "arctan(x) + C"},
    {"integrand": "1 / √(1 - x^2)", "integral": "arcsin(x) + C"},
    {"integrand": "Integration by Parts ∫u dv", "integral": "u*v - ∫v du"},
]
