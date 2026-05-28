#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DEFAULT_FOLDER = "cronjobs"
DEFAULT_INTERVAL_SECONDS = 3600
DEFAULT_TIMEOUT_SECONDS = 1800
DEFAULT_AGENT_ARGS = ["exec", "--ask-for-approval", "never"]
JOB_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
STATUS_LABELS = {
    "never": "Never",
    "executed": "Executed",
    "failed": "Failed",
    "delayed": "Delayed",
    "aborted": "Aborted",
    "timeout": "Timeout",
    "needs-input": "Needs Input",
    "skipped": "Skipped",
}
FAILURE_STATUSES = {"failed", "delayed", "aborted", "timeout", "needs-input", "skipped"}
MONTH_NAMES = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}
DOW_NAMES = {
    "SUN": 0,
    "MON": 1,
    "TUE": 2,
    "WED": 3,
    "THU": 4,
    "FRI": 5,
    "SAT": 6,
}


@dataclass
class Installation:
    jobs_json: Path
    cronjobs_dir: Path
    data: dict[str, Any]
    root: Path
    is_root: bool


@dataclass(frozen=True)
class CronSpec:
    minutes: set[int]
    hours: set[int]
    days_of_month: set[int]
    months: set[int]
    days_of_week: set[int]
    day_of_month_any: bool
    day_of_week_any: bool


@dataclass(frozen=True)
class DueInfo:
    due_at: dt.datetime
    action: str
    reason: str
    late_by_seconds: int


def local_tz() -> dt.tzinfo:
    return dt.datetime.now().astimezone().tzinfo or dt.timezone.utc


def now_local() -> dt.datetime:
    return dt.datetime.now().astimezone().replace(microsecond=0)


def parse_datetime(value: Any) -> dt.datetime | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError(f"expected datetime string, got {type(value).__name__}")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_tz())
    return parsed.astimezone(local_tz()).replace(microsecond=0)


def isoformat(value: dt.datetime) -> str:
    return value.astimezone(local_tz()).replace(microsecond=0).isoformat()


def display_stamp(value: dt.datetime) -> str:
    return value.astimezone(local_tz()).strftime("%Y-%m-%d %H:%M:%S %A")


def json_dump(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=False) + "\n"


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_write_text(path, json_dump(data))


def normalize_folder(value: str) -> Path:
    folder = Path(value)
    if folder.is_absolute() or ".." in folder.parts:
        raise ValueError("cronjobs-folder must be a relative path inside the context")
    return folder


def jobs_json_for(context_root: Path, cronjobs_folder: str) -> Path:
    return context_root / normalize_folder(cronjobs_folder) / "jobs.json"


def resolve_child_jobs_json(root: Path, child: str) -> Path:
    child_path = Path(child)
    if not child_path.is_absolute():
        child_path = root / child_path
    if child_path.name != "jobs.json":
        child_path = child_path / "jobs.json"
    return child_path.resolve()


def load_installations(root: Path, cronjobs_folder: str) -> list[Installation]:
    root = root.resolve()
    root_jobs = jobs_json_for(root, cronjobs_folder).resolve()
    seen: set[Path] = set()
    installations: list[Installation] = []

    def visit(path: Path, is_root: bool) -> None:
        resolved = path.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        data = read_json(resolved)
        inst = Installation(
            jobs_json=resolved,
            cronjobs_dir=resolved.parent,
            data=data,
            root=root,
            is_root=is_root,
        )
        installations.append(inst)
        for child in data.get("children", []):
            if not isinstance(child, str):
                continue
            visit(resolve_child_jobs_json(root, child), False)

    visit(root_jobs, True)
    return installations


def validate_job_id(job_id: Any) -> str | None:
    if not isinstance(job_id, str) or not job_id:
        return "job id must be a non-empty string"
    if len(job_id) > 64:
        return "job id must be at most 64 characters"
    if not JOB_ID_RE.match(job_id):
        return "job id must match [a-z0-9]+(-[a-z0-9]+)*"
    if job_id.lower() in WINDOWS_RESERVED:
        return "job id must not be a Windows reserved filename"
    return None


def parse_cron_value(raw: str, minimum: int, maximum: int, names: dict[str, int] | None) -> int:
    token = raw.strip().upper()
    if names and token in names:
        value = names[token]
    else:
        value = int(token)
    if value < minimum or value > maximum:
        raise ValueError(f"value {raw!r} outside {minimum}-{maximum}")
    return value


def normalize_dow(value: int) -> int:
    return 0 if value == 7 else value


def parse_cron_field(
    raw: str,
    minimum: int,
    maximum: int,
    names: dict[str, int] | None = None,
    normalize: Any | None = None,
) -> tuple[set[int], bool]:
    if raw == "":
        raise ValueError("empty cron field")
    values: set[int] = set()
    any_field = raw == "*"
    for part in raw.split(","):
        part = part.strip()
        if not part:
            raise ValueError("empty cron list item")
        if "/" in part:
            base, step_text = part.split("/", 1)
            step = int(step_text)
            if step <= 0:
                raise ValueError("cron step must be greater than zero")
        else:
            base = part
            step = 1
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            start_text, end_text = base.split("-", 1)
            start = parse_cron_value(start_text, minimum, maximum, names)
            end = parse_cron_value(end_text, minimum, maximum, names)
            if start > end:
                raise ValueError(f"cron range {base!r} starts after it ends")
        else:
            if step != 1:
                raise ValueError(f"cron step on single value {part!r} is not supported")
            value = parse_cron_value(base, minimum, maximum, names)
            normalized = normalize(value) if normalize else value
            values.add(normalized)
            continue
        for value in range(start, end + 1, step):
            normalized = normalize(value) if normalize else value
            values.add(normalized)
    return values, any_field


