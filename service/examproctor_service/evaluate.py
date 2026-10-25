"""Gate C evaluation: accuracy and fairness of identity matching on OUK's own photos.

Runs on OUK infrastructure against the admission photo store; writes aggregate numbers only (no
images, names or ids leave the machine).

Input: a CSV with columns `path,person,group` (group optional, e.g. a self-reported or reviewer
-assigned skin-tone band, or "lighting:low"). With one photo per person (admissions today) the tool
measures enrolment failures and the false match rate; genuine pairs (false non-match rate) need a
second photo per person, e.g. the live pre-check frame from pilot sittings.

    python -m examproctor_service.evaluate --csv photos.csv --out report.md [--impostor-pairs 200000]
"""

import argparse
import csv
import itertools
import json
import random
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .analysis.faces import SFACE_COSINE_THRESHOLD, FaceEngine, FrameResult
from .refphotos import validate

MODELS = Path(__file__).resolve().parents[1] / "models"


@dataclass
class Sample:
    person: str
    groups: list[str]
    embedding: np.ndarray | None
    reason: str | None


@dataclass
class Rates:
    trials: int = 0
    errors: int = 0

    @property
    def rate(self) -> float | None:
        return self.errors / self.trials if self.trials else None


@dataclass
class Report:
    threshold: float
    photos: int
    enrolment_failures: dict[str, Rates] = field(default_factory=lambda: defaultdict(Rates))
    failure_reasons: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    fnmr: dict[str, Rates] = field(default_factory=lambda: defaultdict(Rates))
    fmr: dict[str, Rates] = field(default_factory=lambda: defaultdict(Rates))
    genuine_scores: list[float] = field(default_factory=list)
    impostor_scores: list[float] = field(default_factory=list)


def auto_groups(result: FrameResult) -> list[str]:
    """Groups the tool can derive itself: lighting and face size."""
    light = "low" if result.brightness < 80 else "high" if result.brightness > 180 else "normal"
    size = "small" if result.largest_face_px < 160 else "large"
    return [f"lighting:{light}", f"face:{size}"]


def load(rows: list[dict[str, str]], analyse: Callable[[bytes], FrameResult]) -> list[Sample]:
    samples = []
    for row in rows:
        result = analyse(Path(row["path"]).read_bytes())
        reason = validate(result)
        groups = ["all", *auto_groups(result)] + ([f"group:{row['group']}"] if row.get("group") else [])
        emb = np.asarray(result.embedding, np.float32) if result.embedding and not reason else None
        if emb is not None:
            emb /= np.linalg.norm(emb) or 1.0
        samples.append(Sample(row["person"], groups, emb, reason))
    return samples


def evaluate(
    samples: list[Sample], threshold: float = SFACE_COSINE_THRESHOLD, impostor_pairs: int = 200_000, seed: int = 7
) -> Report:
    report = Report(threshold=threshold, photos=len(samples))
    for s in samples:
        for g in s.groups:
            report.enrolment_failures[g].trials += 1
            report.enrolment_failures[g].errors += s.reason is not None
        if s.reason:
            report.failure_reasons[s.reason] += 1
    usable = [s for s in samples if s.embedding is not None]
    by_person = defaultdict(list)
    for s in usable:
        by_person[s.person].append(s)
    for photos in by_person.values():
        for a, b in itertools.combinations(photos, 2):
            score = float(a.embedding @ b.embedding)
            report.genuine_scores.append(score)
            for g in set(a.groups) & set(b.groups):
                report.fnmr[g].trials += 1
                report.fnmr[g].errors += score < threshold
    rng = random.Random(seed)  # noqa: S311 - reproducible sampling, not security
    if len(by_person) > 1:
        for _ in range(impostor_pairs):
            a, b = rng.sample(usable, 2)
            if a.person == b.person:
                continue
            score = float(a.embedding @ b.embedding)
            report.impostor_scores.append(score)
            for g in set(a.groups) & set(b.groups):
                report.fmr[g].trials += 1
                report.fmr[g].errors += score >= threshold
    return report


def fmt(r: Rates) -> str:
    return "n/a" if r.rate is None else f"{r.rate:.2%} ({r.errors}/{r.trials})"


def to_markdown(report: Report) -> str:
    groups = sorted(set(report.enrolment_failures) | set(report.fmr) | set(report.fnmr), key=lambda g: (g != "all", g))
    lines = [
        "# ExamProctor identity matching: evaluation report",
        "",
        f"Model: YuNet + SFace. Threshold (cosine): {report.threshold}. Photos: {report.photos}.",
        "Aggregates only. FMR = different people accepted as the same; FNMR = same person rejected.",
        "",
        "| Group | Enrolment failures | FMR | FNMR |",
        "| --- | --- | --- | --- |",
    ]
    for g in groups:
        lines.append(f"| {g} | {fmt(report.enrolment_failures[g])} | {fmt(report.fmr[g])} | {fmt(report.fnmr[g])} |")
    lines += ["", "Enrolment failure reasons: " + json.dumps(dict(report.failure_reasons))]
    for name, scores in (("genuine", report.genuine_scores), ("impostor", report.impostor_scores)):
        if scores:
            p = np.percentile(scores, [1, 5, 50, 95, 99]).round(3).tolist()
            lines.append(f"{name} similarity percentiles 1/5/50/95/99: {p}")
    lines += [
        "",
        "Gate C reading guide: compare each group's rates with `all`. A group whose FNMR or enrolment",
        "failure rate is clearly higher is disadvantaged; do not enable identity flags for production until",
        "that is fixed (threshold, capture guidance, or model).",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--threshold", type=float, default=SFACE_COSINE_THRESHOLD)
    parser.add_argument("--impostor-pairs", type=int, default=200_000)
    args = parser.parse_args()
    with args.csv.open() as fh:
        rows = list(csv.DictReader(fh))
    engine = FaceEngine(MODELS)
    report = evaluate(load(rows, engine.analyse), args.threshold, args.impostor_pairs)
    args.out.write_text(to_markdown(report))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
