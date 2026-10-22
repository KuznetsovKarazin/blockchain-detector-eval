import numpy as np

from bal.eval.labelshift import adjust_posterior, bbse_prior, em_prior
from bal.eval.metrics import threshold_at_fpr, threshold_at_val_f1


def _calibrated_scores(pi, n, rng):
    """Scores that are exact posteriors for two unit-variance Gaussians at prior 0.5."""
    y = (rng.random(n) < pi).astype(int)
    x = rng.normal(loc=np.where(y == 1, 1.5, -1.5))
    p = 1 / (1 + np.exp(-3.0 * x))          # log-likelihood ratio of N(1.5,1) vs N(-1.5,1)
    return y, p


def test_em_recovers_shifted_prior():
    rng = np.random.default_rng(0)
    _, p = _calibrated_scores(0.05, 40000, rng)
    assert abs(em_prior(p, 0.5) - 0.05) < 0.01


def test_bbse_recovers_shifted_prior():
    rng = np.random.default_rng(1)
    yv, pv = _calibrated_scores(0.5, 20000, rng)
    _, pt = _calibrated_scores(0.1, 20000, rng)
    est = bbse_prior((pt >= 0.5).astype(int), yv, (pv >= 0.5).astype(int))
    assert abs(est - 0.1) < 0.02


def test_adjust_posterior_identity_and_monotone():
    p = np.linspace(0.01, 0.99, 50)
    assert np.allclose(adjust_posterior(p, 0.3, 0.3), p)
    q = adjust_posterior(p, 0.3, 0.05)
    assert np.all(np.diff(q) > 0) and np.all(q < p)


def test_threshold_at_fpr():
    s = np.arange(10000) / 10000
    thr = threshold_at_fpr(s, 0.01)
    assert abs((s > thr).mean() - 0.01) < 1e-3


def test_threshold_at_val_f1_separable():
    y = np.r_[np.zeros(50), np.ones(50)]
    s = np.r_[np.linspace(0, 0.4, 50), np.linspace(0.6, 1, 50)]
    thr = threshold_at_val_f1(y, s)
    assert 0.4 < thr <= 0.6


def test_budget_threshold_never_exceeds_budget_with_ties():
    from bal.eval.alarm import threshold_at_budget
    s = np.r_[np.full(13, 9.8), np.linspace(0, 5, 3916)]      # 13 tied at the cap, n = 3929
    thr, achieved = threshold_at_budget(s, 0.001)
    assert achieved <= 0.001 and (s >= thr).mean() == achieved
    assert thr > 9.8                                            # the tied block is not split
    thr, achieved = threshold_at_budget(np.arange(1000.0), 0.01)
    assert achieved == 0.01 and thr == 990.0
    thr, achieved = threshold_at_budget(np.arange(421.0), 0.001)   # budget below resolution 1/421
    assert achieved == 0.0 and thr > 420


def test_alarm_accounting_separates_released_value():
    from bal.eval.alarm import alarm_accounting
    ts = np.array([0, 10, 10, 10, 20, 700])
    label = np.array([0, 1, 1, 1, 1, 1])
    usd = np.array([5.0, 10, 10, 10, 10, 60])
    alarm = np.array([False, False, True, False, False, True])
    r = alarm_accounting(ts, label, usd, alarm)
    assert r["usd_share_before_alarm"] == 0.1
    assert r["usd_share_through_alarm_event"] == 0.2
    assert r["usd_share_through_alarm_block"] == 0.3          # same timestamp as the alarm
    assert r["usd_share_after_delay_0s"] == 0.7
    assert r["usd_share_after_delay_600s"] == 0.6


def test_causal_usd_is_prefix_invariant():
    import pandas as pd
    from bal.data.xchain import causal_usd
    rng = np.random.default_rng(0)
    n = 400
    ev = pd.DataFrame({"ts": np.sort(rng.integers(0, 30 * 86400, n)),
                       "token": rng.choice(["a", "b"], n), "amount": rng.lognormal(3, 1, n),
                       "matched": rng.random(n) > 0.2})
    ev["value_usd_dataset"] = np.where(ev.matched, ev.amount * rng.normal(2, 0.1, n), np.nan)
    full, _ = causal_usd(ev)
    for k in (50, 200, 399):
        part, _ = causal_usd(ev.iloc[:k])
        assert np.allclose(full[:k], part)


def test_prior_correction_with_fixed_threshold_can_fail_under_exact_label_shift():
    """Documented limitation of T2: an oracle prior is not an F1 upper bound."""
    from bal.eval.labelshift import adjust_posterior
    from bal.eval.metrics import threshold_at_val_f1
    rng = np.random.default_rng(0)

    def sample(n, pi):
        y = (rng.random(n) < pi).astype(int)
        s = np.where(y == 1, rng.normal(1.0, 1.0, n), rng.normal(0.0, 1.0, n))
        return y, s

    def post(s, pi):           # exact posterior for N(1,1) vs N(0,1)
        lr = np.exp(s - 0.5)
        return pi * lr / (pi * lr + 1 - pi)

    ys, ss = sample(20000, 0.5)
    yt, st = sample(20000, 0.1)
    thr = threshold_at_val_f1(ys, post(ss, 0.5))
    p_corr = adjust_posterior(post(st, 0.5), 0.5, 0.1)          # oracle prior, exact model
    f1 = lambda yy, yh: 2 * (yh & (yy == 1)).sum() / max(1, yh.sum() + (yy == 1).sum())
    f1_none = f1(yt, post(st, 0.5) >= thr)
    f1_oracle = f1(yt, p_corr >= thr)
    assert f1_oracle < f1_none          # correction + fixed threshold makes F1 worse here


