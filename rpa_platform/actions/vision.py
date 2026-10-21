"""Claude Vision-powered actions for intelligent screen automation."""

import os
import re
import base64
import json
import time
from io import BytesIO
from typing import Dict, Any, Optional, Tuple

import pyautogui
from PIL import Image

from .base import BaseAction, ActionResult

_HAIKU  = "claude-haiku-4-5-20251001"
_SONNET = "claude-sonnet-4-6"

_MODEL_CHOICES = ["sonnet (preciso)", "haiku (rápido)"]
_MODEL_MAP     = {"sonnet (preciso)": _SONNET, "haiku (rápido)": _HAIKU}


def _client():
    try:
        import anthropic
    except ImportError:
        raise ImportError("Instala el SDK: pip install anthropic")
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY no está configurada. "
            "Agrégala como variable de entorno antes de ejecutar."
        )
    return anthropic.Anthropic(api_key=key)


def _capture_b64(region=None, max_px: int = 1600, debug_save: bool = False) -> Tuple[str, float, int, int, tuple]:
    """
    Capture screenshot and return (base64_png, scale, img_w, img_h, actual_region).
    scale < 1 means image was shrunk; use screen_coord = img_coord / scale + offset.
    Defaults to primary screen when region is None.
    """
    if region is None:
        from core.screen_utils import primary_rect
        region = primary_rect()
    img = pyautogui.screenshot(region=region)
    raw_w, raw_h = img.size
    scale = 1.0
    if max(raw_w, raw_h) > max_px:
        scale = max_px / max(raw_w, raw_h)
        img = img.resize((int(raw_w * scale), int(raw_h * scale)), Image.LANCZOS)
    img_w, img_h = img.size
    if debug_save:
        import os, tempfile
        path = os.path.join(tempfile.gettempdir(), "rpa_vision_debug.png")
        img.save(path)
        print(f"[Vision DEBUG] captura guardada -> {path}  region={region}  raw={raw_w}x{raw_h}  enviado={img_w}x{img_h}  scale={scale:.3f}")
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.standard_b64encode(buf.getvalue()).decode()
    return b64, scale, img_w, img_h, region


def _parse_region(region_str: str) -> Optional[Tuple[int, int, int, int]]:
    try:
        parts = [int(x.strip()) for x in region_str.split(",")]
        return tuple(parts) if len(parts) == 4 else None
    except (ValueError, AttributeError):
        return None


