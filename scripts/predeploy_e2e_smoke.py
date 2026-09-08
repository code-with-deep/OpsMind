"""Live API end-to-end smoke against running Docker stack (pre-deploy check)."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import httpx

BASE = "http://localhost:8000"
ROOT = Path(__file__).resolve().parents[1]
ZIP = ROOT / "data" / "csv_templates" / "nova_retail" / "sample_nova_retail.zip"
PLAYBOOK = ROOT / "data" / "csv_templates" / "nova_retail" / "nova-ops-playbook.md"
Q1 = (
    "Why did Nova Retail revenue drop in 2026-09-08 to 2026-09-14 "
    "compared to 2026-09-01 to 2026-09-07, and what should we do?"
)


def main() -> None:
    assert ZIP.is_file(), f"missing {ZIP}"
    assert PLAYBOOK.is_file(), f"missing {PLAYBOOK}"

    suffix = uuid.uuid4().hex[:8]
    email = f"e2e-{suffix}@example.com"
    password = "password123"
    company = f"E2E Nova {suffix}"

    with httpx.Client(base_url=BASE, timeout=300.0) as client:
        health = client.get("/health")
        health.raise_for_status()
        print("health", health.json())

        denied = client.get("/investigations")
        assert denied.status_code in (401, 403), denied.status_code
        print("unauth_blocked", denied.status_code)

        signup = client.post(
            "/auth/signup",
            json={"company_name": company, "email": email, "password": password},
        )
        assert signup.status_code == 200, signup.text
        token = signup.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("signup_ok", email)

        ready0 = client.get("/data/ready", headers=headers)
        assert ready0.status_code == 200, ready0.text
        assert ready0.json().get("ready") is False
        print("ready_before_csv", False)

        with ZIP.open("rb") as f:
            up = client.post(
                "/data/csv",
                headers=headers,
                files={"file": ("sample_nova_retail.zip", f, "application/zip")},
            )
        assert up.status_code == 200, up.text
        print("csv_upload_ok")

        ready = False
        for _ in range(40):
            r = client.get("/data/ready", headers=headers)
            r.raise_for_status()
            if r.json().get("ready"):
                ready = True
                break
            time.sleep(0.5)
        assert ready, "tenant never became ready after CSV"
        print("ready_after_csv", True)

        with PLAYBOOK.open("rb") as f:
            pb = client.post(
                "/playbooks",
                headers=headers,
                files={"file": ("nova-ops-playbook.md", f, "text/markdown")},
                data={"title": "Nova Ops Playbook"},
            )
        assert pb.status_code == 200, pb.text
        print("playbook_ok")

        inv = client.post("/auth/invites", headers=headers, json={"max_uses": 1})
        assert inv.status_code == 200, inv.text
        invite_id = inv.json()["invite"]["id"]
        code = inv.json()["invite"]["code"]
        rev = client.post(f"/auth/invites/{invite_id}/revoke", headers=headers)
        assert rev.status_code == 200
        join = client.post(
            "/auth/join",
            json={
                "invite_code": code,
                "email": f"joiner-{suffix}@example.com",
                "password": password,
            },
        )
        assert join.status_code == 400, join.text
        print("invite_revoke_blocks_join_ok")

        print("investigate_start")
        run = client.post(
            "/investigations",
            headers=headers,
            json={"question": Q1, "wait": True},
        )
        assert run.status_code == 200, run.text
        body = run.json()
        inv_row = body.get("investigation") or body
        status = inv_row.get("status")
        inv_id = inv_row.get("id") or body.get("id")
        rec = inv_row.get("recommendation") or body.get("recommendation") or {}
        hyp = inv_row.get("hypothesis") or body.get("hypothesis") or {}
        blob = (
            str(rec.get("summary") or "")
            + " "
            + " ".join(str(d) for d in (hyp.get("drivers") or []))
            + " "
            + str(status or "")
        )
        print("investigate_status", status, "id", inv_id)
        print("summary", (rec.get("summary") or "")[:240])
        print("drivers", hyp.get("drivers"))

        assert "540" in blob, f"expected 540 in output, got: {blob[:500]}"
        assert "1350" in blob or "1,350" in blob
        assert "SKU-1001" not in blob
        assert "FastShip" not in blob
        print("grounding_checks_ok")

        if status == "completed" and inv_id:
            review = client.post(
                f"/investigations/{inv_id}/reviews",
                headers=headers,
                json={
                    "decision": "approved",
                    "reviewer": email,
                    "notes": "predeploy e2e",
                },
            )
            assert review.status_code == 200, review.text
            print("approve_ok")

        other = client.post(
            "/auth/signup",
            json={
                "company_name": f"Other {suffix}",
                "email": f"other-{suffix}@example.com",
                "password": password,
            },
        )
        assert other.status_code == 200
        other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
        if inv_id:
            cross = client.get(f"/investigations/{inv_id}", headers=other_headers)
            assert cross.status_code in (403, 404), cross.status_code
            print("tenant_isolation_ok", cross.status_code)

        print("E2E_PASS")


if __name__ == "__main__":
    main()
