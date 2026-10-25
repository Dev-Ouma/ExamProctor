import pytest
from starlette.websockets import WebSocketDisconnect
from test_review import captured, staff, staff_token  # noqa: F401 - fixture
from test_sessions import start

INVIGILATOR = ["review", "invigilate"]


def act(client, settings, sid, caps=INVIGILATOR, **body):
    return client.post(f"/v1/live/sessions/{sid}/actions", json=body, headers=staff(settings, caps=caps))


def beat(client, sid, headers):
    return client.post(f"/v1/sessions/{sid}/heartbeat", json={"queued_uploads": 0}, headers=headers).json()


@pytest.fixture
def live(client, settings, objects):
    """A started session with a heartbeat, plus the student's headers."""
    from test_evidence import JPEG, presign
    from test_sessions import DESKTOP_OK, consent

    session, headers = start(client, settings)
    sid = session["session_id"]
    consent(client, session, headers, settings)
    client.post(f"/v1/sessions/{sid}/precheck", json=DESKTOP_OK, headers=headers)
    body = presign(client, sid, headers).json()
    objects.put(body["key"], JPEG)
    client.post(f"/v1/sessions/{sid}/uploads/complete", json={"key": body["key"]}, headers=headers)
    beat(client, sid, headers)
    return sid, headers


def test_live_wall_needs_invigilate(client, settings, live):
    assert client.get("/v1/live/quizzes/3/sessions", headers=staff(settings, caps=["review"])).status_code == 403
    assert client.get("/v1/live/quizzes/4/sessions", headers=staff(settings, caps=INVIGILATOR)).status_code == 403


def test_live_wall_shows_online_session_with_latest_camera(client, settings, live):
    sid, _ = live
    body = client.get("/v1/live/quizzes/3/sessions", headers=staff(settings, caps=INVIGILATOR)).json()
    row = body["sessions"][0]
    assert row["session_id"] == sid and row["online"] is True and row["paused"] is False
    assert row["latest_camera"]["url"].startswith("memory://")


def test_reason_required_and_message_needs_text(client, settings, live):
    sid, _ = live
    assert act(client, settings, sid, type="warn", reason="").status_code == 422
    assert act(client, settings, sid, type="message", reason="Clarify rules").status_code == 422
    assert act(client, settings, sid, type="warn", reason="Looking away", caps=["review"]).status_code == 403


def test_warning_reaches_student_once_and_is_acked(client, settings, live, store):
    sid, headers = live
    action = act(client, settings, sid, type="warn", reason="Second person seen", message="Please sit alone.").json()
    notices = beat(client, sid, headers)["notices"]
    assert notices == [
        {"id": action["id"], "type": "warn", "message": "Please sit alone.", "created_at": action["created_at"]}
    ]
    assert "actor_name" not in notices[0]
    assert beat(client, sid, headers)["notices"] == []
    assert client.post(f"/v1/sessions/{sid}/notices/{action['id']}/ack", headers=headers).status_code == 200


def test_pause_and_resume(client, settings, live):
    sid, headers = live
    assert act(client, settings, sid, type="resume", reason="Go on").status_code == 409
    assert act(client, settings, sid, type="pause", reason="Check the room").status_code == 200
    assert act(client, settings, sid, type="pause", reason="Again").status_code == 409
    assert beat(client, sid, headers)["paused"] is True
    assert act(client, settings, sid, type="resume", reason="Room is clear").status_code == 200
    assert beat(client, sid, headers)["paused"] is False


def test_terminate_closes_session_and_tells_moodle(client, settings, live, store):
    sid, headers = live
    assert act(client, settings, sid, type="terminate", reason="Impersonation confirmed by ID").status_code == 200
    assert store.sessions[sid].status == "terminated"
    assert store.outbox[-1].event == "session.terminated"
    assert store.outbox[-1].payload["reason"] == "Impersonation confirmed by ID"
    assert beat(client, sid, headers)["notices"][0]["type"] == "terminate"
    assert act(client, settings, sid, type="warn", reason="late").status_code == 409


def test_actions_are_audited_and_published(client, settings, live):
    sid, _ = live
    act(client, settings, sid, type="warn", reason="Looking away")
    assert client.app.state.reviews.audit_rows[-1]["action"] == "live_warn"
    assert (3, {"type": "action", "session_id": sid, "action": "warn"}) in client.app.state.bus.published


def test_stream_needs_token_as_first_message(client, settings):
    with client.websocket_connect("/v1/live/quizzes/3/stream") as ws:
        ws.send_text("junk")
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4401


def test_stream_rejects_other_quiz(client, settings):
    with client.websocket_connect("/v1/live/quizzes/4/stream") as ws:
        ws.send_text(staff_token(settings, caps=INVIGILATOR))
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4403


def test_stream_says_hello_then_forwards_events(client, settings, live):
    sid, headers = live
    with client.websocket_connect("/v1/live/quizzes/3/stream") as ws:
        ws.send_text(staff_token(settings, caps=INVIGILATOR))
        assert ws.receive_json() == {"type": "hello"}
        beat(client, sid, headers)
        assert ws.receive_json() == {"type": "heartbeat", "session_id": sid}