def _parse_json(raw: str) -> dict:
    """
    Extract a JSON object from model response robustly.
    Handles: direct JSON, markdown fences, JSON embedded in text.
    """
    text = raw.strip()
    # 1. Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 2. Strip markdown fences
    if "```" in text:
        for part in text.split("```"):
            p = part.strip()
            if p.lower().startswith("json"):
                p = p[4:].strip()
            try:
                return json.loads(p)
            except json.JSONDecodeError:
                continue
    # 3. Regex: find first {...} block (handles text before/after JSON)
    m = re.search(r'\{[^{}]+\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    raise json.JSONDecodeError(f"No JSON en respuesta: {text[:120]}", text, 0)


def _find_prompt(desc: str, img_w: int, img_h: int) -> str:
    """Build the element-finding prompt with concrete example coordinates."""
    cx, cy = img_w // 2, img_h // 2
    return (
        f"Esta es una captura de pantalla ({img_w}×{img_h} píxeles).\n"
        f"Busca el siguiente elemento de interfaz de usuario: \"{desc}\"\n\n"
        f"Responde SOLO con un objeto JSON (sin markdown, sin texto extra):\n"
        f"  Si lo encuentras:     {{\"found\": true,  \"x\": {cx}, \"y\": {cy}, \"note\": \"descripcion corta\"}}\n"
        f"  Si NO lo encuentras:  {{\"found\": false}}\n\n"
        f"x e y = coordenadas del CENTRO del elemento en píxeles de esta imagen."
    )


# ── Vision Find Element ───────────────────────────────────────────────────────

class VisionFindElementAction(BaseAction):
    action_type = "vision_find_element"
    label = "Vision - Encontrar Elemento"
    icon = "🤖"

    PARAM_SCHEMA = {
        "description": {
            "type": "str",
            "label": "Descripción del elemento (ej: 'botón Guardar', 'campo Cantidad')",
            "required": True,
            "default": "",
        },
        "region": {
            "type": "region",
            "label": "Región de búsqueda (x,y,ancho,alto) — vacío = Pantalla 1 completa",
            "default": "",
        },
        "output_variable": {
            "type": "str",
            "label": "Variable para posición encontrada (x,y)",
            "default": "vision_position",
        },
        "click_on_found": {
            "type": "bool",
            "label": "Hacer click al encontrar",
            "default": False,
        },
        "model": {
            "type": "choice",
            "label": "Modelo Claude",
            "default": "sonnet (preciso)",
            "choices": _MODEL_CHOICES,
        },
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params     = self.resolve_params(context.get("variables", {}))
        desc       = params.get("description", "").strip()
        region_str = params.get("region", "")
        out_var    = params.get("output_variable", "vision_position")
        click      = params.get("click_on_found", False)
        model_id   = _MODEL_MAP.get(params.get("model", "sonnet (preciso)"), _SONNET)

        if not desc:
            return ActionResult.failure("La descripción del elemento no puede estar vacía")

        region = _parse_region(region_str)
        offset = (region[0], region[1]) if region else (0, 0)

        raw_response = ""
        try:
            cli = _client()
            b64, scale, img_w, img_h, actual_region = _capture_b64(region)
            rx, ry, rw, rh = actual_region
            prompt = _find_prompt(desc, img_w, img_h)

            resp = cli.messages.create(
                model=model_id,
                max_tokens=200,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": prompt},
                ]}],
            )
            raw_response = resp.content[0].text
            data = _parse_json(raw_response)

            capture_info = f"región=({rx},{ry},{rw},{rh})  imagen={img_w}×{img_h}  scale={scale:.2f}"

            if not data.get("found"):
                return ActionResult.failure(
                    f"Elemento '{desc}' no encontrado\n"
                    f"  {capture_info}\n"
                    f"  Claude: {raw_response[:300]}\n"
                    f"  Debug img: %TEMP%\\rpa_vision_debug.png"
                )

            sx = int(data["x"] / scale) + offset[0]
            sy = int(data["y"] / scale) + offset[1]
            variables = {out_var: f"{sx},{sy}"}

            if click:
                if region:
                    cx = region[0] + region[2] // 2
                    cy = region[1] + region[3] // 2
                else:
                    cx, cy = sx, sy
                pyautogui.click(cx, cy)

            note = data.get("note", desc)
            click_info = f"click:({cx},{cy})" if click else "sin click"
            return ActionResult.success(
                output=f"'{note}' encontrado  {capture_info}\n  coord=({sx},{sy})  {click_info}",
                variables=variables,
            )

        except json.JSONDecodeError:
            return ActionResult.failure(
                f"No se pudo parsear respuesta del modelo.\n"
                f"  Raw: {raw_response[:200]}"
            )
        except Exception as e:
            return ActionResult.failure(str(e))

    def get_summary(self) -> str:
        desc = self.params.get("description", "")
        return f"Vision: buscar '{desc[:35]}'"


# ── Vision Read Text ──────────────────────────────────────────────────────────

