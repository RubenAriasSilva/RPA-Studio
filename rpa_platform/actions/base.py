from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from enum import Enum
import uuid


class ActionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ActionResult:
    status: ActionStatus
    output: Any = None
    error: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)
    abort: bool = False  # stop the whole workflow, not just this step

    @classmethod
    def success(cls, output=None, variables=None):
        return cls(ActionStatus.SUCCESS, output=output, variables=variables or {})

    @classmethod
    def failure(cls, error: str, abort: bool = False):
        return cls(ActionStatus.FAILED, error=error, abort=abort)


_BAR_WIDTH = 20


def progress_bar(elapsed: float, total: float, paused: bool = False) -> str:
    """Log line for a timed wait, e.g. `⏱ █████░░░ 75/100 s (75%)`."""
    fmt = (lambda v: str(int(v))) if float(total).is_integer() else (lambda v: f"{v:.1f}")
    ratio = min(1.0, elapsed / total) if total else 1.0
    filled = int(_BAR_WIDTH * ratio)
    bar = "█" * filled + "░" * (_BAR_WIDTH - filled)
    state = "  (en pausa)" if paused else ""
    return f"  ⏱ {bar} {fmt(elapsed)}/{fmt(total)} s ({int(100 * ratio)}%){state}"


class BaseAction:
    action_type: str = "base"
    label: str = "Acción Base"
    icon: str = "⚙️"

    PARAM_SCHEMA: Dict[str, Dict] = {}

    def __init__(self, params: Dict[str, Any] = None, step_id: str = None):
        self.step_id = step_id or str(uuid.uuid4())[:8]
        self.params = params or {}
        self.enabled = True

    def resolve_params(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        resolved = {}
        for key, value in self.params.items():
            if isinstance(value, str):
                for var_name, var_value in variables.items():
                    value = value.replace(f"{{{var_name}}}", str(var_value))
            resolved[key] = value
        return resolved

    def execute(self, context: Dict[str, Any]) -> ActionResult:
        raise NotImplementedError

    def to_dict(self) -> Dict:
        return {
            "step_id": self.step_id,
            "action_type": self.action_type,
            "params": self.params,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "BaseAction":
        action = cls(params=data.get("params", {}), step_id=data.get("step_id"))
        action.enabled = data.get("enabled", True)
        return action

    def get_summary(self) -> str:
        return self.label
