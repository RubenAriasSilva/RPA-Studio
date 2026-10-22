import time
import pyperclip
from typing import Dict, Any
from .base import BaseAction, ActionResult


class DelayAction(BaseAction):
    action_type = "delay"
    label = "Esperar (Delay)"
    icon = "⏱️"

    SOURCE_FIXED = "Valor fijo"
    SOURCE_VARIABLE = "Variable"

    PARAM_SCHEMA = {
        "source": {"type": "choice", "label": "Origen de los segundos", "default": SOURCE_FIXED,
                   "choices": [SOURCE_FIXED, SOURCE_VARIABLE]},
        "seconds": {"type": "float", "label": "Segundos a esperar", "default": 1.0,
                    "visible_if": ("source", SOURCE_FIXED)},
        "variable_name": {"type": "str", "label": "Variable con los segundos",
                          "placeholder": "ej. tiempo_espera",
                          "visible_if": ("source", SOURCE_VARIABLE)},
    }

    def _uses_variable(self) -> bool:
        return self.params.get("source", self.SOURCE_FIXED) == self.SOURCE_VARIABLE

    def _variable_name(self) -> str:
        return str(self.params.get("variable_name", "")).strip().strip("{}").strip()

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        variables = context.get("variables", {})
        if self._uses_variable():
            name = self._variable_name()
            if not name:
                return ActionResult.failure("No se indicó la variable con los segundos")
            if name not in variables:
                return ActionResult.failure(f"La variable '{name}' no existe")
            raw = variables[name]
            try:
                seconds = float(str(raw).strip().replace(",", "."))
            except ValueError:
                return ActionResult.failure(f"La variable '{name}' no es un número válido: {raw!r}")
        else:
            params = self.resolve_params(variables)
            seconds = float(params.get("seconds", 1.0))

        if seconds < 0:
            return ActionResult.failure(f"Los segundos no pueden ser negativos: {seconds}")

        # Sleep in small slices so "Detener" interrupts long waits and "Pausar" freezes them
        stop_event = context.get("stop_event")
        pause_event = context.get("pause_event")
        log = context.get("log")
        show_progress = log is not None and seconds >= self.PROGRESS_MIN_SECONDS
        end = time.monotonic() + seconds
        shown = -1
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                break
            elapsed = seconds - remaining
            if stop_event is not None and stop_event.is_set():
                return ActionResult.success(
                    output=f"Espera interrumpida ({self._fmt(elapsed, seconds)}/{self._fmt(seconds, seconds)} s)")
            if pause_event is not None and not pause_event.is_set():
                if show_progress:
                    log(self._progress_text(elapsed, seconds, paused=True), "progress")
                pause_started = time.monotonic()
                pause_event.wait()
                end += time.monotonic() - pause_started
                shown = -1
                continue
            if show_progress and int(elapsed) != shown:
                shown = int(elapsed)
                log(self._progress_text(elapsed, seconds), "progress")
            time.sleep(min(0.1, remaining))
        return ActionResult.success(output=f"Esperó {seconds} segundos")

    # Shorter delays finish before a progress line is worth reading
    PROGRESS_MIN_SECONDS = 2
    _BAR_WIDTH = 20

    @staticmethod
    def _fmt(value: float, total: float) -> str:
        return str(int(value)) if float(total).is_integer() else f"{value:.1f}"

    @classmethod
    def _progress_text(cls, elapsed: float, total: float, paused: bool = False) -> str:
        filled = min(cls._BAR_WIDTH, int(cls._BAR_WIDTH * elapsed / total))
        bar = "█" * filled + "░" * (cls._BAR_WIDTH - filled)
        state = "  (en pausa)" if paused else ""
        return (f"  ⏱ {bar} {cls._fmt(elapsed, total)}/{cls._fmt(total, total)} s "
                f"({int(100 * elapsed / total)}%){state}")

    def get_summary(self) -> str:
        if self._uses_variable():
            return f"Esperar {{{self._variable_name()}}}s"
        return f"Esperar {self.params.get('seconds', 1.0)}s"


