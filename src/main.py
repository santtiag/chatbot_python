"""Bucle de consola: Typer arranca, input()/print() conversan, Rich solo pinta el tema."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from src.agente import AgenteAsesor
from src.cursos import CatalogoCursos
from src.email_service import EmailService
from src.temas import NOMBRES_TEMA, obtener_tema
from src.tui_correo import panel_borrador, panel_fallo, panel_recibo

app = typer.Typer(
    add_completion=False,
    help="Agente de asesoría académica en consola.",
    no_args_is_help=False,
)


class ConsolaChat:
    """Orquesta el while True de la terminal con un tema Rich intercambiable."""

    def __init__(self, tema: str) -> None:
        self.tema = tema
        self.console = Console(theme=obtener_tema(tema))

    def mostrar_cabecera(self, modelo: str, procesador: str, cantidad: int) -> None:
        self.console.print(
            Panel(
                f"Tema [banner]{self.tema}[/banner]  ·  modelo [agent]{modelo}[/agent]\n"
                f"Procesador Ollama: [muted]{procesador}[/muted]\n"
                f"Cursos cargados: {cantidad}. Escribe [user]salir[/user] o [user]exit[/user] para terminar.",
                title="Asesor académico",
                border_style="banner",
            )
        )

    def leer_usuario(self) -> str:
        self.console.print("[user]Tú[/user]")
        try:
            return input("> ")
        except UnicodeDecodeError:
            print("> ", end="", flush=True)
            crudo = sys.stdin.buffer.readline()
            if not crudo:
                raise EOFError
            return crudo.decode("utf-8", errors="replace")

    def imprimir_agente(self, texto: str) -> None:
        print(f"Asesor: {texto}")

    def imprimir_ok(self, texto: str) -> None:
        print(texto)

    def imprimir_error(self, texto: str) -> None:
        print(texto)

    def enviar_con_tui(self, correo: EmailService, destinatario: str, curso: dict) -> None:
        print(f"Preparando correo de inscripción → {destinatario}")
        self.console.print()
        self.console.print(
            panel_borrador(
                destinatario=destinatario,
                remitente=correo.remitente,
                host=correo.host,
                port=correo.port,
                usar_tls=correo.usar_tls,
                curso=curso,
            )
        )
        try:
            transporte = "STARTTLS · login · DATA" if correo.usar_tls else "SSL · login · DATA"
            with self.console.status(
                f"[mail.kicker]smtp[/mail.kicker]  [muted]{transporte}[/muted]",
                spinner="line",
            ):
                correo.enviar_inscripcion(destinatario, curso)
        except Exception as exc:  # noqa: BLE001
            self.console.print(panel_fallo(str(exc)))
            self.imprimir_error(f"No se envió el correo: {exc}")
            return
        print(f"Correo enviado a {destinatario} con el curso {curso['id']} — {curso['nombre']}.")
        self.console.print(panel_recibo(destinatario, curso, datetime.now()))
        self.console.print()

    def ejecutar(self, agente: AgenteAsesor, catalogo: CatalogoCursos, correo: EmailService) -> None:
        while True:
            try:
                entrada = self.leer_usuario()
            except UnicodeDecodeError:
                self.imprimir_error(
                    "No pude leer ese texto (tildes o signos). Escríbelo de nuevo."
                )
                continue
            except (KeyboardInterrupt, EOFError):
                print("\nHasta luego.")
                break
            texto = entrada.strip()
            if not texto:
                continue
            if texto.lower() in {"salir", "exit"}:
                print("Hasta luego.")
                break
            try:
                with self.console.status(
                    "[muted]modelo generando…[/muted]",
                    spinner="line",
                ):
                    respuesta = agente.responder(texto)
            except Exception as exc:  # noqa: BLE001 — el bucle no debe caerse en la demo
                self.imprimir_error(str(exc))
                continue
            accion = agente.extraer_accion(respuesta)
            if accion is None:
                self.imprimir_agente(respuesta)
                continue
            curso = catalogo.por_id(accion["curso_id"])
            if curso is None:
                self.imprimir_error(
                    f"El modelo pidió el curso {accion['curso_id']}, que no está en la oferta."
                )
                continue
            self.enviar_con_tui(correo, accion["correo"], curso)


def _entero(nombre: str, defecto: int) -> int:
    crudo = os.getenv(nombre, str(defecto)).strip()
    try:
        return int(crudo)
    except ValueError:
        return defecto


def _float(nombre: str, defecto: float) -> float:
    crudo = os.getenv(nombre, str(defecto)).strip()
    try:
        return float(crudo)
    except ValueError:
        return defecto


def _bool(nombre: str, defecto: bool) -> bool:
    crudo = os.getenv(nombre, "true" if defecto else "false").strip().lower()
    return crudo in {"1", "true", "yes", "si", "sí"}


def _forzar_utf8() -> None:
    for flujo in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(flujo, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


@app.callback(invoke_without_command=True)
def principal(
    ctx: typer.Context,
    tema: str = typer.Option(
        "clasico",
        "--tema",
        "-t",
        help=f"Diseño de consola: {', '.join(NOMBRES_TEMA)}",
    ),
) -> None:
    """Arranca el chat si no se indicó un subcomando."""
    if ctx.invoked_subcommand is None:
        chat(tema=tema)


@app.command()
def chat(
    tema: str = typer.Option(
        "clasico",
        "--tema",
        "-t",
        help=f"Diseño de consola: {', '.join(NOMBRES_TEMA)}",
    ),
) -> None:
    """Chat en consola con memoria y envío de correo."""
    _forzar_utf8()
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    try:
        consola = ConsolaChat(tema)
    except ValueError as exc:
        print(str(exc))
        raise typer.Exit(code=1) from exc

    catalogo = CatalogoCursos(os.getenv("CURSOS_URL", ""))
    try:
        catalogo.cargar()
    except Exception as exc:  # noqa: BLE001
        consola.imprimir_error(str(exc))
        raise typer.Exit(code=1) from exc

    agente = AgenteAsesor(
        catalogo_texto=catalogo.texto_para_prompt(),
        host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
        model=os.getenv("OLLAMA_MODEL", "openbmb/minicpm5-2b"),
        num_gpu=_entero("OLLAMA_NUM_GPU", -1),
        num_ctx=_entero("OLLAMA_NUM_CTX", 4096),
        temperature=_float("OLLAMA_TEMPERATURE", 0.2),
        keep_alive=os.getenv("OLLAMA_KEEP_ALIVE", "30m"),
        timeout=_entero("OLLAMA_TIMEOUT", 600),
        num_predict=_entero("OLLAMA_NUM_PREDICT", 384),
        think=_bool("OLLAMA_THINK", False),
    )
    try:
        agente.comprobar_ollama()
    except Exception as exc:  # noqa: BLE001
        consola.imprimir_error(str(exc))
        raise typer.Exit(code=1) from exc

    try:
        with consola.console.status(
            f"[muted]Cargando el modelo en GPU (el primer arranque puede tardar)…[/muted]",
            spinner="line",
        ):
            agente.precargar()
    except Exception as exc:  # noqa: BLE001
        consola.imprimir_error(str(exc))
        raise typer.Exit(code=1) from exc

    correo = EmailService(
        host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        port=_entero("SMTP_PORT", 587),
        usuario=os.getenv("SMTP_USER", ""),
        password=os.getenv("SMTP_PASSWORD", ""),
        remitente=os.getenv("SMTP_FROM", ""),
        usar_tls=_bool("SMTP_USE_TLS", True),
    )
    consola.mostrar_cabecera(agente.model, agente.procesador_activo(), len(catalogo.cursos))
    consola.ejecutar(agente, catalogo, correo)


if __name__ == "__main__":
    app()
