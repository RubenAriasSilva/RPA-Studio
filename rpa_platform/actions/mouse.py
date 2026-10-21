import time
from typing import Dict, Any
import pyautogui
from .base import BaseAction, ActionResult

pyautogui.FAILSAFE = True

coordinateAdjustment = 1 # 1 por defecto


from typing import Dict, Tuple, Optional

def _resolve_coords(params: Dict, variables: Dict) -> Optional[Tuple[int, int]]:
    """
    Returns (x, y) resolved from either:
      - 'from_variable' → variable containing "x,y" string  (OCR output format)
      - 'x' + 'y' fields (can also be variable references)
    Multiplies both coordinates by 1.25.
    Returns None if coords cannot be determined.
    """
    from_var = str(params.get("from_variable", "")).strip()
    if from_var:
        raw = variables.get(from_var, "")
        parts = str(raw).split(",")
        if len(parts) >= 2:
            try:
                x = int(float(parts[0].strip()) * coordinateAdjustment)
                y = int(float(parts[1].strip()) * coordinateAdjustment)
                return x, y
            except ValueError:
                pass

    try:
        x_raw = str(params.get("x", "0")).strip()
        y_raw = str(params.get("y", "0")).strip()
        # resolve variable references like {found_x}
        for k, v in variables.items():
            x_raw = x_raw.replace(f"{{{k}}}", str(v))
            y_raw = y_raw.replace(f"{{{k}}}", str(v))
            
        x = int(float(x_raw) * coordinateAdjustment)
        y = int(float(y_raw) * coordinateAdjustment)
        return x, y
    except (ValueError, TypeError):
        return None


class MouseClickAction(BaseAction):
    action_type = "mouse_click"
    label = "Click"
    icon = "🖱️"

    PARAM_SCHEMA = {
        "region": {
            "type": "region",
            "label": "Región (click al centro) — vacío = usar X, Y",
            "default": "",
        },
        "from_variable": {
            "type": "str",
            "label": "Posición desde variable «x,y» (ej: {text_position})",
            "default": "",
        },
        "x": {"type": "str", "label": "X — coordenada o variable", "default": "0"},
        "y": {"type": "str", "label": "Y — coordenada o variable", "default": "0"},
        "button": {
            "type": "choice", "label": "Botón del mouse", "default": "left",
            "choices": ["left", "right", "middle"],
        },
        "clicks": {"type": "int", "label": "Número de clicks (2 = doble click)", "default": 1},
        "offset_x": {"type": "int", "label": "Desplazamiento X (offset)", "default": 0},
        "offset_y": {"type": "int", "label": "Desplazamiento Y (offset)", "default": 0},
        "wait_after": {"type": "float", "label": "Espera después del click (seg)", "default": 0.1},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params    = self.resolve_params(context.get("variables", {}))
        variables = context.get("variables", {})

        region_str = str(params.get("region", "")).strip()
        if region_str:
            try:
                rx, ry, rw, rh = [int(v.strip()) for v in region_str.split(",")]
                x = (rx * coordinateAdjustment) + rw // 2
                y = (ry * coordinateAdjustment) + rh // 2
            except (ValueError, TypeError):
                return ActionResult.failure(f"Región inválida: '{region_str}'")
        else:
            coords = _resolve_coords(params, variables)
            if coords is None:
                return ActionResult.failure(
                    "No se pudieron determinar las coordenadas. "
                    "Selecciona una región o define X e Y."
                )
            x, y = coords

        x += int(params.get("offset_x", 0))
        y += int(params.get("offset_y", 0))
        button    = params.get("button", "left")
        clicks    = int(params.get("clicks", 1))
        wait_after = float(params.get("wait_after", 0.1))

        try:
            pyautogui.click(x, y, clicks=clicks, button=button)
            time.sleep(wait_after)
            label = "doble click" if clicks == 2 else f"click {button}"
            source = f"region->centro" if region_str else "coords"
            return ActionResult.success(output=f"{label} en ({x}, {y})  [{source}]")
        except Exception as e:
            return ActionResult.failure(str(e))

    def get_summary(self) -> str:
        region = self.params.get("region", "")
        if region:
            return f"Click en región {region}"
        from_var = self.params.get("from_variable", "")
        if from_var:
            clicks = int(self.params.get("clicks", 1))
            label = "doble click" if clicks == 2 else "click"
            return f"{label} en {{{from_var}}}"
        x      = self.params.get("x", "0")
        y      = self.params.get("y", "0")
        clicks = int(self.params.get("clicks", 1))
        label  = "Doble click" if clicks == 2 else "Click"
        btn    = self.params.get("button", "left")
        suffix = f" [{btn}]" if btn != "left" else ""
        return f"{label} ({x}, {y}){suffix}"


class MouseMoveAction(BaseAction):
    action_type = "mouse_move"
    label = "Mover Mouse"
    icon = "↖️"

    PARAM_SCHEMA = {
        "from_variable": {
            "type": "str",
            "label": "Posición desde variable «x,y»",
            "default": "",
        },
        "x": {"type": "str", "label": "X", "default": "0"},
        "y": {"type": "str", "label": "Y", "default": "0"},
        "duration": {"type": "float", "label": "Duración del movimiento (seg)", "default": 0.2},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        variables = context.get("variables", {})

        coords = _resolve_coords(params, variables)
        if coords is None:
            return ActionResult.failure("No se pudieron determinar las coordenadas.")

        x, y = coords
        duration = float(params.get("duration", 0.2))
        try:
            pyautogui.moveTo(x, y, duration=duration)
            return ActionResult.success(output=f"Mouse movido a ({x}, {y})")
        except Exception as e:
            return ActionResult.failure(str(e))

    def get_summary(self) -> str:
        from_var = self.params.get("from_variable", "")
        if from_var:
            return f"Mover mouse a {{{from_var}}}"
        return f"Mover mouse a ({self.params.get('x','0')}, {self.params.get('y','0')})"


class MouseScrollAction(BaseAction):
    action_type = "mouse_scroll"
    label = "Scroll"
    icon = "🖱️↕"

    PARAM_SCHEMA = {
        "direction": {
            "type": "choice", "label": "Dirección", "default": "down",
            "choices": ["down", "up"],
        },
        "clicks": {"type": "int", "label": "Cantidad de scroll", "default": 3},
        "x": {"type": "str", "label": "X (vacío = posición actual)", "default": ""},
        "y": {"type": "str", "label": "Y (vacío = posición actual)", "default": ""},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        direction = params.get("direction", "down")
        clicks = int(params.get("clicks", 3))
        amount = -clicks if direction == "down" else clicks

        x_raw = str(params.get("x", "")).strip()
        y_raw = str(params.get("y", "")).strip()

        try:
            if x_raw and y_raw:
                pyautogui.scroll(amount, x=int(x_raw), y=int(y_raw))
            else:
                pyautogui.scroll(amount)
            return ActionResult.success(output=f"Scroll {direction} × {clicks}")
        except Exception as e:
            return ActionResult.failure(str(e))

    def get_summary(self) -> str:
        direction = self.params.get("direction", "down")
        clicks = self.params.get("clicks", 3)
        arrow = "↓" if direction == "down" else "↑"
        return f"Scroll {arrow} × {clicks}"
