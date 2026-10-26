from examproctor_service import facegate
from examproctor_service.analysis.faces import Face, FrameResult

ME = [1.0, 0.0, 0.0]
SOMEONE_ELSE = [0.0, 1.0, 0.0]


def frame(yaw=0.0, embedding=ME, faces=1, px=160, brightness=120.0, sharpness=80.0) -> FrameResult:
    return FrameResult(
        faces=[Face((0, 0, px, px), 0.95, yaw) for _ in range(faces)],
        brightness=brightness,
        contrast=40.0,
        sharpness=sharpness,
        embedding=embedding if faces else None,
        largest_face_px=px if faces else 0,
    )


def run(frames, reference=ME, challenge="left", now=1000.0):
    state = facegate.new_state(now) | {"challenge": challenge}
    reasons = []
    for f in frames:
        state, reason = facegate.step(state, f, reference, now)
        reasons.append(reason)
    return state, reasons


def turned(challenge):
    return frame(yaw=0.5 * facegate.YAW_SIGN[challenge], embedding=None)


def test_frontal_frames_then_turn_then_look_back_passes():
    state, reasons = run([frame(), frame(), frame(), turned("left"), frame()])

    assert state["stage"] == "passed"
    assert reasons == [None] * 5
    assert state["similarity"] == 1.0


def test_each_stage_tells_the_student_what_to_do():
    state, _ = run([frame()])
    assert facegate.instruction(state) == "hold_still"
    state, _ = run([frame()] * 3, challenge="right")
    assert facegate.instruction(state) == "turn_right"
    state, _ = run([frame()] * 3 + [turned("right")], challenge="right")
    assert facegate.instruction(state) == "look_back"


def test_a_different_person_never_reaches_the_challenge():
    state, reasons = run([frame(embedding=SOMEONE_ELSE)] * 5)

    assert state["stage"] == "frontal"
    assert reasons == ["not_same_person"] * 5
    assert state["similarity"] == 0.0


def test_photo_that_cannot_turn_stays_in_the_turn_stage():
    state, reasons = run([frame()] * 6)

    assert state["stage"] == "turn"
    assert reasons[3:] == ["turn_head"] * 3


def test_turning_the_wrong_way_does_not_count():
    state, reasons = run([frame()] * 3 + [turned("right")], challenge="left")

    assert state["stage"] == "turn"
    assert reasons[-1] == "turn_other_way"


def test_swapping_faces_after_the_turn_restarts():
    state, reasons = run([frame()] * 3 + [turned("left"), frame(embedding=SOMEONE_ELSE)])

    assert state["stage"] == "frontal"
    assert reasons[-1] == "not_same_person"


def test_losing_the_face_mid_turn_restarts():
    state, reasons = run([frame()] * 3 + [frame(faces=0)])

    assert state["stage"] == "frontal"
    assert reasons[-1] == "no_face"


def test_looking_away_or_bad_frames_reset_the_frontal_count():
    state, reasons = run([frame(), frame(), frame(yaw=0.3), frame(), frame()])

    assert state["stage"] == "frontal" and state["good"] == 2
    assert reasons[2] == "look_at_camera"
    _, reasons = run([frame(faces=2), frame(px=60), frame(brightness=10)])
    assert reasons == ["multiple_faces", "face_too_small", "too_dark"]


def test_challenge_expires_and_restarts():
    state, _ = run([frame()] * 3)
    state, reason = facegate.step(state, turned(state["challenge"]), ME, 1000.0 + facegate.CHALLENGE_SECONDS + 1)

    assert state["stage"] == "frontal"
    assert reason == "look_at_camera"


def test_without_a_reference_liveness_is_still_required():
    state, _ = run([frame(embedding=None)] * 3 + [turned("left"), frame(embedding=None)], reference=None)

    assert state["stage"] == "passed"
    assert state["similarity"] is None


def test_passed_stays_passed():
    state, _ = run([frame(), frame(), frame(), turned("left"), frame()])
    state, reason = facegate.step(state, frame(faces=0), ME, 5000.0)

    assert state["stage"] == "passed" and reason is None
