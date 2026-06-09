"""Tests for the export-job filmstrip preview service (ffmpeg mocked)."""
from __future__ import annotations

import os
from pathlib import Path

from web.services import export_preview


def test_preview_path_under_cache_dir(tmp_path: Path):
    sp = export_preview.preview_path(str(tmp_path), 42)
    assert sp.endswith(os.path.join(".export_previews", "42.jpg"))
    assert os.path.isdir(os.path.join(str(tmp_path), ".export_previews"))


def test_preview_timestamps_even_midpoints():
    ts = export_preview.preview_timestamps(100.0, n=10)
    assert ts == [5.0, 15.0, 25.0, 35.0, 45.0, 55.0, 65.0, 75.0, 85.0, 95.0]


def test_preview_timestamps_degrades_for_unknown_duration():
    assert export_preview.preview_timestamps(0.0) == [0.0]
    assert export_preview.preview_timestamps(None) == [0.0]


async def test_ensure_none_when_ffmpeg_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(export_preview.shutil, "which", lambda _n: None)
    out = tmp_path / "out.mp4"
    out.write_bytes(b"\x00")
    assert await export_preview.ensure_export_preview(
        str(tmp_path), 1, str(out), 60.0) is None


async def test_ensure_none_when_output_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(export_preview.shutil, "which", lambda _n: "/usr/bin/ffmpeg")
    assert await export_preview.ensure_export_preview(
        str(tmp_path), 1, str(tmp_path / "nope.mp4"), 60.0) is None


async def test_ensure_cache_hit_skips_generation(tmp_path: Path, monkeypatch):
    sp = export_preview.preview_path(str(tmp_path), 7)
    Path(sp).write_bytes(b"\xff\xd8\xff\xd9")  # pre-seeded sprite

    async def _boom(*a, **k):
        raise AssertionError("should not generate on cache hit")

    monkeypatch.setattr(export_preview.filmstrip, "generate_sprite_at", _boom)
    got = await export_preview.ensure_export_preview(
        str(tmp_path), 7, str(tmp_path / "out.mp4"), 60.0)
    assert got == sp


async def test_ensure_generates_and_returns_path(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(export_preview.shutil, "which", lambda _n: "/usr/bin/ffmpeg")
    out = tmp_path / "out.mp4"
    out.write_bytes(b"\x00")

    async def fake_gen(ffmpeg, video_path, sprite, timestamps):
        Path(sprite).write_bytes(b"\xff\xd8\xff\xd9")
        assert len(timestamps) == export_preview.N_FRAMES
        return True

    monkeypatch.setattr(export_preview.filmstrip, "generate_sprite_at", fake_gen)
    got = await export_preview.ensure_export_preview(
        str(tmp_path), 9, str(out), 100.0)
    assert got == export_preview.preview_path(str(tmp_path), 9)
    assert os.path.getsize(got) > 0
