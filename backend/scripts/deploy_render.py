"""Trigger a Render deploy of the backend service and poll until it finishes.

Reads RENDER_API_KEY and RENDER_SERVICE_ID from backend/.env (gitignored). Use after pushing to
GitHub so the always-on backend picks up the new code. Supabase migrations run automatically on
container boot (see Dockerfile), so this single step also applies any new migrations.

Usage (from backend/):
    python -m scripts.deploy_render
"""

from __future__ import annotations

import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

API = "https://api.render.com/v1"


def main() -> int:
    # Simplest path: the private deploy hook (no API key needed).
    hook = os.getenv("RENDER_DEPLOY_HOOK")
    if hook:
        try:
            r = httpx.get(hook, timeout=30.0)
            r.raise_for_status()
            print(f"Deploy hook fired: {r.status_code} {r.text[:120]}")
            print("Render Auto-Deploy is On-Commit, so a git push also deploys. Check the dashboard for status.")
            return 0
        except httpx.HTTPError as exc:
            print(f"Deploy hook failed ({exc}); falling back to API...")

    key = os.getenv("RENDER_API_KEY")
    service = os.getenv("RENDER_SERVICE_ID")
    if not key or not service:
        print("RENDER_API_KEY / RENDER_SERVICE_ID not set in backend/.env")
        return 1

    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    try:
        resp = httpx.post(f"{API}/services/{service}/deploys", headers=headers,
                          json={"clearCache": "do_not_clear"}, timeout=30.0)
        resp.raise_for_status()
        deploy = resp.json()
    except httpx.HTTPError as exc:
        print(f"Deploy trigger failed: {exc}")
        return 1

    deploy_id = deploy.get("id")
    print(f"Triggered deploy {deploy_id} (status {deploy.get('status')}). Polling...")

    terminal = {"live", "deactivated", "build_failed", "update_failed", "canceled", "pre_deploy_failed"}
    for _ in range(60):  # ~10 minutes
        time.sleep(10)
        try:
            d = httpx.get(f"{API}/services/{service}/deploys/{deploy_id}", headers=headers, timeout=30.0).json()
        except httpx.HTTPError:
            continue
        status = d.get("status")
        print(f"  status: {status}")
        if status in terminal:
            ok = status == "live"
            print("Deploy succeeded." if ok else f"Deploy ended: {status}")
            return 0 if ok else 1
    print("Still deploying after timeout; check the Render dashboard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