class WaitForWindowAction(BaseAction):
    action_type = "wait_for_window"
    label = "Esperar Ventana"
    icon = "💬"

    ON_TIMEOUT_FAIL = "Marcar error"
    ON_TIMEOUT_CONTINUE = "Continuar"

    PARAM_SCHEMA = {
        "title_contains": {"type": "str", "label": "Título contiene (vacío = cualquier ventana nueva)",
                           "placeholder": "ej. Información, Guardar como"},
        "process_name": {"type": "str", "label": "Programa (vacío = cualquiera)",
                         "placeholder": "ej. saplogon.exe, excel.exe"},
        "only_new": {"type": "bool", "label": "Ignorar ventanas que ya estaban abiertas", "default": True},
        "timeout": {"type": "float", "label": "Tiempo máximo de espera (seg)", "default": 30.0},
        "on_timeout": {"type": "choice", "label": "Si no aparece", "default": ON_TIMEOUT_FAIL,
                       "choices": [ON_TIMEOUT_FAIL, ON_TIMEOUT_CONTINUE]},
        "focus": {"type": "bool", "label": "Enfocar la ventana cuando aparezca", "default": True},
        "output_variable": {"type": "str", "label": "Variable para el título (vacía si no apareció)",
                            "default": "ventana_titulo"},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        from .windows import list_windows, matches_process, focus_window, wait_until

        params = self.resolve_params(context.get("variables", {}))
        title_part = str(params.get("title_contains", "")).strip().lower()
        process = str(params.get("process_name", "")).strip()
        # Without a title "any window" only makes sense for windows that appear from now on
        only_new = bool(params.get("only_new", True)) or not title_part
        timeout = max(0.0, float(params.get("timeout", 30.0)))
        output_var = str(params.get("output_variable", self.PARAM_SCHEMA["output_variable"]["default"])).strip()

        try:
            existing = {w.hwnd for w in list_windows()} if only_new else set()
        except Exception as e:
            return ActionResult.failure(f"No se pudieron enumerar las ventanas: {e}")

        def find():
            for w in list_windows():
                if w.hwnd in existing or not matches_process(w, process):
                    continue
                if title_part and title_part not in w.title.lower():
                    continue
                return w
            return None

        window, elapsed, stopped = wait_until(context, find, timeout)
        if stopped:
            return ActionResult.success(output="Espera de ventana interrumpida al detener el workflow")

        if window is None:
            variables = {output_var: ""} if output_var else {}
            what = f"con «{params.get('title_contains', '').strip()}»" if title_part else "nueva"
            msg = f"No apareció ninguna ventana {what} en {timeout:g} s"
            if params.get("on_timeout", self.ON_TIMEOUT_FAIL) == self.ON_TIMEOUT_CONTINUE:
                return ActionResult.success(output=f"{msg} — se continúa", variables=variables)
            if only_new and title_part:
                msg += " (si ya estaba abierta antes de este paso, desmarca 'Ignorar ventanas que ya estaban abiertas')"
            return ActionResult.failure(msg)

        if params.get("focus", True):
            focus_window(window.hwnd)
        variables = {output_var: window.title} if output_var else {}
        return ActionResult.success(
            output=f"Apareció la ventana {window.describe()} tras {elapsed:.1f} s", variables=variables)

    def get_summary(self) -> str:
        title = str(self.params.get("title_contains", "")).strip()
        process = str(self.params.get("process_name", "")).strip()
        target = f"«{title}»" if title else "nueva"
        where = f" de {process}" if process else ""
        return f"Esperar ventana {target}{where} (máx {self.params.get('timeout', 30.0)}s)"


class WaitForVariableAction(BaseAction):
    action_type = "wait"
    label = "Esperar Variable (Wait For)"
    icon = "⏳"

    PARAM_SCHEMA = {
        "variable_name": {"type": "str", "label": "Nombre de la variable a monitorear", "required": True},
        "expected_value": {"type": "str", "label": "Valor esperado", "default": "True"},
        "timeout": {"type": "float", "label": "Tiempo máximo de espera (segundos)", "default": 30.0},
        "poll_interval": {"type": "float", "label": "Intervalo de consulta (segundos)", "default": 0.5},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))

        variable_name = params.get("variable_name", "").strip()
        expected_value = str(params.get("expected_value", "True"))
        timeout = float(params.get("timeout", 30.0))
        poll_interval = float(params.get("poll_interval", 0.5))

        if not variable_name:
            return ActionResult.failure("El nombre de variable no puede estar vacío")

        if poll_interval <= 0:
            poll_interval = 0.5

        start_time = time.time()
        elapsed = 0.0

        while True:
            # Releer las variables en cada iteración por si otra acción/hilo las actualiza
            current_variables = context.get("variables", {})
            current_value = current_variables.get(variable_name)

            if current_value is not None and str(current_value) == expected_value:
                return ActionResult.success(
                    output=f"'{variable_name}' llegó a '{expected_value}' después de {elapsed:.2f}s"
                )

            elapsed = time.time() - start_time
            if elapsed >= timeout:
                return ActionResult.failure(
                    f"Timeout esperando '{variable_name}' == '{expected_value}' "
                    f"(esperó {timeout}s, valor actual: {current_value!r})"
                )

            time.sleep(min(poll_interval, timeout - elapsed))

    def get_summary(self) -> str:
        var = self.params.get("variable_name", "")
        val = self.params.get("expected_value", "True")
        timeout = self.params.get("timeout", 30.0)
        return f"Esperar hasta que {var} == \"{val}\" (timeout {timeout}s)"

