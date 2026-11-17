# ui_consola.py
from __future__ import annotations

import os
import sys
import time

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from simulador import Mundo


COLORES_TERRENO = {
    "Hierba": "green",
    "TierraMaldita": "magenta",
    "SueloRocoso": "grey62",
}

COLORES_OBJETO = {
    "Roca": "white",
    "Totem": "yellow",
    "Dispositivo": "cyan",
    "ArbolMuerto": "dark_green",
}

COLORES_FACCION = {
    "horda": "red",
    "laboratorio": "cyan",
}


# ============================================================
# TECLADO (modo raw, multiplataforma)
# ============================================================

class Teclado:
    def __init__(self):
        self._unix = os.name != "nt"
        self._fd = None
        self._old = None

    def __enter__(self):
        if self._unix:
            try:
                import termios
                import tty
                self._fd = sys.stdin.fileno()
                self._old = termios.tcgetattr(self._fd)
                tty.setcbreak(self._fd)
            except Exception:
                self._fd = None
        return self

    def __exit__(self, *args):
        if self._unix and self._fd is not None and self._old is not None:
            import termios
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)

    def leer(self, timeout: float = 0.05) -> str | None:
        if self._unix:
            return self._leer_unix(timeout)
        return self._leer_windows(timeout)

    def _leer_unix(self, timeout: float) -> str | None:
        import select
        if not select.select([sys.stdin], [], [], timeout)[0]:
            return None
        ch = os.read(self._fd, 1)
        if not ch:
            return None
        ch = ch.decode("utf-8", "replace")
        if ch != "\x1b":
            return self._traducir(ch)

        # posible secuencia de escape
        if not select.select([sys.stdin], [], [], 0.02)[0]:
            return "esc"
        ch2 = os.read(self._fd, 1).decode("utf-8", "replace")
        if ch2 != "[":
            return ch + ch2
        if not select.select([sys.stdin], [], [], 0.02)[0]:
            return "esc"
        ch3 = os.read(self._fd, 1).decode("utf-8", "replace")
        return {
            "A": "arriba", "B": "abajo", "C": "derecha", "D": "izquierda",
        }.get(ch3, "")

    def _leer_windows(self, timeout: float) -> str | None:
        import msvcrt
        inicio = time.monotonic()
        while time.monotonic() - inicio < timeout:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):
                    ch2 = msvcrt.getwch()
                    return {
                        "H": "arriba", "P": "abajo",
                        "M": "derecha", "K": "izquierda",
                    }.get(ch2, "")
                return self._traducir(ch)
            time.sleep(0.01)
        return None

    @staticmethod
    def _traducir(ch: str) -> str:
        if ch in ("\r", "\n"):
            return "enter"
        if ch == "\t":
            return "tab"
        if ch == " ":
            return "espacio"
        return ch


# ============================================================
# JUEGO
# ============================================================

