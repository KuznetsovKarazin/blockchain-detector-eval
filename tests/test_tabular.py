import numpy as np
import pytest

from bal.models.tabular import TorchClassifier


@pytest.mark.parametrize("kind", ["mlp", "kan"])
@pytest.mark.parametrize("prep", ["robust", "quantile"])
def test_torch_classifier_learns_and_chunks(kind, prep):
    rng = np.random.default_rng(0)
    X = rng.standard_t(2, size=(1500, 6)).astype(np.float32)     # heavy tails
    y = (X[:, 0] + 0.5 * X[:, 1] > 0.5).astype(int)
    m = TorchClassifier(kind, hidden=(8,), seed=0, epochs=30, prep=prep).fit(X, y)
    s_full = m.predict_score(X)
    s_chunk = m.predict_score(X, chunk=100)
    assert np.allclose(s_full, s_chunk, atol=1e-6)
    assert ((s_full > 0.5) == y).mean() > 0.85
