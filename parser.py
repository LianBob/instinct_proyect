# parser.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lexer import Token, TokenType, CompileError, tokenize


# ============================================================
# 1. AST
# ============================================================

@dataclass
class Expr:
    line: int


@dataclass
class Number(Expr):
    value: int


@dataclass
class String(Expr):
    value: str


@dataclass
class Var(Expr):
    name: str


@dataclass
class Call(Expr):
    name: str
    args: list[Expr]


@dataclass
class Unary(Expr):
    op: str
    expr: Expr


@dataclass
class Binary(Expr):
    left: Expr
    op: str
    right: Expr


@dataclass
class Stmt:
    line: int


@dataclass
class Label(Stmt):
    name: str


@dataclass
class Goto(Stmt):
    target: str


@dataclass
class IfGoto(Stmt):
    cond: Expr
    target: str


@dataclass
class Assign(Stmt):
    name: str
    value: Expr


@dataclass
class Action(Stmt):
    name: str
    args: list[Expr]


@dataclass
class CreatureProgram:
    name: str
    faction: str
    health: int
    vision: int
    lifespan: int
    statements: list[Stmt] = field(default_factory=list)
    labels: dict[str, int] = field(default_factory=dict)


# ============================================================
# 2. CATÁLOGO BÁSICO (lo que el validador necesita conocer)
# ============================================================

ACTIONS: dict[str, int] = {
    "wait": 1,
    "move": 3,
    "attack": 3,
    "consume": 4,
    "reproduce": 3,
    "roar": 1,
    "say": 1,
}

FUNCTIONS: dict[str, int] = {
    "see": 2,
    "name": 2,
}

CONSTANTS: dict[str, int] = {
    "NONE": -1,
    "GROUND": 0,
    "OBJECT": 1,
    "ALLY": 2,
    "ENEMY": 3,
}

PERCEPTIONS: set[str] = {
    "health", "age", "lifespan", "vision", "species", "faction",
    "x", "y", "terrain_here", "reserve_here",
    "width", "height", "tick",
    "total_creatures", "total_allies", "total_enemies",
    "random",
    "allies_near", "enemies_near", "objects_near",
    "enemy_dist", "enemy_dx", "enemy_dy",
    "ally_dist", "ally_dx", "ally_dy",
    "object_dist", "object_dx", "object_dy",
    "roars_near", "last_roar",
}


# ============================================================
# 3. PARSER
# ============================================================

class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def advance(self) -> Token:
        tok = self.peek()
        if tok.type != TokenType.EOF:
            self.pos += 1
        return tok

    def check(self, tipo: TokenType) -> bool:
        return self.peek().type == tipo

    def match(self, *tipos: TokenType) -> Token | None:
        if self.peek().type in tipos:
            return self.advance()
        return None

    def expect(self, tipo: TokenType, mensaje: str | None = None) -> Token:
        if not self.check(tipo):
            tok = self.peek()
            raise CompileError(
                tok.line,
                mensaje or f"Se esperaba {tipo.name}, se encontró {tok.type.name}",
            )
        return self.advance()

    def skip_newlines(self) -> None:
        while self.match(TokenType.NEWLINE):
            pass

    # ---------- expresiones ----------

    def parse_expression(self) -> Expr:
        return self.parse_or()

    def parse_or(self) -> Expr:
        expr = self.parse_and()
        while (tok := self.match(TokenType.OR)) is not None:
            right = self.parse_and()
            expr = Binary(tok.line, expr, "or", right)
        return expr

    def parse_and(self) -> Expr:
        expr = self.parse_comparison()
        while (tok := self.match(TokenType.AND)) is not None:
            right = self.parse_comparison()
            expr = Binary(tok.line, expr, "and", right)
        return expr

    def parse_comparison(self) -> Expr:
        expr = self.parse_additive()
        while self.peek().type in (
            TokenType.LESS,
            TokenType.LESS_EQUAL,
            TokenType.GREATER,
            TokenType.GREATER_EQUAL,
            TokenType.EQUAL_EQUAL,
            TokenType.DISTINCT_EQUAL,
        ):
            op = self.advance()
            right = self.parse_additive()
            expr = Binary(op.line, expr, op.literal, right)
        return expr

    def parse_additive(self) -> Expr:
        expr = self.parse_multiplicative()
        while self.peek().type in (TokenType.PLUS, TokenType.MINUS):
            op = self.advance()
            right = self.parse_multiplicative()
            expr = Binary(op.line, expr, op.literal, right)
        return expr

    def parse_multiplicative(self) -> Expr:
        expr = self.parse_unary()
        while self.peek().type in (
            TokenType.STAR,
            TokenType.SLASH,
            TokenType.MODULO,
        ):
            op = self.advance()
            right = self.parse_unary()
            expr = Binary(op.line, expr, op.literal, right)
        return expr

    def parse_unary(self) -> Expr:
        if (tok := self.match(TokenType.MINUS)) is not None:
            return Unary(tok.line, "-", self.parse_unary())
        if (tok := self.match(TokenType.NOT)) is not None:
            return Unary(tok.line, "not", self.parse_unary())
        return self.parse_primary()

    def parse_primary(self) -> Expr:
        tok = self.advance()

        if tok.type == TokenType.NUMBER:
            return Number(tok.line, int(tok.literal))

        if tok.type == TokenType.STRING:
            return String(tok.line, tok.literal)

        if tok.type == TokenType.IDENTIFIER:
            if self.match(TokenType.LEFT_PAREN):
                args: list[Expr] = []
                if not self.check(TokenType.RIGHT_PAREN):
                    args.append(self.parse_expression())
                    while self.match(TokenType.COMMA):
                        args.append(self.parse_expression())
                self.expect(TokenType.RIGHT_PAREN, "Se esperaba ')'")
                return Call(tok.line, tok.literal, args)
            return Var(tok.line, tok.literal)

        if tok.type == TokenType.LEFT_PAREN:
            expr = self.parse_expression()
            self.expect(TokenType.RIGHT_PAREN, "Se esperaba ')'")
            return expr

        raise CompileError(tok.line, f"Expresión inválida: {tok.literal!r}")


