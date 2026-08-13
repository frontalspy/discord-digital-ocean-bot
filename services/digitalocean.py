from __future__ import annotations

import os
import time
from typing import Optional

import requests

_BASE = "https://api.digitalocean.com/v2"


def get_droplet_name() -> str:
    return os.environ.get("DO_DROPLET_NAME", "pew-pew")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['DO_API_TOKEN']}",
        "Content-Type": "application/json",
    }


def get_droplet() -> Optional[dict]:
    r = requests.get(f"{_BASE}/droplets?per_page=200", headers=_headers())
    r.raise_for_status()
    return next((d for d in r.json()["droplets"] if d["name"] == get_droplet_name()), None)


def get_snapshot() -> Optional[dict]:
    r = requests.get(
        f"{_BASE}/snapshots?resource_type=droplet&per_page=200", headers=_headers()
    )
    r.raise_for_status()
    return next((s for s in r.json()["snapshots"] if s["name"] == get_droplet_name()), None)


def _get_cheapest_size(region: str) -> dict:
    r = requests.get(f"{_BASE}/sizes", headers=_headers())
    r.raise_for_status()
    sizes = [
        s
        for s in r.json()["sizes"]
        if s["available"] and region in s.get("regions", [])
    ]
    if not sizes:
        raise RuntimeError(f"No available droplet sizes in region {region!r}")
    return min(sizes, key=lambda s: s["price_monthly"])


def create_droplet_from_snapshot(snapshot: dict) -> dict:
    region = snapshot["regions"][0]
    size = _get_cheapest_size(region)
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
    r.raise_for_status()
    return r.json()["droplet"]


def wait_for_droplet_active(droplet_id: int, timeout: int = 300) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = requests.get(f"{_BASE}/droplets/{droplet_id}", headers=_headers())
        r.raise_for_status()
        droplet = r.json()["droplet"]
        if droplet["status"] == "active":
            return droplet
        time.sleep(5)
    raise TimeoutError(f"Droplet {droplet_id} did not become active within {timeout}s")


def assign_reserved_ip(droplet_id: int, ip: str) -> None:
    r = requests.post(
        f"{_BASE}/reserved_ips/{ip}/actions",
        headers=_headers(),
        json={"type": "assign", "droplet_id": droplet_id},
    )
    r.raise_for_status()


def unassign_reserved_ip(ip: str) -> None:
    r = requests.post(
        f"{_BASE}/reserved_ips/{ip}/actions",
        headers=_headers(),
        json={"type": "unassign"},
    )
    r.raise_for_status()


def power_off_droplet(droplet_id: int) -> None:
    r = requests.post(
        f"{_BASE}/droplets/{droplet_id}/actions",
        headers=_headers(),
        json={"type": "power_off"},
    )
    r.raise_for_status()


def wait_for_droplet_off(droplet_id: int, timeout: int = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = requests.get(f"{_BASE}/droplets/{droplet_id}", headers=_headers())
        r.raise_for_status()
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
    r.raise_for_status()
    action_id = r.json()["action"]["id"]
    _wait_for_action(droplet_id, action_id, timeout=600)


def _wait_for_action(droplet_id: int, action_id: int, timeout: int = 600) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = requests.get(
            f"{_BASE}/droplets/{droplet_id}/actions/{action_id}", headers=_headers()
        )
        r.raise_for_status()
        status = r.json()["action"]["status"]
        if status == "completed":
            return
        if status == "errored":
            raise RuntimeError(f"DO action {action_id} errored")
        time.sleep(10)
    raise TimeoutError(f"DO action {action_id} did not complete within {timeout}s")


def delete_snapshot(snapshot_id: str) -> None:
    r = requests.delete(f"{_BASE}/snapshots/{snapshot_id}", headers=_headers())
    r.raise_for_status()


def destroy_droplet(droplet_id: int) -> None:
    r = requests.delete(f"{_BASE}/droplets/{droplet_id}", headers=_headers())
    r.raise_for_status()
