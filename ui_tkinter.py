# ui_tkinter.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from simulador import Mundo


# ============================================================
# Paletas y colores (auto-asigna color a cualquier nombre nuevo)
# ============================================================

PALETA_TERRENOS = [
    "green", "blue", "magenta", "cyan", "yellow",
    "bright_green", "bright_blue", "bright_magenta", "bright_cyan",
    "dark_green", "dark_cyan",
]
PALETA_OBJETOS = [
    "white", "bright_white", "yellow", "bright_yellow",
    "grey50", "grey62", "bright_black",
]
PALETA_FACCIONES = [
    "red", "cyan", "magenta", "yellow", "green", "blue",
    "bright_red", "bright_cyan", "bright_magenta", "bright_yellow",
]

COLORES_TERRENO_RESERVADOS = {
    "Hierba": "green", "TierraMaldita": "magenta", "SueloRocoso": "grey62",
}
COLORES_OBJETO_RESERVADOS = {
    "Roca": "white", "Totem": "yellow", "Dispositivo": "cyan",
    "ArbolMuerto": "dark_green",
}
COLORES_FACCION_RESERVADOS = {
    "horda": "red", "laboratorio": "cyan",
}

RICH_A_TK = {
    "green": "#1e7a2e", "bright_green": "#4ad76a", "dark_green": "#0e4a1a",
    "blue": "#2452a8", "bright_blue": "#5fa8ff", "dark_cyan": "#0e4a55",
    "cyan": "#1e8e9e", "bright_cyan": "#4fd8ee",
    "magenta": "#8e1e8e", "bright_magenta": "#e04fe0",
    "yellow": "#a88520", "bright_yellow": "#f0d84a",
    "red": "#a82424", "bright_red": "#ff5252",
    "white": "#d0d0d0", "bright_white": "#ffffff",
    "bright_black": "#555555",
    "grey50": "#808080", "grey62": "#9e9e9e",
}


def _color_auto(nombre: str, paleta: list[str]) -> str:
    h = 0
    for c in nombre:
        h = (h * 131 + ord(c)) & 0xFFFFFFFF
    return paleta[h % len(paleta)]


def color_terreno(nombre: str) -> str:
    return COLORES_TERRENO_RESERVADOS.get(nombre) or _color_auto(nombre, PALETA_TERRENOS)


def color_objeto(nombre: str) -> str:
    return COLORES_OBJETO_RESERVADOS.get(nombre) or _color_auto(nombre, PALETA_OBJETOS)


def color_faccion(nombre: str) -> str:
    return COLORES_FACCION_RESERVADOS.get(nombre) or _color_auto(nombre, PALETA_FACCIONES)


def _tk(rich_color: str, dark: float = 0.0) -> str:
    base = RICH_A_TK.get(rich_color, "#888888")
    if dark <= 0:
        return base
    r = int(base[1:3], 16)
    g = int(base[3:5], 16)
    b = int(base[5:7], 16)
    return f"#{int(r*(1-dark)):02x}{int(g*(1-dark)):02x}{int(b*(1-dark)):02x}"


# ============================================================
# App
# ============================================================

