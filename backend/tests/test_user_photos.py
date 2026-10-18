"""The person's own photos: upload, use on a site, limits, deletion."""
import json

import pytest
from fastapi.testclient import TestClient

from app import projects, publishing, usage, user_photos, versions
from app.api import routes
from app.generation.mock import MockGenerator
from app.main import app

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"0" * 200


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(projects, "_STORE_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(usage, "_STORE_PATH", tmp_path / "usage.json")
    monkeypatch.setattr(publishing, "_STORE_PATH", tmp_path / "published.json")
    monkeypatch.setattr(versions, "_STORE_PATH", tmp_path / "versions.json")
    monkeypatch.setattr(routes, "_generator", MockGenerator(delay=0))


@pytest.fixture
def client():
    return TestClient(app)


def upload(client, data=JPEG, mime="image/jpeg", project_id=None):
    params = {"project_id": project_id} if project_id else {}
    return client.post("/api/photos", content=data, headers={"Content-Type": mime}, params=params)


def generate(client, prompt, project_id=None, photo_ids=()):
    res = client.post(
        "/api/generate",
        json={"prompt": prompt, "project_id": project_id, "photo_ids": list(photo_ids)},
    )
    assert res.status_code == 200, res.text
    return [json.loads(line) for line in res.text.splitlines()][-1]


def test_upload_and_serve(client):
    photo = upload(client, WEBP, "image/webp").json()
    assert photo["url"] == f"/api/uploads/local/{photo['id']}.webp"
    assert client.get(photo["url"]).content == WEBP


@pytest.mark.parametrize(
    "data, mime",
    [
        (b"hello, not a photo", "image/jpeg"),  # wrong content
        (JPEG, "image/gif"),  # type we don't take
        (WEBP, "image/jpeg"),  # says jpeg, is webp
    ],
)
def test_only_real_photos_are_taken(client, data, mime):
    res = upload(client, data, mime)
    assert res.status_code == 400
    assert "photo we can use" in res.json()["detail"]


def test_too_large(client, monkeypatch):
    monkeypatch.setattr(user_photos, "MAX_BYTES", 100)
    assert upload(client).json()["detail"] == "That photo is too large"


def test_photos_go_onto_the_page_without_credits(client):
    ids = [upload(client).json()["id"] for _ in range(2)]
    done = generate(client, "my cafe", photo_ids=ids)
    for photo_id in ids:
        assert f"/api/uploads/local/{photo_id}.jpg" in done["html"]
    assert done["unused_photos"] == []
    assert "vf-photo-credits" not in done["html"]


def test_photos_the_ai_left_out_are_reported(client, monkeypatch):
    class IgnoresPhotos(MockGenerator):
        async def stream(self, request):
            yield ("model", "mock")
            yield ("text", "<html>no photos here</html>")

    monkeypatch.setattr(routes, "_generator", IgnoresPhotos(delay=0))
    ids = [upload(client).json()["id"] for _ in range(3)]
    assert generate(client, "my cafe", photo_ids=ids)["unused_photos"] == [1, 2, 3]


def test_someone_elses_or_unknown_photo(client):
    res = client.post("/api/generate", json={"prompt": "x", "photo_ids": ["nope"]})
    assert res.status_code == 404


def test_limit_per_site(client, monkeypatch):
    monkeypatch.setattr(user_photos, "MAX_PER_SITE", 2)
    first = [upload(client).json()["id"] for _ in range(2)]
    assert upload(client).json()["detail"] == "You can add up to 2 photos per site"

    # Once they're on a site, a new site starts with a clean slate…
    project_id = generate(client, "cafe", photo_ids=first)["project_id"]
    assert upload(client).status_code == 200
    # …and the site itself is full while both are still on its page.
    assert upload(client, project_id=project_id).status_code == 400


def test_replaced_photos_stop_counting(client, monkeypatch):
    monkeypatch.setattr(user_photos, "MAX_PER_SITE", 1)
    photo = upload(client).json()
    project_id = generate(client, "cafe", photo_ids=[photo["id"]])["project_id"]
    assert upload(client, project_id=project_id).status_code == 400
    generate(client, "remove the photo", project_id)  # mock page has no photo now
    assert upload(client, project_id=project_id).status_code == 200


def test_upload_for_someone_elses_site(client):
    assert upload(client, project_id="not-a-project").status_code == 404


def test_taking_back_an_unsent_photo(client):
    photo = upload(client).json()
    assert client.delete(f"/api/photos/{photo['id']}").status_code == 200
    assert client.get(photo["url"]).status_code == 404

    sent = upload(client).json()
    generate(client, "cafe", photo_ids=[sent["id"]])
    assert client.delete(f"/api/photos/{sent['id']}").status_code == 404  # it's on a site


def test_deleting_a_site_deletes_its_photos(client):
    photo = upload(client).json()
    project_id = generate(client, "cafe", photo_ids=[photo["id"]])["project_id"]
    other = upload(client).json()  # waiting for a new site: stays
    client.delete(f"/api/projects/{project_id}")
    assert client.get(photo["url"]).status_code == 404
    assert client.get(other["url"]).status_code == 200


def test_deleting_the_account_deletes_all_photos(client):
    photo = upload(client).json()
    generate(client, "cafe", photo_ids=[photo["id"]])
    pending = upload(client).json()
    client.delete("/api/account")
    assert client.get(photo["url"]).status_code == 404
    assert client.get(pending["url"]).status_code == 404


def test_uploads_route_cant_leave_the_folder(client):
    assert client.get("/api/uploads/../projects.json").status_code == 404
