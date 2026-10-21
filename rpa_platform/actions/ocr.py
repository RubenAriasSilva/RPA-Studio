import os
import time
from typing import Dict, Any, List, Optional, Tuple
import pyautogui
from PIL import Image
from .base import BaseAction, ActionResult

_ocr_reader = None


def get_ocr_reader(languages=None):
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        langs = languages or ["es", "en"]
        _ocr_reader = easyocr.Reader(langs, gpu=False)
    return _ocr_reader


class OCRRegionAction(BaseAction):
    action_type = "ocr_region"
    label = "OCR - Leer Región"
    icon = "📝"

    PARAM_SCHEMA = {
        "region": {"type": "region", "label": "Región (x,y,ancho,alto) — vacío = pantalla completa", "default": ""},
        "output_variable": {"type": "str", "label": "Variable para el texto extraído", "default": "ocr_text"},
        "languages": {"type": "str", "label": "Idiomas (ej: es,en)", "default": "es,en"},
        "detail": {"type": "bool", "label": "Guardar detalle con posiciones", "default": False},
        "preprocessing": {"type": "choice", "label": "Pre-procesamiento", "default": "none",
                         "choices": ["none", "grayscale", "threshold", "contrast"]},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        region_str = params.get("region", "")
        output_var = params.get("output_variable", "ocr_text")
        lang_str = params.get("languages", "es,en")
        detail = params.get("detail", False)
        preprocessing = params.get("preprocessing", "none")

        try:
            region = None
            if region_str:
                parts = [int(x.strip()) for x in region_str.split(",")]
                if len(parts) == 4:
                    region = tuple(parts)

            screenshot = pyautogui.screenshot(region=region)
            image = _preprocess_image(screenshot, preprocessing)

            langs = [l.strip() for l in lang_str.split(",")]
            reader = get_ocr_reader(langs)

            import numpy as np
            img_array = np.array(image)

            if detail:
                results = reader.readtext(img_array)
                full_text = "\n".join([r[1] for r in results])
                detail_list = [{"text": r[1], "confidence": round(r[2], 3),
                                "box": r[0]} for r in results]
                variables = {output_var: full_text, f"{output_var}_detail": str(detail_list)}
            else:
                results = reader.readtext(img_array, detail=0)
                full_text = "\n".join(results)
                variables = {output_var: full_text}

            return ActionResult.success(
                output=f"Texto extraído ({len(full_text)} chars): {full_text[:100]}",
                variables=variables,
            )
        except Exception as e:
            return ActionResult.failure(str(e))

    def get_summary(self) -> str:
        var = self.params.get("output_variable", "ocr_text")
        region = self.params.get("region", "")
        return f"OCR -> {var} {'(region)' if region else '(pantalla)'}"


class OCRFindTextAction(BaseAction):
    action_type = "ocr_find_text"
    label = "OCR - Buscar Texto"
    icon = "🔎"

    PARAM_SCHEMA = {
        "search_text": {"type": "str", "label": "Texto a buscar", "required": True},
        "region": {"type": "region", "label": "Región de búsqueda (x,y,ancho,alto)", "default": ""},
        "case_sensitive": {"type": "bool", "label": "Distinguir mayúsculas", "default": False},
        "output_variable": {"type": "str", "label": "Variable para posición (x,y)", "default": "text_position"},
        "click_on_found": {"type": "bool", "label": "Click al encontrar", "default": False},
        "languages": {"type": "str", "label": "Idiomas", "default": "es,en"},
        "timeout": {"type": "int", "label": "Tiempo máximo buscando (seg, 0=una vez)", "default": 0},
    }

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        params = self.resolve_params(context.get("variables", {}))
        search_text = params.get("search_text", "")
        region_str = params.get("region", "")
        case_sensitive = params.get("case_sensitive", False)
        output_var = params.get("output_variable", "text_position")
        click_on_found = params.get("click_on_found", False)
        lang_str = params.get("languages", "es,en")
        timeout = int(params.get("timeout", 0))

        if not search_text:
            return ActionResult.failure("El texto de búsqueda no puede estar vacío")

        region = None
        if region_str:
            parts = [int(x.strip()) for x in region_str.split(",")]
            if len(parts) == 4:
                region = tuple(parts)

        langs = [l.strip() for l in lang_str.split(",")]

        start = time.time()
        attempts = 0
        while True:
            attempts += 1
            result = self._search_once(search_text, region, case_sensitive, langs)
            if result:
                cx, cy, text_found = result
                variables = {output_var: f"{cx},{cy}"}
                if click_on_found:
                    if region:
                        abs_x = region[0] + cx
                        abs_y = region[1] + cy
                    else:
                        abs_x, abs_y = cx, cy
                    pyautogui.click(abs_x, abs_y)
                return ActionResult.success(
                    output=f"Texto '{text_found}' encontrado en ({cx},{cy})",
                    variables=variables,
                )
            if timeout > 0 and time.time() - start < timeout:
                time.sleep(0.5)
            else:
                break

        return ActionResult.failure(f"Texto '{search_text}' no encontrado en pantalla")

    def _search_once(self, search_text, region, case_sensitive, langs):
        try:
            import numpy as np
            screenshot = pyautogui.screenshot(region=region)
            img_array = np.array(screenshot)
            reader = get_ocr_reader(langs)
            results = reader.readtext(img_array)

            compare = search_text if case_sensitive else search_text.lower()
            for bbox, text, conf in results:
                text_compare = text if case_sensitive else text.lower()
                if compare in text_compare:
                    pts = bbox
                    cx = int(sum(p[0] for p in pts) / 4)
                    cy = int(sum(p[1] for p in pts) / 4)
                    return cx, cy, text
        except Exception:
            pass
        return None

    def get_summary(self) -> str:
        text = self.params.get("search_text", "")
        return f"Buscar texto: \"{text[:30]}\""


def _preprocess_image(image: Image.Image, mode: str) -> Image.Image:
    if mode == "grayscale":
        return image.convert("L").convert("RGB")
    elif mode == "threshold":
        gray = image.convert("L")
        return gray.point(lambda x: 0 if x < 128 else 255).convert("RGB")
    elif mode == "contrast":
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(2.0)
    return image
