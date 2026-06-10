"""First-run setup wizard routes.

Mounted unconditionally; the routes themselves return 404 once the
app is configured. Setup-mode middleware (web/setup_mode.py) makes
every other route 307 to /setup while we're unconfigured.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from ..settings_schema import validate_new_password

router = APIRouter()


def _require_unconfigured(request: Request) -> None:
    if not request.app.state.settings_provider.get().is_unconfigured:
        raise HTTPException(status_code=404)


@router.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request) -> HTMLResponse:
    _require_unconfigured(request)
    import os
    static = os.path.join(os.path.dirname(__file__), "..", "static", "setup.html")
    with open(static, encoding="utf-8") as f:
        return HTMLResponse(f.read())


@router.post("/setup")
async def setup_submit(
    request: Request,
    response: Response,
    address: str = Form(""),
    password: str = Form(...),
    confirm: str = Form(...),
):
    _require_unconfigured(request)
    if password != confirm:
        raise HTTPException(status_code=400, detail="passwords do not match")
    try:
        validate_new_password(password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    provider = request.app.state.settings_provider
    if address:
        provider.update({"ADDRESS": address.strip()}, actor="setup-wizard")
    provider.set_password(password, actor="setup-wizard")
    redirect = RedirectResponse(url="/", status_code=303)
    request.app.state.auth.issue_session(redirect)
    return redirect


class TestDashcamRequest(BaseModel):
    address: str


@router.post("/api/setup/test-dashcam")
async def test_dashcam(request: Request, body: TestDashcamRequest):
    _require_unconfigured(request)
    # This route is reachable WITHOUT auth (the setup window), so
    # confine it to LAN targets — otherwise it's a TCP-connect prober
    # against arbitrary host:port for anyone on the network. The
    # authenticated settings probe stays unrestricted (an admin may
    # legitimately point at a remote dashcam over VPN).
    return await _probe(body.address, lan_only=True)


def _is_lan_host(host: str) -> bool:
    """True only if every address ``host`` resolves to is private,
    loopback, or link-local. A name that resolves to a global address
    (or doesn't resolve) is rejected for the unauthenticated probe."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr.split("%", 1)[0])  # strip zone id
        except ValueError:
            return False
        if not (ip.is_private or ip.is_loopback or ip.is_link_local):
            return False
    return bool(infos)


async def _probe(address: str, *, lan_only: bool = False) -> dict:
    """Best-effort TCP-connect probe; returns ok+latency or error.

    With ``lan_only`` the target must resolve entirely to LAN
    addresses (see :func:`_is_lan_host`) before any connection is
    attempted."""
    host, _, port_s = address.partition(":")
    port = int(port_s) if port_s.isdigit() else 80
    if lan_only and not _is_lan_host(host):
        return {"ok": False, "error": "address is not on the local network"}
    loop = asyncio.get_running_loop()
    start = loop.time()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, _sync_connect, host, port),
            timeout=3.0,
        )
        return {"ok": True, "latency_ms": int((loop.time() - start) * 1000)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _sync_connect(host: str, port: int) -> None:
    with socket.create_connection((host, port), timeout=3.0):
        pass