class VisionReadTextAction(BaseAction):
    action_type = "vision_read_text"
    label = "Vision - Leer Texto"
    icon = "🔤"

    PARAM_SCHEMA = {
        "prompt": {
            "type": "str",
            "label": "Qué extraer (ej: 'el número de orden', 'todos los montos de la tabla')",
            "required": True,
            "default": "el texto visible en pantalla",
        },
        "region": {
            "type": "region",
            "label": "Región (x,y,ancho,alto) — vacío = Pantalla 1 completa",
            "default": "",
        },
        "output_variable": {
            "type": "str",
            "label": "Variable para el texto extraído",
            "default": "vision_text",
        },
        "model": {
            "type": "choice",
            "label": "Modelo Claude",
            "default": "haiku (rápido)",
            "choices": _MODEL_CHOICES,
        },
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params      = self.resolve_params(context.get("variables", {}))
        user_prompt = params.get("prompt", "el texto visible en pantalla")
        region_str  = params.get("region", "")
        out_var     = params.get("output_variable", "vision_text")
        model_id    = _MODEL_MAP.get(params.get("model", "haiku (rápido)"), _HAIKU)

        region = _parse_region(region_str)

        try:
            cli = _client()
            b64, _, img_w, img_h = _capture_b64(region, max_px=1920)

            prompt = (
                f"Esta es una captura de pantalla ({img_w}×{img_h} píxeles).\n"
                f"Extrae: {user_prompt}\n\n"
                f"Responde ÚNICAMENTE con el valor extraído, sin explicaciones ni formato extra.\n"
                f"Si no encuentras lo solicitado, responde exactamente: [NO ENCONTRADO]"
            )

            resp = cli.messages.create(
                model=model_id,
                max_tokens=512,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": prompt},
                ]}],
            )

            text = resp.content[0].text.strip()
            variables = {out_var: text}
            preview = text[:80] + ("…" if len(text) > 80 else "")
            return ActionResult.success(
                output=f"Texto extraído: «{preview}»",
                variables=variables,
            )

        except Exception as e:
            return ActionResult.failure(str(e))

    def get_summary(self) -> str:
        prompt = self.params.get("prompt", "")
        return f"Vision leer: {prompt[:35]}"


# ── Vision Verify ─────────────────────────────────────────────────────────────

class VisionVerifyAction(BaseAction):
    action_type = "vision_verify"
    label = "Vision - Verificar Estado"
    icon = "✅"

    PARAM_SCHEMA = {
        "question": {
            "type": "str",
            "label": "Pregunta sí/no sobre la pantalla (ej: '¿el diálogo de error está cerrado?')",
            "required": True,
            "default": "",
        },
        "region": {
            "type": "region",
            "label": "Región (x,y,ancho,alto) — vacío = Pantalla 1 completa",
            "default": "",
        },
        "output_variable": {
            "type": "str",
            "label": "Variable resultado (true / false)",
            "default": "vision_ok",
        },
        "fail_if_false": {
            "type": "bool",
            "label": "Fallar el paso si la respuesta es false",
            "default": False,
        },
        "model": {
            "type": "choice",
            "label": "Modelo Claude",
            "default": "haiku (rápido)",
            "choices": _MODEL_CHOICES,
        },
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params        = self.resolve_params(context.get("variables", {}))
        question      = params.get("question", "").strip()
        region_str    = params.get("region", "")
        out_var       = params.get("output_variable", "vision_ok")
        fail_on_false = params.get("fail_if_false", False)
        model_id      = _MODEL_MAP.get(params.get("model", "haiku (rápido)"), _HAIKU)

        if not question:
            return ActionResult.failure("La pregunta no puede estar vacía")

        region = _parse_region(region_str)

        try:
            cli = _client()
            b64, _, img_w, img_h = _capture_b64(region)

            prompt = (
                f"Esta es una captura de pantalla ({img_w}×{img_h} píxeles).\n"
                f"Responde la siguiente pregunta sobre lo que ves:\n\n"
                f"{question}\n\n"
                f"Responde ÚNICAMENTE con la palabra:  true  o  false  (sin puntos, sin explicaciones)."
            )

            resp = cli.messages.create(
                model=model_id,
                max_tokens=10,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": prompt},
                ]}],
            )

            answer    = resp.content[0].text.strip().lower()
            result    = answer.startswith("true")
            val_str   = "true" if result else "false"
            variables = {out_var: val_str}
            icon      = "✓" if result else "✗"

            if fail_on_false and not result:
                return ActionResult.failure(
                    f"Verificacion fallida: «{question[:60]}» -> false",
                    variables=variables,
                )

            return ActionResult.success(
                output=f"{icon} «{question[:60]}» -> {val_str}",
                variables=variables,
            )

        except Exception as e:
            return ActionResult.failure(str(e))

    def get_summary(self) -> str:
        q = self.params.get("question", "")
        return f"¿{q[:40]}?"