class JuegoTkinter:
    def __init__(self, mundo: Mundo):
        self.mundo = mundo
        self.root = tk.Tk()
        self.root.title("INSTINCT · El experimento del anciano")
        self.root.geometry("1200x760")
        self.root.configure(bg="#1a1a1a")

        # Estado
        self.modo = "prep"
        self.cursor = (0, 0)
        self.especie_actual: str | None = None
        self.velocidad = 10
        self.pausado = True
        self._after_id = None
        self._resize_job = None
        self._cell_size = 24
        self._ox = 0
        self._oy = 0
        self._rects: list[list[int]] = []
        self._texts: list[list[int]] = []

        self._construir_ui()
        self._seleccionar_mapa_inicial()
        self.root.bind("<Key>", self._on_key)

    def correr(self):
        self.root.mainloop()

    # ---------- Construcción de la UI ----------

    def _construir_ui(self):
        # Barra superior
        self.frame_top = tk.Frame(self.root, bg="#1a1a1a", height=44)
        self.frame_top.pack(fill="x", padx=10, pady=(10, 4))
        self.frame_top.pack_propagate(False)

        left = tk.Frame(self.frame_top, bg="#1a1a1a")
        left.pack(side="left", fill="y")
        tk.Label(left, text="Mapa:", fg="#ddd", bg="#1a1a1a",
                 font=("Courier", 11)).pack(side="left")
        self.mapa_var = tk.StringVar()
        self.combo_mapas = ttk.Combobox(
            left, textvariable=self.mapa_var,
            values=list(self.mundo.mapas), state="readonly", width=32,
        )
        self.combo_mapas.pack(side="left", padx=(6, 0))
        self.combo_mapas.bind("<<ComboboxSelected>>", self._on_mapa_cambiado)

        self.btn_modo = tk.Button(
            self.frame_top, text="▶ Iniciar simulación",
            command=self._toggle_modo,
            bg="#5a1a1a", fg="white", activebackground="#7a2a2a",
            activeforeground="white", relief="flat", bd=0,
            font=("Courier", 11, "bold"), padx=14, pady=6,
        )
        self.btn_modo.pack(side="right", padx=(8, 0))

        self.status_label = tk.Label(
            self.frame_top, text="", fg="#aaa", bg="#1a1a1a",
            font=("Courier", 10),
        )
        self.status_label.pack(side="right", padx=(0, 8))

        # Área principal
        self.frame_main = tk.Frame(self.root, bg="#1a1a1a")
        self.frame_main.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        self.canvas = tk.Canvas(
            self.frame_main, bg="#0a0a0a",
            highlightthickness=0, bd=0,
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.focus_set()

        self.sidebar = tk.Frame(self.frame_main, bg="#1a1a1a", width=300)
        self.sidebar.pack(side="right", fill="y", padx=(10, 0))
        self.sidebar.pack_propagate(False)

        self._crear_seccion_info()
        self._crear_seccion_especies()
        self._crear_seccion_controles()
        self._crear_seccion_logs()

        tk.Label(
            self.sidebar,
            text="Prep: Flechas · Enter · x · Tab · s\n"
                 "Sim: Espacio · n · +/- · r",
            fg="#666", bg="#1a1a1a", font=("Courier", 8),
            justify="left", anchor="w",
        ).pack(side="bottom", fill="x", pady=(8, 0))

    def _crear_seccion_info(self):
        tk.Label(self.sidebar, text="INFO", fg="#f88", bg="#1a1a1a",
                 font=("Courier", 10, "bold")).pack(anchor="w", pady=(0, 4))
        self.info_label = tk.Label(
            self.sidebar, text="", fg="#ddd", bg="#1a1a1a",
            justify="left", anchor="w", font=("Courier", 9),
            wraplength=290, height=7,
        )
        self.info_label.pack(fill="x", pady=(0, 12))

    def _crear_seccion_especies(self):
        self.frame_especies = tk.Frame(self.sidebar, bg="#1a1a1a")
        self.frame_especies.pack(fill="x", pady=(0, 12))
        tk.Label(self.frame_especies, text="ESPECIE", fg="#f88",
                 bg="#1a1a1a",
                 font=("Courier", 10, "bold")).pack(anchor="w", pady=(0, 4))
        self.especie_var = tk.StringVar()
        self.combo_especies = ttk.Combobox(
            self.frame_especies, textvariable=self.especie_var,
            values=list(self.mundo.especies), state="readonly",
        )
        self.combo_especies.pack(fill="x")
        self.combo_especies.bind("<<ComboboxSelected>>", self._on_especie_cambiada)

    def _crear_seccion_controles(self):
        self.frame_controles = tk.Frame(self.sidebar, bg="#1a1a1a")
        self.frame_controles.pack(fill="x", pady=(0, 12))
        tk.Label(self.frame_controles, text="CONTROLES", fg="#f88",
                 bg="#1a1a1a",
                 font=("Courier", 10, "bold")).pack(anchor="w", pady=(0, 4))

        self.btn_play = tk.Button(
            self.frame_controles, text="▶ Play",
            command=self._toggle_play, state="disabled",
            bg="#2a2a2a", fg="white", activebackground="#3a3a3a",
            activeforeground="white", relief="flat", bd=0,
            font=("Courier", 10), pady=4,
        )
        self.btn_play.pack(fill="x", pady=2)

        self.btn_step = tk.Button(
            self.frame_controles, text="⏭ Step",
            command=self._step, state="disabled",
            bg="#2a2a2a", fg="white", activebackground="#3a3a3a",
            activeforeground="white", relief="flat", bd=0,
            font=("Courier", 10), pady=4,
        )
        self.btn_step.pack(fill="x", pady=2)

        frame_vel = tk.Frame(self.frame_controles, bg="#1a1a1a")
        frame_vel.pack(fill="x", pady=6)
        tk.Label(frame_vel, text="Velocidad:", fg="#aaa",
                 bg="#1a1a1a", font=("Courier", 9)).pack(side="left")
        self.vel_label = tk.Label(frame_vel, text="10 t/s", fg="#ddd",
                                  bg="#1a1a1a",
                                  font=("Courier", 9, "bold"))
        self.vel_label.pack(side="right")

        self.btn_reiniciar = tk.Button(
            self.frame_controles, text="⟲ Reiniciar",
            command=self._reiniciar, state="disabled",
            bg="#2a2a2a", fg="white", activebackground="#3a3a3a",
            activeforeground="white", relief="flat", bd=0,
            font=("Courier", 10), pady=4,
        )
        self.btn_reiniciar.pack(fill="x", pady=2)

    def _crear_seccion_logs(self):
        tk.Label(self.sidebar, text="LOGS", fg="#f88", bg="#1a1a1a",
                 font=("Courier", 10, "bold")).pack(anchor="w", pady=(0, 4))
        self.logs_text = tk.Text(
            self.sidebar, height=10, bg="#0a0a0a", fg="#ccc",
            font=("Courier", 8), wrap="word", state="disabled",
            bd=0, highlightthickness=0,
        )
        self.logs_text.pack(fill="both", expand=True)

    # ---------- Selección de mapa ----------

    def _seleccionar_mapa_inicial(self):
        if not self.mundo.mapas:
            self.status_label.config(text="No hay mapas cargados")
            return
        nombre = list(self.mundo.mapas)[0]
        self.mapa_var.set(nombre)
        self.mundo.elegir_mapa(nombre)
        self._post_mapa()
        for err in self.mundo.errores_carga:
            self.mundo.logs.append(f"[carga] {err}")
        self._actualizar_logs()

    def _on_mapa_cambiado(self, _evt):
        nombre = self.mapa_var.get()
        if nombre in self.mundo.mapas:
            self.mundo.elegir_mapa(nombre)
            self._post_mapa()
        self.canvas.focus_set()

    def _on_especie_cambiada(self, _evt):
        self.especie_actual = self.especie_var.get()
        self._redibujar()
        self.canvas.focus_set()

    def _post_mapa(self):
        mapa = self.mundo.mapa
        if mapa is None:
            return
        self.cursor = (mapa.width // 2, mapa.height // 2)
        especies = list(self.mundo.especies)
        if especies:
            if self.especie_actual not in especies:
                self.especie_actual = especies[0]
            self.especie_var.set(self.especie_actual)

        self.modo = "prep"
        self.pausado = True
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None

        self.frame_especies.pack(fill="x", pady=(0, 12), before=self.frame_controles)
        self.btn_modo.config(text="▶ Iniciar simulación")
        self.btn_play.config(state="disabled", text="▶ Play")
        self.btn_step.config(state="disabled")
        self.btn_reiniciar.config(state="disabled")
        self.root.after(100, self._rebuild_y_dibujar)

    # ---------- Canvas ----------

    def _rebuild_y_dibujar(self):
        if self.canvas.winfo_width() < 50:
            self.root.after(60, self._rebuild_y_dibujar)
            return
        self._rebuild_canvas()
        self._redibujar()

    def _rebuild_canvas(self):
        self.canvas.delete("all")
        self._rects = []
        self._texts = []
        mapa = self.mundo.mapa
        if mapa is None:
            return

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        cell = max(6, min(24, cw // mapa.width, ch // mapa.height))
        self._cell_size = cell

        gw = cell * mapa.width
        gh = cell * mapa.height
        self._ox = (cw - gw) // 2
        self._oy = (ch - gh) // 2

        font = ("Courier", max(6, cell - 9), "bold")
        for y in range(mapa.height):
            fila_r = []
            fila_t = []
            for x in range(mapa.width):
                px = self._ox + x * cell
                py = self._oy + y * cell
                fila_r.append(self.canvas.create_rectangle(
                    px, py, px + cell, py + cell,
                    fill="#222", outline="#111",
                ))
                fila_t.append(self.canvas.create_text(
                    px + cell / 2, py + cell / 2,
                    text="?", fill="white", font=font,
                ))
            self._rects.append(fila_r)
            self._texts.append(fila_t)

    def _on_resize(self, _evt):
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(200, self._verificar_resize)

    def _verificar_resize(self):
        if self.mundo.mapa is None:
            return
        self._rebuild_canvas()
        self._redibujar()

    def _redibujar(self):
        mapa = self.mundo.mapa
        if mapa is None or not self._rects:
            return

        for y in range(mapa.height):
            for x in range(mapa.width):
                cell = mapa.casillas[y][x]
                rect = self._rects[y][x]
                text = self._texts[y][x]

                if cell.criatura is not None and cell.criatura.viva:
                    color = color_faccion(cell.criatura.program.faction)
                    letra = cell.criatura.program.name[0].upper()
                    bg = _tk(color, dark=0.30)
                    fg = "#ffffff"
                elif cell.objeto is not None:
                    color = color_objeto(cell.objeto.nombre)
                    letra = cell.objeto.char
                    bg = _tk(color, dark=0.55)
                    fg = RICH_A_TK.get(color, "#ffffff")
                else:
                    color = color_terreno(cell.terreno.nombre)
                    letra = cell.terreno.char
                    bg = _tk(color, dark=0.78)
                    fg = RICH_A_TK.get(color, "#ffffff")

                es_cursor = (x, y) == self.cursor
                outline = "#ffff00" if es_cursor else "#111111"
                width = 2 if es_cursor else 1

                self.canvas.itemconfig(rect, fill=bg, outline=outline, width=width)
                self.canvas.itemconfig(text, text=letra, fill=fg)

        self._actualizar_info()
        self._actualizar_status()
        self._actualizar_logs()

    # ---------- Paneles ----------

    def _actualizar_info(self):
        mapa = self.mundo.mapa
        if mapa is None:
            self.info_label.config(text="(sin mapa)")
            return
        cx, cy = self.cursor
        if not (0 <= cx < mapa.width and 0 <= cy < mapa.height):
            return
        cell = mapa.casillas[cy][cx]
        lineas = [f"Cursor: ({cx}, {cy})"]
        if cell.criatura is not None and cell.criatura.viva:
            c = cell.criatura
            lineas.append(f"Criatura: {c.program.name}")
            lineas.append(f" facción: {c.program.faction}")
            lineas.append(f" hp: {c.health}/{c.program.health}")
            lineas.append(f" edad: {c.age}/{c.program.lifespan}")
        elif cell.objeto is not None:
            lineas.append(f"Objeto: {cell.objeto.nombre}")
            lineas.append(
                f" reserva: {cell.objeto.resource}/{cell.objeto.resource_max}"
            )
        else:
            lineas.append(f"Terreno: {cell.terreno.nombre}")
            lineas.append(
                f" reserva: {cell.terreno.resource}/{cell.terreno.resource_max}"
            )
        if self.modo == "prep":
            lineas.append("")
            lineas.append(f"Especie: {self.especie_actual or '(ninguna)'}")
        self.info_label.config(text="\n".join(lineas))

    def _actualizar_status(self):
        mapa = self.mundo.mapa
        if mapa is None:
            self.status_label.config(text="")
            return
        vivas = len(mapa.criaturas)
        if self.modo == "prep":
            estado = "PREPARACIÓN"
        else:
            estado = "PAUSA" if self.pausado else "▶"
        self.status_label.config(
            text=f"{estado} · tick {self.mundo.tick} · "
                 f"{self.velocidad} t/s · {vivas} vivas"
        )

    def _actualizar_logs(self):
        if not self.mundo.logs:
            return
        self.logs_text.config(state="normal")
        self.logs_text.delete("1.0", "end")
        for log in self.mundo.logs[-40:]:
            self.logs_text.insert("end", log + "\n")
        self.logs_text.see("end")
        self.logs_text.config(state="disabled")

    # ---------- Acciones ----------

    def _mover_cursor(self, keysym: str):
        mapa = self.mundo.mapa
        if mapa is None:
            return
        cx, cy = self.cursor
        if keysym == "Up":
            cy = max(0, cy - 1)
        elif keysym == "Down":
            cy = min(mapa.height - 1, cy + 1)
        elif keysym == "Left":
            cx = max(0, cx - 1)
        elif keysym == "Right":
            cx = min(mapa.width - 1, cx + 1)
        self.cursor = (cx, cy)
        self._redibujar()

    def _colocar(self):
        if not self.especie_actual:
            return
        if self.mundo.puede_colocar(*self.cursor):
            self.mundo.colocar_criatura(self.especie_actual, *self.cursor)
            self._redibujar()

    def _ciclar_especie(self):
        especies = list(self.mundo.especies)
        if not especies:
            return
        try:
            i = especies.index(self.especie_actual)
        except ValueError:
            i = 0
        self.especie_actual = especies[(i + 1) % len(especies)]
        self.especie_var.set(self.especie_actual)
        self._redibujar()

    def _toggle_modo(self):
        if self.modo == "prep":
            self.modo = "sim"
            self.pausado = False
            self.frame_especies.pack_forget()
            self.btn_modo.config(text="⏸ Pausa")
            self.btn_play.config(state="normal", text="⏸ Pausa")
            self.btn_step.config(state="normal")
            self.btn_reiniciar.config(state="normal")
            self._update_vel_label()
            self._redibujar()
            self._schedule_tick()
        else:
            self._reiniciar()

    def _toggle_play(self):
        if self.modo != "sim":
            return
        self.pausado = not self.pausado
        label = "▶ Play" if self.pausado else "⏸ Pausa"
        self.btn_play.config(text=label)
        self.btn_modo.config(text=label)
        if self.pausado:
            if self._after_id:
                self.root.after_cancel(self._after_id)
                self._after_id = None
        else:
            self._schedule_tick()
        self._redibujar()

    def _step(self):
        if self.modo != "sim":
            return
        self.pausado = True
        self.btn_play.config(text="▶ Play")
        self.btn_modo.config(text="▶ Play")
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self.mundo.simular_tick()
        self._redibujar()

    def _reiniciar(self):
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        mapa = self.mundo.mapa
        if mapa is None:
            return
        nombre = mapa.nombre
        self.mundo.elegir_mapa(nombre)
        self._post_mapa()

    def _update_vel_label(self):
        self.vel_label.config(text=f"{self.velocidad} t/s")

    def _schedule_tick(self):
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        if self.modo == "sim" and not self.pausado:
            intervalo = max(16, int(1000 / self.velocidad))
            self._after_id = self.root.after(intervalo, self._tick)

    def _tick(self):
        self._after_id = None
        if self.modo != "sim" or self.pausado:
            return
        self.mundo.simular_tick()
        self._redibujar()
        self._schedule_tick()

    # ---------- Eventos ----------

    def _on_key(self, evt):
        mapa = self.mundo.mapa
        if mapa is None:
            return
        k = evt.keysym

        if k in ("Up", "Down", "Left", "Right"):
            self._mover_cursor(k)
        elif k == "space" and self.modo == "sim":
            self._toggle_play()
        elif k.lower() == "n" and self.modo == "sim":
            self._step()
        elif k.lower() == "r" and self.modo == "sim":
            self._reiniciar()
        elif k in ("plus", "equal") and self.modo == "sim":
            self.velocidad = min(self.velocidad * 2, 60)
            self._update_vel_label()
            self._redibujar()
        elif k == "minus" and self.modo == "sim":
            self.velocidad = max(self.velocidad // 2, 1)
            self._update_vel_label()
            self._redibujar()
        elif k == "Tab" and self.modo == "prep":
            self._ciclar_especie()
        elif k == "Return" and self.modo == "prep":
            self._colocar()
        elif k.lower() == "x" and self.modo == "prep":
            self.mundo.quitar_criatura(*self.cursor)
            self._redibujar()
        elif k.lower() == "s" and self.modo == "prep":
            self._toggle_modo()

    def _on_click(self, evt):
        mapa = self.mundo.mapa
        if mapa is None:
            return
        x = (evt.x - self._ox) // self._cell_size
        y = (evt.y - self._oy) // self._cell_size
        if 0 <= x < mapa.width and 0 <= y < mapa.height:
            self.cursor = (x, y)
            self.canvas.focus_set()
            self._redibujar()

    def _on_double_click(self, evt):
        if self.modo != "prep":
            return
        mapa = self.mundo.mapa
        if mapa is None:
            return
        x = (evt.x - self._ox) // self._cell_size
        y = (evt.y - self._oy) // self._cell_size
        if not (0 <= x < mapa.width and 0 <= y < mapa.height):
            return
        self.cursor = (x, y)
        if self.mundo.puede_colocar(x, y):
            self._colocar()
        else:
            self.mundo.quitar_criatura(x, y)
            self._redibujar()