def test_asof_prices_are_available_and_ignore_matching():
    """Every price used for a release closed at or before it; valuation does not read `matched`."""
    from pathlib import Path
    import pytest
    from bal.data.prices import price_asof
    from bal.data.xchain import load_bridge
    if not Path("data/raw/XChainWatcher/token-price-data").exists():
        pytest.skip("XChainWatcher data not present")
    ev = load_bridge("ronin").events
    priced = ev.price_time_s >= 0
    assert priced.all()
    assert (ev.price_time_s <= ev.ts).all()
    p1, _, _ = price_asof("ronin", ev.token.to_numpy(), ev.ts.to_numpy())
    flipped = ev.assign(matched=~ev.matched)
    p2, _, _ = price_asof("ronin", flipped.token.to_numpy(), flipped.ts.to_numpy())
    assert np.array_equal(p1, p2)


def test_price_candles_snap_to_grid(tmp_path):
    from bal.data.prices import load_series
    f = tmp_path / "x-1.csv"
    # 2022-03-18 16:00 UTC open, written as in the source files (rounded, comma decimals)
    f.write_text("timeOpen;timeClose;timeHigh;timeLow;priceOpen;priceHigh;priceLow;priceClose;volume\n"
                 "1,64762E+12;1,64771E+12;0;0;1;1;1;2,5;1\n")
    s = load_series(f)
    assert s.open_s[0] == 1647619200 and s.close_s[0] == 1647619200 + 86400 and s.price[0] == 2.5


def test_top_k_with_ties_is_order_free():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("c4", Path("scripts/c4_slither_vs_ml.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    y = np.array([1, 0, 1, 0, 0, 1])
    s = np.array([0.9, 0.5, 0.5, 0.5, 0.5, 0.1])        # k = 2: one of four tied files
    p, r, lo, hi = m.at_budget(y, s, 2)
    assert (lo, hi) == (1, 2) and np.isclose(p, (1 + 0.25) / 2)
    p2, *_ = m.at_budget(y[::-1], s[::-1], 2)
    assert np.isclose(p, p2)


def test_code_state_covers_files_in_new_directories(tmp_path, monkeypatch):
    """Changing a file inside an untracked directory must change the code digest."""
    import subprocess
    from bal.utils import repro
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-qm", "init"], check=True)
    monkeypatch.setattr(repro, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(repro, "CODE_PATHS", ("scripts",))
    new = tmp_path / "scripts" / "tools" / "new_method.py"
    new.parent.mkdir()
    new.write_text("METHOD = 1\n")
    s1 = repro.git_code_state()
    new.write_text("METHOD = 999\n")
    s2 = repro.git_code_state()
    assert "scripts/tools/new_method.py" in s1["dirty_files"]
    assert s1["diff_sha256"] != s2["diff_sha256"]


def test_price_asof_uses_last_closed_candle(tmp_path):
    from bal.data.prices import price_asof
    d = tmp_path / "ronin-bridge" / "bitget"
    d.mkdir(parents=True)
    # two daily candles closing 2022-03-19 and 2022-03-20 16:00 UTC, newest first as in the source
    (d / "usdc-1.csv").write_text(
        "timeOpen;timeClose;timeHigh;timeLow;priceOpen;priceHigh;priceLow;priceClose;volume\n"
        "1,64771E+12;1,64779E+12;0;0;1;1;1;0,99;1\n"
        "1,64762E+12;1,64771E+12;0;0;1;1;1;1,01;1\n")
    usdc = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    c1, c2 = 1647705600, 1647792000
    ts = np.array([c1 - 1, c1, c2 - 1, c2 + 10, c2])
    tok = np.array([usdc, usdc, usdc, usdc, "0xunknown"])
    p, pt, dec = price_asof("ronin", tok, ts, root=tmp_path)
    assert np.isnan(p[0]) and pt[0] == -1
    assert list(p[1:4]) == [1.01, 1.01, 0.99] and list(pt[1:4]) == [c1, c1, c2]
    assert np.isnan(p[4]) and dec[4] == 0 and dec[1] == 6
    assert (pt[pt >= 0] <= ts[pt >= 0]).all()


def test_tie_ranks_give_midrank_and_range():
    from bal.eval.metrics import tie_ranks
    mid, lo, hi = tie_ranks([0.9, 0.5, 0.5, 0.5, 0.1])
    assert list(lo) == [1, 2, 2, 2, 5] and list(hi) == [1, 4, 4, 4, 5]
    assert list(mid) == [1, 3, 3, 3, 5]
