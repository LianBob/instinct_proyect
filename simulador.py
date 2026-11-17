# simulador.py
from __future__ import annotations

import os
import random
from typing import Any

from lexer import CompileError
from parser import (
    CONSTANTS,
    CreatureProgram,
    compile_creature,
)
from runtime import (
    CreatureRuntime,
    InstinctRuntimeError,
    WorldContext,
)


# ============================================================
# MODELOS
# ============================================================

class Terreno:
    def __init__(self, nombre: str, char: str, resource_max: int, regen: int):
        self.nombre = nombre
        self.char = char
        self.resource_max = resource_max
        self.regen = regen
        self.resource = resource_max

    def copia(self) -> "Terreno":
        t = Terreno(self.nombre, self.char, self.resource_max, self.regen)
        t.resource = self.resource
        return t

    def __repr__(self):
        return f"Terreno({self.nombre!r}, {self.resource}/{self.resource_max})"


class Objeto:
    def __init__(self, nombre: str, char: str, resource_max: int):
        self.nombre = nombre
        self.char = char
        self.resource_max = resource_max
        self.resource = resource_max

    def copia(self) -> "Objeto":
        o = Objeto(self.nombre, self.char, self.resource_max)
        o.resource = self.resource
        return o

    def __repr__(self):
        return f"Objeto({self.nombre!r}, {self.resource}/{self.resource_max})"


class Casilla:
    def __init__(self, terreno: Terreno, objeto: Objeto | None = None):
        self.terreno = terreno
        self.objeto = objeto
        self.criatura: "Criatura | None" = None


class Mapa:
    def __init__(self, nombre: str, casillas: list[list[Casilla]]):
        self.nombre = nombre
        self.casillas = casillas
        self.height = len(casillas)
        self.width = len(casillas[0]) if casillas else 0
        self.criaturas: list["Criatura"] = []


# ============================================================
# CRIATURA (implementa WorldContext)
# ============================================================

