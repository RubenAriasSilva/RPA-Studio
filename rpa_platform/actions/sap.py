import time
import re
import os
import subprocess
from typing import Dict, Any, Optional, List, Tuple
import pyautogui
from .base import BaseAction, ActionResult

# Rutas comunes de saplogon.exe en instalaciones estándar
_SAP_DEFAULT_PATHS = [
    r"C:\Program Files\SAP\FrontEnd\SAPgui\saplogon.exe",
    r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe",
    r"C:\Program Files\SAP\FrontEnd\SAPgui\SapLogon.exe",
]

# SAP GUI scripting is often disabled by admins.
# All actions here use win32gui window detection + keyboard + OCR instead.


def find_sap_window(title_fragment: str = "") -> Optional[int]:
    """Return the hwnd of the first SAP GUI window matching title_fragment."""
    try:
        import win32gui
        results = []

        def _cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if "SAP" in title.upper():
                    if not title_fragment or title_fragment.upper() in title.upper():
                        results.append(hwnd)

        win32gui.EnumWindows(_cb, None)
        return results[0] if results else None
    except Exception:
        return None


def focus_sap_window(hwnd: int) -> bool:
    try:
        import win32gui
        import win32con
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        return True
    except Exception:
        return False


def get_sap_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    try:
        import win32gui
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        return left, top, right - left, bottom - top
    except Exception:
        return None