def parse_cron_expression(expression: str) -> CronSpec:
    parts = expression.split()
    if len(parts) != 5:
        raise ValueError("cron expression must have exactly five fields")
    minutes, _ = parse_cron_field(parts[0], 0, 59)
    hours, _ = parse_cron_field(parts[1], 0, 23)
    days_of_month, dom_any = parse_cron_field(parts[2], 1, 31)
    months, _ = parse_cron_field(parts[3], 1, 12, MONTH_NAMES)
    days_of_week, dow_any = parse_cron_field(parts[4], 0, 7, DOW_NAMES, normalize_dow)
    return CronSpec(
        minutes=minutes,
        hours=hours,
        days_of_month=days_of_month,
        months=months,
        days_of_week=days_of_week,
        day_of_month_any=dom_any,
        day_of_week_any=dow_any,
    )


def cron_matches(spec: CronSpec, value: dt.datetime) -> bool:
    cron_dow = (value.weekday() + 1) % 7
    dom_match = value.day in spec.days_of_month
    dow_match = cron_dow in spec.days_of_week
    if not spec.day_of_month_any and not spec.day_of_week_any:
        day_match = dom_match or dow_match
    else:
        day_match = dom_match and dow_match
    return (
        value.minute in spec.minutes
        and value.hour in spec.hours
        and value.month in spec.months
        and day_match
    )


def latest_cron_due(
    expression: str,
    now: dt.datetime,
    since: dt.datetime,
    max_lookback_days: int,
) -> dt.datetime | None:
    spec = parse_cron_expression(expression)
    cursor = now.replace(second=0, microsecond=0)
    lower_bound = max(since, cursor - dt.timedelta(days=max_lookback_days))
    while cursor > lower_bound:
        if cron_matches(spec, cursor):
            return cursor
        cursor -= dt.timedelta(minutes=1)
    return None


def installation_config(inst: Installation) -> dict[str, Any]:
    config = inst.data.get("installation", {})
    return config if isinstance(config, dict) else {}


def agent_config(inst: Installation) -> dict[str, Any]:
    config = installation_config(inst).get("agent", {})
    return config if isinstance(config, dict) else {}


def root_runtime_config(root_inst: Installation) -> dict[str, Any]:
    config = installation_config(root_inst)
    return {
        "check_interval_seconds": int(config.get("check_interval_seconds", DEFAULT_INTERVAL_SECONDS)),
        "misfire_grace_seconds": int(
            config.get("misfire_grace_seconds", config.get("check_interval_seconds", DEFAULT_INTERVAL_SECONDS))
        ),
        "max_lookback_days": int(config.get("max_lookback_days", 366)),
    }


def latest_marker(job: dict[str, Any]) -> dt.datetime | None:
    markers = []
    for key in ("last_due_at", "last_run_at"):
        parsed = parse_datetime(job.get(key))
        if parsed is not None:
            markers.append(parsed)
    return max(markers) if markers else None


def initial_marker(job: dict[str, Any], now: dt.datetime, interval_seconds: int) -> dt.datetime:
    for key in ("not_before", "created_at"):
        parsed = parse_datetime(job.get(key))
        if parsed is not None:
            return parsed
    return now - dt.timedelta(seconds=max(interval_seconds, 60))


def compute_due(job: dict[str, Any], runtime: dict[str, Any], now: dt.datetime) -> DueInfo | None:
    if job.get("enabled", True) is False:
        return None
    schedule = job.get("schedule")
    if not isinstance(schedule, dict):
        return None
    schedule_type = schedule.get("type")
    marker = latest_marker(job)
    interval_seconds = int(runtime["check_interval_seconds"])
    grace_seconds = int(job.get("misfire_grace_seconds", runtime["misfire_grace_seconds"]))
    catch_up = bool(job.get("catch_up", False))

    if schedule_type == "once":
        due_at = parse_datetime(schedule.get("at"))
        if due_at is None or due_at > now:
            return None
        if marker is not None and marker >= due_at:
            return None
    elif schedule_type == "cron":
        expression = schedule.get("expression")
        if not isinstance(expression, str):
            return None
        since = marker or initial_marker(job, now, interval_seconds)
        due_at = latest_cron_due(expression, now, since, int(runtime["max_lookback_days"]))
        if due_at is None:
            return None
    else:
        return None

    late_by = max(0, int((now - due_at).total_seconds()))
    if late_by > grace_seconds and not catch_up:
        return DueInfo(due_at=due_at, action="delay", reason="missed", late_by_seconds=late_by)
    reason = "catch-up" if late_by > interval_seconds else "due"
    return DueInfo(due_at=due_at, action="execute", reason=reason, late_by_seconds=late_by)


def lock_path(cronjobs_dir: Path, job_id: str) -> Path:
    return cronjobs_dir / ".locks" / f"{job_id}.lock"