class Criatura:
    def __init__(self, mundo: "Mundo", program: CreatureProgram, x: int, y: int):
        self.mundo = mundo
        self.program = program
        self.x = x
        self.y = y
        self.health = program.health
        self.age = 0
        self.viva = True
        self.percepciones: dict[str, Any] = {}
        self.runtime = CreatureRuntime(program, self)

    def __repr__(self):
        estado = "viva" if self.viva else "muerta"
        return f"Criatura({self.program.name}@{self.x},{self.y} {estado} hp={self.health})"

    # ---- WorldContext ----

    def get_perception(self, name: str) -> Any:
        if name == "random":
            return self.mundo.rng.randint(0, 99)
        if name not in self.percepciones:
            raise KeyError(f"Percepción no preparada: {name}")
        return self.percepciones[name]

    def call_function(self, name: str, args: list[Any]) -> Any:
        x, y = args
        if name == "see":
            return self.mundo.ver(self, x, y)
        if name == "name":
            return self.mundo.nombre(self, x, y)
        raise ValueError(f"Función desconocida: {name}")

    def do_action(self, name: str, args: list[Any]) -> None:
        if name == "say":
            self.mundo.logs.append(
                f"[tick {self.mundo.tick}] {self.program.name} dice: {args[0]!r}"
            )
        elif name == "roar":
            self.mundo.roars_este_tick.append((self.x, self.y, args[0]))
            self.mundo.logs.append(
                f"[tick {self.mundo.tick}] {self.program.name} ruge: {args[0]!r}"
            )
        elif name == "wait":
            pass  # el runtime maneja sleep_turns
        elif name == "move":
            self._do_move(*args)
        elif name == "attack":
            self._do_attack(*args)
        elif name == "consume":
            self._do_consume(*args)
        elif name == "reproduce":
            self._do_reproduce(*args)
        else:
            raise ValueError(f"Acción desconocida: {name}")
    @property
    def _mapa(self) -> "Mapa":
        return self.mundo._mapa_obligatorio()

    # ---- Acciones ----

    def _do_move(self, dx: int, dy: int, speed: int) -> None:
        for _ in range(speed):
            nx, ny = self.x + dx, self.y + dy
            if not self.mundo.dentro(nx, ny):
                break
            cell = self.mundo.mapa.casillas[ny][nx]
            if cell.criatura is not None or cell.objeto is not None:
                break
            self.mundo.mapa.casillas[self.y][self.x].criatura = None
            cell.criatura = self
            self.x, self.y = nx, ny

    def _do_attack(self, dx: int, dy: int, damage: int) -> None:
        tx, ty = self.x + dx, self.y + dy
        if not self.mundo.dentro(tx, ty):
            return
        cell = self.mundo.mapa.casillas[ty][tx]
        if cell.criatura is not None:
            cell.criatura.health -= damage
            if cell.criatura.health <= 0:
                self.mundo.matar(cell.criatura)
        elif cell.objeto is not None:
            cell.objeto.resource -= damage
        elif cell.terreno is not None:
            cell.terreno.resource -= damage

    def _do_consume(self, dx: int, dy: int, damage: int, heal: int) -> None:
        self._do_attack(dx, dy, damage)
        self.health += heal

    def _do_reproduce(self, dx: int, dy: int, health: int) -> None:
        tx, ty = self.x + dx, self.y + dy
        if not self.mundo.dentro(tx, ty):
            return
        cell = self.mundo.mapa.casillas[ty][tx]
        if cell.criatura is not None or cell.objeto is not None:
            return
        if self.health <= health:
            return
        self.health -= health
        baby = Criatura(self.mundo, self.program, tx, ty)
        baby.health = health
        cell.criatura = baby
        self.mundo.mapa.criaturas.append(baby)

    # ---- Percepciones ----

    def actualizar_percepciones(self) -> None:
        m = self.mundo
        cells = m.mapa.casillas
        w, h = m.mapa.width, m.mapa.height
        vision = self.program.vision
        faccion = self.program.faction

        cell_here = cells[self.y][self.x]
        self.percepciones["health"] = self.health
        self.percepciones["age"] = self.age
        self.percepciones["lifespan"] = self.program.lifespan
        self.percepciones["vision"] = vision
        self.percepciones["species"] = self.program.name
        self.percepciones["faction"] = faccion
        self.percepciones["x"] = self.x
        self.percepciones["y"] = self.y
        self.percepciones["terrain_here"] = (
            cell_here.terreno.nombre if cell_here.terreno else ""
        )
        self.percepciones["reserve_here"] = (
            cell_here.terreno.resource if cell_here.terreno else 0
        )

        self.percepciones["width"] = w
        self.percepciones["height"] = h
        self.percepciones["tick"] = m.tick

        total_c = total_a = total_e = 0
        for other in m.mapa.criaturas:
            if other is self or not other.viva:
                continue
            total_c += 1
            if other.program.faction == faccion:
                total_a += 1
            else:
                total_e += 1
        self.percepciones["total_creatures"] = total_c
        self.percepciones["total_allies"] = total_a
        self.percepciones["total_enemies"] = total_e

        allies_near = enemies_near = objects_near = 0
        best_enemy: tuple | None = None
        best_ally: tuple | None = None
        best_object: tuple | None = None

        for dy in range(-vision, vision + 1):
            for dx in range(-vision, vision + 1):
                if dx == 0 and dy == 0:
                    continue
                x, y = self.x + dx, self.y + dy
                if not (0 <= x < w and 0 <= y < h):
                    continue
                d = max(abs(dx), abs(dy))
                cell = cells[y][x]

                if cell.criatura is not None and cell.criatura.viva:
                    cand = (d, y, x, dx, dy)
                    if cell.criatura.program.faction == faccion:
                        allies_near += 1
                        if best_ally is None or cand[:3] < best_ally[:3]:
                            best_ally = cand
                    else:
                        enemies_near += 1
                        if best_enemy is None or cand[:3] < best_enemy[:3]:
                            best_enemy = cand
                elif cell.objeto is not None:
                    objects_near += 1
                    cand = (d, y, x, dx, dy)
                    if best_object is None or cand[:3] < best_object[:3]:
                        best_object = cand

        self.percepciones["allies_near"] = allies_near
        self.percepciones["enemies_near"] = enemies_near
        self.percepciones["objects_near"] = objects_near

        def signo(n: int) -> int:
            return (n > 0) - (n < 0)

        if best_enemy:
            d, _, _, dx, dy = best_enemy
            self.percepciones["enemy_dist"] = d
            self.percepciones["enemy_dx"] = signo(dx)
            self.percepciones["enemy_dy"] = signo(dy)
        else:
            self.percepciones["enemy_dist"] = -1
            self.percepciones["enemy_dx"] = 0
            self.percepciones["enemy_dy"] = 0

        if best_ally:
            d, _, _, dx, dy = best_ally
            self.percepciones["ally_dist"] = d
            self.percepciones["ally_dx"] = signo(dx)
            self.percepciones["ally_dy"] = signo(dy)
        else:
            self.percepciones["ally_dist"] = -1
            self.percepciones["ally_dx"] = 0
            self.percepciones["ally_dy"] = 0

        if best_object:
            d, _, _, dx, dy = best_object
            self.percepciones["object_dist"] = d
            self.percepciones["object_dx"] = signo(dx)
            self.percepciones["object_dy"] = signo(dy)
        else:
            self.percepciones["object_dist"] = -1
            self.percepciones["object_dx"] = 0
            self.percepciones["object_dy"] = 0

        roars_near = 0
        last_roar = ""
        for rx, ry, texto in m.roars_tick_anterior:
            if max(abs(rx - self.x), abs(ry - self.y)) <= vision:
                roars_near += 1
                last_roar = str(texto)
        self.percepciones["roars_near"] = roars_near
        self.percepciones["last_roar"] = last_roar


