import base64

import pytest
from test_refphotos import signed_headers
from test_review import captured  # noqa: F401 - fixture

from examproctor_service.review_store import Review


def call(client, method: str, path: str):
    return client.request(method, path, headers=signed_headers(method, path, b""))


@pytest.fixture
def reviews(client):
    return client.app.state.reviews


def test_privacy_calls_must_be_signed(client, captured):  # noqa: F811
    assert client.get("/v1/admin/privacy/users/42").status_code == 401
    assert client.delete("/v1/admin/privacy/users/42").status_code == 401


def test_query_string_is_part_of_the_signature(client, captured):  # noqa: F811
    headers = signed_headers("DELETE", "/v1/admin/privacy/users/42?quiz_id=3", b"")
    assert client.delete("/v1/admin/privacy/users/42", headers=headers).status_code == 401


def test_lookup_by_user_and_quiz(client, captured):  # noqa: F811
    assert call(client, "GET", "/v1/admin/privacy/users/42/quizzes").json()["quiz_ids"] == [3]
    assert call(client, "GET", "/v1/admin/privacy/quizzes/3/users").json()["user_ids"] == [42]


def test_export_includes_images_and_no_embeddings(client, captured, reviews):  # noqa: F811
    sid, key = captured
    reviews.analysis[(sid, key)] = {"faces": [], "embedding": [0.1]}
    body = call(client, "GET", "/v1/admin/privacy/users/42?quiz_id=3").json()
    upload = body["sessions"][0]["uploads"][0]
    assert base64.b64decode(upload["jpeg_base64"]).startswith(b"\xff\xd8")
    assert upload["analysis"] == {"faces": []}
    assert reviews.audit_rows[-1]["action"] == "privacy_export"


def test_erase_removes_rows_and_objects(client, captured, reviews, objects, store):  # noqa: F811
    sid, key = captured
    reviews.review_rows.append(Review(sid, "decision", "no_issue", "", 1, "R"))
    body = call(client, "DELETE", "/v1/admin/privacy/users/42?quiz_id=3").json()
    assert body == {"user_id": 42, "erased": [sid], "held": []}
    assert key not in objects.objects
    assert sid not in store.sessions
    assert reviews.review_rows == []
    assert call(client, "GET", "/v1/admin/privacy/users/42").json()["sessions"] == []


def test_legal_hold_blocks_erase(client, captured, store, objects):  # noqa: F811
    sid, key = captured
    store.sessions[sid].legal_hold = True
    body = call(client, "DELETE", "/v1/admin/privacy/users/42").json()
    assert body["held"] == [sid] and body["erased"] == []
    assert key in objects.objects


def test_erase_is_scoped_to_the_quiz(client, captured, store):  # noqa: F811
    sid, _ = captured
    assert call(client, "DELETE", "/v1/admin/privacy/users/42?quiz_id=99").json()["erased"] == []
    assert sid in store.sessions
