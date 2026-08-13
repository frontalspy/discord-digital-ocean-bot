from __future__ import annotations

import os
import time
from typing import Optional

import requests

_BASE = "https://api.digitalocean.com/v2"


def get_droplet_name() -> str:
    return os.environ.get("DO_DROPLET_NAME", "pew-pew")


def _raise_for_status(r: requests.Response) -> None:
    """Like requests.Response.raise_for_status(), but includes DigitalOcean's
    actual error message instead of just the HTTP status line."""
    if r.ok:
        return
    try:
        detail = r.json().get("message", r.text)
    except ValueError:
        detail = r.text
    raise requests.HTTPError(f"{r.status_code} {r.reason} for {r.url}: {detail}", response=r)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['DO_API_TOKEN']}",
        "Content-Type": "application/json",
    }


def get_droplet() -> Optional[dict]:
    r = requests.get(f"{_BASE}/droplets?per_page=200", headers=_headers())
    _raise_for_status(r)
    return next((d for d in r.json()["droplets"] if d["name"] == get_droplet_name()), None)


def get_snapshot() -> Optional[dict]:
    r = requests.get(
        f"{_BASE}/snapshots?resource_type=droplet&per_page=200", headers=_headers()
    )
    _raise_for_status(r)
    return next((s for s in r.json()["snapshots"] if s["name"] == get_droplet_name()), None)


def _get_cheapest_size(region: str, min_disk_gb: int) -> dict:
    r = requests.get(f"{_BASE}/sizes", headers=_headers())
    _raise_for_status(r)
    sizes = [
        s
        for s in r.json()["sizes"]
        if s["available"] and region in s.get("regions", []) and s["disk"] >= min_disk_gb
    ]
    if not sizes:
        raise RuntimeError(
            f"No available droplet sizes in region {region!r} with at least "
            f"{min_disk_gb}GB disk (required to restore this snapshot)"
        )
    return min(sizes, key=lambda s: s["price_monthly"])


def create_droplet_from_snapshot(snapshot: dict) -> dict:
    region = snapshot["regions"][0]
    # The target size's disk must be at least as large as the snapshot's
    # min_disk_size, or DigitalOcean rejects the create with a 422.
    size = _get_cheapest_size(region, snapshot["min_disk_size"])
    r = requests.post(
        f"{_BASE}/droplets",
        headers=_headers(),
        json={
            "name": get_droplet_name(),
            "region": region,
            "size": size["slug"],
            "image": snapshot["id"],
        },
    )
    _raise_for_status(r)
    return r.json()["droplet"]


def wait_for_droplet_active(droplet_id: int, timeout: int = 600) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = requests.get(f"{_BASE}/droplets/{droplet_id}", headers=_headers())
        _raise_for_status(r)
        droplet = r.json()["droplet"]
        if droplet["status"] == "active":
            return droplet
        time.sleep(30)
    raise TimeoutError(f"Droplet {droplet_id} did not become active within {timeout}s")


def assign_reserved_ip(droplet_id: int, ip: str) -> None:
    r = requests.post(
        f"{_BASE}/reserved_ips/{ip}/actions",
        headers=_headers(),
        json={"type": "assign", "droplet_id": droplet_id},
    )
    _raise_for_status(r)


def unassign_reserved_ip(ip: str) -> None:
    r = requests.post(
        f"{_BASE}/reserved_ips/{ip}/actions",
        headers=_headers(),
        json={"type": "unassign"},
    )
    _raise_for_status(r)


def power_off_droplet(droplet_id: int) -> None:
    r = requests.post(
        f"{_BASE}/droplets/{droplet_id}/actions",
        headers=_headers(),
        json={"type": "power_off"},
    )
    _raise_for_status(r)


def wait_for_droplet_off(droplet_id: int, timeout: int = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = requests.get(f"{_BASE}/droplets/{droplet_id}", headers=_headers())
        _raise_for_status(r)
        if r.json()["droplet"]["status"] == "off":
            return
        time.sleep(5)
    raise TimeoutError(f"Droplet {droplet_id} did not power off within {timeout}s")


def create_snapshot(droplet_id: int, name: str) -> None:
    r = requests.post(
        f"{_BASE}/droplets/{droplet_id}/actions",
        headers=_headers(),
        json={"type": "snapshot", "name": name},
    )
    _raise_for_status(r)
    action_id = r.json()["action"]["id"]
    _wait_for_action(droplet_id, action_id, timeout=600)


def _wait_for_action(droplet_id: int, action_id: int, timeout: int = 600) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = requests.get(
            f"{_BASE}/droplets/{droplet_id}/actions/{action_id}", headers=_headers()
        )
        _raise_for_status(r)
        status = r.json()["action"]["status"]
        if status == "completed":
            return
        if status == "errored":
            raise RuntimeError(f"DO action {action_id} errored")
        time.sleep(10)
    raise TimeoutError(f"DO action {action_id} did not complete within {timeout}s")


def delete_snapshot(snapshot_id: str) -> None:
    r = requests.delete(f"{_BASE}/snapshots/{snapshot_id}", headers=_headers())
    _raise_for_status(r)


def destroy_droplet(droplet_id: int) -> None:
    r = requests.delete(f"{_BASE}/droplets/{droplet_id}", headers=_headers())
    _raise_for_status(r)
