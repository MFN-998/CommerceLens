"""One retained, supervised Q01 job with a shared monotonic deadline.

SQL limits bound server work; process supervision also bounds DNS, network waits
and worker threads. Settings cross a private startup pipe, never command-line
arguments. Two seconds of the job budget are reserved for terminating/reaping.
"""

from __future__ import annotations

import json
import math
import multiprocessing
import os
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

JOB_SECONDS = 600
CLEANUP_SECONDS = 2
MAX_RESULT_BYTES = 8 * 1024 * 1024


class MeasurementError(ValueError):
    """Fixed diagnostics without settings, SQL values or driver details."""


@dataclass(frozen=True)
class Deadline:
    expires_at: float

    def remaining(self) -> float:
        remaining = self.expires_at - monotonic()
        if not math.isfinite(remaining) or remaining <= 0:
            raise MeasurementError("Measurement job deadline exceeded")
        return remaining

    def check(self) -> None:
        self.remaining()

    def milliseconds(self, maximum: int = 55_000) -> int:
        value = min(maximum, math.floor(self.remaining() * 1000))
        if value < 1:
            raise MeasurementError("Measurement job deadline exceeded")
        return value

    def connection_options(self) -> dict[str, int]:
        # libpq rounds values below two seconds up to two; never start a
        # connection with less time than that left in the work budget.
        connect_timeout = min(10, math.floor(self.remaining()))
        if connect_timeout < 2:
            raise MeasurementError("Insufficient measurement connection budget")
        timeout = self.milliseconds()
        return {
            "connect_timeout": connect_timeout,
            "statement_timeout_ms": timeout,
            "lock_timeout_ms": min(5_000, timeout),
        }

    def execute(self, connection: Any, statement: Any, *args: Any, **kwargs: Any) -> Any:
        timeout = self.milliseconds()
        # SET does not perform a query before SET TRANSACTION READ ONLY. Values
        # are bounded integers derived here, never user-provided SQL fragments.
        connection.execute(f"SET statement_timeout='{timeout}ms'")
        connection.execute(f"SET lock_timeout='{min(5_000, timeout)}ms'")
        self.check()
        result = connection.execute(statement, *args, **kwargs)
        self.check()
        return result


Work = Callable[[Any, Path, Deadline], dict[str, Any]]


def _worker(work: Work, settings: Any, folder: Path, deadline: Deadline, output: Path) -> None:
    # Suppress even an unexpected callback print/traceback. The only crossing
    # result is a bounded aggregate receipt or a fixed error status.
    with open(os.devnull, "w", encoding="utf-8") as sink:
        with redirect_stdout(sink), redirect_stderr(sink):
            try:
                deadline.check()
                result = work(settings, folder, deadline)
                deadline.check()
                body = json.dumps({"status": "passed", "result": result}).encode("utf-8")
                if len(body) > MAX_RESULT_BYTES:
                    raise MeasurementError("Measurement receipt exceeds boundary")
            except BaseException:
                body = b'{"status":"failed"}'
            try:
                with output.open("xb") as handle:
                    handle.write(body)
            except OSError:
                # Parent treats a missing or incomplete receipt as failure.
                pass


def run_bounded_measurement(
    work: Work, settings: Any, folder: Path, *, job_seconds: float = JOB_SECONDS
) -> dict[str, Any]:
    """Run the entire before/access/queries/after callback under one budget."""
    if not math.isfinite(job_seconds) or not CLEANUP_SECONDS < job_seconds <= JOB_SECONDS:
        raise MeasurementError("Invalid measurement job budget")
    expires_at = monotonic() + job_seconds
    deadline = Deadline(expires_at - CLEANUP_SECONDS)
    output = folder / f"measurement-worker-{uuid4().hex}.json"
    process = multiprocessing.get_context("spawn").Process(
        target=_worker,
        args=(work, settings, folder, deadline, output),
        daemon=True,
    )
    started = False
    try:
        deadline.check()
        process.start()
        started = True
        process.join(timeout=deadline.remaining())
        if process.is_alive():
            raise MeasurementError("Measurement job deadline exceeded")
        deadline.check()
        if process.exitcode != 0 or output.stat().st_size > MAX_RESULT_BYTES:
            raise MeasurementError("Measurement worker failed; evidence retained")
        receipt = json.loads(output.read_bytes())
        deadline.check()
        if receipt.get("status") != "passed" or not isinstance(receipt.get("result"), dict):
            raise MeasurementError("Measurement worker failed; evidence retained")
        return dict(receipt["result"])
    except (Exception, KeyboardInterrupt):
        raise MeasurementError("Measurement job failed or expired; evidence retained") from None
    finally:
        if started:
            if process.is_alive():
                process.terminate()
                process.join(timeout=min(1.0, max(0.0, expires_at - monotonic())))
            if process.is_alive():
                process.kill()
                process.join(timeout=max(0.0, expires_at - monotonic()))
            if process.is_alive():
                raise MeasurementError("Measurement worker termination could not be verified")
            process.close()
