"""Application policy and local mock receipt ledger, separate from framework history."""
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3

from .hitl import ApprovalRequest, Decision
from .logging_util import log
from .tools_mock import RISK, book_flight, get_weather, validate_city


class ToolRuntime:
    def __init__(self, directory: Path, operation_id: str, city: str, role="traveler"):
        self.directory, self.operation_id = Path(directory), operation_id
        self.city, self.role = validate_city(city), role
        if role not in ("traveler", "readonly"):
            raise ValueError("Unknown role")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.database = self.directory / "approvals.sqlite"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS requests (
                    operation_id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending');
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY, operation_id TEXT, status TEXT, reason TEXT);
                CREATE TABLE IF NOT EXISTS effects (
                    operation_id TEXT PRIMARY KEY, receipt TEXT NOT NULL);
            """)

    def connect(self):
        return sqlite3.connect(self.database, timeout=10)

    def authorize(self, tool_name: str) -> None:
        allowed = {"get_weather"} if self.role == "readonly" else set(RISK)
        if tool_name not in allowed:
            raise PermissionError(f"Role {self.role} cannot invoke {tool_name}")

    def request(self, city: str, agent_id: str = "booking") -> ApprovalRequest:
        self.authorize("book_flight")
        # Bind the approval to actual validated arguments, never a prompt description.
        request = ApprovalRequest(self.operation_id, "book_flight",
                                  {"city": validate_city(city)}, "high", agent_id)
        payload = json.dumps(asdict(request), sort_keys=True)
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO requests(operation_id,payload) VALUES (?,?)",
                       (self.operation_id, payload))
            stored = db.execute("SELECT payload FROM requests WHERE operation_id=?",
                                (self.operation_id,)).fetchone()[0]
            if stored != payload:
                raise PermissionError("operation_id is already bound to different arguments/agent")
        log("trace", boundary="pre-tool", operation_id=self.operation_id)
        return request

    def pending_request(self) -> ApprovalRequest:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM requests WHERE operation_id=?",
                             (self.operation_id,)).fetchone()
        if not row:
            raise RuntimeError("No high-risk tool was proposed by the model")
        return ApprovalRequest(**json.loads(row[0]))

    def status(self) -> str:
        with self.connect() as db:
            row = db.execute("SELECT status FROM requests WHERE operation_id=?",
                             (self.operation_id,)).fetchone()
        return row[0] if row else "missing"

    def attempts(self) -> int:
        with self.connect() as db:
            return db.execute("SELECT count(*) FROM decisions WHERE operation_id=?",
                              (self.operation_id,)).fetchone()[0]

    def decide(self, approver) -> Decision:
        request = self.pending_request()
        if self.status() != "pending":
            raise RuntimeError("Only a pending request can receive a new decision")
        decision = approver.decide(request, self.attempts())
        with self.connect() as db:
            db.execute("INSERT INTO decisions(operation_id,status,reason) VALUES (?,?,?)",
                       (self.operation_id, decision.status, decision.reason))
            db.execute("UPDATE requests SET status=? WHERE operation_id=?",
                       (decision.status, self.operation_id))
        log("approval", operation_id=self.operation_id, **asdict(decision))
        return decision

    def reopen(self) -> None:
        if self.status() != "rejected" or self.effect_count():
            raise RuntimeError("Only an unexecuted rejection may be explicitly retried")
        with self.connect() as db:
            db.execute("UPDATE requests SET status='pending' WHERE operation_id=?",
                       (self.operation_id,))
        log("approval", operation_id=self.operation_id, status="retry-new-attempt")

    def weather(self, city: str) -> str:
        self.authorize("get_weather")
        log("tool.call", tool="get_weather", city=city)
        log("approval", tool="get_weather", status="approved", reason="Low-risk allowlist")
        result = get_weather(city)
        log("tool.return", tool="get_weather", result=result)
        return result

    def book(self, city: str) -> str:
        self.request(city)
        # Defense in depth: native approvals do not replace the application policy.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            status = db.execute("SELECT status FROM requests WHERE operation_id=?",
                                (self.operation_id,)).fetchone()[0]
            if status != "approved":
                raise PermissionError("No approved decision: mock side effect blocked")
            existing = db.execute("SELECT receipt FROM effects WHERE operation_id=?",
                                  (self.operation_id,)).fetchone()
            if existing:
                return existing[0]
            result = book_flight(city, self.operation_id)
            db.execute("INSERT INTO effects VALUES (?,?)", (self.operation_id, result))
        log("tool.call", tool="book_flight", city=city, operation_id=self.operation_id)
        log("tool.return", tool="book_flight", result=result)
        # The mock receipt and effect are one local transaction. External APIs need their
        # own idempotency key / reconciliation; session history cannot supply that guarantee.
        return result

    def guarded_book(self, city: str) -> str:
        self.request(city)
        if self.status() == "pending":
            return "PENDING_APPROVAL: booking not executed."
        if self.status() == "rejected":
            return "REJECTED: booking not executed."
        return self.book(city)

    def effect_count(self) -> int:
        with self.connect() as db:
            return db.execute("SELECT count(*) FROM effects WHERE operation_id=?",
                              (self.operation_id,)).fetchone()[0]
