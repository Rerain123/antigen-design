"""SQLite-backed run, idempotency, and mock job state."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from .contracts import (
    ConfigureRunRequest,
    JobCancelRequest,
    JobLookupRequest,
    Outcome,
    RunRecord,
    RunStatus,
    StepResult,
    StepStatus,
    T01Input,
)


class IdempotencyConflict(ValueError):
    """Raised when a key is reused for different work."""


class RunNotFound(KeyError):
    """Raised when a configured run is missing."""


class RunConfigurationConflict(ValueError):
    """Raised when an executed run_id is rebound to different fixtures."""


class JobNotFound(KeyError):
    """Raised when a mock job is missing or belongs to another run."""


def utc_now() -> datetime:
    return datetime.now(UTC)


class SQLiteStore:
    """Small persistent store suitable for a single Mock MCP process.

    Each operation opens its own connection.  The lock protects compound
    read/modify/write operations and keeps unit tests deterministic.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    outcome TEXT,
                    input_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS step_results (
                    idempotency_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_step_results_run_id
                    ON step_results(run_id);
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    polls INTEGER NOT NULL,
                    final_result_json TEXT NOT NULL,
                    cancel_reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_jobs_run_id ON jobs(run_id);
                """
            )

    def configure_run(self, request: ConfigureRunRequest) -> RunRecord:
        now = utc_now()
        payload = request.input.model_dump_json() if request.input is not None else None
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM runs WHERE run_id = ?", (request.run_id,)
            ).fetchone()
            if existing is not None:
                same_configuration = (
                    existing["scenario_id"] == request.scenario_id
                    and existing["input_json"] == payload
                )
                if same_configuration:
                    return self.get_run(request.run_id)
                step_count = connection.execute(
                    "SELECT COUNT(*) FROM step_results WHERE run_id = ?", (request.run_id,)
                ).fetchone()[0]
                job_count = connection.execute(
                    "SELECT COUNT(*) FROM jobs WHERE run_id = ?", (request.run_id,)
                ).fetchone()[0]
                if step_count or job_count:
                    raise RunConfigurationConflict(
                        "run_id already has results; use a new run_id for a different scenario or input"
                    )
            created_at = existing["created_at"] if existing else now.isoformat()
            connection.execute(
                """
                INSERT INTO runs(run_id, scenario_id, status, outcome, input_json, created_at, updated_at)
                VALUES (?, ?, ?, NULL, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    scenario_id = excluded.scenario_id,
                    status = excluded.status,
                    outcome = NULL,
                    input_json = excluded.input_json,
                    updated_at = excluded.updated_at
                """,
                (
                    request.run_id,
                    request.scenario_id,
                    RunStatus.QUEUED.value,
                    payload,
                    created_at,
                    now.isoformat(),
                ),
            )
        return self.get_run(request.run_id)

    def ensure_run(self, run_id: str, scenario_id: str) -> RunRecord:
        try:
            return self.get_run(run_id)
        except RunNotFound:
            return self.configure_run(
                ConfigureRunRequest(run_id=run_id, scenario_id=scenario_id, input=None)
            )

    def get_run(self, run_id: str) -> RunRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise RunNotFound(run_id)
        input_value = T01Input.model_validate_json(row["input_json"]) if row["input_json"] else None
        return RunRecord(
            run_id=row["run_id"],
            scenario_id=row["scenario_id"],
            status=RunStatus(row["status"]),
            outcome=Outcome(row["outcome"]) if row["outcome"] else None,
            input=input_value,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def set_run_status(
        self, run_id: str, status: RunStatus, outcome: Outcome | None = None
    ) -> None:
        with self._lock, self._connect() as connection:
            updated = connection.execute(
                "UPDATE runs SET status = ?, outcome = ?, updated_at = ? WHERE run_id = ?",
                (status.value, outcome.value if outcome else None, utc_now().isoformat(), run_id),
            )
            if updated.rowcount == 0:
                raise RunNotFound(run_id)

    def get_idempotent_result(
        self, idempotency_key: str, tool_name: str, request_hash: str
    ) -> StepResult | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM step_results WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
        if row is None:
            return None
        if row["tool_name"] != tool_name or row["request_hash"] != request_hash:
            raise IdempotencyConflict(idempotency_key)
        return StepResult.model_validate_json(row["result_json"])

    def save_idempotent_result(
        self,
        *,
        idempotency_key: str,
        run_id: str,
        tool_name: str,
        request_hash: str,
        result: StepResult,
    ) -> None:
        with self._lock, self._connect() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO step_results(
                        idempotency_key, run_id, tool_name, request_hash, result_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        idempotency_key,
                        run_id,
                        tool_name,
                        request_hash,
                        result.model_dump_json(),
                        utc_now().isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                prior = self.get_idempotent_result(idempotency_key, tool_name, request_hash)
                if prior is None:  # pragma: no cover - defensive race fallback
                    raise exc

    def create_job(self, job_id: str, run_id: str, final_result: StepResult) -> None:
        with self._lock, self._connect() as connection:
            now = utc_now().isoformat()
            connection.execute(
                """
                INSERT INTO jobs(
                    job_id, run_id, state, polls, final_result_json,
                    cancel_reason, created_at, updated_at
                ) VALUES (?, ?, ?, 0, ?, NULL, ?, ?)
                """,
                (
                    job_id,
                    run_id,
                    StepStatus.QUEUED.value,
                    final_result.model_dump_json(),
                    now,
                    now,
                ),
            )

    def read_job(self, request: JobLookupRequest) -> tuple[StepStatus, int, StepResult, str | None]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ? AND run_id = ?",
                (request.job_id, request.run_id),
            ).fetchone()
        if row is None:
            raise JobNotFound(request.job_id)
        return (
            StepStatus(row["state"]),
            int(row["polls"]),
            StepResult.model_validate_json(row["final_result_json"]),
            row["cancel_reason"],
        )

    def advance_job(self, request: JobLookupRequest) -> tuple[StepStatus, int, StepResult, str | None]:
        with self._lock:
            state, polls, final_result, cancel_reason = self.read_job(request)
            if state == StepStatus.QUEUED:
                state = StepStatus.RUNNING
                polls = 1
            elif state == StepStatus.RUNNING:
                state = StepStatus.SUCCEEDED
                polls = 2
            if state in {StepStatus.QUEUED, StepStatus.RUNNING, StepStatus.SUCCEEDED}:
                with self._connect() as connection:
                    connection.execute(
                        "UPDATE jobs SET state = ?, polls = ?, updated_at = ? WHERE job_id = ?",
                        (state.value, polls, utc_now().isoformat(), request.job_id),
                    )
            return state, polls, final_result, cancel_reason

    def cancel_job(self, request: JobCancelRequest) -> tuple[StepStatus, int, StepResult, str | None]:
        with self._lock:
            state, polls, final_result, cancel_reason = self.read_job(request)
            if state not in {StepStatus.QUEUED, StepStatus.RUNNING}:
                return state, polls, final_result, cancel_reason
            state = StepStatus.CANCELLED
            cancel_reason = request.reason
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE jobs SET state = ?, cancel_reason = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (state.value, cancel_reason, utc_now().isoformat(), request.job_id),
                )
            return state, polls, final_result, cancel_reason

    def export_run_debug(self, run_id: str) -> dict[str, object]:
        run = self.get_run(run_id)
        with self._connect() as connection:
            steps = connection.execute(
                """
                SELECT tool_name, request_hash, result_json, created_at
                FROM step_results WHERE run_id = ? ORDER BY created_at
                """,
                (run_id,),
            ).fetchall()
            jobs = connection.execute(
                """
                SELECT job_id, state, polls, created_at, updated_at
                FROM jobs WHERE run_id = ? ORDER BY created_at
                """,
                (run_id,),
            ).fetchall()
        return {
            "run": run.model_dump(mode="json"),
            "steps": [
                {
                    "tool_name": row["tool_name"],
                    "request_hash": row["request_hash"],
                    "result": json.loads(row["result_json"]),
                    "created_at": row["created_at"],
                }
                for row in steps
            ],
            "jobs": [dict(row) for row in jobs],
        }
