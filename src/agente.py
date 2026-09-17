"""Cerebro local: Ollama, memoria en lista y JSON de acción nativo."""

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
        num_ctx: int = 4096,
        temperature: float = 0.2,
        keep_alive: str = "30m",
        timeout: int = 600,
        num_predict: int = 384,
        think: bool = False,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.num_gpu = num_gpu
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.keep_alive = keep_alive
        self.timeout = timeout
        self.num_predict = num_predict
        self.think = think
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
        if not any(self._mismo_modelo(nombre) for nombre in nombres):
            raise FileNotFoundError(
                "No está el modelo configurado en OLLAMA_MODEL. "
                "Revisa el nombre y ejecuta ollama pull."
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
            if self._mismo_modelo(str(item.get("name", ""))):
                procesador = item.get("processor") or item.get("gpu") or ""
                if procesador:
                    return str(procesador)
                detalles = item.get("details") or {}
                familias = detalles.get("families") or detalles.get("family")
                return str(familias or "cargado")
        return "modelo aún no residente"

    def _mismo_modelo(self, nombre: str) -> bool:
        pedido = self.model.split(":")[0]
        instalado = nombre.split(":")[0]
        return nombre == self.model or instalado == pedido or nombre.startswith(f"{pedido}:")

    def _opciones(self, num_ctx: int | None = None, num_predict: int | None = None) -> dict[str, Any]:
        return {
            "num_gpu": self.num_gpu,
            "num_ctx": self.num_ctx if num_ctx is None else num_ctx,
            "temperature": self.temperature,
            "num_predict": self.num_predict if num_predict is None else num_predict,
        }

    def precargar(self) -> None:
        """Deja el modelo residente en GPU para que el primer turno no expire."""
        self._chat(
            [{"role": "user", "content": "ok"}],
            num_ctx=min(2048, self.num_ctx),
            num_predict=1,
        )

    def responder(self, texto_usuario: str) -> str:
        self.memoria.append("user", texto_usuario)
        texto = self._chat(self.memoria.como_lista())
        self.memoria.append("assistant", texto)
        return texto

    def _chat(
        self,
        mensajes: list[dict[str, str]],
        num_ctx: int | None = None,
        num_predict: int | None = None,
    ) -> str:
        cuerpo = {
            "model": self.model,
            "messages": mensajes,
            "stream": True,
            "think": self.think,
            "keep_alive": self.keep_alive,
            "options": self._opciones(num_ctx=num_ctx, num_predict=num_predict),
        }
        try:
            with requests.post(
                f"{self.host}/api/chat",
                json=cuerpo,
                stream=True,
                timeout=(10, self.timeout),
            ) as respuesta:
                respuesta.raise_for_status()
                partes: list[str] = []
                for linea in respuesta.iter_lines():
                    if not linea:
                        continue
                    dato = json.loads(linea)
                    error = dato.get("error")
                    if error:
                        raise RuntimeError(str(error))
                    mensaje = dato.get("message") or {}
                    partes.append(str(mensaje.get("content") or ""))
                return self._limpiar_respuesta("".join(partes))
        except requests.exceptions.ReadTimeout as exc:
            raise TimeoutError(
                f"Ollama no terminó en {self.timeout}s. "
                "Deja el modelo cargado (ollama ps), usa OLLAMA_THINK=false "
                "y prueba OLLAMA_NUM_CTX=4096."
            ) from exc
        except requests.RequestException as exc:
            raise ConnectionError(f"No pude hablar con Ollama: {exc}") from exc

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
            "6. No razones en voz alta ni uses etiquetas think/thinking. "
            "Responde en pocas frases.\n"
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
