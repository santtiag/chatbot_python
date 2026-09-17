# Agente de asesoría académica

Prototipo del primer parcial: un asesor en consola que lee la oferta de cursos desde GitHub, conversa con un **modelo local servido por Ollama** (`openbmb/minicpm5-2b`) y envía un correo con `smtplib` cuando detecta una inscripción real.

Diagrama interactivo (Archify): [docs/arquitectura.html](docs/arquitectura.html).

La interfaz fija del visor Archify (`<html lang>` y botones Light/Dark, Present, Export) queda en inglés. El contenido del diagrama (títulos, nodos, relaciones y tarjetas) está en español.

## Requisitos

- Python 3.11+ (el proyecto se instala con `uv`)
- [Ollama](https://ollama.com) con el modelo indicado en `OLLAMA_MODEL`
- GPU detectada por Ollama (NVIDIA/AMD según tu equipo)
- Un `cursos.json` público en GitHub
- Cuenta SMTP (Gmail con contraseña de aplicación, u otro host)

## Cómo ejecutarlo

```bash
cd prototipo
uv sync
cp .env.example .env   # si aún no tienes .env
```

En `.env`:

- `CURSOS_URL`: URL **raw** de GitHub, por ejemplo `https://raw.githubusercontent.com/<usuario>/<repo>/main/data/cursos.json`
- `OLLAMA_MODEL=openbmb/minicpm5-2b`
- `OLLAMA_NUM_GPU=-1` (todas las capas a GPU)
- `OLLAMA_THINK=false` (evita razonamiento largo que hace timeout)
- `OLLAMA_NUM_CTX=4096` y `OLLAMA_TIMEOUT=600`
- `SMTP_*` con tus credenciales de correo

Descarga el modelo si hace falta:

```bash
ollama pull openbmb/minicpm5-2b
```

Arranque:

```bash
uv run asesor
uv run asesor --tema oscuro
uv run asesor --tema universidad
```

Salida limpia: escribe `salir` o `exit`, o `Ctrl+C`.

Para Moodle / pip clásico:

```bash
pip install -r requirements.txt
python -m src.main --tema clasico
```

## Decisión de arquitectura: ¿qué API de IA se utilizó y por qué?

No usamos una API de nube (Gemini, Groq u OpenAI). El cerebro es un **modelo local** expuesto por **Ollama** en `http://127.0.0.1:11434/api/chat`. El modelo concreto es **`openbmb/minicpm5-2b`**, configurable en `.env` (`OLLAMA_MODEL`) sin reescribir el agente.

Ollama se eligió porque es sencillo de implementar: se instala, se hace `pull` del modelo y el programa habla con él por HTTP nativo (`requests`), sin LangChain ni LlamaIndex, tal como pide el enunciado.

Se eligió **inferencia local** por estas razones:

- **Costo.** No hay un tercero que cobre créditos ni tokens. En la sustentación el chat no depende de saldo, cuotas ni tarjetas.
- **Independencia de internet.** Una vez descargado el modelo, la conversación corre en la máquina. Solo hace falta red al arrancar para bajar `cursos.json` desde GitHub y, si aplica, para SMTP.
- **Privacidad y seguridad.** El historial, el system prompt y los datos del estudiante no salen a un proveedor. Si comprometen la API de un cloud, esa filtración no incluye nuestras conversaciones.
- **Superficie de ataque menor.** No hay clave de API del LLM que se pueda filtrar en el ZIP de Moodle; las únicas secretos son SMTP.
- **Control del entorno de demo.** El docente ve el mismo modelo, la misma GPU y el mismo comportamiento; no hay caídas del proveedor ni cambios silenciosos de versión en la nube.
- **GPU propia.** Ollama puede offload de capas (`num_gpu = -1`) y acotar contexto (`num_ctx`) para caber en VRAM.
- **Portabilidad académica.** Cambiar de modelo es cambiar `OLLAMA_MODEL`; la memoria (lista Python), el JSON de inscripción y `smtplib` no se tocan.

El cliente usa `POST /api/chat` en streaming, con `OLLAMA_THINK=false`, para que la respuesta no se quede pensando hasta el timeout.

Si `ollama ps` muestra el modelo en CPU, revisa que el servicio vea la GPU (`nvidia-smi` o ROCm/Vulkan) y que `OLLAMA_NUM_GPU` no esté en `0`.

## Orden JSON para el correo

El system prompt pide que, **solo** con interés real, un `curso_id` de la oferta y un correo, el modelo responda únicamente:

```json
{"accion":"enviar_correo","correo":"estudiante@correo.com","curso_id":"PY-101"}
```

`AgenteAsesor.extraer_accion()` intercepta ese objeto (también si viene envuelto en markdown). `ConsolaChat` busca el curso en el catálogo cargado y `EmailService` lo envía con `smtplib`.

No usamos el function-calling de Ollama: el enunciado pide JSON nativo interceptado en Python.

## URL raw de cursos.json

```
CURSOS_URL=https://raw.githubusercontent.com/santtiag/chatbot_python/main/data/cursos.json
```

El JSON local de referencia está en [`data/cursos.json`](data/cursos.json) (6 cursos: id, nombre, descripcion, modalidad, duracion, costo, requisitos).

Prueba de `requests` sin GitHub (solo desarrollo):

```bash
uv run python -m http.server 8000 --directory data
# CURSOS_URL=http://127.0.0.1:8000/cursos.json
```

## Estructura

```
prototipo/
├── src/
│   ├── main.py            # Typer + while True + input()/print()
│   ├── agente.py          # memoria (list.append) y cliente Ollama
│   ├── cursos.py          # GET del JSON remoto
│   ├── email_service.py   # smtplib
│   └── temas.py           # diseños Rich
├── data/cursos.json
├── docs/arquitectura.html
├── .env
├── requirements.txt
└── README.md
```

## Memoria

`MemoriaConversacion` guarda una lista de dicts `{role, content}`. Cada turno hace `.append()` del usuario y de la respuesta, y reenvía **toda** la lista a Ollama.
