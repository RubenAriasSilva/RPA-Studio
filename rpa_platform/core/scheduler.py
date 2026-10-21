"""Windows Task Scheduler wrapper: runs workflows at a fixed time even when
neither RPA Studio nor the Orchestrator is open (see run_scheduled.py)."""

import csv
import ctypes
import io
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from xml.sax.saxutils import escape

TASK_FOLDER = "RPA Studio"
RUNNER_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "run_scheduled.py")

MODES = {
    "once": "Solo una vez",
    "daily": "Todos los días",
    "weekdays": "Lunes a viernes",
}

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _python_exe() -> str:
    """pythonw.exe next to the current interpreter (no console window), else python."""
    candidate = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return candidate if os.path.exists(candidate) else sys.executable


def _schtasks(*args) -> Tuple[int, str]:
    try:
        oem = f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    except Exception:
        oem = "utf-8"
    proc = subprocess.run(
        ["schtasks", *args], capture_output=True, creationflags=_NO_WINDOW,
    )
    out = (proc.stdout or b"") + (proc.stderr or b"")
    return proc.returncode, out.decode(oem, errors="replace").strip()


def _safe_task_name(text: str) -> str:
    bad = '\\/:*?"<>|'
    return "".join("_" if c in bad else c for c in text).strip() or "workflow"


def next_run(hh: int, mm: int, mode: str, now: datetime = None) -> datetime:
    now = now or datetime.now()
    run = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if run <= now:
        run += timedelta(days=1)
    if mode == "weekdays":
        while run.weekday() >= 5:
            run += timedelta(days=1)
    return run


def _task_xml(workflow_path: str, workflow_name: str, start: datetime, mode: str) -> str:
    start_iso = start.strftime("%Y-%m-%dT%H:%M:%S")
    if mode == "once":
        end_iso = (start + timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%S")
        trigger = (
            f"<TimeTrigger><StartBoundary>{start_iso}</StartBoundary>"
            f"<EndBoundary>{end_iso}</EndBoundary><Enabled>true</Enabled></TimeTrigger>"
        )
        cleanup = "<DeleteExpiredTaskAfter>P1D</DeleteExpiredTaskAfter>"
    elif mode == "weekdays":
        days = "".join(f"<{d}/>" for d in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"))
        trigger = (
            f"<CalendarTrigger><StartBoundary>{start_iso}</StartBoundary><Enabled>true</Enabled>"
            f"<ScheduleByWeek><DaysOfWeek>{days}</DaysOfWeek><WeeksInterval>1</WeeksInterval>"
            f"</ScheduleByWeek></CalendarTrigger>"
        )
        cleanup = ""
    else:
        trigger = (
            f"<CalendarTrigger><StartBoundary>{start_iso}</StartBoundary><Enabled>true</Enabled>"
            f"<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay></CalendarTrigger>"
        )
        cleanup = ""

    args = f'"{RUNNER_SCRIPT}" "{os.path.abspath(workflow_path)}"'
    desc = f"RPA Studio · {workflow_name} · {MODES.get(mode, mode)} · {os.path.abspath(workflow_path)}"
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>RPA Studio</Author>
    <Description>{escape(desc)}</Description>
  </RegistrationInfo>
  <Triggers>{trigger}</Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <WakeToRun>true</WakeToRun>
    <ExecutionTimeLimit>PT12H</ExecutionTimeLimit>
    {cleanup}
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(_python_exe())}</Command>
      <Arguments>{escape(args)}</Arguments>
      <WorkingDirectory>{escape(os.path.dirname(RUNNER_SCRIPT))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def create_task(workflow_path: str, workflow_name: str, hh: int, mm: int, mode: str) -> Tuple[str, datetime]:
    """Register (or replace) a scheduled task. Returns (task name, first run). Raises RuntimeError."""
    if mode not in MODES:
        raise ValueError(f"Modo desconocido: {mode}")
    start = next_run(hh, mm, mode)
    task_name = _safe_task_name(f"{workflow_name} {hh:02d}{mm:02d} {mode}")
    xml = _task_xml(workflow_path, workflow_name, start, mode)

    fd, xml_path = tempfile.mkstemp(suffix=".xml", prefix="rpa_task_")
    os.close(fd)
    try:
        with open(xml_path, "w", encoding="utf-16") as f:
            f.write(xml)
        code, out = _schtasks("/Create", "/TN", f"{TASK_FOLDER}\\{task_name}", "/XML", xml_path, "/F")
    finally:
        try:
            os.remove(xml_path)
        except OSError:
            pass
    if code != 0:
        raise RuntimeError(out or f"schtasks devolvió {code}")
    return task_name, start


def list_tasks() -> List[Dict[str, str]]:
    """Tasks inside the RPA Studio folder: [{name, next_run, status}]."""
    code, out = _schtasks("/Query", "/FO", "CSV", "/NH")
    if code != 0:
        return []
    prefix = f"\\{TASK_FOLDER}\\"
    tasks = []
    # Columns (language independent by position): TaskName, Next Run Time, Status
    for row in csv.reader(io.StringIO(out)):
        if len(row) >= 3 and row[0].startswith(prefix):
            tasks.append({"name": row[0][len(prefix):], "next_run": row[1], "status": row[2]})
    return tasks


def delete_task(task_name: str):
    code, out = _schtasks("/Delete", "/TN", f"{TASK_FOLDER}\\{task_name}", "/F")
    if code != 0:
        raise RuntimeError(out or f"schtasks devolvió {code}")