# ============================================================
# MUNDO
# ============================================================

class Mundo:
    def __init__(self, ruta_base: str = ".", semilla: int = 0):
        self.ruta_base = ruta_base
        self.rng = random.Random(semilla)

        self.terrenos: dict[str, Terreno] = {}
        self.objetos: dict[str, Objeto] = {}
        self.especies: dict[str, CreatureProgram] = {}
        self.mapas: dict[str, list[str]] = {}

        self.mapa: Mapa | None = None
        self.tick: int = 0

        self.roars_este_tick: list[tuple[int, int, Any]] = []
        self.roars_tick_anterior: list[tuple[int, int, Any]] = []

        self.logs: list[str] = []
        self.errores_carga: list[str] = []

    # ---- Carga ----

    def cargar_todo(self) -> None:
        self.cargar_terrenos(os.path.join(self.ruta_base, "terrains"))
        self.cargar_objetos(os.path.join(self.ruta_base, "objects"))
        self.cargar_mapas(os.path.join(self.ruta_base, "maps"))
        self.cargar_especies(os.path.join(self.ruta_base, "creatures"))

    def _archivos(self, carpeta: str, ext: str) -> list[str]:
        if not os.path.isdir(carpeta):
            self.errores_carga.append(f"carpeta no encontrada: {carpeta}")
            return []
        return [
            os.path.join(carpeta, a)
            for a in sorted(os.listdir(carpeta))
            if a.endswith(ext)
        ]

    def cargar_terrenos(self, carpeta: str) -> None:
        for path in self._archivos(carpeta, ".te"):
            try:
                t = _parse_terreno(path)
                self.terrenos[t.nombre] = t
            except Exception as e:
                self.errores_carga.append(f"{os.path.basename(path)}: {e}")

    def cargar_objetos(self, carpeta: str) -> None:
        for path in self._archivos(carpeta, ".ob"):
            try:
                o = _parse_objeto(path)
                self.objetos[o.nombre] = o
            except Exception as e:
                self.errores_carga.append(f"{os.path.basename(path)}: {e}")

    def cargar_mapas(self, carpeta: str) -> None:
        for path in self._archivos(carpeta, ".map"):
            try:
                nombre, filas = _parse_mapa(path)
                self.mapas[nombre] = filas
            except Exception as e:
                self.errores_carga.append(f"{os.path.basename(path)}: {e}")

    def cargar_especies(self, carpeta: str) -> None:
        for path in self._archivos(carpeta, ".ins"):
            try:
                with open(path, encoding="utf-8") as f:
                    src = f.read()
                prog = compile_creature(src)
                self.especies[prog.name] = prog
            except CompileError as e:
                self.errores_carga.append(f"{os.path.basename(path)}: {e}")
            except Exception as e:
                self.errores_carga.append(
                    f"{os.path.basename(path)}: error inesperado: {e}"
                )

    def _mapa_obligatorio(self) -> "Mapa":
        if self.mapa is None:
            raise RuntimeError("primero hay que elegir un mapa")
        return self.mapa
    # ---- Preparación ----

    def elegir_mapa(self, nombre: str, colocar_orco: bool = True) -> None:
        if nombre not in self.mapas:
            raise ValueError(f"mapa no encontrado: {nombre}")
        filas = self.mapas[nombre]

        casillas: list[list[Casilla]] = []
        for y, fila in enumerate(filas):
            fila_casillas: list[Casilla] = []
            for x, ch in enumerate(fila):
                t = self._terreno_para_char(ch)
                o = self._objeto_para_char(ch)
                if t is None and o is None:
                    raise ValueError(
                        f"mapa '{nombre}' línea {y + 2} columna {x + 1}: "
                        f"char '{ch}' no definido"
                    )
                if t is not None and o is not None:
                    raise ValueError(
                        f"mapa '{nombre}' línea {y + 2} columna {x + 1}: "
                        f"char '{ch}' ambiguo (terreno y objeto)"
                    )
                if t is None:
                    t = self._primer_terreno()
                fila_casillas.append(Casilla(t.copia(), o.copia() if o else None))
            casillas.append(fila_casillas)

        self.mapa = Mapa(nombre, casillas)
        self.tick = 0
        self.roars_este_tick = []
        self.roars_tick_anterior = []
        self.logs = []

        if colocar_orco and "Orco" in self.especies:
            cx, cy = self.mapa.width // 2, self.mapa.height // 2
            if self.puede_colocar(cx, cy):
                self.colocar_criatura("Orco", cx, cy)

    def puede_colocar(self, x: int, y: int) -> bool:
        if self.mapa is None or not self.dentro(x, y):
            return False
        cell = self.mapa.casillas[y][x]
        return cell.criatura is None and cell.objeto is None

    def colocar_criatura(self, especie: str, x: int, y: int) -> None:
        if especie not in self.especies:
            raise ValueError(f"especie no encontrada: {especie}")
        if not self.puede_colocar(x, y):
            raise ValueError(f"no se puede colocar en ({x}, {y})")
        c = Criatura(self, self.especies[especie], x, y)
        self.mapa.casillas[y][x].criatura = c
        self.mapa.criaturas.append(c)

    def quitar_criatura(self, x: int, y: int) -> bool:
        if self.mapa is None or not self.dentro(x, y):
            return False
        cell = self.mapa.casillas[y][x]
        if cell.criatura is None:
            return False
        c = cell.criatura
        c.viva = False
        cell.criatura = None
        self.mapa.criaturas = [k for k in self.mapa.criaturas if k is not c]
        return True

    # ---- Simulación ----

    def simular_tick(self) -> None:
        if self.mapa is None:
            raise RuntimeError("primero hay que elegir un mapa")

        vivas = [c for c in self.mapa.criaturas if c.viva]
        self.rng.shuffle(vivas)

        for c in vivas:
            if not c.viva:
                continue
            c.actualizar_percepciones()
            try:
                c.runtime.run_turn()
            except InstinctRuntimeError as e:
                self.logs.append(f"[tick {self.tick}] {c.program.name} muere: {e}")
                self.matar(c)

        self._fin_de_tick()

    def _fin_de_tick(self) -> None:
        for c in self.mapa.criaturas:
            if not c.viva:
                continue
            c.health -= 1
            c.age += 1
            if c.health <= 0 or c.age >= c.program.lifespan:
                self.matar(c)

        for fila in self.mapa.casillas:
            for cell in fila:
                if cell.terreno is not None:
                    cell.terreno.resource = min(
                        cell.terreno.resource + cell.terreno.regen,
                        cell.terreno.resource_max,
                    )
                if cell.objeto is not None and cell.objeto.resource <= 0:
                    cell.objeto = None

        self.mapa.criaturas = [c for c in self.mapa.criaturas if c.viva]
        self.roars_tick_anterior = self.roars_este_tick
        self.roars_este_tick = []
        self.tick += 1

    def matar(self, c: Criatura) -> None:
        if not c.viva:
            return
        c.viva = False
        if self.dentro(c.x, c.y):
            cell = self.mapa.casillas[c.y][c.x]
            if cell.criatura is c:
                cell.criatura = None

    # ---- Consultas para el lenguaje ----

    def dentro(self, x: int, y: int) -> bool:
        if self.mapa is None:
            return False
        return 0 <= x < self.mapa.width and 0 <= y < self.mapa.height

    def ver(self, criatura: Criatura, x: int, y: int) -> int:
        if max(abs(x - criatura.x), abs(y - criatura.y)) > criatura.program.vision:
            return CONSTANTS["NONE"]
        if not self.dentro(x, y):
            return CONSTANTS["OBJECT"]
        cell = self.mapa.casillas[y][x]
        if cell.criatura is not None and cell.criatura.viva:
            if cell.criatura.program.faction == criatura.program.faction:
                return CONSTANTS["ALLY"]
            return CONSTANTS["ENEMY"]
        if cell.objeto is not None:
            return CONSTANTS["OBJECT"]
        return CONSTANTS["GROUND"]

    def nombre(self, criatura: Criatura, x: int, y: int) -> str:
        if max(abs(x - criatura.x), abs(y - criatura.y)) > criatura.program.vision:
            return ""
        if not self.dentro(x, y):
            return ""
        cell = self.mapa.casillas[y][x]
        if cell.criatura is not None and cell.criatura.viva:
            return cell.criatura.program.name
        if cell.objeto is not None:
            return cell.objeto.nombre
        if cell.terreno is not None:
            return cell.terreno.nombre
        return ""

    def _terreno_para_char(self, ch: str) -> Terreno | None:
        for t in self.terrenos.values():
            if t.char == ch:
                return t
        return None

    def _objeto_para_char(self, ch: str) -> Objeto | None:
        for o in self.objetos.values():
            if o.char == ch:
                return o
        return None

    def _primer_terreno(self) -> Terreno:
        for t in self.terrenos.values():
            return t
        raise ValueError("no hay terrenos cargados")


