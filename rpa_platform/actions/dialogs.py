"""Acciones de diálogo interactivo: alert() y prompt() para workflows."""

import ctypes
from typing import Dict, Any
from .base import BaseAction, ActionResult

# ── constantes MessageBox ────────────────────────────────────────────────────
_MB_OK            = 0x00000000
_MB_OKCANCEL      = 0x00000001
_MB_ICON_ERROR    = 0x00000010
_MB_ICON_WARN     = 0x00000030
_MB_ICON_INFO     = 0x00000040
_MB_SETFOREGROUND = 0x00010000
_MB_TOPMOST       = 0x00040000
_BASE_FLAGS       = _MB_SETFOREGROUND | _MB_TOPMOST

_ALERT_ICONS = {
    "info":       _MB_ICON_INFO,
    "advertencia": _MB_ICON_WARN,
    "error":      _MB_ICON_ERROR,
}


def _msgbox(message: str, title: str, flags: int) -> int:
    """Llama al MessageBoxW nativo de Windows. Retorna el botón presionado."""
    return ctypes.windll.user32.MessageBoxW(0, message, title, flags | _BASE_FLAGS)


# ── ShowAlertAction ──────────────────────────────────────────────────────────

class ShowAlertAction(BaseAction):
    action_type = "show_alert"
    label       = "Mostrar Alerta"
    icon        = "⚠️"

    PARAM_SCHEMA = {
        "message": {
            "type": "multiline",
            "label": "Mensaje",
            "required": True,
            "default": "",
        },
        "title": {
            "type": "str",
            "label": "Título de la ventana",
            "default": "RPA Studio",
        },
        "alert_type": {
            "type": "choice",
            "label": "Tipo de alerta",
            "choices": ["info", "advertencia", "error"],
            "default": "info",
        },
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params     = self.resolve_params(context.get("variables", {}))
        message    = str(params.get("message", ""))
        title      = str(params.get("title", "RPA Studio"))
        alert_type = str(params.get("alert_type", "info"))

        try:
            icon_flag = _ALERT_ICONS.get(alert_type, _MB_ICON_INFO)
            _msgbox(message, title, _MB_OK | icon_flag)
            preview = message[:60] + ("…" if len(message) > 60 else "")
            return ActionResult.success(output=f"Alerta mostrada: «{preview}»")
        except Exception as e:
            return ActionResult.failure(str(e))

    def get_summary(self) -> str:
        msg = str(self.params.get("message", ""))
        preview = msg[:40] + ("…" if len(msg) > 40 else "")
        t = self.params.get("alert_type", "info")
        return f"Alerta [{t}]: «{preview}»"


# ── ShowPromptAction ─────────────────────────────────────────────────────────

class ShowPromptAction(BaseAction):
    action_type = "show_prompt"
    label       = "Pedir Dato al Usuario"
    icon        = "💬"

    PARAM_SCHEMA = {
        "message": {
            "type": "str",
            "label": "Pregunta / Mensaje",
            "required": True,
            "default": "",
        },
        "title": {
            "type": "str",
            "label": "Título de la ventana",
            "default": "RPA Studio",
        },
        "default_value": {
            "type": "str",
            "label": "Valor por defecto",
            "default": "",
        },
        "output_variable": {
            "type": "str",
            "label": "Variable donde guardar la respuesta",
            "required": True,
            "default": "user_input",
        },
        "cancel_stops": {
            "type": "bool",
            "label": "Detener el workflow si el usuario cancela",
            "default": True,
        },
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params       = self.resolve_params(context.get("variables", {}))
        message      = str(params.get("message", ""))
        title        = str(params.get("title", "RPA Studio"))
        default_val  = str(params.get("default_value", ""))
        output_var   = str(params.get("output_variable", "user_input"))
        cancel_stops = bool(params.get("cancel_stops", True))

        try:
            import tkinter as tk
            from tkinter import simpledialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            result = simpledialog.askstring(
                title, message,
                initialvalue=default_val,
                parent=root,
            )
            root.destroy()
        except Exception as e:
            return ActionResult.failure(f"Error al mostrar diálogo: {e}")

        if result is None:
            if cancel_stops:
                return ActionResult.failure("El usuario canceló el diálogo — workflow detenido")
            return ActionResult.success(
                output="Usuario canceló — continuando con valor por defecto",
                variables={output_var: default_val},
            )

        return ActionResult.success(
            output=f"Respuesta recibida -> {output_var} = «{result}»",
            variables={output_var: result},
        )

    def get_summary(self) -> str:
        var = self.params.get("output_variable", "user_input")
        msg = str(self.params.get("message", ""))[:35]
        dots = "…" if len(str(self.params.get("message", ""))) > 35 else ""
        return f"Prompt -> {var}: «{msg}{dots}»"
