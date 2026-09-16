"""Cerebro local: Ollama granite4.2, memoria en lista y JSON de acción nativo."""

from __future__ import annotations

import json
import re
from typing import Any

import requests

JSON_INSCRIPCION = (
    '{"accion":"enviar_correo","correo":"estudiante@correo.com","curso_id":"PY-101"}'
)


class MemoriaConversacion:
    """Historial de chat como lista de diccionarios role/content."""

    def __init__(self) -> None:
        self.mensajes: list[dict[str, str]] = []

    def append(self, role: str, content: str) -> None:
        self.mensajes.append({"role": role, "content": content})

    def como_lista(self) -> list[dict[str, str]]:
        return list(self.mensajes)


class AgenteAsesor:
    """Habla con Ollama y detecta la orden estructurada de envío de correo."""

    def __init__(
        self,
        catalogo_texto: str,
        host: str,
        model: str,
        num_gpu: int = -1,
        num_ctx: int = 8192,
        temperature: float = 0.2,
        keep_alive: str = "30m",
        timeout: int = 180,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.num_gpu = num_gpu
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.keep_alive = keep_alive
        self.timeout = timeout
        self.memoria = MemoriaConversacion()
        self.memoria.append("system", self._system_prompt(catalogo_texto))

    def comprobar_ollama(self) -> dict[str, Any]:
        try:
            version = requests.get(f"{self.host}/api/version", timeout=5)
            version.raise_for_status()
        except requests.RequestException as exc:
            raise ConnectionError(
                f"Ollama no responde en {self.host}. Arranca el servicio e intenta de nuevo."
            ) from exc

        etiquetas = requests.get(f"{self.host}/api/tags", timeout=5)
        etiquetas.raise_for_status()
        nombres = [item.get("name", "") for item in etiquetas.json().get("models", [])]
        if not any(nombre.startswith(self.model) for nombre in nombres):
            raise FileNotFoundError(
                f"No está el modelo {self.model}. Ejecuta: ollama pull {self.model}"
            )
        return version.json()

    def procesador_activo(self) -> str:
        try:
            estado = requests.get(f"{self.host}/api/ps", timeout=5)
            estado.raise_for_status()
            modelos = estado.json().get("models", [])
        except requests.RequestException:
            return "desconocido"
        for item in modelos:
            if str(item.get("name", "")).startswith(self.model):
                procesador = item.get("processor") or item.get("gpu") or ""
                if procesador:
                    return str(procesador)
                detalles = item.get("details") or {}
                familias = detalles.get("families") or detalles.get("family")
                return str(familias or "cargado")
        return "modelo aún no residente"

    def responder(self, texto_usuario: str) -> str:
        self.memoria.append("user", texto_usuario)
        cuerpo = {
            "model": self.model,
            "messages": self.memoria.como_lista(),
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "num_gpu": self.num_gpu,
                "num_ctx": self.num_ctx,
                "temperature": self.temperature,
            },
        }
        respuesta = requests.post(
            f"{self.host}/api/chat",
            json=cuerpo,
            timeout=self.timeout,
        )
        respuesta.raise_for_status()
        mensaje = (respuesta.json().get("message") or {}).get("content", "")
        texto = self._limpiar_respuesta(mensaje)
        self.memoria.append("assistant", texto)
        return texto

    def extraer_accion(self, texto: str) -> dict[str, Any] | None:
        candidato = self._buscar_json(texto)
        if not isinstance(candidato, dict):
            return None
        if candidato.get("accion") != "enviar_correo":
            return None
        correo = str(candidato.get("correo", "")).strip()
        curso_id = str(candidato.get("curso_id", "")).strip()
        if not correo or not curso_id:
            return None
        return {"accion": "enviar_correo", "correo": correo, "curso_id": curso_id}

    def _system_prompt(self, catalogo_texto: str) -> str:
        return (
            "Eres un asesor académico de cursos online. Solo puedes hablar de la "
            "oferta siguiente; no inventes cursos, precios ni requisitos.\n\n"
            f"OFERTA:\n{catalogo_texto}\n\n"
            "Reglas:\n"
            "1. Responde en español, breve y concreto.\n"
            "2. Recuerda lo que el usuario ya dijo en esta conversación.\n"
            "3. Si pide inscribirse pero no ha dado un correo válido, pídele el correo "
            "y confirma el curso (usa el id).\n"
            "4. Cuando haya interés real de inscripción, un curso de la oferta y un "
            "correo, responde ÚNICAMENTE con un JSON válido, sin markdown ni texto "
            f"alrededor, con esta forma exacta: {JSON_INSCRIPCION}\n"
            "5. No envíes JSON si solo está explorando o comparando cursos.\n"
        )

    def _limpiar_respuesta(self, texto: str) -> str:
        limpio = texto.strip()
        limpio = re.sub(r"<think>.*?</think>", "", limpio, flags=re.DOTALL | re.IGNORECASE)
        limpio = re.sub(r"<thinking>.*?</thinking>", "", limpio, flags=re.DOTALL | re.IGNORECASE)
        return limpio.strip()

    def _buscar_json(self, texto: str) -> Any:
        limpio = texto.strip()
        cerca = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", limpio, flags=re.DOTALL)
        if cerca:
            limpio = cerca.group(1)
        try:
            return json.loads(limpio)
        except json.JSONDecodeError:
            inicio = limpio.find("{")
            fin = limpio.rfind("}")
            if inicio == -1 or fin <= inicio:
                return None
            try:
                return json.loads(limpio[inicio : fin + 1])
            except json.JSONDecodeError:
                return None
