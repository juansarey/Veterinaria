"""El botón «Derivar a laboratorio» del historial lleva al formulario de derivación."""

import asyncio
from datetime import datetime

from test_pantallas import pestana, ui  # noqa: F401  (fixture)
from veterinaria.dominio.clinica.atencion import TipoAtencion
from veterinaria.interfaz import seccion_atencion as sa


def test_boton_de_la_tabla_preselecciona_avisa_desplaza_y_enfoca(ui, monkeypatch):  # noqa: F811
    app, pag = ui
    srv = app.servicios
    cliente = srv.clinica.crear_cliente("Ana", "Pérez", "0012345")
    mascota = srv.clinica.crear_mascota(cliente, "Luna", "Perro", abrir_historia=True)
    clinica = srv.clinica.crear_clinica("Centro", "Calle 1")
    vet = srv.clinica.crear_veterinario(clinica, "Luis", "Gómez", "MP-1")
    srv.atencion.registrar_atencion(mascota, vet, datetime(2026, 11, 1, 9), TipoAtencion.CONSULTA, "Uno")
    segunda = srv.atencion.registrar_atencion(mascota, vet, datetime(2026, 11, 2, 9), TipoAtencion.CONSULTA, "Dos")
    app.ir_a(2)
    at = pestana(app, sa.PestanaAtenciones)

    llamadas = []

    async def scroll_to(**kwargs):
        llamadas.append(("scroll", kwargs["scroll_key"]))

    async def focus():
        llamadas.append(("foco", at.estudio.label))

    monkeypatch.setattr(at.columna, "scroll_to", scroll_to, raising=False)
    monkeypatch.setattr(at.estudio, "focus", focus, raising=False)
    pag.run_task = lambda corrutina: asyncio.run(corrutina())

    fila = next(r for r in at.tabla.rows if r.cells[0].content.value == "02/11/2026 09:00")
    boton = fila.cells[-1].content.controls[0]
    assert boton.tooltip == "Derivar a laboratorio"
    boton.on_click(None)

    assert at.atencion.value == str(segunda)
    assert any(f"Atención #{segunda} seleccionada" in m for m in pag.mensajes)
    assert at.tarjeta_derivar.key.value == at.CLAVE_DERIVAR
    assert at.tarjeta_derivar in at.columna.controls
    assert llamadas == [("scroll", at.CLAVE_DERIVAR), ("foco", "Estudio solicitado")]