# ============================================================
# 4. PARSER DE SENTENCIAS
# ============================================================

def parse_statement(p: Parser) -> Stmt:
    tok = p.peek()

    if tok.type == TokenType.IF:
        p.advance()
        cond = p.parse_expression()
        p.expect(TokenType.GOTO, "Se esperaba 'goto'")
        target = p.expect(TokenType.IDENTIFIER, "Se esperaba etiqueta")
        p.expect(TokenType.NEWLINE, "Se esperaba fin de línea")
        return IfGoto(tok.line, cond, target.literal)

    if tok.type == TokenType.GOTO:
        p.advance()
        target = p.expect(TokenType.IDENTIFIER, "Se esperaba etiqueta")
        p.expect(TokenType.NEWLINE, "Se esperaba fin de línea")
        return Goto(tok.line, target.literal)

    if tok.type == TokenType.IDENTIFIER:
        nxt = p.peek(1)

        if nxt.type == TokenType.COLON:
            name = p.advance().literal
            p.expect(TokenType.COLON)
            p.expect(TokenType.NEWLINE, "Se esperaba fin de línea")
            return Label(tok.line, name)

        if nxt.type == TokenType.EQUAL:
            name = p.advance().literal
            p.expect(TokenType.EQUAL)
            value = p.parse_expression()
            p.expect(TokenType.NEWLINE, "Se esperaba fin de línea")
            return Assign(tok.line, name, value)

        if nxt.type == TokenType.LEFT_PAREN:
            name = p.advance().literal
            p.expect(TokenType.LEFT_PAREN)
            args: list[Expr] = []
            if not p.check(TokenType.RIGHT_PAREN):
                args.append(p.parse_expression())
                while p.match(TokenType.COMMA):
                    args.append(p.parse_expression())
            p.expect(TokenType.RIGHT_PAREN, "Se esperaba ')'")
            p.expect(TokenType.NEWLINE, "Se esperaba fin de línea")
            return Action(tok.line, name, args)

    raise CompileError(tok.line, f"Línea no válida: {tok.literal!r}")


# ============================================================
# 5. VALIDACIÓN SEMÁNTICA
# ============================================================

def _validate_expr(expr: Expr) -> None:
    if isinstance(expr, Call):
        if expr.name not in FUNCTIONS:
            raise CompileError(expr.line, f"Función desconocida: {expr.name}")
        esperado = FUNCTIONS[expr.name]
        if len(expr.args) != esperado:
            raise CompileError(
                expr.line,
                f"{expr.name} espera {esperado} argumentos, recibió {len(expr.args)}",
            )
        for a in expr.args:
            _validate_expr(a)

    elif isinstance(expr, Unary):
        _validate_expr(expr.expr)

    elif isinstance(expr, Binary):
        _validate_expr(expr.left)
        _validate_expr(expr.right)


