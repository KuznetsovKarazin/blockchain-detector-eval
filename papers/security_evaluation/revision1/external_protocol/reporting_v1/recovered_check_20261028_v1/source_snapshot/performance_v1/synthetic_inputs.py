"""Fictional in-memory survey inputs only; never loads source code or human keys."""
import numpy as np
import pandas as pd

POS = "source_reported_positive_pending_adjudication"


def fixture(N=8, n_per_class=4, classes=("reentrancy",), census=False):
    if N % 2 or n_per_class % 2 or N < n_per_class:
        raise ValueError("Synthetic fixture needs even population/sample sizes")
    records, sample, allocations, first, second, adjudicated = [], [], [], [], [], []
    for cls in classes:
        for i in range(N):
            records.append({"path": f"synthetic://file_{i:04d}", "class": cls,
                            "source_id": "synthetic_A" if i < N // 2 else "synthetic_B", "label_status": POS})
        for stratum, start in (("synthetic_A", 0), ("synthetic_B", N // 2)):
            nh = N // 2 if census else n_per_class // 2
            allocations.append({"source_id": stratum, "class": cls, "label_status": POS, "N_h": N // 2, "n_h": nh})
            ids = list(range(start, start + N // 2)) if census else np.linspace(start, start + N // 2 - 1, nh, dtype=int).tolist()
            for i in ids:
                case = f"fictional_{cls}_{i:04d}"
                value = "positive" if i % 3 == 0 else "negative"
                sample.append({"path": f"synthetic://file_{i:04d}", "class": cls, "source_id": stratum,
                               "label_status": POS, "case_id": case, "N_h": N // 2, "n_h": nh,
                               "design_weight": (N // 2) / nh, "inclusion_probability": nh / (N // 2)})
                base = {"case_id": case, "class": cls, "judgment_positive_negative_unknown": value,
                        "reviewed_utc": "SYNTHETIC_NOT_A_HUMAN_REVIEW", "reason": "fictional unit test"}
                first.append({**base, "reviewer_id": "SYNTHETIC_REVIEWER_A"})
                second.append({**base, "reviewer_id": "SYNTHETIC_REVIEWER_B"})
                adjudicated.append({"case_id": case, "class": cls, "reviewer_1_judgment": value,
                                    "reviewer_2_judgment": value, "adjudicated_judgment": value,
                                    "adjudicator_id": "SYNTHETIC_ADJUDICATOR", "adjudication_reason": "fictional unit test",
                                    "adjudicated_utc": "SYNTHETIC_NOT_A_HUMAN_REVIEW"})
    scores = pd.DataFrame({"path": [f"synthetic://file_{i:04d}" for i in range(N)],
                           "class": classes[0], "score": [(N - i) / N for i in range(N)], "status": "ok"})
    return tuple(pd.DataFrame(x) for x in (records, sample, allocations, first, second, adjudicated)) + (scores,)
