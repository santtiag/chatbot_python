# Agente de asesoría académica

Prototipo del primer parcial: un asesor en consola que lee la oferta de cursos desde GitHub, conversa con **Ollama `granite4.2`** en GPU y envía un correo con `smtplib` cuando detecta una inscripción real.

Diagrama interactivo (Archify): [docs/arquitectura.html](docs/arquitectura.html).

La interfaz fija del visor Archify (`<html lang>` y botones Light/Dark, Present, Export) queda en inglés. El contenido del diagrama (títulos, nodos, relaciones y tarjetas) está en español.

## Requisitos

- Python 3.11+ (el proyecto se instala con `uv`)
- [Ollama](https://ollama.com) con el modelo `granite4.2`
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
- `OLLAMA_MODEL=granite4.2`
- `OLLAMA_NUM_GPU=-1` (todas las capas a GPU)
- `SMTP_*` con tus credenciales de correo

Descarga el modelo si hace falta:

```bash
ollama pull granite4.2
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

## Decisión de arquitectura: ¿qué API de IA y por qué?

Elegimos **Ollama local** y el modelo **`granite4.2`**, no Gemini/Groq/OpenAI.

- Corre en esta máquina: no hay clave de API de nube ni costo por token en la sustentación.
- Ollama puede offload de capas a GPU (`options.num_gpu = -1`) y un `num_ctx` acotado (8192) para no inflar el KV cache.
- La oferta de cursos se inyecta en el system prompt; el historial no sale a un proveedor externo.
- Está prohibido LangChain/LlamaIndex: el cliente es `requests` contra `POST /api/chat`.

Si `ollama ps` muestra el modelo en CPU, revisa que el servicio vea la GPU (`nvidia-smi` o el backend ROCm/Vulkan) y que `OLLAMA_NUM_GPU` no esté en `0`.

## Orden JSON para el correo

El system prompt pide que, **solo** con interés real, un `curso_id` de la oferta y un correo, el modelo responda únicamente:

```json
{"accion":"enviar_correo","correo":"estudiante@correo.com","curso_id":"PY-101"}
```

`AgenteAsesor.extraer_accion()` intercepta ese objeto (también si viene envuelto en markdown). `ConsolaChat` busca el curso en el catálogo cargado y `EmailService` lo envía con `smtplib`.

No usamos el function-calling de Ollama: el enunciado pide JSON nativo interceptado en Python.

## URL raw de cursos.json

Pegar aquí la URL pública cuando el archivo esté en GitHub:

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
