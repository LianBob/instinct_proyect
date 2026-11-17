# main.py
from simulador import Mundo
from ui_tkinter import JuegoTkinter


def main() -> None:
    mundo = Mundo(ruta_base=".", semilla=42)
    mundo.cargar_todo()

    if mundo.errores_carga:
        print("Avisos / errores de carga:")
        for e in mundo.errores_carga:
            print("  -", e)
        print()

    JuegoTkinter(mundo).correr()


if __name__ == "__main__":
    main()