def read_lock(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return read_json(path)
    except Exception:
        return {"unreadable": True}


def active_lock_info(cronjobs_dir: Path, job_id: str, now: dt.datetime) -> tuple[bool, dict[str, Any] | None]:
    path = lock_path(cronjobs_dir, job_id)
    info = read_lock(path)
    if info is None:
        return False, None
    expires_at = None
    try:
        expires_at = parse_datetime(info.get("expires_at"))
    except Exception:
        pass
    if expires_at is not None and expires_at <= now:
        return False, info
    return True, info


class JobLock:
    def __init__(self, cronjobs_dir: Path, job_id: str, timeout_seconds: int, now: dt.datetime):
        self.path = lock_path(cronjobs_dir, job_id)
        self.job_id = job_id
        self.timeout_seconds = timeout_seconds
        self.now = now
        self.acquired = False
        self.stale_info: dict[str, Any] | None = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "job_id": self.job_id,
            "pid": os.getpid(),
            "started_at": isoformat(self.now),
            "expires_at": isoformat(self.now + dt.timedelta(seconds=max(self.timeout_seconds, 60))),
        }
        while True:
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                info = read_lock(self.path)
                expires_at = None
                try:
                    expires_at = parse_datetime((info or {}).get("expires_at"))
                except Exception:
                    pass
                if expires_at is not None and expires_at <= self.now:
                    self.stale_info = info
                    self.path.unlink(missing_ok=True)
                    continue
                return False
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
            self.acquired = True
            return True

    def release(self) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False


def concise_result(text: str, limit: int = 4000) -> str:
    cleaned = text.strip()
    if not cleaned:
        return "(no output)"
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "\n\n[truncated]"


def append_job_log(
    cronjobs_dir: Path,
    job_id: str,
    status: str,
    checked: bool,
    result: str,
    when: dt.datetime,
) -> None:
    label = STATUS_LABELS.get(status, status.replace("-", " ").title())
    entry = (
        f"# {display_stamp(when)}\n"
        f"**Status**: {label}\n"
        f"**Checked**: {'true' if checked else 'false'}\n"
        f"**Results**:\n"
        f"{concise_result(result)}\n"
    )
    log_file = cronjobs_dir / f"{job_id}.md"
    if log_file.exists():
        existing = log_file.read_text(encoding="utf-8").lstrip("\n")
        text = entry + ("\n" + existing if existing else "")
    else:
        text = entry
    atomic_write_text(log_file, text)


def update_job_after_result(
    job: dict[str, Any],
    due_at: dt.datetime,
    finished_at: dt.datetime,
    status: str,
    result: str,
) -> None:
    job["last_due_at"] = isoformat(due_at)
    if status != "delayed":
        job["last_run_at"] = isoformat(finished_at)
    job["last_status"] = status
    job["last_result"] = concise_result(result, 1000)
    schedule = job.get("schedule")
    if isinstance(schedule, dict) and schedule.get("type") == "once" and status != "needs-input":
        job["enabled"] = False


def pending_records(root: Path, cronjobs_folder: str, scope: str, now: dt.datetime) -> list[dict[str, Any]]:
    installations = load_installations(root, cronjobs_folder)
    runtime = root_runtime_config(installations[0])
    records: list[dict[str, Any]] = []
    for inst in installations:
        jobs = inst.data.get("jobs", [])
        if not isinstance(jobs, list):
            continue
        for job in jobs:
            if not isinstance(job, dict):
                continue
            background = bool(job.get("background", False))
            if scope == "background" and not background:
                continue
            if scope == "interactive" and background:
                continue
            job_id = job.get("id")
            if validate_job_id(job_id) is not None:
                continue
            due = compute_due(job, runtime, now)
            if due is None:
                continue
            active, lock_info = active_lock_info(inst.cronjobs_dir, job_id, now)
            if active:
                continue
            records.append(
                {
                    "id": job_id,
                    "jobs_json": str(inst.jobs_json.relative_to(root) if inst.jobs_json.is_relative_to(root) else inst.jobs_json),
                    "cronjobs_dir": str(
                        inst.cronjobs_dir.relative_to(root) if inst.cronjobs_dir.is_relative_to(root) else inst.cronjobs_dir
                    ),
                    "installation_id": installation_config(inst).get("id"),
                    "background": background,
                    "prompt": job.get("prompt", ""),
                    "due_at": isoformat(due.due_at),
                    "action": due.action,
                    "reason": due.reason,
                    "late_by_seconds": due.late_by_seconds,
                    "stale_lock": lock_info if lock_info else None,
                }
            )
    return records


