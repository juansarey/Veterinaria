"""Punto de entrada de la aplicación.

    python src/veterinaria/main.py            aplicación de escritorio
    python src/veterinaria/main.py --demo     además carga datos de demostración si la base está vacía
    python src/veterinaria/main.py --web      se abre en el navegador (http://localhost:8550)
"""

import os
import sys
from pathlib import Path

if __package__ in (None, ""):          # ejecución directa del archivo
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import flet as ft

from veterinaria.interfaz.app import AplicacionVeterinaria
from veterinaria.servicios.datos_demo import cargar_demo, hay_datos
from veterinaria.servicios.fachada import Servicios


def ruta_base_datos() -> Path:
    return Path(os.environ.get("VETERINARIA_DB", Path.cwd() / "veterinaria.db"))


def preparar_servicios(demo: bool = False) -> tuple[Servicios, Path]:
    ruta = ruta_base_datos()
    servicios = Servicios(ruta)
    if demo and not hay_datos(servicios):
        print("Cargando datos de demostración...")
        cargar_demo(servicios)
    return servicios, ruta


def main(page: ft.Page):
    servicios, ruta = preparar_servicios("--demo" in sys.argv)
    page.window.width, page.window.height = 1360, 860
    AplicacionVeterinaria(page, servicios, ruta).iniciar()


if __name__ == "__main__":
    if "--web" in sys.argv:
        ft.run(main, view=ft.AppView.WEB_BROWSER, port=8550)
    else:
        ft.run(main)
