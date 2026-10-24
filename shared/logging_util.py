"""Small structured logs; credentials and whole environments are never logged."""
import json
import os
import time


def log(tag: str, **fields) -> None:
    if tag == "trace" and os.getenv("LAB_TRACE", "0") != "1":
        return
    print(f"[{tag}] " + json.dumps({"time": round(time.time(), 3), **fields},
                                    ensure_ascii=False, default=str), flush=True)