def run_agent(inst: Installation, job: dict[str, Any], due: DueInfo, started_at: dt.datetime) -> tuple[str, str]:
    config = agent_config(inst)
    command = str(config.get("command") or "codex")
    args = config.get("args", DEFAULT_AGENT_ARGS)
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        args = DEFAULT_AGENT_ARGS
    prompt_mode = str(config.get("prompt_mode") or "argument")
    timeout = int(config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
    prompt = (
        "You are executing a SkillBag cronjob.\n\n"
        f"Jobs file: {inst.jobs_json}\n"
        f"Job id: {job.get('id')}\n"
        f"Due at: {isoformat(due.due_at)}\n"
        f"Started at: {isoformat(started_at)}\n\n"
        "Run this job and return a concise result summary. If the job needs "
        "human input, permissions, or feedback, stop and say exactly what is needed.\n\n"
        f"Job prompt:\n{job.get('prompt', '')}\n"
    )
    command_line = [command, *args]
    stdin_text = None
    if prompt_mode == "stdin":
        stdin_text = prompt
    else:
        command_line.append(prompt)
    try:
        completed = subprocess.run(
            command_line,
            input=stdin_text,
            text=True,
            capture_output=True,
            cwd=str(inst.root),
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return "failed", f"Agent command not found: {command}"
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + ("\n" + exc.stderr if exc.stderr else "")
        return "timeout", concise_result(output or f"Timed out after {timeout} seconds")
    output = completed.stdout.strip()
    if completed.stderr.strip():
        output = (output + "\n\n" if output else "") + completed.stderr.strip()
    if completed.returncode == 0:
        return "executed", output or "(agent completed without output)"
    return "failed", output or f"Agent exited with status {completed.returncode}"


def find_jobs(
    root: Path,
    cronjobs_folder: str,
    job_id: str,
    jobs_json: str | None = None,
) -> list[tuple[Installation, dict[str, Any]]]:
    matches: list[tuple[Installation, dict[str, Any]]] = []
    installations = load_installations(root, cronjobs_folder)
    wanted_path = (root / jobs_json).resolve() if jobs_json else None
    for inst in installations:
        if wanted_path is not None and inst.jobs_json != wanted_path:
            continue
        for job in inst.data.get("jobs", []):
            if isinstance(job, dict) and job.get("id") == job_id:
                matches.append((inst, job))
    return matches


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.context_root).resolve()
    folder = normalize_folder(args.cronjobs_folder)
    cronjobs_dir = root / folder
    jobs_json = cronjobs_dir / "jobs.json"
    created = not jobs_json.exists()
    cronjobs_dir.mkdir(parents=True, exist_ok=True)
    (cronjobs_dir / ".locks").mkdir(exist_ok=True)
    detected_path = shutil.which(args.agent_command)
    agent_args = args.agent_arg if args.agent_arg is not None else list(DEFAULT_AGENT_ARGS)
    if jobs_json.exists():
        data = read_json(jobs_json)
    else:
        installation: dict[str, Any] = {
            "id": args.installation_id,
            "type": "child" if args.child else "root",
            "cronjobs_folder": str(folder),
            "timezone": "local",
            "versioned": not args.not_versioned,
            "agent": {
                "command": args.agent_command,
                "args": agent_args,
                "prompt_mode": args.prompt_mode,
                "timeout_seconds": args.timeout_seconds,
                "detected_path": detected_path,
            },
            "scheduler": {
                "type": "none",
                "installed": False,
            },
        }
        if not args.child:
            installation["check_interval_seconds"] = args.check_interval_seconds
        data = {
            "schema_version": SCHEMA_VERSION,
            "installation": installation,
            "children": [],
            "runtime": {"last_checked_at": None},
            "jobs": [],
        }
        write_json(jobs_json, data)
    parent_updated = False
    if args.parent_jobs_json:
        parent_root = Path(args.parent_context_root).resolve() if args.parent_context_root else root
        parent_path = (parent_root / args.parent_jobs_json).resolve()
        parent = read_json(parent_path)
        children = parent.setdefault("children", [])
        if not isinstance(children, list):
            raise ValueError(f"{parent_path} children must be an array")
        rel = os.path.relpath(jobs_json, parent_root)
        if rel not in children:
            children.append(rel)
            children.sort()
            write_json(parent_path, parent)
            parent_updated = True
    result = {
        "jobs_json": str(jobs_json),
        "created": created,
        "agent_command": args.agent_command,
        "agent_detected_path": detected_path,
        "agent_found": detected_path is not None,
        "parent_updated": parent_updated,
        "scheduler_installed": False,
    }
    if args.install_scheduler:
        if args.child:
            raise ValueError("child installations cannot install the root scheduler")
        install_result = install_scheduler(root, args.cronjobs_folder, args.scheduler_platform, args.scheduler_name)
        update_scheduler_state(root, args.cronjobs_folder, install_result)
        result["scheduler_installed"] = True
        result["scheduler"] = install_result
    print(json_dump(result), end="")
    return 0


def validate_schedule(job: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schedule = job.get("schedule")
    if not isinstance(schedule, dict):
        return ["schedule must be an object"]
    schedule_type = schedule.get("type")
    if schedule_type == "cron":
        expression = schedule.get("expression")
        if not isinstance(expression, str):
            errors.append("cron schedule requires expression")
        else:
            try:
                parse_cron_expression(expression)
            except Exception as exc:
                errors.append(f"invalid cron expression: {exc}")
    elif schedule_type == "once":
        try:
            if parse_datetime(schedule.get("at")) is None:
                errors.append("once schedule requires at")
        except Exception as exc:
            errors.append(f"invalid once at datetime: {exc}")
    else:
        errors.append("schedule.type must be cron or once")
    return errors


def cmd_validate(args: argparse.Namespace) -> int:
    root = Path(args.context_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        installations = load_installations(root, args.cronjobs_folder)
    except Exception as exc:
        print(json_dump({"ok": False, "errors": [str(exc)], "warnings": []}), end="")
        return 1
    for inst in installations:
        prefix = str(inst.jobs_json)
        if inst.data.get("schema_version") != SCHEMA_VERSION:
            warnings.append(f"{prefix}: schema_version should be {SCHEMA_VERSION}")
        jobs = inst.data.get("jobs")
        if not isinstance(jobs, list):
            errors.append(f"{prefix}: jobs must be an array")
            continue
        seen_ids: set[str] = set()
        config = installation_config(inst)
        if not inst.is_root and "check_interval_seconds" in config:
            errors.append(f"{prefix}: child installations must not define check_interval_seconds")
        for index, job in enumerate(jobs):
            if not isinstance(job, dict):
                errors.append(f"{prefix}: jobs[{index}] must be an object")
                continue
            job_id = job.get("id")
            id_error = validate_job_id(job_id)
            if id_error:
                errors.append(f"{prefix}: jobs[{index}] {id_error}")
            elif job_id in seen_ids:
                errors.append(f"{prefix}: duplicate job id {job_id}")
            else:
                seen_ids.add(job_id)
            if not isinstance(job.get("prompt"), str) or not job.get("prompt", "").strip():
                errors.append(f"{prefix}: job {job_id or index} prompt must be a non-empty string")
            if "isBackgroundjob" in job:
                warnings.append(f"{prefix}: job {job_id or index} should use background, not isBackgroundjob")
            errors.extend(f"{prefix}: job {job_id or index} {message}" for message in validate_schedule(job))
    result = {"ok": not errors, "errors": errors, "warnings": warnings}
    print(json_dump(result), end="")
    return 0 if not errors else 1


def cmd_pending(args: argparse.Namespace) -> int:
    now = parse_datetime(args.now) if args.now else now_local()
    assert now is not None
    root = Path(args.context_root).resolve()
    records = pending_records(root, args.cronjobs_folder, args.scope, now)
    print(
        json_dump(
            {
                "checked_at": isoformat(now),
                "scope": args.scope,
                "count": len(records),
                "jobs": records,
            }
        ),
        end="",
    )
    return 0


def cmd_run_due(args: argparse.Namespace) -> int:
    now = parse_datetime(args.now) if args.now else now_local()
    assert now is not None
    root = Path(args.context_root).resolve()
    installations = load_installations(root, args.cronjobs_folder)
    runtime = root_runtime_config(installations[0])
    results: list[dict[str, Any]] = []
    for inst in installations:
        jobs = inst.data.get("jobs", [])
        if not isinstance(jobs, list):
            continue
        changed = False
        for job in jobs:
            if not isinstance(job, dict):
                continue
            job_id = job.get("id")
            if validate_job_id(job_id) is not None:
                continue
            background = bool(job.get("background", False))
            if args.scope == "background" and not background:
                continue
            if args.scope == "interactive" and background:
                continue
            due = compute_due(job, runtime, now)
            if due is None:
                continue
            timeout = int(agent_config(inst).get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
            lock = JobLock(inst.cronjobs_dir, job_id, timeout, now)
            if not lock.acquire():
                results.append({"id": job_id, "status": "locked", "jobs_json": str(inst.jobs_json)})
                continue
            try:
                if lock.stale_info:
                    append_job_log(
                        inst.cronjobs_dir,
                        job_id,
                        "aborted",
                        False,
                        f"Removed stale lock before this run: {json.dumps(lock.stale_info, sort_keys=True)}",
                        now,
                    )
                if due.action == "delay":
                    status = "delayed"
                    output = (
                        f"Scheduled run at {isoformat(due.due_at)} was missed by "
                        f"{due.late_by_seconds} seconds and catch_up is false."
                    )
                    checked = False
                else:
                    status, output = run_agent(inst, job, due, now)
                    checked = status == "executed"
                finished_at = now_local()
                append_job_log(inst.cronjobs_dir, job_id, status, checked, output, finished_at)
                update_job_after_result(job, due.due_at, finished_at, status, output)
                changed = True
                results.append(
                    {
                        "id": job_id,
                        "jobs_json": str(inst.jobs_json),
                        "status": status,
                        "due_at": isoformat(due.due_at),
                        "checked": checked,
                    }
                )
            finally:
                lock.release()
        if changed:
            inst.data.setdefault("runtime", {})["last_checked_at"] = isoformat(now_local())
            write_json(inst.jobs_json, inst.data)
    print(json_dump({"ran_at": isoformat(now), "scope": args.scope, "results": results}), end="")
    return 0


def cmd_record_result(args: argparse.Namespace) -> int:
    root = Path(args.context_root).resolve()
    matches = find_jobs(root, args.cronjobs_folder, args.job_id, args.jobs_json)
    if not matches:
        raise ValueError(f"job not found: {args.job_id}")
    if len(matches) > 1:
        raise ValueError("multiple matching jobs found; pass --jobs-json to disambiguate")
    inst, job = matches[0]
    when = parse_datetime(args.when) if args.when else now_local()
    due_at = parse_datetime(args.due_at) if args.due_at else when
    assert when is not None and due_at is not None
    checked = str(args.checked).lower() == "true"
    status = args.status
    append_job_log(inst.cronjobs_dir, args.job_id, status, checked, args.result, when)
    update_job_after_result(job, due_at, when, status, args.result)
    write_json(inst.jobs_json, inst.data)
    print(json_dump({"job_id": args.job_id, "jobs_json": str(inst.jobs_json), "status": status}), end="")
    return 0


def cmd_ack(args: argparse.Namespace) -> int:
    root = Path(args.context_root).resolve()
    matches = find_jobs(root, args.cronjobs_folder, args.job_id, args.jobs_json)
    if not matches:
        raise ValueError(f"job not found: {args.job_id}")
    if len(matches) > 1:
        raise ValueError("multiple matching jobs found; pass --jobs-json to disambiguate")
    inst, job = matches[0]
    log_file = inst.cronjobs_dir / f"{args.job_id}.md"
    if not log_file.exists():
        raise ValueError(f"job log not found: {log_file}")
    text = log_file.read_text(encoding="utf-8")
    updated = text.replace("**Checked**: false", "**Checked**: true", 1)
    if updated == text:
        updated = text.replace("**Checked**: False", "**Checked**: true", 1)
    if updated == text:
        print(json_dump({"job_id": args.job_id, "changed": False, "reason": "no unchecked entry"}), end="")
        return 0
    atomic_write_text(log_file, updated)
    job["last_checked_at"] = isoformat(now_local())
    write_json(inst.jobs_json, inst.data)
    print(json_dump({"job_id": args.job_id, "changed": True}), end="")
    return 0


def latest_log_checked(cronjobs_dir: Path, job_id: str) -> bool | None:
    log_file = cronjobs_dir / f"{job_id}.md"
    if not log_file.exists():
        return None
    text = log_file.read_text(encoding="utf-8")
    match = re.search(r"^\*\*Checked\*\*:\s*(true|false)\s*$", text, flags=re.IGNORECASE | re.MULTILINE)
    if match is None:
        return None
    return match.group(1).lower() == "true"


def cleanup_candidates(root: Path, cronjobs_folder: str, now: dt.datetime) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    installations = load_installations(root, cronjobs_folder)
    for inst in installations:
        jobs = inst.data.get("jobs", [])
        if not isinstance(jobs, list):
            continue
        for job in jobs:
            if not isinstance(job, dict):
                continue
            job_id = job.get("id")
            if validate_job_id(job_id) is not None:
                continue
            schedule = job.get("schedule")
            if not isinstance(schedule, dict) or schedule.get("type") != "once":
                continue
            active, _lock_info = active_lock_info(inst.cronjobs_dir, job_id, now)
            if active:
                continue
            status = str(job.get("last_status") or "never")
            checked = latest_log_checked(inst.cronjobs_dir, job_id)
            remove = status == "executed" or (status in FAILURE_STATUSES and checked is True)
            if not remove:
                continue
            log_file = inst.cronjobs_dir / f"{job_id}.md"
            candidates.append(
                {
                    "id": job_id,
                    "jobs_json": str(inst.jobs_json.relative_to(root) if inst.jobs_json.is_relative_to(root) else inst.jobs_json),
                    "log_file": str(log_file.relative_to(root) if log_file.is_relative_to(root) else log_file),
                    "log_exists": log_file.exists(),
                    "last_status": status,
                    "checked": checked,
                    "last_run_at": job.get("last_run_at"),
                    "last_result": job.get("last_result"),
                }
            )
    return candidates


def apply_cleanup(root: Path, cronjobs_folder: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_jobs_json: dict[Path, set[str]] = {}
    for candidate in candidates:
        jobs_path = resolve_child_jobs_json(root, str(candidate["jobs_json"]))
        by_jobs_json.setdefault(jobs_path, set()).add(str(candidate["id"]))

    removed: list[dict[str, Any]] = []
    for jobs_path, ids in by_jobs_json.items():
        data = read_json(jobs_path)
        jobs = data.get("jobs", [])
        if not isinstance(jobs, list):
            continue
        remaining = []
        cronjobs_dir = jobs_path.parent
        for job in jobs:
            if isinstance(job, dict) and job.get("id") in ids:
                job_id = str(job["id"])
                log_file = cronjobs_dir / f"{job_id}.md"
                checked = latest_log_checked(cronjobs_dir, job_id)
                log_removed = False
                if log_file.exists():
                    log_file.unlink()
                    log_removed = True
                removed.append(
                    {
                        "id": job_id,
                        "jobs_json": str(jobs_path.relative_to(root) if jobs_path.is_relative_to(root) else jobs_path),
                        "log_file": str(log_file.relative_to(root) if log_file.is_relative_to(root) else log_file),
                        "log_removed": log_removed,
                        "last_status": job.get("last_status"),
                        "checked": checked,
                    }
                )
            else:
                remaining.append(job)
        data["jobs"] = remaining
        write_json(jobs_path, data)
    return removed


def cmd_cleanup(args: argparse.Namespace) -> int:
    root = Path(args.context_root).resolve()
    now = parse_datetime(args.now) if args.now else now_local()
    assert now is not None
    candidates = cleanup_candidates(root, args.cronjobs_folder, now)
    result: dict[str, Any] = {
        "checked_at": isoformat(now),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "applied": False,
        "removed": [],
    }
    if args.apply:
        if not args.confirm:
            result["error"] = "cleanup requires --confirm when --apply is used"
            print(json_dump(result), end="")
            return 2
        result["removed"] = apply_cleanup(root, args.cronjobs_folder, candidates)
        result["applied"] = True
    print(json_dump(result), end="")
    return 0


def runner_args(context_root: Path, cronjobs_folder: str) -> list[str]:
    script = Path(__file__).resolve()
    python = sys.executable or "python3"
    return [
        python,
        str(script),
        "run-due",
        str(context_root.resolve()),
        "--cronjobs-folder",
        cronjobs_folder,
        "--scope",
        "background",
    ]


def scheduler_interval(root: Path, cronjobs_folder: str) -> int:
    data = read_json(jobs_json_for(root, cronjobs_folder))
    config = data.get("installation", {})
    if not isinstance(config, dict):
        return DEFAULT_INTERVAL_SECONDS
    return int(config.get("check_interval_seconds", DEFAULT_INTERVAL_SECONDS))


def systemd_units(context_root: Path, cronjobs_folder: str, name: str) -> dict[str, str]:
    interval = scheduler_interval(context_root, cronjobs_folder)
    command = shlex.join(runner_args(context_root, cronjobs_folder))
    service = f"""[Unit]
Description=SkillBag cronjobs runner for {context_root}

[Service]
Type=oneshot
WorkingDirectory={context_root}
ExecStart={command}
Restart=on-failure
RestartSec=30s
"""
    timer = f"""[Unit]
Description=Run SkillBag cronjobs for {context_root}

[Timer]
OnBootSec=2min
OnUnitActiveSec={interval}s
Persistent=true
Unit={name}.service

[Install]
WantedBy=timers.target
"""
    return {f"{name}.service": service, f"{name}.timer": timer}


def launchd_plist(context_root: Path, cronjobs_folder: str, label: str) -> bytes:
    interval = scheduler_interval(context_root, cronjobs_folder)
    cronjobs_dir = context_root / normalize_folder(cronjobs_folder)
    payload = {
        "Label": label,
        "ProgramArguments": runner_args(context_root, cronjobs_folder),
        "WorkingDirectory": str(context_root),
        "RunAtLoad": True,
        "StartInterval": interval,
        "StandardOutPath": str(cronjobs_dir / "scheduler.out.log"),
        "StandardErrorPath": str(cronjobs_dir / "scheduler.err.log"),
    }
    return plistlib.dumps(payload, sort_keys=False)


def windows_powershell(context_root: Path, cronjobs_folder: str, name: str) -> str:
    interval = scheduler_interval(context_root, cronjobs_folder)
    args = runner_args(context_root, cronjobs_folder)
    execute = args[0]
    arguments = subprocess.list2cmdline(args[1:])
    return f"""$Action = New-ScheduledTaskAction -Execute {execute!r} -Argument {arguments!r}
$Startup = New-ScheduledTaskTrigger -AtStartup
$Recurring = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Seconds {interval}) -RepetitionDuration ([TimeSpan]::MaxValue)
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName {name!r} -Action $Action -Trigger @($Startup, $Recurring) -Settings $Settings -Description 'SkillBag cronjobs background runner' -Force
"""


def detect_scheduler_platform(raw: str) -> str:
    if raw != "auto":
        return raw
    system = platform.system().lower()
    if system == "linux":
        return "linux"
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    raise ValueError(f"unsupported platform: {platform.system()}")


def cmd_scheduler_print(args: argparse.Namespace) -> int:
    root = Path(args.context_root).resolve()
    scheduler_platform = detect_scheduler_platform(args.platform)
    if scheduler_platform == "linux":
        units = systemd_units(root, args.cronjobs_folder, args.name)
        for filename, text in units.items():
            print(f"### {filename}\n{text}")
    elif scheduler_platform == "macos":
        print(launchd_plist(root, args.cronjobs_folder, args.name).decode("utf-8"))
    elif scheduler_platform == "windows":
        print(windows_powershell(root, args.cronjobs_folder, args.name))
    else:
        raise ValueError(f"unsupported scheduler platform: {scheduler_platform}")
    return 0


def cmd_scheduler_install(args: argparse.Namespace) -> int:
    root = Path(args.context_root).resolve()
    result = install_scheduler(root, args.cronjobs_folder, args.platform, args.name)
    update_scheduler_state(root, args.cronjobs_folder, result)
    print(json_dump(result), end="")
    return 0


def install_scheduler(context_root: Path, cronjobs_folder: str, raw_platform: str, name: str) -> dict[str, Any]:
    root = context_root.resolve()
    scheduler_platform = detect_scheduler_platform(raw_platform)
    if scheduler_platform == "linux":
        unit_dir = Path.home() / ".config/systemd/user"
        unit_dir.mkdir(parents=True, exist_ok=True)
        for filename, text in systemd_units(root, cronjobs_folder, name).items():
            atomic_write_text(unit_dir / filename, text)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", f"{name}.timer"], check=True)
        result = {"installed": True, "platform": "linux", "unit_dir": str(unit_dir), "timer": f"{name}.timer"}
    elif scheduler_platform == "macos":
        label = name if "." in name else f"ai.skillbag.{name}"
        plist_path = Path.home() / "Library/LaunchAgents" / f"{label}.plist"
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_path.write_bytes(launchd_plist(root, cronjobs_folder, label))
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist_path)], check=False)
        subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist_path)], check=True)
        result = {"installed": True, "platform": "macos", "plist": str(plist_path), "label": label}
    elif scheduler_platform == "windows":
        command = windows_powershell(root, cronjobs_folder, name)
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            check=True,
        )
        result = {"installed": True, "platform": "windows", "task": name}
    else:
        raise ValueError(f"unsupported scheduler platform: {scheduler_platform}")
    result["installed_at"] = isoformat(now_local())
    return result


