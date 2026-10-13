from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from quantbt.studio.data import Settings, demo_bars, load_bars
from quantbt.studio.paper import replay, size_notional, statistics
from quantbt.studio.research import committee_gate, dated_news, execute, research
from quantbt.studio.review import ROLES, review
from quantbt.studio.store import Store

NOW = pd.Timestamp("2026-10-13T01:00:00Z")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"capital": float("nan")},
        {"risk_fraction": True},
        {"market": "../../other"},
        {"interval": "1m"},
        {"source": "url"},
        {"min_trades": 1.5},
    ],
)
def test_settings_reject_invalid_input(kwargs):
    with pytest.raises(ValueError):
        Settings(**kwargs)


def test_completed_bar_quality_and_hash(tmp_path):
    settings = Settings(source="cache")
    bars = demo_bars("1h", NOW.tz_localize(None))
    # A future, incomplete candle is never available to the strategy.
    future = bars.iloc[-1:].copy()
    future.index = pd.DatetimeIndex([NOW.tz_localize(None)])
    pd.concat([bars, future]).to_parquet(tmp_path / "BTC_1h.parquet")
    actual, manifest = load_bars(settings, tmp_path, NOW)
    assert len(actual) == len(bars) and manifest["fresh"] and not manifest["synthetic"]
    _, second = load_bars(settings, tmp_path, NOW)
    assert manifest["sha256"] == second["sha256"]
    bars.iloc[0, 4] += 1
    bars.to_parquet(tmp_path / "BTC_1h.parquet")
    assert load_bars(settings, tmp_path, NOW)[1]["sha256"] != manifest["sha256"]


def test_cached_synthetic_provenance_cannot_become_market_data(tmp_path):
    bars = demo_bars("1h", NOW.tz_localize(None))
    bars.attrs["quantbt_provenance"] = {"source": "generated", "synthetic": True}
    bars.to_parquet(tmp_path / "BTC_1h.parquet")
    _, manifest = load_bars(Settings(source="cache"), tmp_path, NOW)
    assert manifest["synthetic"] and not manifest["provenance_recorded"]
    bars.attrs["quantbt_provenance"] = {
        "source": "binance_static_klines",
        "synthetic": False,
        "symbol": "BTCUSDT",
        "retrieved_at": NOW.isoformat(),
    }
    bars.to_parquet(tmp_path / "BTC_1h.parquet")
    assert load_bars(Settings(source="cache"), tmp_path, NOW)[1]["provenance_recorded"]


@pytest.mark.parametrize("issue", ["gap", "duplicate", "nan", "geometry", "volume"])
def test_bad_market_data_fails_closed(tmp_path, issue):
    bars = demo_bars("1h", NOW.tz_localize(None))
    if issue == "gap":
        bars = bars.drop(bars.index[5])
    elif issue == "duplicate":
        bars = pd.concat([bars.iloc[:6], bars.iloc[5:]])
    elif issue == "nan":
        bars.iloc[5, 1] = np.nan
    elif issue == "geometry":
        bars.iloc[5, 1] = 1
    else:
        bars.iloc[5, 4] = 0
    bars.to_parquet(tmp_path / "BTC_1h.parquet")
    with pytest.raises(ValueError):
        load_bars(Settings(source="cache"), tmp_path, NOW)


def test_stale_and_four_hour_inputs(tmp_path):
    bars = demo_bars("1h", NOW.tz_localize(None), n=3000)
    bars.to_parquet(tmp_path / "BTC_1h.parquet")
    actual, _manifest = load_bars(Settings(source="cache", interval="4h"), tmp_path, NOW)
    assert (actual.index.hour % 4 == 0).all() and len(actual) >= 600
    assert not load_bars(Settings(source="cache"), tmp_path, NOW + pd.Timedelta(days=4))[1]["fresh"]


def test_paper_fills_next_open_and_reconciles_costs():
    idx = pd.date_range("2026-01-01", periods=4)
    bars = pd.DataFrame(
        {
            "Open": [100, 110, 115, 120],
            "High": [100, 116, 120, 121],
            "Low": [100, 109, 114, 119],
            "Close": [100, 115, 119, 120],
        },
        index=idx,
    )
    settings = Settings(fee=0.001, slippage=0.001)
    result = replay(bars, pd.Series([1.0, 1.0, 0.0, 0.0], index=idx), settings)
    assert result.trades[0]["entry"] == pytest.approx(110 * 1.001)
    assert result.trades[0]["exit"] == pytest.approx(120 * 0.999)
    assert result.quantity == 0
    assert result.equity.iloc[-1] == pytest.approx(
        settings.capital + sum(t["pnl"] for t in result.trades)
    )
    assert result.fees > 0
    expensive = replay(
        bars, pd.Series([1.0, 1.0, 0.0, 0.0], index=idx), replace(settings, fee=0.002)
    )
    assert expensive.equity.iloc[-1] < result.equity.iloc[-1]


def test_gap_stop_uses_actual_open_not_unreachable_stop():
    idx = pd.date_range("2026-01-01", periods=4)
    bars = pd.DataFrame(
        {
            "Open": [100, 100, 90, 90],
            "High": [101, 101, 91, 91],
            "Low": [99, 99, 89, 89],
            "Close": [100, 100, 90, 90],
        },
        index=idx,
    )
    result = replay(bars, pd.Series(1.0, index=idx), Settings(fee=0, slippage=0))
    assert result.trades[0]["reason"] == "gap stop" and result.trades[0]["exit"] == 90