# ── Vision Wait For Element ───────────────────────────────────────────────────

class VisionWaitForElementAction(BaseAction):
    action_type = "vision_wait_for_element"
    label = "Vision - Esperar Elemento"
    icon = "⏳🤖"

    PARAM_SCHEMA = {
        "description": {
            "type": "str",
            "label": "Descripción del elemento a esperar",
            "required": True,
            "default": "",
        },
        "region": {
            "type": "region",
            "label": "Región (x,y,ancho,alto)",
            "default": "",
        },
        "timeout": {
            "type": "int",
            "label": "Tiempo máximo (seg)",
            "default": 30,
        },
        "check_interval": {
            "type": "float",
            "label": "Intervalo entre capturas (seg)",
            "default": 3.0,
        },
        "output_variable": {
            "type": "str",
            "label": "Variable para posición encontrada",
            "default": "vision_position",
        },
        "click_on_found": {
            "type": "bool",
            "label": "Click al encontrar",
            "default": False,
        },
        "model": {
            "type": "choice",
            "label": "Modelo Claude",
            "default": "sonnet (preciso)",
            "choices": _MODEL_CHOICES,
        },
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params     = self.resolve_params(context.get("variables", {}))
        desc       = params.get("description", "").strip()
        region_str = params.get("region", "")
        timeout    = int(params.get("timeout", 30))
        interval   = float(params.get("check_interval", 3.0))
        out_var    = params.get("output_variable", "vision_position")
        click      = params.get("click_on_found", False)
        model_id   = _MODEL_MAP.get(params.get("model", "sonnet (preciso)"), _SONNET)

        if not desc:
            return ActionResult.failure("La descripción del elemento no puede estar vacía")

        region = _parse_region(region_str)
        offset = (region[0], region[1]) if region else (0, 0)

        try:
            cli = _client()
        except Exception as e:
            return ActionResult.failure(str(e))

        start    = time.time()
        attempts = 0

        while time.time() - start < timeout:
            attempts += 1
            try:
                b64, scale, img_w, img_h = _capture_b64(region)
                prompt = _find_prompt(desc, img_w, img_h)

                resp = cli.messages.create(
                    model=model_id,
                    max_tokens=200,
                    messages=[{"role": "user", "content": [
                        {"type": "image", "source": {
                            "type": "base64", "media_type": "image/png", "data": b64}},
                        {"type": "text", "text": prompt},
                    ]}],
                )
                data = _parse_json(resp.content[0].text)
                if data.get("found"):
                    elapsed = round(time.time() - start, 1)
                    sx = int(data["x"] / scale) + offset[0]
                    sy = int(data["y"] / scale) + offset[1]
                    variables = {out_var: f"{sx},{sy}"}
                    if click:
                        if region:
                            cx = region[0] + region[2] // 2
                            cy = region[1] + region[3] // 2
                        else:
                            cx, cy = sx, sy
                        pyautogui.click(cx, cy)
                    return ActionResult.success(
                        output=f"Encontrado en {elapsed}s ({attempts} consultas) -> ({sx}, {sy})",
                        variables=variables,
                    )
            except Exception:
                pass

            time.sleep(interval)

        return ActionResult.failure(
            f"'{desc}' no apareció en {timeout}s ({attempts} consultas al API)"
        )

    def get_summary(self) -> str:
        desc    = self.params.get("description", "")
        timeout = self.params.get("timeout", 30)
        return f"Esperar (Vision): '{desc[:25]}' — {timeout}s"