class SAPLaunchAction(BaseAction):
    action_type = "sap_launch"
    label = "SAP - Abrir SAP Logon"
    icon = "🚀"

    PARAM_SCHEMA = {
        "exe_path": {
            "type": "file",
            "label": "Ruta a saplogon.exe (vacío = detectar automáticamente)",
            "default": "",
        },
        "wait_timeout": {
            "type": "float",
            "label": "Espera máxima para que abra (seg)",
            "default": 20.0,
        },
        "if_already_open": {
            "type": "choice",
            "label": "Si SAP ya está abierto",
            "choices": ["enfocar", "ignorar"],
            "default": "enfocar",
        },
        "wait_after": {
            "type": "float",
            "label": "Espera adicional tras detectar ventana (seg)",
            "default": 1.5,
        },
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        exe_path    = params.get("exe_path", "").strip()
        timeout     = float(params.get("wait_timeout", 20.0))
        already     = params.get("if_already_open", "enfocar")
        wait_after  = float(params.get("wait_after", 1.5))

        # ── ¿SAP ya está abierto? ───────────────────────────────────────────
        hwnd = find_sap_window()
        if hwnd:
            if already == "ignorar":
                return ActionResult.success(output="SAP ya estaba abierto — omitido")
            focus_sap_window(hwnd)
            time.sleep(wait_after)
            return ActionResult.success(output="SAP ya estaba abierto — enfocado")

        # ── Resolver ruta del ejecutable ────────────────────────────────────
        resolved = exe_path if exe_path and os.path.exists(exe_path) else ""
        if not resolved:
            for candidate in _SAP_DEFAULT_PATHS:
                if os.path.exists(candidate):
                    resolved = candidate
                    break
        if not resolved:
            return ActionResult.failure(
                "No se encontró saplogon.exe. "
                "Especifica la ruta exacta en el parámetro 'exe_path'."
            )

        # ── Lanzar SAP ──────────────────────────────────────────────────────
        try:
            subprocess.Popen([resolved])
        except Exception as e:
            return ActionResult.failure(f"Error al lanzar SAP: {e}")

        # ── Esperar a que aparezca la ventana ───────────────────────────────
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(0.8)
            hwnd = find_sap_window()
            if hwnd:
                focus_sap_window(hwnd)
                time.sleep(wait_after)
                return ActionResult.success(
                    output=f"SAP Logon abierto correctamente ({resolved})"
                )

        return ActionResult.failure(
            f"SAP no respondió en {timeout:.0f} seg. "
            "Verifica que la ruta sea correcta y que la aplicación pueda iniciarse."
        )

    def get_summary(self) -> str:
        exe = self.params.get("exe_path", "")
        return f"Abrir SAP Logon{' — ' + os.path.basename(exe) if exe else ''}"


class SAPFocusWindowAction(BaseAction):
    action_type = "sap_focus_window"
    label = "SAP - Enfocar Ventana"
    icon = "🪟"

    PARAM_SCHEMA = {
        "title_fragment": {"type": "str", "label": "Fragmento del título (vacío = cualquier SAP)", "default": ""},
        "maximize": {"type": "bool", "label": "Maximizar ventana al enfocar", "default": False},
        "output_variable": {"type": "str", "label": "Variable para hwnd de la ventana", "default": "sap_hwnd"},
        "wait_after": {"type": "float", "label": "Espera después de enfocar (seg)", "default": 0.5},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        import win32gui
        import win32con
        params = self.resolve_params(context.get("variables", {}))
        fragment   = params.get("title_fragment", "")
        maximize   = bool(params.get("maximize", False))
        output_var = params.get("output_variable", "sap_hwnd")
        wait_after = float(params.get("wait_after", 0.5))

        hwnd = find_sap_window(fragment)
        if not hwnd:
            return ActionResult.failure(
                f"No se encontró ventana SAP{'con «' + fragment + '»' if fragment else ''}. "
                "Asegúrate de que SAP GUI esté abierto."
            )

        if not focus_sap_window(hwnd):
            return ActionResult.failure("Se encontró la ventana SAP pero no se pudo enfocar")

        if maximize:
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            time.sleep(0.2)

        time.sleep(wait_after)

        title = win32gui.GetWindowText(hwnd)
        suffix = " (maximizada)" if maximize else ""
        variables = {output_var: str(hwnd)}
        return ActionResult.success(
            output=f"Ventana SAP enfocada{suffix}: «{title}»",
            variables=variables,
        )

    def get_summary(self) -> str:
        fragment = self.params.get("title_fragment", "")
        maximize = self.params.get("maximize", False)
        suffix = " + maximizar" if maximize else ""
        return f"Enfocar SAP{suffix}{'  «' + fragment + '»' if fragment else ''}"


class SAPOpenTransactionAction(BaseAction):
    action_type = "sap_open_transaction"
    label = "SAP - Abrir Transacción"
    icon = "🏢"

    PARAM_SCHEMA = {
        "transaction": {"type": "str", "label": "Código de transacción (ej: MM60, ME21N)", "required": True},
        "method": {"type": "choice", "label": "Método de apertura", "default": "command_field",
                   "choices": ["command_field", "menu_system"]},
        "wait_after": {"type": "float", "label": "Espera después de abrir (seg)", "default": 1.5},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        transaction = params.get("transaction", "").strip().upper()
        method = params.get("method", "command_field")
        wait_after = float(params.get("wait_after", 1.5))

        if not transaction:
            return ActionResult.failure("El código de transacción no puede estar vacío")

        hwnd = find_sap_window()
        if not hwnd:
            return ActionResult.failure("SAP GUI no está abierto")
        focus_sap_window(hwnd)

        try:
            if method == "command_field":
                # Click the SAP command field (top-left box) then type /n<TX>
                pyautogui.hotkey("ctrl", "F12")
                time.sleep(0.3)
                pyautogui.typewrite(f"/n{transaction}", interval=0.05)
                pyautogui.press("enter")
            else:
                # System → Services → Enter transaction
                pyautogui.hotkey("alt", "F10")
                time.sleep(0.5)
                pyautogui.typewrite("y", interval=0.05)
                time.sleep(0.3)
                pyautogui.typewrite("e", interval=0.05)
                time.sleep(0.3)
                pyautogui.typewrite(transaction, interval=0.05)
                pyautogui.press("enter")

            time.sleep(wait_after)
            return ActionResult.success(output=f"Transacción {transaction} abierta")
        except Exception as e:
            return ActionResult.failure(f"Error al abrir transacción: {str(e)}")

    def get_summary(self) -> str:
        return f"SAP: Abrir {self.params.get('transaction', '???')}"


class SAPTypeInFieldAction(BaseAction):
    action_type = "sap_type_in_field"
    label = "SAP - Escribir en Campo (Coordenadas)"
    icon = "✏️"

    PARAM_SCHEMA = {
        "x": {"type": "int", "label": "X (coordenada de pantalla)", "required": True, "default": 0},
        "y": {"type": "int", "label": "Y (coordenada de pantalla)", "required": True, "default": 0},
        "value": {"type": "str", "label": "Valor a escribir", "required": True},
        "clear_first": {"type": "bool", "label": "Limpiar campo primero (Ctrl+A)", "default": True},
        "press_tab": {"type": "bool", "label": "Presionar Tab después", "default": True},
        "relative_to_sap": {"type": "bool", "label": "Coords relativas a ventana SAP", "default": False},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        x = int(params.get("x", 0))
        y = int(params.get("y", 0))
        value = str(params.get("value", ""))
        clear_first = params.get("clear_first", True)
        press_tab = params.get("press_tab", True)
        relative = params.get("relative_to_sap", False)

        hwnd = find_sap_window()
        if not hwnd:
            return ActionResult.failure("SAP GUI no está abierto")
        focus_sap_window(hwnd)

        click_x, click_y = x, y
        if relative:
            rect = get_sap_window_rect(hwnd)
            if rect:
                click_x = rect[0] + x
                click_y = rect[1] + y

        try:
            pyautogui.click(click_x, click_y)
            time.sleep(0.1)
            if clear_first:
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.05)
            pyautogui.typewrite(str(value), interval=0.04)
            if press_tab:
                pyautogui.press("tab")
                time.sleep(0.05)
            return ActionResult.success(output=f"Escrito «{value}» en ({click_x},{click_y})")
        except Exception as e:
            return ActionResult.failure(str(e))

    def get_summary(self) -> str:
        val = str(self.params.get("value", ""))[:20]
        x, y = self.params.get("x", "?"), self.params.get("y", "?")
        return f"SAP escribir «{val}» en ({x},{y})"


class SAPReadFieldOCRAction(BaseAction):
    action_type = "sap_read_field_ocr"
    label = "SAP - Leer Campo (OCR)"
    icon = "📖"

    PARAM_SCHEMA = {
        "region": {"type": "region", "label": "Región a leer (x,y,ancho,alto)", "required": True},
        "output_variable": {"type": "str", "label": "Variable para el texto leído", "default": "sap_value"},
        "strip_whitespace": {"type": "bool", "label": "Quitar espacios sobrantes", "default": True},
        "pattern": {"type": "str", "label": "Patrón regex para extraer (vacío = todo)", "default": ""},
        "languages": {"type": "str", "label": "Idiomas OCR", "default": "es,en"},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        region_str = params.get("region", "")
        output_var = params.get("output_variable", "sap_value")
        strip_ws = params.get("strip_whitespace", True)
        pattern = params.get("pattern", "")
        lang_str = params.get("languages", "es,en")

        if not region_str:
            return ActionResult.failure("Debes especificar la región a leer")

        try:
            parts = [int(x.strip()) for x in region_str.split(",")]
            if len(parts) != 4:
                return ActionResult.failure("Región debe tener formato x,y,ancho,alto")
            region = tuple(parts)
        except ValueError:
            return ActionResult.failure("Región inválida — usa formato: x,y,ancho,alto")

        try:
            import numpy as np
            from actions.ocr import get_ocr_reader
            screenshot = pyautogui.screenshot(region=region)
            img_array = np.array(screenshot)
            langs = [l.strip() for l in lang_str.split(",")]
            reader = get_ocr_reader(langs)
            results = reader.readtext(img_array, detail=0)
            text = " ".join(results)
            if strip_ws:
                text = text.strip()
            if pattern:
                match = re.search(pattern, text)
                text = match.group(0) if match else ""

            variables = {output_var: text}
            return ActionResult.success(
                output=f"Leido -> «{text[:80]}{'...' if len(text) > 80 else ''}»",
                variables=variables,
            )
        except Exception as e:
            return ActionResult.failure(str(e))

    def get_summary(self) -> str:
        var = self.params.get("output_variable", "sap_value")
        region = self.params.get("region", "")
        return f"SAP leer OCR -> {var} ({region})"


class SAPClickButtonAction(BaseAction):
    action_type = "sap_click_button"
    label = "SAP - Click Botón / Icono"
    icon = "🖱️"

    PARAM_SCHEMA = {
        "method": {"type": "choice", "label": "Método", "default": "hotkey",
                   "choices": ["hotkey", "coordinates", "find_image"]},
        "hotkey": {"type": "str", "label": "Tecla rápida (si método=hotkey, ej: F8, F3, enter)",
                   "default": "F8"},
        "x": {"type": "int", "label": "X (si método=coordinates)", "default": 0},
        "y": {"type": "int", "label": "Y (si método=coordinates)", "default": 0},
        "image_path": {"type": "file", "label": "Imagen del botón (si método=find_image)", "default": ""},
        "wait_after": {"type": "float", "label": "Espera después (seg)", "default": 0.8},
    }

    # Most-used SAP toolbar shortcuts
    SAP_HOTKEYS = {
        "Enter / Ejecutar (F8)": "F8",
        "Guardar (Ctrl+S)": "ctrl+s",
        "Atrás (F3)": "F3",
        "Cancelar (F12)": "F12",
        "Buscar (Ctrl+F)": "ctrl+f",
        "Primer página": "ctrl+Home",
        "Última página": "ctrl+End",
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        method = params.get("method", "hotkey")
        wait_after = float(params.get("wait_after", 0.8))

        hwnd = find_sap_window()
        if hwnd:
            focus_sap_window(hwnd)

        try:
            if method == "hotkey":
                keys_str = params.get("hotkey", "F8")
                keys = [k.strip() for k in keys_str.split("+")]
                if len(keys) == 1:
                    pyautogui.press(keys[0])
                else:
                    pyautogui.hotkey(*keys)

            elif method == "coordinates":
                x = int(params.get("x", 0))
                y = int(params.get("y", 0))
                pyautogui.click(x, y)

            elif method == "find_image":
                img = params.get("image_path", "")
                if not img:
                    return ActionResult.failure("No se especificó imagen del botón")
                location = pyautogui.locateOnScreen(img, confidence=0.8)
                if not location:
                    return ActionResult.failure(f"Botón no encontrado en pantalla: {img}")
                pyautogui.click(pyautogui.center(location))

            time.sleep(wait_after)
            return ActionResult.success(output=f"Botón/tecla ejecutada ({method})")
        except Exception as e:
            return ActionResult.failure(str(e))

    def get_summary(self) -> str:
        method = self.params.get("method", "hotkey")
        if method == "hotkey":
            return f"SAP tecla: {self.params.get('hotkey', 'F8')}"
        elif method == "coordinates":
            return f"SAP click: ({self.params.get('x','?')},{self.params.get('y','?')})"
        return "SAP buscar botón"


class SAPWaitScreenAction(BaseAction):
    """Waits until SAP leaves the current screen.

    SAP GUI shows the screen name in the session window title, so a title change
    means the new screen is rendered (e.g. a report that takes minutes to run).
    Popups (information, errors, "Guardar como") are new windows of the SAP process.
    """
    action_type = "sap_wait_screen"
    label = "SAP - Esperar Cambio de Pantalla"
    icon = "⌛"

    COND_ANY = "Cambie la pantalla o aparezca una ventana"
    COND_SCREEN = "Cambie la pantalla"
    COND_POPUP = "Aparezca una ventana emergente"
    COND_CONTAINS = "El título contenga"
    COND_NOT_CONTAINS = "El título deje de contener"

    ON_TIMEOUT_FAIL = "Marcar error"
    ON_TIMEOUT_CONTINUE = "Continuar"

    PARAM_SCHEMA = {
        "condition": {"type": "choice", "label": "Esperar hasta que", "default": COND_ANY,
                      "choices": [COND_ANY, COND_SCREEN, COND_POPUP, COND_CONTAINS, COND_NOT_CONTAINS]},
        "text": {"type": "str", "label": "Texto del título de la pantalla",
                 "placeholder": "ej. Pantalla inicial",
                 "visible_if": ("condition", [COND_CONTAINS, COND_NOT_CONTAINS])},
        "title_fragment": {"type": "str", "label": "Ventana SAP a vigilar (fragmento del título; vacío = la activa)",
                           "default": ""},
        "timeout": {"type": "float", "label": "Tiempo máximo de espera (seg)", "default": 600.0},
        "on_timeout": {"type": "choice", "label": "Si se agota el tiempo", "default": ON_TIMEOUT_FAIL,
                       "choices": [ON_TIMEOUT_FAIL, ON_TIMEOUT_CONTINUE]},
        "wait_after": {"type": "float", "label": "Espera tras detectar el cambio (seg)", "default": 0.5},
        "output_variable": {"type": "str", "label": "Variable para el título nuevo", "default": "sap_titulo"},
    }

    @staticmethod
    def _pick_session(windows, fragment: str):
        """The SAP main window to watch: the active one if it is SAP, else the topmost."""
        fragment = fragment.lower()
        candidates = [w for w in windows if w.is_sap and not w.owned
                      and (not fragment or fragment in w.title.lower())]
        if not candidates:
            return None
        from .windows import foreground_hwnd
        fg = foreground_hwnd()
        return next((w for w in candidates if w.hwnd == fg), candidates[0])

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        from .windows import list_windows, window_exists, window_title, wait_until

        params = self.resolve_params(context.get("variables", {}))
        condition = params.get("condition", self.COND_ANY)
        text = str(params.get("text", "")).strip()
        timeout = max(0.0, float(params.get("timeout", 600.0)))
        wait_after = max(0.0, float(params.get("wait_after", 0.5)))
        output_var = str(params.get("output_variable", self.PARAM_SCHEMA["output_variable"]["default"])).strip()

        if condition in (self.COND_CONTAINS, self.COND_NOT_CONTAINS) and not text:
            return ActionResult.failure("Indica el texto del título a comprobar")

        try:
            windows = list_windows()
        except Exception as e:
            return ActionResult.failure(f"No se pudieron enumerar las ventanas: {e}")
        session = self._pick_session(windows, params.get("title_fragment", "").strip())
        if session is None:
            return ActionResult.failure("No se encontró una ventana de SAP GUI abierta")

        start_title = session.title
        known = {w.hwnd for w in windows if w.is_sap}
        watch_screen = condition in (self.COND_ANY, self.COND_SCREEN)
        watch_popup = condition in (self.COND_ANY, self.COND_POPUP)
        needle = text.lower()

        def check():
            if not window_exists(session.hwnd):
                return "cerrada", ""
            if watch_popup:
                popup = next((w for w in list_windows() if w.is_sap and w.hwnd not in known), None)
                if popup:
                    return "ventana", popup.title
            title = window_title(session.hwnd)
            if watch_screen and title != start_title:
                return "pantalla", title
            if condition == self.COND_CONTAINS and needle in title.lower():
                return "pantalla", title
            if condition == self.COND_NOT_CONTAINS and needle not in title.lower():
                return "pantalla", title
            return None

        found, elapsed, stopped = wait_until(context, check, timeout, interval=0.3)
        if stopped:
            return ActionResult.success(output="Espera de SAP interrumpida al detener el workflow")

        if found is None:
            msg = f"SAP siguió en «{start_title}» después de {timeout:g} s"
            if params.get("on_timeout", self.ON_TIMEOUT_FAIL) == self.ON_TIMEOUT_CONTINUE:
                variables = {output_var: window_title(session.hwnd)} if output_var else {}
                return ActionResult.success(output=f"{msg} — se continúa", variables=variables)
            return ActionResult.failure(msg)

        kind, title = found
        if kind == "cerrada" and condition == self.COND_CONTAINS:
            return ActionResult.failure(f"La ventana SAP «{start_title}» se cerró antes de llegar a «{text}»")
        time.sleep(wait_after)
        variables = {output_var: title} if output_var else {}
        if kind == "cerrada":
            output = f"La ventana SAP «{start_title}» se cerró tras {elapsed:.1f} s"
        elif kind == "ventana":
            output = f"Apareció la ventana SAP «{title}» tras {elapsed:.1f} s"
        else:
            output = f"Pantalla SAP: «{start_title}» → «{title}» tras {elapsed:.1f} s"
        return ActionResult.success(output=output, variables=variables)

    def get_summary(self) -> str:
        condition = self.params.get("condition", self.COND_ANY)
        text = str(self.params.get("text", "")).strip()
        timeout = self.params.get("timeout", 600.0)
        if condition == self.COND_CONTAINS:
            what = f"título contenga «{text}»"
        elif condition == self.COND_NOT_CONTAINS:
            what = f"título deje de contener «{text}»"
        elif condition == self.COND_SCREEN:
            what = "cambio de pantalla"
        elif condition == self.COND_POPUP:
            what = "ventana emergente"
        else:
            what = "cambio de pantalla o ventana"
        return f"SAP esperar {what} (máx {timeout}s)"


# Keep old field names for legacy workflows but point to new classes
SAPWriteFieldAction = SAPTypeInFieldAction
SAPReadFieldAction = SAPReadFieldOCRAction
