"""Outbox TUI: borrador, envío y recibo del correo de inscripción."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from src.email_service import formatear_costo


def _meta(filas: list[tuple[str, str]]) -> Table:
    tabla = Table.grid(padding=(0, 2), expand=True)
    tabla.add_column(style="mail.label", min_width=11, no_wrap=True)
    tabla.add_column(style="mail.value", overflow="fold")
    for etiqueta, valor in filas:
        tabla.add_row(etiqueta.upper(), valor)
    return tabla


def _ficha_curso(curso: dict[str, Any]) -> Table:
    tabla = Table(
        box=box.SIMPLE,
        show_header=False,
        expand=True,
        pad_edge=False,
        border_style="mail.rule",
    )
    tabla.add_column(style="mail.label", min_width=12, no_wrap=True)
    tabla.add_column(style="mail.value", overflow="fold")
    tabla.add_row("código", str(curso.get("id", "")))
    tabla.add_row("curso", str(curso.get("nombre", "")))
    tabla.add_row("modalidad", str(curso.get("modalidad", "")))
    tabla.add_row("duración", str(curso.get("duracion", "")))
    tabla.add_row("costo", formatear_costo(curso.get("costo")))
    tabla.add_row("requisitos", str(curso.get("requisitos", "")))
    return tabla


def panel_borrador(
    destinatario: str,
    remitente: str,
    host: str,
    port: int,
    usar_tls: bool,
    curso: dict[str, Any],
) -> Panel:
    transporte = "STARTTLS" if usar_tls else "SSL"
    cuerpo: RenderableType = Group(
        Text("OUTBOX · SMTP", style="mail.kicker"),
        _meta(
            [
                ("de", remitente or "—"),
                ("para", destinatario),
                ("asunto", f"Inscripción · {curso.get('id', '')} · {curso.get('nombre', '')}"),
                ("vía", f"{host}:{port}  {transporte}"),
            ]
        ),
        Rule(style="mail.rule"),
        Text("FICHA DEL CURSO", style="mail.label"),
        _ficha_curso(curso),
        Text(str(curso.get("descripcion", "")), style="muted"),
    )
    return Panel(
        cuerpo,
        title="[mail.title]correo de inscripción[/mail.title]",
        subtitle="[muted]listo para SMTP[/muted]",
        border_style="mail.border",
        padding=(1, 2),
    )


def panel_recibo(destinatario: str, curso: dict[str, Any], cuando: datetime) -> Panel:
    marca = cuando.strftime("%Y-%m-%d  %H:%M:%S")
    cuerpo = Group(
        Text("●  ENTREGADO", style="mail.ok"),
        Text("El servidor SMTP aceptó el mensaje.", style="muted"),
        Rule(style="mail.rule"),
        _meta(
            [
                ("para", destinatario),
                ("curso", f"{curso.get('id', '')}  ·  {curso.get('nombre', '')}"),
                ("hora", marca),
                ("estado", "250  queued / sent"),
            ]
        ),
    )
    return Panel(
        cuerpo,
        title="[mail.ok]recibo[/mail.ok]",
        border_style="ok",
        padding=(1, 2),
    )


def panel_fallo(detalle: str) -> Panel:
    cuerpo = Group(
        Text("●  NO ENVIADO", style="mail.warn"),
        Text("SMTP rechazó o no alcanzó el servidor.", style="muted"),
        Rule(style="mail.rule"),
        Text(detalle, style="error"),
    )
    return Panel(
        cuerpo,
        title="[mail.warn]error de envío[/mail.warn]",
        border_style="error",
        padding=(1, 2),
    )
