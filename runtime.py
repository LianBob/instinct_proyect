# runtime.py
from __future__ import annotations

from typing import Any, Protocol

from parser import (
    Action,
    Assign,
    Binary,
    Call,
    CreatureProgram,
    Expr,
    Goto,
    IfGoto,
    Label,
    Number,
    String,
    Unary,
    Var,
    CONSTANTS,
    FUNCTIONS,
    PERCEPTIONS,
)


class InstinctRuntimeError(Exception):
    def __init__(self, line: int, message: str):
        super().__init__(f"Línea {line}: {message}")
        self.line = line
        self.message = message


class WorldContext(Protocol):
    """Interfaz que el simulador debe implementar para darle mundo a las criaturas."""

    def get_perception(self, name: str) -> Any:
        """Devuelve el valor actual de una percepción (health, enemy_dx, random, ...)."""
        ...

    def call_function(self, name: str, args: list[Any]) -> Any:
        """Ejecuta see(x, y) o name(x, y)."""
        ...

    def do_action(self, name: str, args: list[Any]) -> None:
        """Aplica el efecto de wait/move/attack/consume/reproduce/roar/say."""
        ...


def _truthy(value: Any) -> bool:
    if type(value) is int:
        return value != 0
    if type(value) is str:
        return value != ""
    return True


