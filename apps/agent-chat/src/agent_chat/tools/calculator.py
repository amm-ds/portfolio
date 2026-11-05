"""A locked-down arithmetic calculator (the typed-args tool example).

Same AST-evaluator pattern as project 09's research-ops toolset: only numeric
literals and arithmetic operators survive parsing — names, calls, and
attribute access are rejected. Malformed input raises ``ModelRetry`` so the
agent is re-asked with the error instead of crashing the run.
"""

import ast
import operator
from typing import Any

from pydantic_ai import ModelRetry

_BIN_OPS: dict[type[ast.operator], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_UNARY_OPS: dict[type[ast.unaryop], Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def calculator(expr: str) -> float:
    """Evaluate a basic arithmetic expression (+ - * / ** % and parentheses).

    Only numeric literals and arithmetic operators are allowed; anything else
    (names, calls, attribute access) is rejected.

    Args:
        expr: Arithmetic expression, e.g. "(2400 + 380) / 7".

    Returns:
        The numeric result, rounded to 6 decimals.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ModelRetry(f"the expression could not be parsed: {exc.msg}") from exc

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            left, right = _eval(node.left), _eval(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 64:
                raise ModelRetry("the exponent is too large; compute a smaller power")
            return float(_BIN_OPS[type(node.op)](left, right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return float(_UNARY_OPS[type(node.op)](_eval(node.operand)))
        raise ModelRetry(f"unsupported expression element: {ast.dump(node)}")

    return round(_eval(tree), 6)
