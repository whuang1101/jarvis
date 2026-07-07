from __future__ import annotations

from jarvis import config, doctor


def test_run_diagnostics_returns_valid_checks():
    checks = doctor.run_diagnostics()

    assert checks
    for check in checks:
        assert isinstance(check, doctor.Check)
        assert check.status in {"ok", "warn", "fail"}


def test_azure_credentials_check_reacts_to_env(monkeypatch):
    for key in config._REQUIRED:
        monkeypatch.setenv(key, "x")

    checks = doctor.run_diagnostics()
    azure_check = next(c for c in checks if c.name == "Azure credentials")
    assert azure_check.status == "ok"

    monkeypatch.delenv(config._REQUIRED[0], raising=False)

    checks = doctor.run_diagnostics()
    azure_check = next(c for c in checks if c.name == "Azure credentials")
    assert azure_check.status == "fail"
    assert config._REQUIRED[0] in azure_check.detail