# ============================================================
# PARSERS DE ARCHIVO
# ============================================================

def _leer_pares(path: str) -> list[tuple[str, str, int]]:
    pares: list[tuple[str, str, int]] = []
    with open(path, encoding="utf-8") as f:
        for i, raw in enumerate(f, 1):
            stripped = raw.strip()

            # Línea vacía o comentario completo
            if not stripped or stripped.startswith("#"):
                continue

            parts = stripped.split()

            # Clave + valor + (comentario opcional ignorado)
            if len(parts) < 2:
                raise ValueError(
                    f"línea {i}: se esperaban al menos 2 palabras, "
                    f"encontradas {len(parts)}: {stripped!r}"
                )

            k, v = parts[0], parts[1]
            pares.append((k, v, i))
    return pares


def _parse_terreno(path: str) -> Terreno:
    pares = _leer_pares(path)
    claves: dict[str, tuple[str, int]] = {}
    for k, v, ln in pares:
        if k in claves:
            raise ValueError(f"línea {ln}: clave duplicada '{k}'")
        claves[k] = (v, ln)

    for req in ("terrain", "char", "resource_max", "regen"):
        if req not in claves:
            raise ValueError(f"falta la clave '{req}'")

    try:
        resource_max = int(claves["resource_max"][0])
        regen = int(claves["regen"][0])
    except ValueError:
        raise ValueError("resource_max y regen deben ser enteros")

    if len(claves["char"][0]) != 1:
        raise ValueError("char debe ser un solo carácter")

    return Terreno(claves["terrain"][0], claves["char"][0], resource_max, regen)


