import time

import pytest
from conftest import launch_token

DESKTOP_OK = {"camera": "ok", "screen": "ok", "screen_surface": "monitor", "network_ok": True}


def start(client, settings, **claims):
    response = client.post("/v1/sessions/exchange", json={"launch_token": launch_token(settings, **claims)})
    assert response.status_code == 200, response.text
    body = response.json()
    return body, {"Authorization": f"Bearer {body['session_token']}"}


def consent(client, session, headers, settings):
    return client.post(
        f"/v1/sessions/{session['session_id']}/consent",
        json={"text_version": settings.consent_text_version, "accepted": True},
        headers=headers,
    )


def test_exchange_returns_session_and_policy(client, settings):
    body, _ = start(client, settings)

    assert body["policy"] == {"camera": True, "screen": True, "strict": True}
    assert body["consent_text_version"] == settings.consent_text_version


def test_launch_token_is_single_use(client, settings):
    token = launch_token(settings)
    assert client.post("/v1/sessions/exchange", json={"launch_token": token}).status_code == 200

    replay = client.post("/v1/sessions/exchange", json={"launch_token": token})

    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "launch_token_used"
    assert replay.json()["error"]["request_id"]


def test_expired_launch_token_is_rejected(client, settings):
    past = int(time.time()) - 600
    token = launch_token(settings, iat=past, exp=past + 60)

    response = client.post("/v1/sessions/exchange", json={"launch_token": token})

    assert response.status_code == 401


def test_launch_token_longer_than_120_seconds_is_rejected(client, settings):
    now = int(time.time())
    token = launch_token(settings, iat=now, exp=now + 3600)

    assert client.post("/v1/sessions/exchange", json={"launch_token": token}).status_code == 401


def test_launch_token_signed_with_wrong_key_is_rejected(client, settings):
    import jwt

    claims = jwt.decode(launch_token(settings), options={"verify_signature": False})
    forged = jwt.encode(claims, "wrong-key-" + "x" * 32, algorithm="HS256")

    assert client.post("/v1/sessions/exchange", json={"launch_token": forged}).status_code == 401


def test_session_endpoints_need_the_matching_session_token(client, settings):
    first, _ = start(client, settings)
    _, other_headers = start(client, settings)

    response = consent(client, first, other_headers, settings)

    assert response.status_code == 403


def test_precheck_requires_consent_first(client, settings):
    session, headers = start(client, settings)

    response = client.post(f"/v1/sessions/{session['session_id']}/precheck", json=DESKTOP_OK, headers=headers)

    assert response.status_code == 409


def test_passing_precheck_sends_signed_ready_webhook(client, settings, moodle):
    session, headers = start(client, settings)
    assert consent(client, session, headers, settings).json() == {"status": "consented"}

    response = client.post(f"/v1/sessions/{session['session_id']}/precheck", json=DESKTOP_OK, headers=headers)

    assert response.json()["status"] == "ready"
    assert response.json()["ready_delivered"] is True
    assert moodle.received == [
        {
            "event": "session.ready",
            "data": {
                "session_id": session["session_id"],
                "moodle_user_id": 42,
                "quiz_id": 3,
                "cmid": 7,
                "policy": {"camera": True, "screen": True, "strict": True},
                "context": {
                    "screen_surface": "monitor",
                    "microphone": "not_requested",
                    "network_ok": True,
                },
            },
        }
    ]


def test_strict_mode_blocks_window_share_and_sends_nothing(client, settings, moodle):
    session, headers = start(client, settings)
    consent(client, session, headers, settings)

    response = client.post(
        f"/v1/sessions/{session['session_id']}/precheck",
        json={**DESKTOP_OK, "screen_surface": "window"},
        headers=headers,
    )

    assert response.json()["status"] == "blocked"
    assert response.json()["reasons"] == ["screen_not_whole_display"]
    assert moodle.received == []


def test_lenient_mode_lets_phone_continue_without_screen(client, settings, moodle):
    session, headers = start(client, settings, policy={"camera": True, "screen": True, "strict": False})
    consent(client, session, headers, settings)

    response = client.post(
        f"/v1/sessions/{session['session_id']}/precheck",
        json={"camera": "ok", "screen": "unsupported"},
        headers=headers,
    )

    assert response.json()["status"] == "ready"
    assert moodle.received[0]["data"]["context"]["screen"] == "unsupported"


def test_denied_camera_blocks_even_in_lenient_mode(client, settings):
    session, headers = start(client, settings, policy={"camera": True, "screen": False, "strict": False})
    consent(client, session, headers, settings)

    response = client.post(f"/v1/sessions/{session['session_id']}/precheck", json={"camera": "denied"}, headers=headers)

    assert response.json()["reasons"] == ["camera_denied"]


def test_undelivered_ready_stays_in_outbox_for_retry(client, settings, moodle, store):
    moodle.status = 503
    session, headers = start(client, settings)
    consent(client, session, headers, settings)

    response = client.post(f"/v1/sessions/{session['session_id']}/precheck", json=DESKTOP_OK, headers=headers)

    assert response.json() == {
        "session_id": session["session_id"],
        "status": "ready",
        "ready_delivered": False,
        "reasons": [],
    }
    assert store.outbox[0].delivered_at is None
    assert store.outbox[0].attempts == 1


@pytest.mark.parametrize(
    ("matches", "status"),
    [(True, "ready"), (False, "blocked"), (None, "blocked")],
)
def test_browser_without_display_surface_uses_display_shape(client, settings, matches, status):
    # Firefox reports no displaySurface; the SDK says whether the capture has the display's shape.
    session, headers = start(client, settings)
    consent(client, session, headers, settings)
    body = {**DESKTOP_OK, "screen_surface": None, "screen_matches_display": matches}
    response = client.post(f"/v1/sessions/{session['session_id']}/precheck", json=body, headers=headers)
    assert response.json()["status"] == status
