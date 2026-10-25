# Gate C: face model licence and fairness review

Owner sign-off is needed before identity flags count toward scores in production.

## Model decision (2026-10-25)

| Part | Choice | Licence | Why |
| --- | --- | --- | --- |
| Face detector | YuNet (OpenCV Model Zoo, 2023mar) | MIT | Small (230 KB), fast on CPU, gives 5 landmarks for alignment and head pose |
| Face recogniser | SFace (OpenCV Model Zoo, 2021dec) | Apache-2.0 | Licence allows institutional use; 128-d embeddings; about 10 ms per face on CPU |
| Runtime | OpenCV DNN, no TensorFlow | Apache-2.0 | DeepFace offers the same two models; calling OpenCV directly keeps the worker small |

Both model files are pinned by sha256 and the worker refuses to start if a file differs.

Lessons taken from the earlier OUK proctor prototype (DeepFace + Facenet): faces smaller than 112 px are not embedded (small crops produced both false rejections and a false match there); the service reports what it can see (match scores), never claims ground truth; human review decides.

Threshold: OpenCV's published SFace cosine threshold, 0.363. Identity mismatch is flagged only after two consecutive frames below it, as a severity-4 flag for review. It never blocks a student and never fails anyone.

## Identity anchor

1. **Admission photo** (default when present): OUK collects photos with consent at admission. Moodle holds them (ExamProctor → Reference photos; ZIP or CLI bulk import; web services for the admissions system). Each photo is checked once: one face, at least 112 px, bright and sharp enough.
2. **Live frame** captured in the pre-check, used only when no usable admission photo exists.

Privacy note: admission consent covers identity confirmation. Using the same photos to *evaluate* the model is a related but separate purpose; record it in the DPIA. The evaluation tool keeps everything on OUK servers and outputs aggregate rates only.

## How to run the evaluation (on an OUK server)

```
# photos.csv: path,person,group   (group optional, e.g. a reviewer-assigned skin-tone band)
python -m examproctor_service.evaluate --csv photos.csv --out gate-c-report.md
```

- With **one photo per student** (the admission store today) the report gives enrolment failure rates by group and the false match rate (different people accepted as the same).
- The false **non**-match rate (same person rejected) needs a second photo per person: use the live pre-check frames from the pilot (M8) with consenting volunteers.
- The tool also groups by lighting and face size automatically.

## Sign-off checklist

- [ ] OUK legal accepts the model licences and the training-data residual risk (`docs/licences.md`).
- [ ] DPIA records model evaluation as a purpose for admission photos.
- [ ] Report run on the admission store: enrolment failure and FMR by group reviewed.
- [ ] Pilot genuine-pair FNMR by group reviewed; no group clearly disadvantaged.
- [ ] Until signed: identity flags shown to reviewers as "unconfirmed", weight 0 in the score (setting to add in M5 admin UI).
