"""Tests for config.py — _read_config / _write_config round-trip."""

import json
from pathlib import Path

import config


def test_write_then_read_roundtrip(tmp_path: Path, monkeypatch):
    """Write a config, read it back, expect equality."""
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(config, "CONFIG_PATH", str(cfg_path))

    payload = {"hotkey": "ctrl+alt+r", "model": "tiny", "language": "th"}
    config._write_config(payload)
    assert cfg_path.exists()

    loaded = config._read_config()
    assert loaded == payload


def test_read_missing_file_returns_empty(tmp_path: Path, monkeypatch):
    """No config file → returns {}, no crash."""
    cfg_path = tmp_path / "does_not_exist.json"
    monkeypatch.setattr(config, "CONFIG_PATH", str(cfg_path))
    assert config._read_config() == {}


def test_read_corrupt_file_returns_empty(tmp_path: Path, monkeypatch):
    """Garbage JSON → returns {}, logs the error, no crash."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", str(cfg_path))
    assert config._read_config() == {}


def test_read_non_dict_returns_empty(tmp_path: Path, monkeypatch):
    """JSON list or scalar → returns {}, not the list."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(["a", "b"]), encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", str(cfg_path))
    assert config._read_config() == {}


def test_write_creates_dir(tmp_path: Path, monkeypatch):
    """CONFIG_DIR doesn't exist → _write_config creates it."""
    sub = tmp_path / "nested" / "dir"
    cfg_path = sub / "config.json"
    monkeypatch.setattr(config, "CONFIG_DIR", str(sub))
    monkeypatch.setattr(config, "CONFIG_PATH", str(cfg_path))

    config._write_config({"k": "v"})
    assert sub.exists()
    assert cfg_path.exists()