class CreatureRuntime:
    def __init__(self, program: CreatureProgram, context: WorldContext):
        self.program = program
        self.context = context
        self.env: dict[str, Any] = {}
        self.pc: int = program.labels["start"]
        self.sleep_turns: int = 0

    # --------------------------------------------------------
    # Bucle de turno
    # --------------------------------------------------------

    def run_turn(self) -> str:
        if self.sleep_turns > 0:
            self.sleep_turns -= 1
            return "sleeping"

        executed = 0

        while executed < 100:
            if self.pc >= len(self.program.statements):
                self.pc = self.program.labels["start"]
                return "end"

            stmt = self.program.statements[self.pc]
            executed += 1

            if isinstance(stmt, Label):
                self.pc += 1
                continue

            if isinstance(stmt, Goto):
                self.pc = self.program.labels[stmt.target]
                continue

            if isinstance(stmt, IfGoto):
                if _truthy(self.eval_expr(stmt.cond)):
                    self.pc = self.program.labels[stmt.target]
                else:
                    self.pc += 1
                continue

            if isinstance(stmt, Assign):
                self.env[stmt.name] = self.eval_expr(stmt.value)
                self.pc += 1
                continue

            if isinstance(stmt, Action):
                consumes = self._exec_action(stmt)
                self.pc += 1
                if consumes:
                    if self.pc >= len(self.program.statements):
                        self.pc = self.program.labels["start"]
                    return "action"
                continue

            raise InstinctRuntimeError(
                getattr(stmt, "line", 1), "Sentencia desconocida"
            )

        return "limit"

    # --------------------------------------------------------
    # Acciones
    # --------------------------------------------------------

    def _exec_action(self, stmt: Action) -> bool:
        args = [self.eval_expr(a) for a in stmt.args]
        name = stmt.name

        if name == "wait":
            n = self._need_int(args[0], stmt.line, "wait(n)")
            self.context.do_action(name, args)
            self.sleep_turns = max(1, n) - 1
            return True

        if name in ("move", "attack", "consume", "reproduce"):
            dx = self._need_int(args[0], stmt.line, f"{name}(dx, ...)")
            dy = self._need_int(args[1], stmt.line, f"{name}(dx, dy, ...)")

            if dx not in (-1, 0, 1) or dy not in (-1, 0, 1):
                raise InstinctRuntimeError(
                    stmt.line, "dx y dy deben estar en {-1, 0, 1}"
                )

            if name == "move":
                self._need_int(args[2], stmt.line, "move(..., speed)")
            elif name == "attack":
                self._need_int(args[2], stmt.line, "attack(..., damage)")
            elif name == "consume":
                self._need_int(args[2], stmt.line, "consume(..., damage, ...)")
                self._need_int(args[3], stmt.line, "consume(..., ..., heal)")
            elif name == "reproduce":
                self._need_int(args[2], stmt.line, "reproduce(..., health)")

        self.context.do_action(name, args)
        return name != "say"

    @staticmethod
    def _need_int(value: Any, line: int, what: str) -> int:
        if type(value) is not int:
            raise InstinctRuntimeError(
                line, f"{what} espera un entero, recibió {value!r}"
            )
        return value

    # --------------------------------------------------------
    # Evaluador de expresiones
    # --------------------------------------------------------

    def eval_expr(self, expr: Expr) -> Any:
        if isinstance(expr, Number):
            return expr.value

        if isinstance(expr, String):
            return expr.value

        if isinstance(expr, Var):
            if expr.name in self.env:
                return self.env[expr.name]
            if expr.name in PERCEPTIONS:
                return self.context.get_perception(expr.name)
            if expr.name in CONSTANTS:
                return CONSTANTS[expr.name]
            raise InstinctRuntimeError(
                expr.line, f"Variable no asignada: {expr.name}"
            )

        if isinstance(expr, Unary):
            value = self.eval_expr(expr.expr)
            if expr.op == "-":
                if type(value) is not int:
                    raise InstinctRuntimeError(
                        expr.line, "El menos unario espera un entero"
                    )
                return -value
            if expr.op == "not":
                return 0 if _truthy(value) else 1
            raise InstinctRuntimeError(
                expr.line, f"Operador unario desconocido: {expr.op}"
            )

        if isinstance(expr, Binary):
            op = expr.op

            if op == "and":
                left = self.eval_expr(expr.left)
                if not _truthy(left):
                    return 0
                return 1 if _truthy(self.eval_expr(expr.right)) else 0

            if op == "or":
                left = self.eval_expr(expr.left)
                if _truthy(left):
                    return 1
                return 1 if _truthy(self.eval_expr(expr.right)) else 0

            left = self.eval_expr(expr.left)
            right = self.eval_expr(expr.right)

            if op in ("==", "!="):
                if type(left) is not type(right):
                    raise InstinctRuntimeError(
                        expr.line, "Comparación entre tipos distintos"
                    )
                eq = left == right
                return int(eq if op == "==" else not eq)

            if op in ("<", "<=", ">", ">="):
                if type(left) is not int or type(right) is not int:
                    raise InstinctRuntimeError(
                        expr.line,
                        "Las comparaciones de orden solo aceptan enteros",
                    )
                if op == "<":
                    return int(left < right)
                if op == "<=":
                    return int(left <= right)
                if op == ">":
                    return int(left > right)
                return int(left >= right)

            if op in ("+", "-", "*", "/", "%"):
                if type(left) is not int or type(right) is not int:
                    raise InstinctRuntimeError(
                        expr.line, "La aritmética solo acepta enteros"
                    )
                if op == "+":
                    return left + right
                if op == "-":
                    return left - right
                if op == "*":
                    return left * right
                if op == "/":
                    if right == 0:
                        raise InstinctRuntimeError(
                            expr.line, "División por cero"
                        )
                    return left // right
                if right == 0:
                    raise InstinctRuntimeError(expr.line, "Módulo por cero")
                return left % right

            raise InstinctRuntimeError(
                expr.line, f"Operador desconocido: {op}"
            )

        if isinstance(expr, Call):
            if expr.name not in FUNCTIONS:
                raise InstinctRuntimeError(
                    expr.line, f"Función desconocida: {expr.name}"
                )
            args = [self.eval_expr(a) for a in expr.args]
            for arg in args:
                if type(arg) is not int:
                    raise InstinctRuntimeError(
                        expr.line,
                        f"{expr.name} espera argumentos enteros",
                    )
            return self.context.call_function(expr.name, args)

        raise InstinctRuntimeError(
            getattr(expr, "line", 1), "Expresión desconocida"
        )