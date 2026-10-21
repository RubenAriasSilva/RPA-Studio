import copy
import json
import uuid
from typing import List, Dict, Any, Optional, Iterable, Tuple
from dataclasses import dataclass, field


DEFAULT_GROUP_TITLE = "Sin título"


def _new_id() -> str:
    return str(uuid.uuid4())[:8]


@dataclass
class WorkflowStep:
    step_id: str
    action_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    label_override: str = ""

    def to_dict(self) -> Dict:
        return {
            "step_id": self.step_id,
            "action_type": self.action_type,
            "params": self.params,
            "enabled": self.enabled,
            "label_override": self.label_override,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "WorkflowStep":
        return cls(
            step_id=data.get("step_id", _new_id()),
            action_type=data["action_type"],
            params=data.get("params", {}),
            enabled=data.get("enabled", True),
            label_override=data.get("label_override", ""),
        )

    def clone(self) -> "WorkflowStep":
        return WorkflowStep(
            step_id=_new_id(),
            action_type=self.action_type,
            params=copy.deepcopy(self.params),
            enabled=self.enabled,
            label_override=self.label_override,
        )


@dataclass
class StepGroup:
    group_id: str
    title: str = DEFAULT_GROUP_TITLE
    steps: List[WorkflowStep] = field(default_factory=list)
    enabled: bool = True
    collapsed: bool = False

    def to_dict(self) -> Dict:
        return {
            "group_id": self.group_id,
            "title": self.title,
            "enabled": self.enabled,
            "collapsed": self.collapsed,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "StepGroup":
        return cls(
            group_id=data.get("group_id", _new_id()),
            title=data.get("title", DEFAULT_GROUP_TITLE),
            steps=[WorkflowStep.from_dict(s) for s in data.get("steps", [])],
            enabled=data.get("enabled", True),
            collapsed=data.get("collapsed", False),
        )

    def clone(self) -> "StepGroup":
        return StepGroup(
            group_id=_new_id(),
            title=f"{self.title} (copia)",
            steps=[s.clone() for s in self.steps],
            enabled=self.enabled,
            collapsed=self.collapsed,
        )


class Workflow:
    def __init__(self, name: str = "Nuevo Workflow", description: str = ""):
        self.workflow_id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.groups: List[StepGroup] = [StepGroup(group_id=_new_id())]
        self.variables: Dict[str, str] = {}

    # ------------------------------------------------------------- queries

    @property
    def steps(self) -> List[WorkflowStep]:
        """Flat, execution-ordered list of every step across all groups."""
        return [s for g in self.groups for s in g.steps]

    def get_group(self, group_id: str) -> Optional[StepGroup]:
        return next((g for g in self.groups if g.group_id == group_id), None)

    def group_of(self, step_id: str) -> Optional[StepGroup]:
        return next((g for g in self.groups if any(s.step_id == step_id for s in g.steps)), None)

    def is_step_active(self, step: WorkflowStep) -> bool:
        group = self.group_of(step.step_id)
        return step.enabled and (group is None or group.enabled)

    def _locate(self, step_id: str) -> Tuple[Optional[StepGroup], int]:
        for g in self.groups:
            for i, s in enumerate(g.steps):
                if s.step_id == step_id:
                    return g, i
        return None, -1

    def _ensure_group(self) -> StepGroup:
        if not self.groups:
            self.groups.append(StepGroup(group_id=_new_id()))
        return self.groups[-1]

    # --------------------------------------------------------------- steps

    def add_step(self, action_type: str, params: Dict = None, index: int = None,
                 group_id: str = None) -> WorkflowStep:
        step = WorkflowStep(step_id=_new_id(), action_type=action_type, params=params or {})
        group = self.get_group(group_id) if group_id else None
        if group is None:
            group = self._ensure_group()
        if index is None:
            group.steps.append(step)
        else:
            group.steps.insert(index, step)
        return step

    def remove_steps(self, step_ids: Iterable[str]):
        ids = set(step_ids)
        for g in self.groups:
            g.steps = [s for s in g.steps if s.step_id not in ids]

    def remove_step(self, step_id: str):
        self.remove_steps([step_id])

    def duplicate_steps(self, step_ids: Iterable[str]) -> List[WorkflowStep]:
        """Copies of the selected steps are inserted, per group, right after the last selected one."""
        ids = set(step_ids)
        created = []
        for g in self.groups:
            positions = [i for i, s in enumerate(g.steps) if s.step_id in ids]
            if not positions:
                continue
            copies = [g.steps[i].clone() for i in positions]
            insert_at = positions[-1] + 1
            g.steps[insert_at:insert_at] = copies
            created.extend(copies)
        return created

    def duplicate_step(self, step_id: str) -> Optional[WorkflowStep]:
        created = self.duplicate_steps([step_id])
        return created[0] if created else None

    def move_steps(self, step_ids: Iterable[str], direction: int):
        """Move the selected steps one position up (-1) or down (+1), crossing group borders."""
        ids = set(step_ids)
        ordered = [s for s in self.steps if s.step_id in ids]
        if direction > 0:
            ordered.reverse()
        for step in ordered:
            group, i = self._locate(step.step_id)
            new_i = i + direction
            if 0 <= new_i < len(group.steps):
                # a selected neighbour still in place could not move: keep the block together
                if group.steps[new_i].step_id in ids:
                    continue
                group.steps[i], group.steps[new_i] = group.steps[new_i], group.steps[i]
                continue
            gi = self.groups.index(group) + direction
            if not 0 <= gi < len(self.groups):
                continue
            target = self.groups[gi]
            if target.steps:
                edge = target.steps[-1] if direction < 0 else target.steps[0]
                if edge.step_id in ids:
                    continue
            group.steps.pop(i)
            if direction < 0:
                target.steps.append(step)
            else:
                target.steps.insert(0, step)

    def move_step(self, step_id: str, direction: int):
        self.move_steps([step_id], direction)

    def move_steps_to_group(self, step_ids: Iterable[str], group_id: str, index: int = None):
        """Move the selected steps (kept in workflow order) into a group at the given index."""
        target = self.get_group(group_id)
        if target is None:
            return
        ids = set(step_ids)
        if index is None:
            index = len(target.steps)
        moving = []
        for g in self.groups:
            kept = []
            for i, s in enumerate(g.steps):
                if s.step_id in ids:
                    moving.append(s)
                    if g is target and i < index:
                        index -= 1
                else:
                    kept.append(s)
            g.steps = kept
        index = max(0, min(index, len(target.steps)))
        target.steps[index:index] = moving

    def set_steps_enabled(self, step_ids: Iterable[str], enabled: bool):
        ids = set(step_ids)
        for s in self.steps:
            if s.step_id in ids:
                s.enabled = enabled

    # -------------------------------------------------------------- groups

    def add_group(self, title: str = DEFAULT_GROUP_TITLE, index: int = None) -> StepGroup:
        group = StepGroup(group_id=_new_id(), title=title or DEFAULT_GROUP_TITLE)
        if index is None:
            self.groups.append(group)
        else:
            self.groups.insert(index, group)
        return group

    def rename_group(self, group_id: str, title: str):
        group = self.get_group(group_id)
        if group:
            group.title = title or DEFAULT_GROUP_TITLE

    def remove_groups(self, group_ids: Iterable[str]):
        ids = set(group_ids)
        self.groups = [g for g in self.groups if g.group_id not in ids]

    def duplicate_groups(self, group_ids: Iterable[str]) -> List[StepGroup]:
        """Copies of the selected groups are inserted right after the last selected one."""
        ids = set(group_ids)
        positions = [i for i, g in enumerate(self.groups) if g.group_id in ids]
        if not positions:
            return []
        copies = [self.groups[i].clone() for i in positions]
        insert_at = positions[-1] + 1
        self.groups[insert_at:insert_at] = copies
        return copies

    def move_groups(self, group_ids: Iterable[str], direction: int):
        ids = set(group_ids)
        indices = [i for i, g in enumerate(self.groups) if g.group_id in ids]
        if direction > 0:
            indices.reverse()
        for i in indices:
            new_i = i + direction
            if not 0 <= new_i < len(self.groups) or self.groups[new_i].group_id in ids:
                continue
            self.groups[i], self.groups[new_i] = self.groups[new_i], self.groups[i]

    def move_groups_to(self, group_ids: Iterable[str], index: int):
        ids = set(group_ids)
        moving = []
        kept = []
        for i, g in enumerate(self.groups):
            if g.group_id in ids:
                moving.append(g)
                if i < index:
                    index -= 1
            else:
                kept.append(g)
        index = max(0, min(index, len(kept)))
        kept[index:index] = moving
        self.groups = kept

    def set_groups_enabled(self, group_ids: Iterable[str], enabled: bool):
        ids = set(group_ids)
        for g in self.groups:
            if g.group_id in ids:
                g.enabled = enabled

    def group_steps(self, step_ids: Iterable[str], title: str = DEFAULT_GROUP_TITLE) -> Optional[StepGroup]:
        """Create a new group holding the selected steps, placed next to the first of them."""
        ids = set(step_ids)
        selected = [s for s in self.steps if s.step_id in ids]
        if not selected:
            return None
        first_group, first_i = self._locate(selected[0].step_id)
        gi = self.groups.index(first_group)
        # Split the first group so the unselected steps after the selection keep running after it
        tail = [s for s in first_group.steps[first_i:] if s.step_id not in ids]
        if first_i > 0 and tail:
            tail_ids = {s.step_id for s in tail}
            first_group.steps = [s for s in first_group.steps if s.step_id not in tail_ids]
            self.groups.insert(gi + 1, StepGroup(
                group_id=_new_id(), title=first_group.title, steps=tail, enabled=first_group.enabled,
            ))
        new_group = self.add_group(title, index=gi if first_i == 0 else gi + 1)
        self.move_steps_to_group(ids, new_group.group_id, 0)
        return new_group

    # --------------------------------------------------------- persistence

    def to_dict(self) -> Dict:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "variables": self.variables,
            "groups": [g.to_dict() for g in self.groups],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Workflow":
        wf = cls(name=data.get("name", "Workflow"), description=data.get("description", ""))
        wf.workflow_id = data.get("workflow_id", str(uuid.uuid4()))
        wf.variables = data.get("variables", {})
        if "groups" in data:
            wf.groups = [StepGroup.from_dict(g) for g in data["groups"]]
        else:
            # legacy workflows (flat step list): wrap everything in a default group
            steps = [WorkflowStep.from_dict(s) for s in data.get("steps", [])]
            wf.groups = [StepGroup(group_id=_new_id(), steps=steps)]
        return wf

    def save(self, filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "Workflow":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
