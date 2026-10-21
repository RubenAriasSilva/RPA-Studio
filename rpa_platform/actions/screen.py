import time
import os
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import numpy as np
import pyautogui
from PIL import Image
from .base import BaseAction, ActionResult


class WaitForScreenChangeAction(BaseAction):
    action_type = "wait_for_screen_change"
    label = "Esperar Cambio de Pantalla"
    icon = "🔄"

    PARAM_SCHEMA = {
        "timeout": {"type": "int", "label": "Tiempo máximo (segundos)", "default": 60},
        "change_threshold": {
            "type": "float",
            "label": "Cambio mínimo de pantalla (%)",
            "default": 0.5,
        },
        "stable_for": {
            "type": "float",
            "label": "Tiempo estable antes de continuar (segundos)",
            "default": 1.0,
        },
        "check_interval": {
            "type": "float",
            "label": "Intervalo de revisión (segundos)",
            "default": 0.4,
        },
    }

    _IMAGE_SIZE = (320, 180)
    _PIXEL_CHANGE_THRESHOLD = 25

    @classmethod
    def _capture_reduced_screen(cls) -> np.ndarray:
        screenshot = pyautogui.screenshot().convert("L")
        screenshot.thumbnail(cls._IMAGE_SIZE, Image.Resampling.BILINEAR)
        return np.asarray(screenshot, dtype=np.int16)

    @classmethod
    def _change_percent(cls, previous: np.ndarray, current: np.ndarray) -> float:
        if previous.shape != current.shape:
            return 100.0
        changed_pixels = np.abs(current - previous) >= cls._PIXEL_CHANGE_THRESHOLD
        return float(np.count_nonzero(changed_pixels) * 100 / changed_pixels.size)

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        timeout = max(1, int(params.get("timeout", 60)))
        change_threshold = min(100.0, max(0.01, float(params.get("change_threshold", 0.5))))
        stable_for = max(0.0, float(params.get("stable_for", 1.0)))
        check_interval = max(0.1, float(params.get("check_interval", 0.4)))
        stop_event = context.get("stop_event")
        pause_event = context.get("pause_event")

        try:
            previous = self._capture_reduced_screen()
        except Exception as exc:
            return ActionResult.failure(f"No se pudo capturar la pantalla: {exc}")

        started_at = time.monotonic()
        deadline = started_at + timeout
        stable_since = None
        change_detected = False

        while True:
            if stop_event and stop_event.is_set():
                return ActionResult.success(output="Espera visual interrumpida al detener el workflow")

            if pause_event and not pause_event.is_set():
                pause_started_at = time.monotonic()
                pause_event.wait()
                paused_for = time.monotonic() - pause_started_at
                deadline += paused_for
                if stable_since is not None:
                    stable_since = time.monotonic()
                continue

            now = time.monotonic()
            if now >= deadline:
                return ActionResult.failure(
                    f"La pantalla no completó un cambio estable en {timeout} segundos"
                )

            try:
                current = self._capture_reduced_screen()
            except Exception as exc:
                return ActionResult.failure(f"No se pudo capturar la pantalla: {exc}")

            changed_percent = self._change_percent(previous, current)
            previous = current

            if changed_percent >= change_threshold:
                change_detected = True
                stable_since = None
            elif change_detected:
                if stable_since is None:
                    stable_since = now
                elif now - stable_since >= stable_for:
                    elapsed = now - started_at
                    return ActionResult.success(
                        output=f"Cambio de pantalla detectado y estable después de {elapsed:.1f}s"
                    )

            wait_time = min(check_interval, max(0.0, deadline - time.monotonic()))
            if stop_event:
                if stop_event.wait(wait_time):
                    return ActionResult.success(
                        output="Espera visual interrumpida al detener el workflow"
                    )
            else:
                time.sleep(wait_time)

    def get_summary(self) -> str:
        timeout = self.params.get("timeout", 60)
        return f"Esperar cambio visual (máx {timeout}s)"


