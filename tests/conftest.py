import socket
from pathlib import Path

import pytest

from research.config import deep_merge
from research.pipeline import create_run, execute

ROOT = Path(__file__).resolve().parents[1]
SMOKE_CONFIG = ROOT / "configs" / "smoke.yaml"
SMOKE_SNAPSHOT = ROOT / "data" / "raw" / "smoke"
FAST = {"inference": {"bootstrap_reps": 300}}


def _refuse(*args, **kwargs):
    raise RuntimeError("network access attempted during an offline test")


@pytest.fixture
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)


def run_smoke(tmp: Path, overrides: dict | None = None, only=None):
    ctx = create_run(ROOT, SMOKE_CONFIG, deep_merge(FAST, overrides or {}), runs_dir=tmp / "runs",
                     processed_root=tmp / "processed", quiet=True)
    return ctx, execute(ctx, only=only)


@pytest.fixture(scope="session")
def smoke_run(tmp_path_factory):
    """One complete offline run shared by read-only integration tests."""
    tmp = tmp_path_factory.mktemp("smoke")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(socket.socket, "connect", _refuse)
        patch.setattr(socket, "create_connection", _refuse)
        ctx, code = run_smoke(tmp)
    assert code == 0, ctx.manifest["stages"]
    return ctx
