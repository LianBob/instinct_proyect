# lexer.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    NUMBER = auto()
    STRING = auto()
    IDENTIFIER = auto()

    IF = auto()
    GOTO = auto()
    AND = auto()
    OR = auto()
    NOT = auto()

    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    MODULO = auto()

    LESS = auto()
    LESS_EQUAL = auto()
    GREATER = auto()
    GREATER_EQUAL = auto()
    EQUAL = auto()
    EQUAL_EQUAL = auto()
    DISTINCT = auto()
    DISTINCT_EQUAL = auto()

    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    COMMA = auto()
    COLON = auto()

    NEWLINE = auto()
    EOF = auto()


KEYWORDS = {
    "if": TokenType.IF,
    "goto": TokenType.GOTO,
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
}


@dataclass(frozen=True)
class Token:
    type: TokenType
    literal: str
    line: int


class CompileError(Exception):
    def __init__(self, line: int, message: str):
        super().__init__(f"Línea {line}: {message}")
        self.line = line
        self.message = message


def tokenize(src: str) -> list[Token]:
    line = 1
    i = 0
    n = len(src)
    tokens: list[Token] = []

    def add(tipo: TokenType, literal: str, ln: int) -> None:
        tokens.append(Token(tipo, literal, ln))

    while i < n:
        c = src[i]

        # 1. Comentarios
        if c == "#":
            while i < n and src[i] != "\n":
                i += 1
            continue

        # 2. Espacios
        if c in " \t\r":
            i += 1
            continue

        # 3. Saltos de línea
        if c == "\n":
            add(TokenType.NEWLINE, "", line)
            line += 1
            i += 1
            continue

        # 4. Strings
        if c == '"':
            start_line = line
            i += 1
            start = i
            while i < n and src[i] != '"':
                if src[i] == "\n":
                    raise CompileError(start_line, "Texto sin cerrar o con salto de línea")
                i += 1
            if i >= n:
                raise CompileError(start_line, "Texto sin cerrar")
            add(TokenType.STRING, src[start:i], start_line)
            i += 1
            continue

        # 5. Números
        if c.isdigit():
            start = i
            while i < n and src[i].isdigit():
                i += 1
            add(TokenType.NUMBER, src[start:i], line)
            continue

        # 6. Identificadores y palabras reservadas
        if c.isalpha() or c == "_":
            start = i
            while i < n and (src[i].isalnum() or src[i] == "_"):
                i += 1
            value = src[start:i]
            add(KEYWORDS.get(value, TokenType.IDENTIFIER), value, line)
            continue

        # 7. Operadores de dos caracteres (antes que los de uno)
        two = src[i:i + 2]
        if two == "<=":
            add(TokenType.LESS_EQUAL, two, line); i += 2; continue
        if two == ">=":
            add(TokenType.GREATER_EQUAL, two, line); i += 2; continue
        if two == "==":
            add(TokenType.EQUAL_EQUAL, two, line); i += 2; continue
        if two == "!=":
            add(TokenType.DISTINCT_EQUAL, two, line); i += 2; continue

        # 8. Operadores y puntuación de un carácter
        single = {
            "<": TokenType.LESS,
            ">": TokenType.GREATER,
            "=": TokenType.EQUAL,
            "!": TokenType.DISTINCT,
            "+": TokenType.PLUS,
            "-": TokenType.MINUS,
            "*": TokenType.STAR,
            "/": TokenType.SLASH,
            "%": TokenType.MODULO,
            "(": TokenType.LEFT_PAREN,
            ")": TokenType.RIGHT_PAREN,
            ",": TokenType.COMMA,
            ":": TokenType.COLON,
        }
        if c in single:
            add(single[c], c, line)
            i += 1
            continue

        # 9. Cualquier otra cosa
        raise CompileError(line, f"Carácter no reconocido: {c!r}")

    # NEWLINE sintético si el archivo no termina en salto
    if not tokens or tokens[-1].type != TokenType.NEWLINE:
        add(TokenType.NEWLINE, "", line)
    add(TokenType.EOF, "", line)
    return tokens