"""Envío de la ficha del curso por SMTP nativo."""

from __future__ import annotations

import html
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any


def formatear_costo(valor: Any) -> str:
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return str(valor)
    return f"${numero:,.0f}".replace(",", ".")


def asunto_inscripcion(curso: dict[str, Any]) -> str:
    return f"Inscripción · {curso.get('id', '')} · {curso.get('nombre', '')}"


class EmailService:
    """Construye y envía el correo de inscripción con smtplib."""

    def __init__(
        self,
        host: str,
        port: int,
        usuario: str,
        password: str,
        remitente: str,
        usar_tls: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.usuario = usuario
        self.password = password
        self.remitente = remitente or usuario
        self.usar_tls = usar_tls

    def enviar_inscripcion(self, destinatario: str, curso: dict[str, Any]) -> None:
        if not self.usuario or not self.password:
            raise ValueError(
                "Faltan SMTP_USER o SMTP_PASSWORD en .env. No se puede enviar el correo."
            )
        mensaje = EmailMessage()
        mensaje["Subject"] = asunto_inscripcion(curso)
        mensaje["From"] = self.remitente
        mensaje["To"] = destinatario
        mensaje.set_content(self.cuerpo_texto(curso))
        mensaje.add_alternative(self.cuerpo_html(curso, destinatario), subtype="html")

        if self.usar_tls:
            contexto = ssl.create_default_context()
            with smtplib.SMTP(self.host, self.port, timeout=30) as servidor:
                servidor.starttls(context=contexto)
                servidor.login(self.usuario, self.password)
                servidor.send_message(mensaje)
            return

        with smtplib.SMTP_SSL(self.host, self.port, timeout=30) as servidor:
            servidor.login(self.usuario, self.password)
            servidor.send_message(mensaje)

    def cuerpo_texto(self, curso: dict[str, Any]) -> str:
        linea = "─" * 52
        return (
            "ASESORÍA ACADÉMICA\n"
            f"{linea}\n"
            "Confirmación de interés de inscripción\n\n"
            f"  Código      {curso.get('id')}\n"
            f"  Curso       {curso.get('nombre')}\n"
            f"  Modalidad   {curso.get('modalidad')}\n"
            f"  Duración    {curso.get('duracion')}\n"
            f"  Costo       {formatear_costo(curso.get('costo'))}\n"
            f"  Requisitos  {curso.get('requisitos')}\n\n"
            f"{linea}\n"
            f"{curso.get('descripcion')}\n\n"
            "Este mensaje se generó al confirmar la inscripción en la consola del asesor.\n"
        )

    def cuerpo_html(self, curso: dict[str, Any], destinatario: str) -> str:
        def e(valor: Any) -> str:
            return html.escape(str(valor or ""))

        return f"""\
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>{e(asunto_inscripcion(curso))}</title></head>
<body style="margin:0;background:#0d1117;color:#e6edf3;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;">
  <div style="max-width:560px;margin:32px auto;padding:0 16px;">
    <div style="font-size:12px;letter-spacing:.12em;color:#58a6ff;margin-bottom:10px;">ASESORÍA ACADÉMICA · OUTBOX</div>
    <div style="border:1px solid #30363d;border-radius:10px;background:#161b22;overflow:hidden;">
      <div style="padding:10px 16px;background:#21262d;border-bottom:1px solid #30363d;color:#8b949e;font-size:12px;">
        ● smtp &nbsp; delivered
      </div>
      <div style="padding:20px 18px 8px;">
        <div style="color:#8b949e;font-size:11px;letter-spacing:.08em;">PARA</div>
        <div style="margin:4px 0 14px;color:#58a6ff;">{e(destinatario)}</div>
        <div style="color:#8b949e;font-size:11px;letter-spacing:.08em;">ASUNTO</div>
        <div style="margin:4px 0 18px;">{e(asunto_inscripcion(curso))}</div>
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
          <tr><td style="color:#8b949e;padding:6px 0;width:110px;">Código</td><td>{e(curso.get("id"))}</td></tr>
          <tr><td style="color:#8b949e;padding:6px 0;">Curso</td><td>{e(curso.get("nombre"))}</td></tr>
          <tr><td style="color:#8b949e;padding:6px 0;">Modalidad</td><td>{e(curso.get("modalidad"))}</td></tr>
          <tr><td style="color:#8b949e;padding:6px 0;">Duración</td><td>{e(curso.get("duracion"))}</td></tr>
          <tr><td style="color:#8b949e;padding:6px 0;">Costo</td><td>{e(formatear_costo(curso.get("costo")))}</td></tr>
          <tr><td style="color:#8b949e;padding:6px 0;vertical-align:top;">Requisitos</td><td>{e(curso.get("requisitos"))}</td></tr>
        </table>
        <p style="margin:18px 0 8px;color:#8b949e;font-size:13px;line-height:1.5;">{e(curso.get("descripcion"))}</p>
      </div>
      <div style="padding:12px 18px;border-top:1px solid #30363d;color:#6e7681;font-size:11px;">
        Generado por el asesor de consola · smtplib
      </div>
    </div>
  </div>
</body>
</html>
"""
