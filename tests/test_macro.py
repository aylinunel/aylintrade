from __future__ import annotations

from aylintrade.config import MacroConfig
from aylintrade.macro import fetch_current_context, load_current_context


def test_current_macro_context_is_explicitly_not_backtest_eligible(monkeypatch, tmp_path) -> None:
    def fake_get(url: str, timeout: float = 30.0) -> bytes:
        series = url.split("id=")[-1]
        return f"observation_date,{series}\n2024-01-01,1\n2024-01-02,2\n".encode()

    monkeypatch.setattr("aylintrade.macro.http_get", fake_get)
    context = fetch_current_context(tmp_path, MacroConfig(series=("DGS2", "T10Y2Y")))
    assert context["status"] == "current_context_only"
    assert [series["id"] for series in context["series"]] == ["DGS2", "T10Y2Y"]
    assert all(series["eligibility"] == "current_context_only" for series in context["series"])
    assert (tmp_path / "macro_current.json").exists()


def test_missing_macro_cache_is_a_visible_empty_state(tmp_path) -> None:
    context = load_current_context(tmp_path, MacroConfig())
    assert context["status"] == "unavailable"
    assert context["series"] == []