def test_sizing_counts_costs_and_short_signals_stay_flat():
    s = Settings()
    notional = size_notional(s.capital, s)
    assert (
        notional * (s.stop_fraction + 2 * (s.fee + s.slippage))
        <= s.capital * s.risk_fraction + 1e-9
    )
    bars = demo_bars("1h", NOW.tz_localize(None))
    result = replay(bars, pd.Series(-1.0, index=bars.index), s)
    assert result.fees == 0 and result.equity.eq(s.capital).all()
    assert statistics(result, s.capital, 8760)["win_rate"] is None


def votes():
    return [{"role": role, "verdict": "APPROVE" if role != "news" else "ABSTAIN"} for role in ROLES]


def test_three_votes_cannot_override_risk_or_duplicate_roles():
    assert committee_gate(votes(), {"data": True})
    assert not committee_gate(votes(), {"data": False})
    wrong = votes()
    wrong[0]["verdict"] = "ABSTAIN"
    wrong[2]["verdict"] = "APPROVE"
    assert not committee_gate(wrong, {"data": True})
    assert not committee_gate([*votes(), votes()[0]], {"data": True})
    wrong = votes()
    wrong[2]["role"] = "invented"
    assert not committee_gate(wrong, {"data": True})


def test_news_enforces_knowledge_time(tmp_path):
    row = {
        "title": "Known event",
        "source_url": "https://example.com/event",
        "published_at": "2026-10-12T00:00:00Z",
        "known_at": "2026-10-12T01:00:00Z",
    }
    future = {**row, "known_at": "2026-10-14T01:00:00Z"}
    (tmp_path / "BTC_news.json").write_text(json.dumps([row, future]))
    assert dated_news(tmp_path, "BTC", NOW) == [row]
    (tmp_path / "BTC_news.json").write_text(json.dumps([{**row, "known_at": "2026-10-12"}]))
    with pytest.raises(ValueError, match="timezone"):
        dated_news(tmp_path, "BTC", NOW)


def test_missing_event_data_abstains_without_network():
    decision = review("news", {"news": [], "dataset_id": "d", "experiment_id": "e"}, "llm")
    assert decision["verdict"] == "ABSTAIN"


def test_llm_schema_and_evidence_are_enforced(monkeypatch):
    monkeypatch.setenv("QUANTBT_LLM_MODEL", "test-model")
    monkeypatch.setenv("QUANTBT_LLM_API_KEY", "test-key")
    decision = {
        "verdict": "APPROVE",
        "reason": "Measured evidence",
        "counterargument": "Regime changes",
        "evidence": ["d"],
    }

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit):
            return json.dumps(
                {"choices": [{"message": {"content": json.dumps(decision)}}]}
            ).encode()

    monkeypatch.setattr(
        "urllib.request.build_opener",
        lambda *args: SimpleNamespace(open=lambda *args, **kwargs: Response()),
    )
    packet = {"news": [], "dataset_id": "d", "experiment_id": "e"}
    assert review("quant", packet, "llm")["provider"] == "test-model"
    decision["evidence"] = ["fabricated"]
    with pytest.raises(ValueError, match="unknown evidence"):
        review("quant", packet, "llm")


def test_store_concurrent_events_restart_and_failure(tmp_path):
    path = tmp_path / "runs.sqlite"
    store = Store(path)
    run_id = store.create({})
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda n: store.event(run_id, "quant", "PROGRESS", {"n": n}), range(80)))
    events = store.events(run_id)
    assert len(events) == 80 and len({e["seq"] for e in events}) == 80
    reopened = Store(path)
    assert reopened.get(run_id)["status"] == "FAILED"
    assert reopened.events(run_id)[-1]["status"] == "FAILED"


@pytest.mark.parametrize("fee", [0.001, 0.01])
def test_full_research_produces_real_events_and_demo_veto(tmp_path, fee):
    store = Store(tmp_path / "runs.sqlite")
    settings = Settings(min_trades=1, fee=fee, slippage=fee)
    run_id = store.create(settings.to_dict())
    result = research(store, run_id, settings, tmp_path)
    assert len(result["trials"]) == 9 and len(result["reviews"]) == 4
    assert result["proposal"]["status"] == "DEMO ONLY"
    assert not result["proposal"]["checks"]["market_data"]
    assert "review_packet" in result and result["review_packet"]["evidence_ids"]
    assert result["proposal"]["notional"] == 0 and result["ledger"]["reconciled"]
    assert set(ROLES) <= {e["agent"] for e in store.events(run_id)}
    assert store.get(run_id)["status"] == "COMPLETED"


def test_worker_failure_stops_running_nodes(tmp_path):
    store = Store(tmp_path / "runs.sqlite")
    settings = Settings(source="cache")
    run_id = store.create(settings.to_dict())
    execute(store, run_id, settings, tmp_path)
    assert store.get(run_id)["status"] == "FAILED"
    data = [e for e in store.events(run_id) if e["agent"] == "data"]
    assert data[-1]["status"] == "FAILED"


def test_event_sink_failure_still_marks_run_failed(tmp_path, monkeypatch):
    store = Store(tmp_path / "runs.sqlite")
    settings = Settings()
    run_id = store.create(settings.to_dict())

    def fail(*args, **kwargs):
        raise RuntimeError("event sink unavailable")

    monkeypatch.setattr(store, "event", fail)
    with pytest.raises(RuntimeError):
        execute(store, run_id, settings, tmp_path)
    assert store.get(run_id)["status"] == "FAILED"