class JuegoConsola:
    def __init__(self, mundo: Mundo):
        self.mundo = mundo
        self.console = Console()
        self.cursor: tuple[int, int] = (0, 0)
        self.especie_actual: str | None = None
        self.velocidad: int = 10
        self.pausado: bool = False

    # ------------------------------------------------
    # Flujo principal
    # ------------------------------------------------

    def correr(self) -> None:
        try:
            self._correr_interno()
        except KeyboardInterrupt:
            pass
        self.console.print("[dim]Hasta luego.[/dim]")

    def _correr_interno(self) -> None:
        self.console.clear()
        self._bienvenida()

        if self.mundo.errores_carga:
            self.console.print(Panel(
                "\n".join(self.mundo.errores_carga),
                title="[yellow]Errores de carga[/yellow]",
                border_style="yellow",
            ))
            self.console.print()

        if not self._seleccionar_mapa():
            return

        while True:
            resultado = self._preparacion()
            if resultado != "start":
                return
            resultado = self._simulacion()
            if resultado == "salir":
                return
            if resultado == "reiniciar":
                nombre = self.mundo.mapa.nombre  # type: ignore[union-attr]
                self.mundo.elegir_mapa(nombre)
                continue

    # ------------------------------------------------
    # Bienvenida y selección de mapa
    # ------------------------------------------------

    def _bienvenida(self) -> None:
        self.console.print(Panel.fit(
            "[bold red]Hay un orco en un mundo desconocido...[/bold red]\n"
            "[dim]Criaturas desconocidas aparecen. Forman clanes. "
            "Se apoderan del mundo.[/dim]\n"
            "[dim]Un científico loco las crea y las deja sueltas.[/dim]\n"
            "[dim]¿Qué sucederá con el orco? ¿Qué sucederá con su mundo?[/dim]",
            title="[bold]INSTINCT · El experimento del anciano[/bold]",
            border_style="red",
        ))

    def _seleccionar_mapa(self) -> bool:
        nombres = list(self.mundo.mapas)
        if not nombres:
            self.console.print("[red]No hay mapas cargados.[/red]")
            return False

        tabla = Table(title="Mapas disponibles", box=box.SIMPLE_HEAVY)
        tabla.add_column("#", style="cyan", justify="right")
        tabla.add_column("Mapa")
        for i, n in enumerate(nombres, 1):
            tabla.add_row(str(i), n)
        self.console.print(tabla)

        while True:
            try:
                eleccion = self.console.input(
                    "\n[bold]Elige un mapa (número), o 'q' para salir: [/bold]"
                ).strip().lower()
            except EOFError:
                return False
            if eleccion == "q":
                return False
            if eleccion.isdigit():
                idx = int(eleccion) - 1
                if 0 <= idx < len(nombres):
                    self.mundo.elegir_mapa(nombres[idx])
                    self.cursor = (
                        self.mundo.mapa.width // 2,  # type: ignore[union-attr]
                        self.mundo.mapa.height // 2,  # type: ignore[union-attr]
                    )
                    if self.mundo.especies:
                        self.especie_actual = list(self.mundo.especies)[0]
                    return True
            self.console.print("[red]Opción inválida.[/red]")

    # ------------------------------------------------
    # Modo preparación
    # ------------------------------------------------

    def _preparacion(self) -> str:
        mapa = self.mundo.mapa
        if mapa is None:
            return "salir"
        especies = list(self.mundo.especies)
        if especies and self.especie_actual not in especies:
            self.especie_actual = especies[0]

        with Live(
            self._render_prep(),
            console=self.console,
            screen=True,
            refresh_per_second=15,
        ) as live:
            with Teclado() as teclado:
                while True:
                    tecla = teclado.leer(timeout=0.05)
                    if tecla is None:
                        continue

                    if tecla == "q":
                        return "salir"
                    elif tecla == "s":
                        return "start"
                    elif tecla == "arriba":
                        self.cursor = (self.cursor[0], max(0, self.cursor[1] - 1))
                    elif tecla == "abajo":
                        self.cursor = (
                            self.cursor[0],
                            min(mapa.height - 1, self.cursor[1] + 1),
                        )
                    elif tecla == "izquierda":
                        self.cursor = (max(0, self.cursor[0] - 1), self.cursor[1])
                    elif tecla == "derecha":
                        self.cursor = (
                            min(mapa.width - 1, self.cursor[0] + 1),
                            self.cursor[1],
                        )
                    elif tecla == "enter":
                        if self.especie_actual and self.mundo.puede_colocar(*self.cursor):
                            self.mundo.colocar_criatura(
                                self.especie_actual, *self.cursor
                            )
                    elif tecla == "x":
                        self.mundo.quitar_criatura(*self.cursor)
                    elif tecla == "tab":
                        if especies:
                            i = (
                                especies.index(self.especie_actual)
                                if self.especie_actual in especies
                                else 0
                            )
                            self.especie_actual = especies[(i + 1) % len(especies)]
                    elif tecla.isdigit():
                        idx = int(tecla) - 1
                        if 0 <= idx < len(especies):
                            self.especie_actual = especies[idx]

                    live.update(self._render_prep())

    # ------------------------------------------------
    # Modo simulación
    # ------------------------------------------------

    def _simulacion(self) -> str:
        mapa = self.mundo.mapa
        if mapa is None:
            return "salir"

        self.pausado = False
        self.velocidad = 10
        intervalo = 1.0 / self.velocidad
        proximo_tick = time.monotonic() + intervalo
        self.cursor = (mapa.width // 2, mapa.height // 2)

        with Live(
            self._render_sim(),
            console=self.console,
            screen=True,
            refresh_per_second=20,
        ) as live:
            with Teclado() as teclado:
                while True:
                    ahora = time.monotonic()
                    cambio = False

                    if not self.pausado and ahora >= proximo_tick:
                        self.mundo.simular_tick()
                        intervalo = 1.0 / self.velocidad
                        proximo_tick = ahora + intervalo
                        cambio = True

                    tecla = teclado.leer(timeout=0.01)
                    if tecla is not None:
                        cambio = True
                        if tecla == "q":
                            return "salir"
                        elif tecla == "espacio":
                            self.pausado = not self.pausado
                            if not self.pausado:
                                proximo_tick = time.monotonic() + intervalo
                        elif tecla == "n" and self.pausado:
                            self.mundo.simular_tick()
                        elif tecla == "+":
                            self.velocidad = min(self.velocidad * 2, 60)
                            intervalo = 1.0 / self.velocidad
                        elif tecla == "-":
                            self.velocidad = max(self.velocidad // 2, 1)
                            intervalo = 1.0 / self.velocidad
                        elif tecla == "r":
                            return "reiniciar"
                        elif tecla == "arriba":
                            self.cursor = (
                                self.cursor[0], max(0, self.cursor[1] - 1)
                            )
                        elif tecla == "abajo":
                            self.cursor = (
                                self.cursor[0],
                                min(mapa.height - 1, self.cursor[1] + 1),
                            )
                        elif tecla == "izquierda":
                            self.cursor = (
                                max(0, self.cursor[0] - 1), self.cursor[1]
                            )
                        elif tecla == "derecha":
                            self.cursor = (
                                min(mapa.width - 1, self.cursor[0] + 1),
                                self.cursor[1],
                            )

                    if cambio:
                        live.update(self._render_sim())

    # ------------------------------------------------
    # Render: preparación
    # ------------------------------------------------

    def _render_prep(self) -> Layout:
        mapa = self.mundo.mapa
        if mapa is None:
            return Layout(Panel("Sin mapa"))

        ancho, alto = self._dimensiones_grid()
        grid = self._render_grid(ancho, alto)

        layout = Layout()
        layout.split_column(
            Layout(
                Panel(
                    grid,
                    title=f"[bold]Mapa: {mapa.nombre}[/bold]",
                    border_style="red",
                ),
                name="mapa",
                ratio=1,
            ),
            Layout(name="info", size=6),
            Layout(name="controles", size=3),
        )
        layout["info"].update(self._render_info_prep())
        layout["controles"].update(self._render_controles_prep())
        return layout

    def _render_info_prep(self) -> Panel:
        mapa = self.mundo.mapa
        if mapa is None:
            return Panel("Sin mapa", title="Info")

        cx = max(0, min(self.cursor[0], mapa.width - 1))
        cy = max(0, min(self.cursor[1], mapa.height - 1))
        cell = mapa.casillas[cy][cx]

        tabla = Table.grid(padding=(0, 2))
        tabla.add_column(style="dim", justify="right")
        tabla.add_column()

        tabla.add_row("Cursor:", f"({cx}, {cy})")

        if cell.criatura is not None and cell.criatura.viva:
            c = cell.criatura
            color = COLORES_FACCION.get(c.program.faction, "white")
            tabla.add_row(
                "Celda:",
                f"[bold {color}]{c.program.name}[/bold {color}]  "
                f"hp={c.health}  edad={c.age}/{c.program.lifespan}",
            )
        elif cell.objeto is not None:
            tabla.add_row(
                "Celda:",
                f"{cell.objeto.nombre}  "
                f"reserva={cell.objeto.resource}/{cell.objeto.resource_max}",
            )
        else:
            tabla.add_row(
                "Celda:",
                f"{cell.terreno.nombre}  "
                f"reserva={cell.terreno.resource}/{cell.terreno.resource_max}",
            )

        especie = self.especie_actual or "(ninguna)"
        tabla.add_row("Especie:", f"[bold yellow]{especie}[/bold yellow]")
        tabla.add_row("Criaturas:", str(len(mapa.criaturas)))

        return Panel(tabla, title="Info", border_style="blue")

    def _render_controles_prep(self) -> Panel:
        t = Text()
        for tecla, texto in [
            ("Flechas", "mover"), ("Enter", "colocar"), ("x", "quitar"),
            ("Tab", "siguiente especie"), ("1-9", "elegir especie"),
            ("s", "comenzar"), ("q", "salir"),
        ]:
            t.append(f" {tecla} ", style="bold cyan")
            t.append(f"{texto}  ", style="dim")
        return Panel(t, border_style="dim")

    # ------------------------------------------------
    # Render: simulación
    # ------------------------------------------------

    def _render_sim(self) -> Layout:
        mapa = self.mundo.mapa
        if mapa is None:
            return Layout(Panel("Sin mapa"))

        ancho, alto = self._dimensiones_grid()
        grid = self._render_grid(ancho, alto)

        layout = Layout()
        layout.split_column(
            Layout(
                Panel(
                    grid,
                    title=f"[bold]Mapa: {mapa.nombre}[/bold]  "
                          f"[dim]tick {self.mundo.tick}[/dim]",
                    border_style="red",
                ),
                name="mapa",
                ratio=1,
            ),
            Layout(name="status", size=3),
            Layout(name="logs", size=9),
            Layout(name="controles", size=3),
        )
        layout["status"].update(self._render_status_sim())
        layout["logs"].update(self._render_logs())
        layout["controles"].update(self._render_controles_sim())
        return layout

    def _render_status_sim(self) -> Panel:
        mapa = self.mundo.mapa
        vivas = len(mapa.criaturas) if mapa else 0
        facciones: dict[str, int] = {}
        for c in mapa.criaturas if mapa else []:
            facciones[c.program.faction] = facciones.get(c.program.faction, 0) + 1

        estado = "[bold yellow]PAUSA[/bold yellow]" if self.pausado else "[bold green]▶[/bold green]"
        t = Text()
        t.append_text(Text.from_markup(estado))
        t.append(f"  tick {self.mundo.tick}", style="bold cyan")
        t.append(f"  · {self.velocidad} ticks/s", style="bold")
        t.append(f"  · {vivas} vivas", style="bold")
        if facciones:
            t.append("  · ", style="dim")
            primera = True
            for faccion, n in sorted(facciones.items()):
                if not primera:
                    t.append(" ", style="dim")
                primera = False
                color = COLORES_FACCION.get(faccion, "white")
                t.append(f"{faccion}:{n}", style=color)
        return Panel(t, border_style="dim")

    def _render_logs(self) -> Panel:
        logs = self.mundo.logs[-8:]
        if not logs:
            return Panel("[dim](sin eventos)[/dim]", title="Logs", border_style="dim")
        t = Text()
        for i, log in enumerate(logs):
            if i > 0:
                t.append("\n")
            t.append(log, style="dim")
        return Panel(t, title="Logs", border_style="dim")

    def _render_controles_sim(self) -> Panel:
        t = Text()
        for tecla, texto in [
            ("Espacio", "play/pausa"), ("n", "step"), ("+/-", "velocidad"),
            ("Flechas", "panear"), ("r", "reiniciar"), ("q", "salir"),
        ]:
            t.append(f" {tecla} ", style="bold cyan")
            t.append(f"{texto}  ", style="dim")
        return Panel(t, border_style="dim")

    # ------------------------------------------------
    # Render: grilla común
    # ------------------------------------------------

    def _dimensiones_grid(self) -> tuple[int, int]:
        mapa = self.mundo.mapa
        if mapa is None:
            return (0, 0)
        try:
            cols, lines = self.console.size
        except Exception:
            cols, lines = (100, 30)
        # Reserve: prep → info(6) + controles(3) + bordes(~4) = 13
        #          sim  → status(3) + logs(9) + controles(3) + bordes(~6) = 21
        reservado = 21
        alto = max(5, min(mapa.height, lines - reservado))
        ancho = max(10, min(mapa.width, cols - 4))
        return ancho, alto

    def _render_grid(self, ancho: int, alto: int) -> Text:
        mapa = self.mundo.mapa
        if mapa is None:
            return Text("Sin mapa")

        x0 = max(0, min(self.cursor[0] - ancho // 2, mapa.width - ancho))
        y0 = max(0, min(self.cursor[1] - alto // 2, mapa.height - alto))

        lineas: list[Text] = []
        for y in range(y0, min(y0 + alto, mapa.height)):
            linea = Text()
            for x in range(x0, min(x0 + ancho, mapa.width)):
                cell = mapa.casillas[y][x]
                es_cursor = (x, y) == self.cursor

                if cell.criatura is not None and cell.criatura.viva:
                    c = cell.criatura
                    color = COLORES_FACCION.get(c.program.faction, "white")
                    letra = c.program.name[0].upper()
                    style = f"bold {color}"
                elif cell.objeto is not None:
                    color = COLORES_OBJETO.get(cell.objeto.nombre, "white")
                    letra = cell.objeto.char
                    style = color
                else:
                    color = COLORES_TERRENO.get(cell.terreno.nombre, "white")
                    letra = cell.terreno.char
                    style = color

                if es_cursor:
                    style += " reverse"
                linea.append(letra, style=style)
            lineas.append(linea)

        return Text("\n").join(lineas)