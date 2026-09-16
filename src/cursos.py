"""Descarga y consulta de la oferta de cursos remota."""

from __future__ import annotations

import json
import re
from typing import Any

import requests

_BLOB_GITHUB = re.compile(
    r"^https?://github\.com/(?P<user>[^/]+)/(?P<repo>[^/]+)/blob/(?P<rest>.+)$"
)

CAMPOS_OBLIGATORIOS = (
    "id",
    "nombre",
    "descripcion",
    "modalidad",
    "duracion",
    "costo",
    "requisitos",
)


class CatalogoCursos:
    """Oferta académica cargada con requests desde un JSON remoto."""

    def __init__(self, url: str, timeout: int = 20) -> None:
        self.url = self._url_raw(url.strip())
        self.timeout = timeout
        self.cursos: list[dict[str, Any]] = []

    def cargar(self) -> list[dict[str, Any]]:
        if not self.url:
            raise ValueError(
                "Falta CURSOS_URL. Publica data/cursos.json en GitHub y pega la URL raw en .env."
            )
        try:
            respuesta = requests.get(self.url, timeout=self.timeout)
            respuesta.raise_for_status()
            payload = respuesta.json()
        except requests.JSONDecodeError as exc:
            raise ValueError(
                "La URL no devolvió JSON. Usa la versión raw de GitHub "
                "(raw.githubusercontent.com/…/cursos.json), no el enlace /blob/ del visor."
            ) from exc
        except requests.RequestException as exc:
            raise ConnectionError(
                f"No pude descargar cursos.json desde {self.url}: {exc}"
            ) from exc
        if isinstance(payload, list):
            cursos = payload
        elif isinstance(payload, dict):
            cursos = payload.get("cursos")
        else:
            cursos = None
        if not isinstance(cursos, list) or not cursos:
            raise ValueError("El JSON remoto no contiene una lista de cursos.")
        for curso in cursos:
            faltantes = [campo for campo in CAMPOS_OBLIGATORIOS if campo not in curso]
            if faltantes:
                raise ValueError(
                    f"El curso {curso.get('id', '(sin id)')} no tiene: {', '.join(faltantes)}"
                )
        self.cursos = cursos
        return self.cursos

    def por_id(self, curso_id: str) -> dict[str, Any] | None:
        buscado = str(curso_id).strip().lower()
        for curso in self.cursos:
            if str(curso.get("id", "")).strip().lower() == buscado:
                return curso
        return None

    def texto_para_prompt(self) -> str:
        return json.dumps(self.cursos, ensure_ascii=False, indent=2)

    def _url_raw(self, url: str) -> str:
        encontrado = _BLOB_GITHUB.match(url)
        if encontrado is None:
            return url
        return (
            "https://raw.githubusercontent.com/"
            f"{encontrado['user']}/{encontrado['repo']}/{encontrado['rest']}"
        )
