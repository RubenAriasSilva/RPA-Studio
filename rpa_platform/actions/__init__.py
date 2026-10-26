from .base import BaseAction, ActionResult
from .vision import (
    VisionFindElementAction, VisionReadTextAction,
    VisionVerifyAction, VisionWaitForElementAction,
)
from .keyboard import TypeTextAction, HotkeyAction, KeyPressAction, KeyHoldStartAction, KeyHoldEndAction
from .mouse import MouseClickAction, MouseMoveAction, MouseScrollAction
from .screen import (
    ScreenshotAction, FindImageAction, WaitForImageAction,
    WaitForScreenChangeAction,
)
from .ocr import OCRRegionAction, OCRFindTextAction
from .sap import (
    SAPLaunchAction, SAPFocusWindowAction, SAPOpenTransactionAction,
    SAPTypeInFieldAction, SAPReadFieldOCRAction, SAPClickButtonAction,
    SAPWaitScreenAction,
)
from .control import DelayAction, WaitForWindowAction, WaitForVariableAction, IfConditionAction, LoopAction, SetVariableAction, GetClipBoard, LoopStartAction, LoopEndAction
from .dialogs import ShowAlertAction, ShowPromptAction
from .excel import (
    ExcelReadCellAction, ExcelReadRangeAction, ExcelWriteCellAction,
    ExcelAppendRowAction, ExcelFormatRangeAction, ExcelFindValueAction,
    ExcelSaveAction, ExcelForEachRowAction, ExcelWaitWorkbookAction,
)

ACTION_REGISTRY = {
    # Vision AI
    "vision_find_element":    VisionFindElementAction,
    "vision_read_text":       VisionReadTextAction,
    "vision_verify":          VisionVerifyAction,
    "vision_wait_for_element": VisionWaitForElementAction,
    # Original
    "type_text": TypeTextAction,
    "hotkey": HotkeyAction,
    "key_press": KeyPressAction,
    "key_hold_start": KeyHoldStartAction,
    "key_hold_end": KeyHoldEndAction,
    "mouse_click": MouseClickAction,
    "mouse_move": MouseMoveAction,
    "mouse_scroll": MouseScrollAction,
    "screenshot": ScreenshotAction,
    "find_image": FindImageAction,
    "wait_for_image": WaitForImageAction,
    "wait_for_screen_change": WaitForScreenChangeAction,
    "ocr_region": OCRRegionAction,
    "ocr_find_text": OCRFindTextAction,
    "sap_launch": SAPLaunchAction,
    "sap_focus_window": SAPFocusWindowAction,
    "sap_open_transaction": SAPOpenTransactionAction,
    "sap_type_in_field": SAPTypeInFieldAction,
    "sap_read_field_ocr": SAPReadFieldOCRAction,
    "sap_click_button": SAPClickButtonAction,
    "sap_wait_screen": SAPWaitScreenAction,
    "show_alert": ShowAlertAction,
    "show_prompt": ShowPromptAction,
    "delay": DelayAction,
    "wait_for_window": WaitForWindowAction,
    "wait" : WaitForVariableAction,
    "if_condition": IfConditionAction,
    "loop": LoopStartAction,
    "loop_start": LoopStartAction,
    "loop_end": LoopEndAction,
    "set_variable": SetVariableAction,
    "get_clipboard": GetClipBoard,
    "excel_read_cell": ExcelReadCellAction,
    "excel_read_range": ExcelReadRangeAction,
    "excel_write_cell": ExcelWriteCellAction,
    "excel_append_row": ExcelAppendRowAction,
    "excel_format_range": ExcelFormatRangeAction,
    "excel_find_value": ExcelFindValueAction,
    "excel_save": ExcelSaveAction,
    "excel_foreach_row": ExcelForEachRowAction,
    "excel_wait_workbook": ExcelWaitWorkbookAction,
}

ACTION_CATEGORIES = {
    "Vision AI 🤖": [
        "vision_find_element",
        "vision_read_text",
        "vision_verify",
        "vision_wait_for_element",
    ],
    "Teclado": ["type_text", "hotkey", "key_press", "key_hold_start"],
    "Mouse": ["mouse_click", "mouse_move", "mouse_scroll"],
    "Pantalla": ["screenshot", "find_image", "wait_for_image", "wait_for_screen_change"],
    "OCR": ["ocr_region", "ocr_find_text"],
    "SAP": ["sap_launch", "sap_focus_window", "sap_open_transaction", "sap_type_in_field", "sap_read_field_ocr", "sap_click_button", "sap_wait_screen"],
    "Excel": ["excel_foreach_row", "excel_read_cell", "excel_read_range", "excel_write_cell",
              "excel_append_row", "excel_format_range", "excel_find_value", "excel_save", "excel_wait_workbook"],
    "Diálogos": ["show_alert", "show_prompt"],
    "Control": ["delay", "wait_for_window", "wait", "set_variable", "get_clipboard", "if_condition", "loop_start", "loop_end"],
}

ACTION_LABELS = {
    # Vision AI
    "vision_find_element":     "Vision - Encontrar Elemento",
    "vision_read_text":        "Vision - Leer Texto",
    "vision_verify":           "Vision - Verificar Estado",
    "vision_wait_for_element": "Vision - Esperar Elemento",
    # Original
    "type_text": "Escribir Texto",
    "hotkey": "Tecla Rápida",
    "key_press": "Presionar Tecla",
    "key_hold_start": "Mantener Tecla Presionada",
    "key_hold_end": "Soltar Tecla",
    "mouse_click": "Click",
    "mouse_move": "Mover Mouse",
    "mouse_scroll": "Scroll",
    "screenshot": "Captura de Pantalla",
    "find_image": "Buscar Imagen",
    "wait_for_image": "Esperar Imagen",
    "wait_for_screen_change": "Esperar Cambio de Pantalla",
    "ocr_region": "OCR - Leer Región",
    "ocr_find_text": "OCR - Buscar Texto",
    "sap_launch": "SAP - Abrir SAP Logon",
    "sap_focus_window": "SAP - Enfocar Ventana",
    "sap_open_transaction": "SAP - Abrir Transacción",
    "sap_type_in_field": "SAP - Escribir Campo",
    "sap_read_field_ocr": "SAP - Leer Campo (OCR)",
    "sap_click_button": "SAP - Click / Tecla",
    "sap_wait_screen": "SAP - Esperar Cambio de Pantalla",
    "show_alert": "Mostrar Alerta",
    "show_prompt": "Pedir Dato al Usuario",
    "delay": "Esperar (Delay)",
    "wait_for_window": "Esperar Ventana",
    "wait": "Esperar a una variable",
    "if_condition": "Condición Si/No",
    "loop_start": "Inicio de Loop",
    "loop_end": "Fin de Loop",
    "loop": "Inicio de Loop",
    "set_variable": "Establecer Variable",
    "excel_read_cell": "Excel - Leer Celda",
    "excel_read_range": "Excel - Leer Rango",
    "excel_write_cell": "Excel - Escribir Celda",
    "excel_append_row": "Excel - Agregar Fila",
    "excel_format_range": "Excel - Dar Formato",
    "excel_find_value": "Excel - Buscar Valor",
    "excel_save": "Excel - Guardar",
    "excel_foreach_row": "Excel - Para Cada Fila",
    "excel_wait_workbook": "Excel - Esperar Libro Nuevo",
}
