#done
import ast
import heapq
import logging
import math
import operator
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict
from typing import Callable, List, Sequence, Tuple
from default_values import (
    asc_penalty_expr,
    desc_penalty_expr,
    flat_penalty_expr,

    continuous_asc_penalty_expr,
    continuous_desc_penalty_expr,
    continuous_flat_penalty_expr ,

    terrain_roughnes_penalty_expr,
    thermal_swing_risk_penalty_expr,
    obstacle_density_penalty_expr,
    terrain_type_IR_based_penalty_expr
)

import numpy as np
EXPRESSION_MAX_LENGTH = 256
EXPRESSION_MAX_NODES = 50
EXPRESSION_MAX_EXPONENT = 10.0


BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}

UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

FUNCTIONS: Dict[str, Callable] = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "sqrt": math.sqrt,
    "log": math.log,
    "exp": math.exp,
    "abs": abs,
    "min": min,
    "max": max,
}


def _evaluate_node(node: ast.AST, x: float) -> float:
    """Recursively evaluate one whitelisted AST node with variable ``x``."""
    if isinstance(node, ast.Constant):
        if type(node.value) not in (int, float):
            raise ValueError("Only numeric constants allowed")
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id != "x":
            raise ValueError(f"Unknown variable: {node.id!r}")
        return float(x)
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in BINARY_OPERATORS:
            raise ValueError("Operator not allowed")
        left = _evaluate_node(node.left, x)
        right = _evaluate_node(node.right, x)
        if not math.isfinite(left) or not math.isfinite(right):
            raise ValueError("Non-finite operand")
        if op_type is ast.Pow and abs(right) > EXPRESSION_MAX_EXPONENT:
            raise ValueError("Exponent too large")
        if op_type is ast.Div and right == 0.0:
            raise ValueError("Division by zero")
        try:
            result = BINARY_OPERATORS[op_type](left, right)
        except (ArithmeticError, ValueError) as exc:
            raise ValueError(f"Arithmetic error: {exc}") from exc
        if not math.isfinite(result):
            raise ValueError("Non-finite result")
        return float(result)
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in UNARY_OPERATORS:
            raise ValueError("Unary operator not allowed")
        return float(UNARY_OPERATORS[op_type](_evaluate_node(node.operand, x)))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Invalid function")
        name = node.func.id
        if name not in FUNCTIONS or node.keywords:
            raise ValueError("Function not allowed")
        args = [_evaluate_node(arg, x) for arg in node.args]
        try:
            result = FUNCTIONS[name](*args)
        except (ArithmeticError, ValueError, TypeError) as exc:
            raise ValueError(f"Function error: {exc}") from exc
        if not math.isfinite(result):
            raise ValueError("Non-finite result")
        return float(result)
    raise ValueError("Invalid expression")


def compile_expression(expression: str) -> Callable[[float], float]:
    """Compile a scalar penalty expression ``f(x)`` into a hardened callable.

    Only the variable ``x``, numeric constants, ``+ - * / **`` and the
    whitelisted math helpers (sin/cos/tan/sqrt/log/exp/abs/min/max) are
    allowed. The returned function rejects NaN/inf inputs, negative
    penalties and unreasonably large outputs.
    """
    if not isinstance(expression, str):
        raise TypeError("Expression must be a string")
    if not expression.strip():
        raise ValueError("Expression must not be empty")
    if len(expression) > EXPRESSION_MAX_LENGTH:
        raise ValueError("Expression too long")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid syntax: {exc}") from exc
    if len(list(ast.walk(tree))) > EXPRESSION_MAX_NODES:
        raise ValueError("Expression too complex")
    body = tree.body

    def function(x: float) -> float:
        try:
            value = float(x)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid input: {exc}") from exc
        if not math.isfinite(value):
            raise ValueError("Non-finite input")
        result = _evaluate_node(body, value)
        if not math.isfinite(result):
            raise ValueError("Non-finite result")
        if result < 0.0:
            raise ValueError("Negative penalty")
        if result > MAX_REASONABLE_PENALTY:
            raise ValueError("Penalty unreasonably large")
        return float(result)

    return function


asc_penalty_func = compile_expression(asc_penalty_expr)
desc_penalty_func = compile_expression(desc_penalty_expr)
flat_penalty_func = compile_expression(flat_penalty_expr)

continuous_asc_penalty_func = compile_expression(continuous_asc_penalty_expr)
continuous_desc_penalty_func = compile_expression(continuous_desc_penalty_expr)
continuous_flat_penalty_func = compile_expression(continuous_flat_penalty_expr)

terrain_roughnes_penalty_func = compile_expression(terrain_roughnes_penalty_expr)
thermal_swing_risk_penalty_func = compile_expression(
    thermal_swing_risk_penalty_expr
)
obstacle_density_penalty_func = compile_expression(obstacle_density_penalty_expr)
terrain_type_IR_based_penalty_func = compile_expression(
    terrain_type_IR_based_penalty_expr
)