def _parse_objeto(path: str) -> Objeto:
    pares = _leer_pares(path)
    claves: dict[str, tuple[str, int]] = {}
    for k, v, ln in pares:
        if k in claves:
            raise ValueError(f"línea {ln}: clave duplicada '{k}'")
        claves[k] = (v, ln)

    for req in ("object", "char", "resource_max"):
        if req not in claves:
            raise ValueError(f"falta la clave '{req}'")

    try:
        resource_max = int(claves["resource_max"][0])
    except ValueError:
        raise ValueError("resource_max debe ser entero")

    if len(claves["char"][0]) != 1:
        raise ValueError("char debe ser un solo carácter")

    return Objeto(claves["object"][0], claves["char"][0], resource_max)


def _parse_mapa(path: str) -> tuple[str, list[str]]:
    with open(path, encoding="utf-8") as f:
        lineas = [l.rstrip("\n") for l in f]

    if not lineas:
        raise ValueError("archivo vacío")

    nombre = lineas[0].strip()
    if not nombre:
        raise ValueError("la primera línea debe ser el nombre del mapa")

    filas = [l for l in lineas[1:] if l.strip()]
    if not filas:
        raise ValueError("mapa sin filas")

    width = len(filas[0])
    for i, fila in enumerate(filas, 2):
        if len(fila) != width:
            raise ValueError(
                f"línea {i}: ancho inconsistente ({len(fila)} vs {width})"
            )

    return nombre, filas