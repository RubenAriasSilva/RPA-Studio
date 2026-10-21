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

    @classmethod
    def success(cls, output=None, variables=None):
        return cls(ActionStatus.SUCCESS, output=output, variables=variables or {})

    @classmethod
    def failure(cls, error: str):
        return cls(ActionStatus.FAILED, error=error)


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
