# ExamProctor to-do

Open items as of 2026-10-26. Code, tests and HawkScan are current on `main`; everything below
needs a person, a host or a decision.

## Before the face gate is used in real exams

- [ ] **Real-face test of the head turn.** Have one person sit the staging quiz on agiledev and
      follow "turn your head to your left / right". The direction is set from camera geometry,
      not tested on a real face. If the turn does not register, flip `YAW_SIGN` in
      `service/examproctor_service/facegate.py`.
- [ ] **Gate C fairness evaluation.** Run `service/examproctor_service/evaluate.py` on OUK's own
      admission photos. A false non-match now blocks a student until an invigilator overrides,
      so identity matching must not be enabled for real exams until accuracy across groups is
      confirmed.
- [ ] **Invigilator cover.** Every identity-check exam needs an invigilator watching the live wall,
      so students held at the face check can be let in ("Let in without face check").
- [ ] **Know the limit.** The head-turn liveness check stops photos and replayed videos, not a
      skilled deepfake or a live accomplice.

## Gate D: load

- [ ] **Dedicated host for the load test.** About 16 vCPU / 32 GB for the service, AI workers capped
      or on their own host, and the simulator on a second machine on the same network.
- [ ] **Rerun 1,000 / 3,000 / 5,000 candidates** there. Targets: API p95 < 300 ms, uploads >= 99 %,
      capture-to-flag on the live wall p95 < 15 s. See `docs/loadtest/README.md` (agiledev missed
      at 500 candidates on a shared 4 vCPU host; bandwidth is not the limit).

## agiledev cleanup

- [ ] **Delete the synthetic load-test data** from the service database and object store.
- [ ] **Remove the temporary passwordless sudo** for `wanyoike` once server work is finished.

## Go-live sign-off (people)

- [ ] Pilot sign-off (`docs/pilot-kit.md`).
- [ ] DPIA approval (`docs/dpia-draft.md`).
- [ ] Remaining items in `docs/go-live-checklist.md`.

## Local

- [ ] Stop the local staging stack when not needed: `make loadtest-down`.