class ScreenshotAction(BaseAction):
    action_type = "screenshot"
    label = "Captura de Pantalla"
    icon = "📷"

    PARAM_SCHEMA = {
        "output_variable": {"type": "str", "label": "Variable para guardar ruta", "default": "screenshot_path"},
        "save_to_file": {"type": "bool", "label": "Guardar como archivo", "default": True},
        "output_dir": {"type": "str", "label": "Carpeta de destino", "default": "captures"},
        "region": {"type": "region", "label": "Región (x,y,ancho,alto) — vacío = pantalla completa", "default": ""},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        output_var = params.get("output_variable", "screenshot_path")
        save_to_file = params.get("save_to_file", True)
        output_dir = params.get("output_dir", "captures")
        region_str = params.get("region", "")

        try:
            region = None
            if region_str:
                parts = [int(x.strip()) for x in region_str.split(",")]
                if len(parts) == 4:
                    region = tuple(parts)

            screenshot = pyautogui.screenshot(region=region)
            variables = {}

            if save_to_file:
                os.makedirs(output_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filepath = os.path.join(output_dir, f"screenshot_{timestamp}.png")
                screenshot.save(filepath)
                variables[output_var] = filepath
                return ActionResult.success(output=filepath, variables=variables)
            else:
                variables[output_var] = screenshot
                return ActionResult.success(output="Captura guardada en variable", variables=variables)

        except Exception as e:
            return ActionResult.failure(str(e))

    def get_summary(self) -> str:
        region = self.params.get("region", "")
        return f"Captura {'región' if region else 'pantalla completa'}"


class FindImageAction(BaseAction):
    action_type = "find_image"
    label = "Buscar Imagen"
    icon = "🔍"

    PARAM_SCHEMA = {
        "template_path": {"type": "file", "label": "Imagen a buscar", "required": True},
        "confidence": {"type": "float", "label": "Confianza (0.0 - 1.0)", "default": 0.8},
        "output_variable": {"type": "str", "label": "Variable para posición encontrada", "default": "found_position"},
        "click_on_found": {"type": "bool", "label": "Hacer click al encontrar", "default": False},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        template_path = params.get("template_path", "")
        confidence = float(params.get("confidence", 0.8))
        output_var = params.get("output_variable", "found_position")
        click_on_found = params.get("click_on_found", False)

        if not template_path or not os.path.exists(template_path):
            return ActionResult.failure(f"Imagen no encontrada: {template_path}")

        try:
            location = pyautogui.locateOnScreen(template_path, confidence=confidence)
            if location is None:
                return ActionResult.failure(f"Imagen '{os.path.basename(template_path)}' no encontrada en pantalla")

            center = pyautogui.center(location)
            variables = {output_var: f"{center.x},{center.y}"}

            if click_on_found:
                pyautogui.click(center)

            return ActionResult.success(
                output=f"Imagen encontrada en ({center.x}, {center.y})",
                variables=variables,
            )
        except Exception as e:
            return ActionResult.failure(str(e))

    def get_summary(self) -> str:
        path = self.params.get("template_path", "")
        return f"Buscar imagen: {os.path.basename(path)}"


class WaitForImageAction(BaseAction):
    action_type = "wait_for_image"
    label = "Esperar Imagen"
    icon = "⏳"

    PARAM_SCHEMA = {
        "template_path": {"type": "file", "label": "Imagen a esperar", "required": True},
        "timeout": {"type": "int", "label": "Tiempo máximo (seg)", "default": 30},
        "confidence": {"type": "float", "label": "Confianza (0.0 - 1.0)", "default": 0.8},
        "output_variable": {"type": "str", "label": "Variable para posición", "default": "wait_position"},
        "check_interval": {"type": "float", "label": "Intervalo de verificación (seg)", "default": 0.5},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        template_path = params.get("template_path", "")
        timeout = int(params.get("timeout", 30))
        confidence = float(params.get("confidence", 0.8))
        output_var = params.get("output_variable", "wait_position")
        check_interval = float(params.get("check_interval", 0.5))

        if not template_path or not os.path.exists(template_path):
            return ActionResult.failure(f"Imagen no encontrada: {template_path}")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                location = pyautogui.locateOnScreen(template_path, confidence=confidence)
                if location:
                    center = pyautogui.center(location)
                    variables = {output_var: f"{center.x},{center.y}"}
                    elapsed = round(time.time() - start_time, 1)
                    return ActionResult.success(
                        output=f"Imagen apareció en {elapsed}s en ({center.x}, {center.y})",
                        variables=variables,
                    )
            except Exception:
                pass
            time.sleep(check_interval)

        return ActionResult.failure(f"Imagen no apareció en {timeout} segundos")

    def get_summary(self) -> str:
        timeout = self.params.get("timeout", 30)
        return f"Esperar imagen (máx {timeout}s)"
