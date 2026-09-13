"""Live end-to-end smoke test against a running OpsMind stack (pre-deploy check).

Covers the real product path with the sample bundle shipped in
data/sample_templates: signup validation → signup → CSV + playbook upload →
invite revoke → background investigation followed over the live event stream
→ review → cross-tenant isolation.

    python scripts/predeploy_e2e_smoke.py [--base-url http://localhost:8000]
"""

from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DATA = ROOT / "data" / "sample_templates" / "opsmind_sample_data.zip"
SAMPLE_PLAYBOOKS = ROOT / "data" / "sample_templates" / "opsmind_sample_playbooks.zip"
QUESTION = "Why did revenue decrease in the week of 2026-08-10 compared to the prior week?"
TERMINAL = {
    "completed",
    "unsupported",
    "needs_clarification",
    "insufficient_evidence",
    "budget_exceeded",
    "guardrail_rejected",
    "failed",
}


class EventCollector(threading.Thread):
    """Reads GET /events/stream in the background and records change events."""

    def __init__(self, base_url: str, headers: dict[str, str]) -> None:
        super().__init__(daemon=True)
        self.base_url = base_url
        self.headers = headers
        self.events: list[dict] = []
        self.ready = threading.Event()
        self.stop = threading.Event()

    def run(self) -> None:
        with httpx.Client(base_url=self.base_url, timeout=None) as client:
            with client.stream("GET", "/events/stream", headers=self.headers) as response:
                response.raise_for_status()
                name = ""
                for line in response.iter_lines():
                    if self.stop.is_set():
                        return
                    if line.startswith("event:"):
                        name = line[6:].strip()
                    elif line.startswith("data:"):
                        if name == "ready":
                            self.ready.set()
                        elif name == "change":
                            self.events.append(json.loads(line[5:]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    assert SAMPLE_DATA.is_file(), f"missing {SAMPLE_DATA}"
    assert SAMPLE_PLAYBOOKS.is_file(), f"missing {SAMPLE_PLAYBOOKS}"

    suffix = uuid.uuid4().hex[:8]
    email = f"e2e-{suffix}@example.com"
    password = "password123"

    with httpx.Client(base_url=args.base_url, timeout=120.0) as client:
        assert client.get("/health").status_code == 200
        denied = client.get("/investigations")
        assert denied.status_code in (401, 403), denied.status_code
        print("unauth_blocked", denied.status_code)

        bad_email = client.post(
            "/auth/signup",
            json={"company_name": "E2E", "email": "not-an-email", "password": password},
        )
        assert bad_email.status_code == 422, bad_email.text
        assert "valid email" in bad_email.json()["detail"], bad_email.text
        weak = client.post(
            "/auth/signup",
            json={"company_name": "E2E", "email": email, "password": "onlyletters"},
        )
        assert weak.status_code == 422 and "number" in weak.json()["detail"], weak.text
        print("validation_messages_ok")

        signup = client.post(
            "/auth/signup",
            json={"company_name": f"E2E {suffix}", "email": email, "password": password},
        )
        assert signup.status_code == 200, signup.text
        headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
        dup = client.post(
            "/auth/signup",
            json={"company_name": f"E2E {suffix}", "email": email, "password": password},
        )
        assert dup.status_code == 409, dup.text
        print("signup_ok", email)

        blocked = client.post("/investigations", headers=headers, json={"question": QUESTION})
        assert blocked.status_code == 409, blocked.text
        print("not_ready_gate_ok")

        with SAMPLE_DATA.open("rb") as f:
            up = client.post(
                "/data/csv", headers=headers, files={"file": (SAMPLE_DATA.name, f, "application/zip")}
            )
        assert up.status_code == 200, up.text
        assert client.get("/data/ready", headers=headers).json().get("ready") is True
        with SAMPLE_PLAYBOOKS.open("rb") as f:
            pb = client.post(
                "/playbooks",
                headers=headers,
                files={"file": (SAMPLE_PLAYBOOKS.name, f, "application/zip")},
            )
        assert pb.status_code == 200, pb.text
        print("data_and_playbooks_ok", pb.json().get("count"))

        inv = client.post("/auth/invites", headers=headers, json={"max_uses": 1})
        assert inv.status_code == 200, inv.text
        invite = inv.json()["invite"]
        assert client.post(f"/auth/invites/{invite['id']}/revoke", headers=headers).status_code == 200
        join = client.post(
            "/auth/join",
            json={"invite_code": invite["code"], "email": f"joiner-{suffix}@example.com", "password": password},
        )
        assert join.status_code == 400, join.text
        print("invite_revoke_blocks_join_ok")

        collector = EventCollector(args.base_url, headers)
        collector.start()
        assert collector.ready.wait(10), "event stream did not open"

        started = time.monotonic()
        run = client.post(
            "/investigations", headers=headers, json={"question": QUESTION, "wait": False}
        )
        assert run.status_code == 202, run.text
        inv_id = run.json()["id"]
        assert run.json()["status"] == "running"
        print("investigation_started", inv_id, f"{(time.monotonic() - started) * 1000:.0f}ms")

        detail: dict = {}
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            detail = client.get(f"/investigations/{inv_id}", headers=headers).json()
            if detail["status"] in TERMINAL:
                break
            time.sleep(1)
        print("investigation_status", detail["status"], f"{time.monotonic() - started:.1f}s")
        assert detail["status"] == "completed", detail["status"]
        assert any(f["source_id"].startswith("sql_") for f in detail["findings"])
        assert any(f["source_id"].startswith("rag_") for f in detail["findings"])
        drivers = (detail.get("hypothesis") or {}).get("drivers") or []
        print("drivers", drivers)
        blob = json.dumps(detail.get("hypothesis")) + json.dumps(detail.get("recommendation"))
        assert "SKU-1001" not in blob and "FastShip" not in blob, "demo-tenant data leaked"
        print("grounding_checks_ok")

        time.sleep(1)
        collector.stop.set()
        live = [e for e in collector.events if e.get("investigation_id") == inv_id or e.get("id") == inv_id]
        tables = sorted({e["table"] for e in live})
        print("live_events", len(live), tables)
        assert "investigation_events" in tables and "investigations" in tables, collector.events

        review = client.post(
            f"/investigations/{inv_id}/reviews",
            headers=headers,
            json={"decision": "approved", "notes": "predeploy e2e"},
        )
        assert review.status_code == 200, review.text
        print("approve_ok", review.json().get("case_promoted"))

        other = client.post(
            "/auth/signup",
            json={"company_name": f"Other {suffix}", "email": f"other-{suffix}@example.com", "password": password},
        )
        assert other.status_code == 200, other.text
        other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
        cross = client.get(f"/investigations/{inv_id}", headers=other_headers)
        assert cross.status_code in (403, 404), cross.status_code
        assert client.get("/investigations", headers=other_headers).json()["count"] == 0
        print("tenant_isolation_ok", cross.status_code)

        print("E2E_PASS")


if __name__ == "__main__":
    main()
