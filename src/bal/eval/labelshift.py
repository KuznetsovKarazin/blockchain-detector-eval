"""
Label-shift (prior-shift) correction without target labels (T2, HT.3).

Elliptic's test period contains the shutdown of a large dark market after time
step 42: the illicit share falls from ~11% in training to well under 1% in some
steps. Under pure label shift p(x|y) is unchanged and only p(y) moves, so the
classifier's posterior can be re-weighted once the new prior is estimated.

* `em_prior` — Saerens, Latinne & Decaestecker (2002), EM on the unlabelled
  target scores; needs calibrated probabilities.
* `bbse_prior` — Lipton, Wang & Smola (2018), black-box shift estimation from
  the validation confusion matrix of the thresholded classifier.
* `adjust_posterior` — Bayes re-weighting p'(1|x) ∝ p(1|x) * pi_t / pi_s.

Calibration (`fit_platt`) is fitted on the validation steps only.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression


def fit_platt(s_val, y_val):
    lr = LogisticRegression(C=1e6, max_iter=1000)
    z = np.log(np.clip(s_val, 1e-6, 1 - 1e-6) / np.clip(1 - s_val, 1e-6, 1))
    lr.fit(z.reshape(-1, 1), y_val)

    def f(s):
        zz = np.log(np.clip(s, 1e-6, 1 - 1e-6) / np.clip(1 - s, 1e-6, 1))
        return lr.predict_proba(zz.reshape(-1, 1))[:, 1]
    return f


def adjust_posterior(p, pi_src, pi_tgt):
    a = p * (pi_tgt / pi_src)
    b = (1 - p) * ((1 - pi_tgt) / (1 - pi_src))
    return a / np.clip(a + b, 1e-12, None)


def em_prior(p, pi_src, n_iter: int = 100, tol: float = 1e-6):
    pi = pi_src
    for _ in range(n_iter):
        q = adjust_posterior(p, pi_src, pi)
        new = float(np.clip(q.mean(), 1e-6, 1 - 1e-6))
        if abs(new - pi) < tol:
            break
        pi = new
    return pi


def bbse_prior(yhat_tgt, y_val, yhat_val):
    """Binary BBSE: C[i, j] = P_val(yhat=i, y=j), mu_i = P_tgt(yhat=i).

    Solving C w = mu gives importance weights w_j = q(y=j) / p(y=j); the target
    prior is q_j = w_j * p_j with p_j the validation class marginals."""
    C = np.zeros((2, 2))
    for a in (0, 1):
        for b in (0, 1):
            C[a, b] = np.mean((yhat_val == a) & (y_val == b))
    mu = np.array([np.mean(yhat_tgt == 0), np.mean(yhat_tgt == 1)])
    try:
        w = np.linalg.solve(C, mu)
    except np.linalg.LinAlgError:
        return float("nan")
    p_src = C.sum(axis=0)
    q = np.clip(w, 0, None) * p_src
    return float(np.clip(q[1] / max(q.sum(), 1e-12), 1e-6, 1 - 1e-6))
