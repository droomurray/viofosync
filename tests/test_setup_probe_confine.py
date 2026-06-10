"""The unauthenticated setup probe must not be a general SSRF tool,
and the import scan must not leak filenames of arbitrary directories.
"""
from __future__ import annotations

from web.routers import setup as setup_mod

# ---- SSRF: the pre-auth setup probe is restricted to LAN targets ----

async def test_setup_probe_rejects_public_host(monkeypatch):
    connect_calls = []

    def _spy_connect(host, port):
        connect_calls.append((host, port))

    monkeypatch.setattr(setup_mod, "_sync_connect", _spy_connect)
    res = await setup_mod._probe("93.184.216.34:443", lan_only=True)
    assert res["ok"] is False
    assert connect_calls == [], "probe connected to a public address"


async def test_setup_probe_allows_private_host(monkeypatch):
    connect_calls = []
    monkeypatch.setattr(setup_mod, "_sync_connect",
                        lambda h, p: connect_calls.append((h, p)))
    res = await setup_mod._probe("192.168.1.230", lan_only=True)
    assert res["ok"] is True
    assert connect_calls == [("192.168.1.230", 80)]


async def test_setup_probe_allows_localhost(monkeypatch):
    monkeypatch.setattr(setup_mod, "_sync_connect", lambda h, p: None)
    res = await setup_mod._probe("127.0.0.1:8080", lan_only=True)
    assert res["ok"] is True


async def test_probe_without_lan_only_is_unrestricted(monkeypatch):
    # The authenticated settings probe stays permissive (admin may
    # point at a remote dashcam over VPN with a public-resolving name).
    calls = []
    monkeypatch.setattr(setup_mod, "_sync_connect",
                        lambda h, p: calls.append((h, p)))
    res = await setup_mod._probe("93.184.216.34")
    assert res["ok"] is True
    assert calls == [("93.184.216.34", 80)]


async def test_setup_probe_rejects_unresolvable_host(monkeypatch):
    monkeypatch.setattr(setup_mod, "_sync_connect",
                        lambda h, p: (_ for _ in ()).throw(AssertionError("no connect")))
    res = await setup_mod._probe("no-such-host.invalid", lan_only=True)
    assert res["ok"] is False


# ---- info leak: scan must not return arbitrary filenames ----

def test_scan_does_not_leak_skipped_filenames(tmp_path, monkeypatch):
    """The scan response used to include every non-matching filename
    under the scanned root — an authenticated directory-listing
    primitive for any readable path. It must report counts only."""
    from web.routers import imports as imports_router

    class _Item:
        def __init__(self, basename, size):
            self.basename = basename
            self.size_bytes = size

    class _Manifest:
        items = [_Item("2026_0101_080000_0001F.MP4", 10)]
        total_bytes = 10
        skipped = [
            {"name": "id_rsa", "reason": "not_recognised"},
            {"name": "secret-budget.xlsx", "reason": "not_recognised"},
        ]

    monkeypatch.setattr(imports_router.importer, "scan_source",
                        lambda root: _Manifest())
    monkeypatch.setattr(imports_router.importer, "present_in_archive",
                        lambda snap, sizes: set())
    monkeypatch.setattr(imports_router.importer, "is_cross_volume",
                        lambda a, b: False)
    monkeypatch.setattr(imports_router.importer, "scan_item_dict",
                        lambda it: {"basename": it.basename})
    monkeypatch.setattr(imports_router.os.path, "isdir", lambda p: True)

    from types import SimpleNamespace
    snap = SimpleNamespace(import_path="/anything", recordings="/rec")
    monkeypatch.setattr(imports_router, "_snap", lambda req: snap)

    body = imports_router.scan(request=None, body=imports_router._PathBody(path="/etc"))

    blob = str(body)
    assert "id_rsa" not in blob and "secret-budget" not in blob, \
        "scan leaked arbitrary filenames"
    assert body["skipped_count"] == 2
