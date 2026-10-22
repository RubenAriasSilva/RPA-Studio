"""Headless workflow runner launched by the Windows Task Scheduler.

Usage: pythonw run_scheduled.py "<path to .rpa.json>"
Runs without RPA Studio or the Orchestrator being open. Output goes to logs/.
"""

import os
import sys
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
os.chdir(_HERE)  # actions resolve relative paths (assets/, workflows/) from here

from core.workflow import Workflow
from core.runner import WorkflowRunner, RunnerState
from core.history import LOGS_DIR, append_history


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in " -_." else "_" for c in name).strip() or "workflow"


def main() -> int:
    if len(sys.argv) < 2:
        return 2
    path = sys.argv[1]
    os.makedirs(LOGS_DIR, exist_ok=True)
    started = datetime.now()

    try:
        wf = Workflow.load(path)
        name = wf.name
    except Exception as e:
        wf, name = None, os.path.basename(path)
        load_error = str(e)

    log_path = os.path.join(LOGS_DIR, f"{_safe(name)}_{started.strftime('%Y%m%d_%H%M%S')}.log")
    errors = []

    with open(log_path, "w", encoding="utf-8") as log:
        def on_log(msg, level="info"):
            if level == "progress":  # live delay counters only make sense on screen
                return
            log.write(f"[{datetime.now().strftime('%H:%M:%S')}] {level.upper():7} {msg}\n")
            log.flush()

        def on_error(idx, step, error):
            errors.append(error)

        on_log(f"Ejecución programada: {path}")
        if wf is None:
            on_log(f"No se pudo cargar el workflow: {load_error}", "error")
            state = "failed"
        else:
            runner = WorkflowRunner()
            runner.on_log = on_log
            runner.on_error = on_error
            runner.run(wf)
            runner._thread.join()
            if runner.state == RunnerState.STOPPED:
                state = "stopped"
            else:
                state = "failed" if errors else "success"

        sec = int((datetime.now() - started).total_seconds())
        elapsed = f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"
        on_log(f"Resultado: {state} · duración {elapsed}")

    append_history({
        "name": name,
        "state": state,
        "elapsed": elapsed,
        "ts": started.strftime("%Y-%m-%d %H:%M:%S"),
        "origin": "programado",
        "log": log_path,
    })
    return 0 if state == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
