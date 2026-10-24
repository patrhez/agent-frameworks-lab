"""Shared prepare/approve/resume lifecycle. Adapters own native framework state."""
import argparse
import asyncio
import os
from pathlib import Path
import uuid

from .hitl import ScriptedApprover, make_approver
from .logging_util import log
from .runtime import ToolRuntime
from .storage import read_json, write_json


def main(adapter) -> None:
    parser = argparse.ArgumentParser(description=adapter.__doc__)
    parser.add_argument("--hitl", choices=["auto_approve", "auto_reject", "scripted"],
                        default=os.getenv("HITL_MODE", "auto_approve"))
    parser.add_argument("--script", default=os.getenv("HITL_SCRIPT"))
    parser.add_argument("--phase", choices=["all", "prepare", "resume"], default="all")
    parser.add_argument("--state-dir", type=Path, default=Path(".local-data/advanced"))
    parser.add_argument("--city", default="Shanghai")
    parser.add_argument("--role", choices=["traveler", "readonly"], default="traveler")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--stream", action="store_true", help="Print native framework events")
    args = parser.parse_args()
    asyncio.run(execute(adapter, args))


async def execute(adapter, args) -> dict:
    if args.live and os.getenv("RUN_LIVE") != "1":
        raise RuntimeError("Live model calls require RUN_LIVE=1")
    directory = args.state_dir.resolve()
    meta_path = directory / "control.json"
    if meta_path.exists():
        meta = read_json(meta_path)
    else:
        if args.phase == "resume":
            raise ValueError("No saved run to resume")
        meta = {"operation_id": str(uuid.uuid4()), "city": args.city, "role": args.role,
                "live": args.live, "framework": adapter.__name__}
        write_json(meta_path, meta)
    if meta["framework"] != adapter.__name__:
        raise ValueError("State directory belongs to a different adapter")
    if meta["live"] and os.getenv("RUN_LIVE") != "1":
        raise RuntimeError("Resuming a live run requires RUN_LIVE=1")
    runtime = ToolRuntime(directory, meta["operation_id"], meta["city"], meta["role"])
    runtime.authorize("book_flight")
    finished = directory / "completed.json"
    if finished.exists():
        log("final", **read_json(finished), replay=True)
        return read_json(finished)
    approver = make_approver(args.hitl, args.script)
    log("user", message=f"Check weather and book a mock flight to {runtime.city}",
        backend="live" if meta["live"] else "native-mock")
    checkpoint = directory / "checkpoint.json"
    for _ in range(10):  # A finite retry budget: never wait for human input.
        if not checkpoint.exists():
            if args.phase == "resume":
                raise ValueError("No framework checkpoint exists")
            await adapter.prepare(runtime, live=meta["live"], stream=args.stream)
            runtime.pending_request()
            assert runtime.effect_count() == 0, "Side effect ran before approval"
            log("checkpoint", path=str(checkpoint), status="pending", effects=0)
        if args.phase == "prepare":
            return {"status": "pending", "effects": 0}
        if runtime.status() == "pending":
            runtime.decide(approver)
        # Reuse a saved decision after a crash between deciding and resuming.
        await adapter.resume(runtime, live=meta["live"], stream=args.stream)
        count = runtime.effect_count()
        status = runtime.status()
        if status == "approved" and count != 1:
            raise RuntimeError("Approved run failed to execute exactly one local mock effect")
        if status == "rejected" and count:
            raise RuntimeError("Rejected operation executed a side effect")
        retry = (args.phase == "all" and status == "rejected"
                 and isinstance(approver, ScriptedApprover)
                 and approver.has_next(runtime.pending_request(), runtime.attempts()))
        if retry:
            runtime.reopen()
            checkpoint.unlink()
            continue
        result = {"status": status, "effects": count, "operation_id": runtime.operation_id}
        write_json(finished, result)
        log("final", **result)
        return result
    raise RuntimeError("Scripted retry budget exhausted")