def _validate_program(program: CreatureProgram) -> None:
    labels: dict[str, int] = {}

    for i, stmt in enumerate(program.statements):
        if isinstance(stmt, Label):
            if stmt.name in labels:
                raise CompileError(stmt.line, f"Etiqueta duplicada: {stmt.name}")
            labels[stmt.name] = i

    if "start" not in labels:
        raise CompileError(1, "Falta la etiqueta obligatoria 'start:'")

    program.labels = labels

    for stmt in program.statements:
        if isinstance(stmt, Goto):
            if stmt.target not in labels:
                raise CompileError(stmt.line, f"Etiqueta desconocida: {stmt.target}")

        elif isinstance(stmt, IfGoto):
            if stmt.target not in labels:
                raise CompileError(stmt.line, f"Etiqueta desconocida: {stmt.target}")
            _validate_expr(stmt.cond)

        elif isinstance(stmt, Assign):
            if stmt.name in PERCEPTIONS or stmt.name in CONSTANTS:
                raise CompileError(stmt.line, f"No se puede asignar a {stmt.name}")
            _validate_expr(stmt.value)

        elif isinstance(stmt, Action):
            if stmt.name not in ACTIONS:
                raise CompileError(stmt.line, f"Acción desconocida: {stmt.name}")
            esperado = ACTIONS[stmt.name]
            if len(stmt.args) != esperado:
                raise CompileError(
                    stmt.line,
                    f"{stmt.name} espera {esperado} argumentos, recibió {len(stmt.args)}",
                )
            for a in stmt.args:
                _validate_expr(a)


# ============================================================
# 6. COMPILACIÓN COMPLETA
# ============================================================

def compile_creature(source: str) -> CreatureProgram:
    tokens = tokenize(source)
    p = Parser(tokens)
    p.skip_newlines()

    first = p.expect(TokenType.IDENTIFIER, "Se esperaba 'creature Nombre'")
    if first.literal != "creature":
        raise CompileError(first.line, "La primera línea debe ser 'creature Nombre'")

    name_tok = p.peek()
    if name_tok.type not in (TokenType.IDENTIFIER, TokenType.STRING):
        raise CompileError(name_tok.line, "Nombre de criatura inválido")
    p.advance()
    name = name_tok.literal
    p.expect(TokenType.NEWLINE, "Se esperaba fin de línea")

    header: dict[str, tuple[str, int]] = {
        "creature": (name, first.line),
    }

    while True:
        p.skip_newlines()

        if p.peek().type == TokenType.EOF:
            raise CompileError(p.peek().line, "Falta la etiqueta 'start:'")

        if (
            p.peek().type == TokenType.IDENTIFIER
            and p.peek().literal == "start"
            and p.peek(1).type == TokenType.COLON
        ):
            break

        key_tok = p.expect(TokenType.IDENTIFIER, "Se esperaba clave de cabecera o 'start:'")
        key = key_tok.literal

        val_tok = p.peek()
        if val_tok.type not in (TokenType.IDENTIFIER, TokenType.STRING, TokenType.NUMBER):
            raise CompileError(val_tok.line, f"Valor inválido para '{key}'")
        p.advance()
        val = val_tok.literal
        p.expect(TokenType.NEWLINE, "Se esperaba fin de línea")

        if key in header:
            raise CompileError(key_tok.line, f"Clave duplicada: {key}")
        header[key] = (val, key_tok.line)

    required = {"creature", "faction", "health", "vision", "lifespan"}
    missing = required - set(header)
    extra = set(header) - required

    if missing:
        raise CompileError(first.line, f"Faltan claves: {', '.join(sorted(missing))}")
    if extra:
        raise CompileError(first.line, f"Claves desconocidas: {', '.join(sorted(extra))}")

    for k in ("creature", "faction"):
        if not header[k][0]:
            raise CompileError(header[k][1], f"{k} no puede estar vacío")

    def get_int(key: str) -> int:
        raw, ln = header[key]
        try:
            value = int(raw)
        except ValueError:
            raise CompileError(ln, f"{key} debe ser un entero")
        if key == "health" and value <= 0:
            raise CompileError(ln, "health debe ser mayor que 0")
        if key == "vision" and value < 1:
            raise CompileError(ln, "vision debe ser mayor o igual que 1")
        if key == "lifespan" and value <= 0:
            raise CompileError(ln, "lifespan debe ser mayor que 0")
        return value

    health = get_int("health")
    vision = get_int("vision")
    lifespan = get_int("lifespan")
    faction = header["faction"][0]

    start_tok = p.expect(TokenType.IDENTIFIER, "Se esperaba 'start'")
    p.expect(TokenType.COLON, "Se esperaba ':' después de start")
    p.expect(TokenType.NEWLINE, "Se esperaba fin de línea después de start:")

    statements: list[Stmt] = [Label(start_tok.line, "start")]

    while True:
        p.skip_newlines()
        if p.peek().type == TokenType.EOF:
            break
        statements.append(parse_statement(p))

    program = CreatureProgram(
        name=name,
        faction=faction,
        health=health,
        vision=vision,
        lifespan=lifespan,
        statements=statements,
    )
    _validate_program(program)
    return program