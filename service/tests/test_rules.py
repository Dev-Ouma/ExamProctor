from datetime import UTC, datetime, timedelta

from examproctor_service.analysis.rules import Frame, PageEvent, all_flags
from examproctor_service.analysis.score import compute

T0 = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)
REF = [1.0, 0.0, 0.0]
SAME = [0.9, 0.1, 0.0]
OTHER = [0.0, 1.0, 0.0]


def face(yaw=0.0):
    return {"box": [0, 0, 150, 150], "score": 0.95, "yaw": yaw}


def cam(i, faces=1, blank=False, embedding=SAME, yaw=0.0):
    result = {"faces": [face(yaw) for _ in range(faces)], "blank": blank}
    if faces == 1 and embedding is not None:
        result["embedding"] = embedding
    return Frame(f"cam/{i}", "camera", T0 + timedelta(seconds=30 * i), result)


def ev(seconds, type_, **data):
    return PageEvent(type_, T0 + timedelta(seconds=seconds), data)


def types(flags):
    return [f.type for f in flags]


def test_clean_session_scores_100_and_is_clear():
    frames = [cam(i) for i in range(10)]

    flags = all_flags(frames, [], REF)
    score = compute(flags)

    assert flags == []
    assert (score.value, score.band, score.reasons) == (100.0, "clear", [])


def test_single_bad_frame_is_noise_two_in_a_row_is_a_flag():
    one = [cam(0), cam(1, faces=0), cam(2)]
    two = [cam(0), cam(1, faces=0), cam(2, faces=0), cam(3)]

    assert all_flags(one, [], REF) == []
    flags = all_flags(two, [], REF)
    assert types(flags) == ["NO_FACE"]
    assert flags[0].evidence == ["cam/1", "cam/2"]
    assert flags[0].duration_s == 30


def test_multiple_faces_flags_on_first_frame():
    assert types(all_flags([cam(0), cam(1, faces=2)], [], REF)) == ["MULTIPLE_FACES"]


def test_identity_mismatch_needs_two_consecutive_frames_and_a_reference():
    frames = [cam(0), cam(1, embedding=OTHER), cam(2, embedding=OTHER)]

    flagged = all_flags(frames, [], REF)
    assert types(flagged) == ["IDENTITY_MISMATCH"]
    assert flagged[0].severity == 4
    assert flagged[0].context["mean_similarity"] == 0.0
    assert all_flags(frames, [], None) == []


def test_covered_camera_is_obstructed_not_no_face():
    frames = [cam(0, faces=0, blank=True), cam(1, faces=0, blank=True)]
    assert types(all_flags(frames, [], REF)) == ["CAMERA_OBSTRUCTED"]


def test_attention_away_needs_three_sustained_frames():
    frames = [cam(i, yaw=0.6) for i in range(3)]
    assert types(all_flags(frames, [], REF)) == ["ATTENTION_AWAY"]
    assert all_flags(frames[:2], [], REF) == []


def test_focus_loss_duration_and_severity():
    flags = all_flags([], [ev(0, "blur"), ev(1, "focus"), ev(10, "blur"), ev(40, "focus")], None)

    assert types(flags) == ["FOCUS_LOSS"]  # 1 s blip ignored
    assert (flags[0].severity, flags[0].duration_s) == (2, 30)


def test_copy_leave_return_paste_on_same_question():
    events = [
        ev(0, "copy", question="question-1-3"),
        ev(5, "blur"),
        ev(60, "focus"),
        ev(70, "paste", question="question-1-3"),
        ev(80, "paste", question="question-1-4"),
    ]

    flags = [f for f in all_flags([], events, None) if f.type == "COPY_PASTE_SEQUENCE"]

    assert len(flags) == 1
    assert flags[0].question == "question-1-3"


def test_paste_without_leaving_is_not_a_sequence():
    events = [ev(0, "copy", question="q1"), ev(5, "paste", question="q1")]
    assert all_flags([], events, None) == []


def test_flags_during_a_connection_drop_get_lower_confidence_and_context():
    frames = [cam(0, faces=0), cam(1, faces=0)]
    events = [ev(-5, "offline"), ev(40, "online")]

    (flag,) = all_flags(frames, events, REF)

    assert flag.context["connectivity_gap"] is True
    assert flag.confidence == 0.4


def test_score_is_traceable_and_banded():
    frames = [cam(0), cam(1, embedding=OTHER), cam(2, embedding=OTHER), cam(3, faces=2)]
    events = [
        ev(0, "copy", question="q"),
        ev(1, "blur"),
        ev(30, "focus"),
        ev(31, "paste", question="q"),
    ]

    score = compute(all_flags(frames, events, REF))

    assert score.band in {"review", "high"}
    assert score.reasons[0]["type"] == "IDENTITY_MISMATCH"
    assert {r["type"] for r in score.reasons} == {
        "IDENTITY_MISMATCH",
        "MULTIPLE_FACES",
        "COPY_PASTE_SEQUENCE",
        "FOCUS_LOSS",
    }
    assert round(100 - sum(r["points"] for r in score.reasons), 1) == score.value
