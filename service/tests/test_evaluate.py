import numpy as np

from examproctor_service.evaluate import Sample, evaluate, to_markdown


def unit(*v):
    a = np.asarray(v, np.float32)
    return a / np.linalg.norm(a)


def test_rates_per_group_from_synthetic_embeddings():
    samples = [
        Sample("ann", ["all", "group:A"], unit(1, 0, 0), None),
        Sample("ann", ["all", "group:A"], unit(0.95, 0.05, 0), None),  # genuine, matches
        Sample("bob", ["all", "group:B"], unit(0, 1, 0), None),
        Sample("bob", ["all", "group:B"], unit(0.2, 0.1, 1), None),  # genuine, rejected -> FNMR for B
        Sample("cat", ["all", "group:B"], None, "no_face"),
    ]

    report = evaluate(samples, threshold=0.5, impostor_pairs=2000)

    assert report.enrolment_failures["group:B"].rate == 1 / 3
    assert report.fnmr["group:A"].rate == 0.0
    assert report.fnmr["group:B"].rate == 1.0
    assert report.fmr["all"].trials > 0
    assert report.failure_reasons == {"no_face": 1}
    md = to_markdown(report)
    assert "| group:B |" in md and "Enrolment failure reasons" in md