class SetVariableAction(BaseAction):
    action_type = "set_variable"
    label = "Establecer Variable"
    icon = "📌"

    PARAM_SCHEMA = {
        "variable_name": {"type": "str", "label": "Nombre de la variable", "required": True},
        "value": {"type": "str", "label": "Valor (puede usar {otras_variables})", "required": True},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        name = params.get("variable_name", "").strip()
        value = params.get("value", "")
        if not name:
            return ActionResult.failure("El nombre de variable no puede estar vacío")
        return ActionResult.success(output=f"'{name}' = '{value}'", variables={name: value})

    def get_summary(self) -> str:
        return f"Set {self.params.get('variable_name','')} = \"{str(self.params.get('value',''))[:20]}\""

class GetClipBoard(BaseAction):
    action_type = "get_clipboard"
    label = "Obtener Portapapeles"
    icon = "📋"

    PARAM_SCHEMA = {
        "variable_name": {"type": "str", "label": "Nombre de la variable", "required": True},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        name = params.get("variable_name", "").strip()
        if not name:
            return ActionResult.failure("El nombre de variable no puede estar vacío")

        try:
            value = pyperclip.paste()
        except pyperclip.PyperclipException as e:
            return ActionResult.failure(f"No se pudo leer el portapapeles: {e}")

        return ActionResult.success(output=f"'{name}' = '{value}'", variables={name: value})

    def get_summary(self) -> str:
        return f"Portapapeles → {self.params.get('variable_name', '')}"

class IfConditionAction(BaseAction):
    action_type = "if_condition"
    label = "Condición Si/No"
    icon = "🔀"

    PARAM_SCHEMA = {
        "variable": {"type": "str", "label": "Variable a evaluar", "required": True},
        "operator": {"type": "choice", "label": "Operador", "default": "equals",
                    "choices": ["equals", "not_equals", "contains", "not_contains",
                                "starts_with", "is_empty", "is_not_empty"]},
        "value": {"type": "str", "label": "Valor a comparar"},
        "output_variable": {"type": "str", "label": "Variable resultado (true/false)", "default": "condition_result"},
    }

    OPERATOR_LABELS = {
        "equals": "==", "not_equals": "!=", "contains": "contiene",
        "not_contains": "no contiene", "starts_with": "empieza con",
        "is_empty": "está vacío", "is_not_empty": "no está vacío",
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        actual = str(context.get("variables", {}).get(params.get("variable", ""), ""))
        op = params.get("operator", "equals")
        cmp = params.get("value", "")
        result = self._eval(actual, op, cmp)
        out = params.get("output_variable", "condition_result")
        return ActionResult.success(
            output=f"{params.get('variable','')} {self.OPERATOR_LABELS.get(op,op)} '{cmp}' -> {result}",
            variables={out: "true" if result else "false"},
        )

    def _eval(self, a, op, b):
        if op == "equals": return a == b
        if op == "not_equals": return a != b
        if op == "contains": return b in a
        if op == "not_contains": return b not in a
        if op == "starts_with": return a.startswith(b)
        if op == "is_empty": return a.strip() == ""
        if op == "is_not_empty": return a.strip() != ""
        return False

    def get_summary(self) -> str:
        return f"Si {self.params.get('variable','')} {self.OPERATOR_LABELS.get(self.params.get('operator',''),'?')} \"{self.params.get('value','')}\""


# ── Loop actions — handled by the runner, execute() is never called ──────────

class LoopStartAction(BaseAction):
    """Marks the start of a repeat-N-times block. Runner handles the actual looping."""
    action_type = "loop_start"
    label = "Inicio de Loop"
    icon = "🔁"

    PARAM_SCHEMA = {
        "iterations": {"type": "int", "label": "Número de repeticiones", "default": 3},
        "counter_variable": {"type": "str", "label": "Variable contador (empieza en 0)", "default": "loop_index"},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        return ActionResult.success(output="Loop start — manejado por el runner")

    def get_summary(self) -> str:
        return f"🔁 Inicio loop × {self.params.get('iterations', 3)}"


class LoopEndAction(BaseAction):
    """Marks the end of any loop block. Runner handles jumping back."""
    action_type = "loop_end"
    label = "Fin de Loop"
    icon = "🔚"

    PARAM_SCHEMA = {}

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        return ActionResult.success(output="Loop end — manejado por el runner")

    def get_summary(self) -> str:
        return "🔚 Fin de loop"


# Keep old name for any saved workflows
LoopAction = LoopStartAction
