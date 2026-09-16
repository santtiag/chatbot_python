"""Temas visuales de la consola (Rich). No cambian la lógica del chat."""

from __future__ import annotations

from rich.theme import Theme

_CORREO = {
    "mail.kicker": "bold dim cyan",
    "mail.label": "bold dim",
    "mail.value": "bold",
    "mail.title": "bold cyan",
    "mail.border": "cyan",
    "mail.rule": "dim cyan",
    "mail.ok": "bold green",
    "mail.warn": "bold red",
}

TEMAS: dict[str, Theme] = {
    "clasico": Theme(
        {
            "banner": "bold cyan",
            "user": "bold green",
            "agent": "bold magenta",
            "ok": "bold green",
            "error": "bold red",
            "muted": "dim",
            **_CORREO,
        }
    ),
    "oscuro": Theme(
        {
            "banner": "bold white on rgb(20,24,32)",
            "user": "bold bright_cyan",
            "agent": "bold bright_white",
            "ok": "bold bright_green",
            "error": "bold bright_red",
            "muted": "grey70",
            "mail.kicker": "bold bright_cyan",
            "mail.label": "grey70",
            "mail.value": "bold bright_white",
            "mail.title": "bold bright_cyan",
            "mail.border": "bright_cyan",
            "mail.rule": "grey50",
            "mail.ok": "bold bright_green",
            "mail.warn": "bold bright_red",
        }
    ),
    "universidad": Theme(
        {
            "banner": "bold white on dark_red",
            "user": "bold gold1",
            "agent": "bold cyan",
            "ok": "bold green",
            "error": "bold red",
            "muted": "italic dim",
            "mail.kicker": "bold gold1",
            "mail.label": "dim gold1",
            "mail.value": "bold",
            "mail.title": "bold gold1",
            "mail.border": "gold1",
            "mail.rule": "dark_red",
            "mail.ok": "bold green",
            "mail.warn": "bold red",
        }
    ),
}

NOMBRES_TEMA = tuple(TEMAS.keys())


def obtener_tema(nombre: str) -> Theme:
    clave = (nombre or "clasico").strip().lower()
    if clave not in TEMAS:
        conocidos = ", ".join(NOMBRES_TEMA)
        raise ValueError(f"Tema desconocido: {nombre}. Usa uno de: {conocidos}")
    return TEMAS[clave]