def update_scheduler_state(root: Path, cronjobs_folder: str, result: dict[str, Any]) -> None:
    jobs_json = jobs_json_for(root, cronjobs_folder)
    data = read_json(jobs_json)
    installation = data.setdefault("installation", {})
    if not isinstance(installation, dict):
        raise ValueError(f"{jobs_json} installation must be an object")
    installation["scheduler"] = result
    write_json(jobs_json, data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage SkillBag cronjobs jobs.json files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="create a cronjobs/jobs.json installation")
    init.add_argument("context_root")
    init.add_argument("--cronjobs-folder", default=DEFAULT_FOLDER)
    init.add_argument("--installation-id", default="root")
    init.add_argument("--child", action="store_true")
    init.add_argument("--parent-context-root")
    init.add_argument("--parent-jobs-json")
    init.add_argument("--check-interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    init.add_argument("--agent-command", default="codex")
    init.add_argument("--agent-arg", action="append")
    init.add_argument("--prompt-mode", choices=["argument", "stdin"], default="argument")
    init.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    init.add_argument("--not-versioned", action="store_true")
    init.add_argument("--install-scheduler", action="store_true")
    init.add_argument("--scheduler-platform", choices=["auto", "linux", "macos", "windows"], default="auto")
    init.add_argument("--scheduler-name", default="skillbag-cronjobs")
    init.set_defaults(func=cmd_init)

    validate = subparsers.add_parser("validate", help="validate root and child jobs.json files")
    validate.add_argument("context_root")
    validate.add_argument("--cronjobs-folder", default=DEFAULT_FOLDER)
    validate.set_defaults(func=cmd_validate)

    pending = subparsers.add_parser("pending", help="print pending jobs as JSON")
    pending.add_argument("context_root")
    pending.add_argument("--cronjobs-folder", default=DEFAULT_FOLDER)
    pending.add_argument("--scope", choices=["all", "background", "interactive"], default="all")
    pending.add_argument("--now")
    pending.set_defaults(func=cmd_pending)

    run_due = subparsers.add_parser("run-due", help="run or mark due jobs")
    run_due.add_argument("context_root")
    run_due.add_argument("--cronjobs-folder", default=DEFAULT_FOLDER)
    run_due.add_argument("--scope", choices=["all", "background", "interactive"], default="background")
    run_due.add_argument("--now")
    run_due.set_defaults(func=cmd_run_due)

    record = subparsers.add_parser("record-result", help="record a result for a manually run job")
    record.add_argument("context_root")
    record.add_argument("--cronjobs-folder", default=DEFAULT_FOLDER)
    record.add_argument("--jobs-json")
    record.add_argument("--job-id", required=True)
    record.add_argument("--status", choices=sorted(STATUS_LABELS), required=True)
    record.add_argument("--checked", choices=["true", "false"], default="true")
    record.add_argument("--result", required=True)
    record.add_argument("--due-at")
    record.add_argument("--when")
    record.set_defaults(func=cmd_record_result)

    ack = subparsers.add_parser("ack", help="mark the latest unchecked job log entry as checked")
    ack.add_argument("context_root")
    ack.add_argument("--cronjobs-folder", default=DEFAULT_FOLDER)
    ack.add_argument("--jobs-json")
    ack.add_argument("--job-id", required=True)
    ack.set_defaults(func=cmd_ack)

    cleanup = subparsers.add_parser("cleanup", help="list or remove completed one-time jobs")
    cleanup.add_argument("context_root")
    cleanup.add_argument("--cronjobs-folder", default=DEFAULT_FOLDER)
    cleanup.add_argument("--apply", action="store_true")
    cleanup.add_argument("--confirm", action="store_true")
    cleanup.add_argument("--now")
    cleanup.set_defaults(func=cmd_cleanup)

    scheduler = subparsers.add_parser("scheduler", help="print or install OS scheduler setup")
    scheduler_sub = scheduler.add_subparsers(dest="scheduler_command", required=True)
    sched_print = scheduler_sub.add_parser("print", help="print scheduler setup")
    sched_print.add_argument("context_root")
    sched_print.add_argument("--cronjobs-folder", default=DEFAULT_FOLDER)
    sched_print.add_argument("--platform", choices=["auto", "linux", "macos", "windows"], default="auto")
    sched_print.add_argument("--name", default="skillbag-cronjobs")
    sched_print.set_defaults(func=cmd_scheduler_print)
    sched_install = scheduler_sub.add_parser("install", help="install scheduler setup")
    sched_install.add_argument("context_root")
    sched_install.add_argument("--cronjobs-folder", default=DEFAULT_FOLDER)
    sched_install.add_argument("--platform", choices=["auto", "linux", "macos", "windows"], default="auto")
    sched_install.add_argument("--name", default="skillbag-cronjobs")
    sched_install.set_defaults(func=cmd_scheduler_install)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(json_dump({"ok": False, "error": str(exc)}), file=sys.stderr, end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
