import re
import time
import pyautogui
import pyperclip
from typing import Dict, Any
from .base import BaseAction, ActionResult

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


class TypeTextAction(BaseAction):
    action_type = "type_text"
    label = "Escribir Texto"
    icon = "⌨️"

    SOURCE_TEXT = "Texto"
    SOURCE_VARIABLE = "Variable"

    PARAM_SCHEMA = {
        "source": {"type": "choice", "label": "Qué escribir", "default": SOURCE_TEXT,
                   "choices": [SOURCE_TEXT, SOURCE_VARIABLE]},
        "text": {"type": "str", "label": "Texto a escribir (puede incluir {variables})", "multiline": True,
                 "visible_if": ("source", SOURCE_TEXT)},
        "variable_name": {"type": "str", "label": "Variable cuyo contenido se escribirá",
                          "placeholder": "ej. col_A", "visible_if": ("source", SOURCE_VARIABLE)},
        "interval": {"type": "float", "label": "Intervalo entre teclas (seg)", "default": 0.02},
        "clear_first": {"type": "bool", "label": "Limpiar campo primero (Ctrl+A)", "default": False},
    }

    _UNRESOLVED = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

    def _uses_variable(self) -> bool:
        return self.params.get("source", self.SOURCE_TEXT) == self.SOURCE_VARIABLE

    def _variable_name(self) -> str:
        return str(self.params.get("variable_name", "")).strip().strip("{}").strip()

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        variables = context.get("variables", {})
        params = self.resolve_params(variables)
        interval = float(params.get("interval", 0.02))
        clear_first = params.get("clear_first", False)
        warning = ""

        if self._uses_variable():
            name = self._variable_name()
            if not name:
                return ActionResult.failure("No se indicó la variable a escribir")
            if name not in variables:
                return ActionResult.failure(f"La variable '{name}' no existe")
            text = "" if variables[name] is None else str(variables[name])
        else:
            text = params.get("text", "")
            if not text:
                return ActionResult.failure("El texto no puede estar vacío")
            missing = sorted(set(self._UNRESOLVED.findall(text)))
            if missing:
                warning = f" (⚠ variables sin valor: {', '.join(missing)})"

        try:
            if clear_first:
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.05)
            if text:
                self._write(text, interval)
            preview = text[:50] + ("..." if len(text) > 50 else "")
            return ActionResult.success(output=f"Texto escrito: {preview}{warning}")
        except Exception as e:
            return ActionResult.failure(str(e))

    @staticmethod
    def _write(text: str, interval: float):
        # typewrite silently drops non-ASCII characters (á, ñ, €...): paste those instead
        if all(32 <= ord(c) < 127 or c in "\n\t" for c in text):
            pyautogui.typewrite(text, interval=interval)
            return
        try:
            previous = pyperclip.paste()
        except pyperclip.PyperclipException:
            previous = None
        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.15)  # let the target app read the clipboard before restoring it
        if previous is not None:
            pyperclip.copy(previous)

    def get_summary(self) -> str:
        if self._uses_variable():
            return f"Escribir: {{{self._variable_name()}}}"
        text = self.params.get("text", "")
        preview = text[:30] + ("..." if len(text) > 30 else "")
        return f"Escribir: \"{preview}\""


class HotkeyAction(BaseAction):
    action_type = "hotkey"
    label = "Tecla Rápida"
    icon = "🔑"

    PARAM_SCHEMA = {
        "keys": {"type": "str", "label": "Teclas (ej: ctrl+c, alt+F4, enter)", "required": True},
        "delay_after": {"type": "float", "label": "Espera después (seg)", "default": 0.1},
    }

    COMMON_HOTKEYS = [
        "ctrl+c", "ctrl+v", "ctrl+x", "ctrl+z", "ctrl+a",
        "ctrl+s", "ctrl+f", "ctrl+enter", "alt+F4",
        "enter", "escape", "tab", "F1", "F3", "F5", "F8",
    ]

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        keys_str = params.get("keys", "")
        delay_after = float(params.get("delay_after", 0.1))

        if not keys_str:
            return ActionResult.failure("Debe especificar las teclas")

        try:
            keys = [k.strip() for k in keys_str.split("+")]
            if len(keys) == 1:
                pyautogui.press(keys[0])
            else:
                pyautogui.hotkey(*keys)
            time.sleep(delay_after)
            return ActionResult.success(output=f"Tecla ejecutada: {keys_str}")
        except Exception as e:
            return ActionResult.failure(str(e))

    def get_summary(self) -> str:
        return f"Tecla: {self.params.get('keys', '')}"


class KeyPressAction(BaseAction):
    action_type = "key_press"
    label = "Presionar Tecla"
    icon = "⬇️"

    PARAM_SCHEMA = {
        "key": {"type": "str", "label": "Tecla (ej: enter, tab, F3, escape)", "required": True},
        "presses": {"type": "int", "label": "Número de veces", "default": 1},
        "interval": {"type": "float", "label": "Intervalo entre pulsaciones (seg)", "default": 0.1},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        key = params.get("key", "")
        presses = int(params.get("presses", 1))
        interval = float(params.get("interval", 0.1))

        if not key:
            return ActionResult.failure("Debe especificar la tecla")

        try:
            pyautogui.press(key, presses=presses, interval=interval)
            return ActionResult.success(output=f"Tecla '{key}' presionada {presses} vez/veces")
        except Exception as e:
            return ActionResult.failure(str(e))

    def get_summary(self) -> str:
        presses = self.params.get("presses", 1)
        return f"Tecla '{self.params.get('key', '')}' × {presses}"
