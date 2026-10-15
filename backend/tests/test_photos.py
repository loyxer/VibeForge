"""Filling in Unsplash photos, against a fake Unsplash — no real requests."""
import httpx
import pytest

from app import photos


def fake_photo(n, name="Ann Lee"):
    return {
        "urls": {"raw": f"https://images.unsplash.com/photo-{n}?ixid=abc"},
        "user": {"name": name, "links": {"html": f"https://unsplash.com/@user{n}"}},
        "links": {"download_location": f"https://api.unsplash.com/photos/{n}/download"},
        "alt_description": f"photo {n}",
    }


class FakeUnsplash:
    def __init__(self, results=None, status=200, remaining="40"):
        self.results = results if results is not None else [fake_photo(1), fake_photo(2, "Bo Kim")]
        self.status = status
        self.remaining = remaining
        self.searches = []
        self.downloads = []

    def get(self, url, params=None, headers=None, timeout=None):
        request = httpx.Request("GET", url)
        headers = {"X-Ratelimit-Remaining": self.remaining}
        if url.endswith("/download"):
            self.downloads.append(url)
            return httpx.Response(200, json={}, headers=headers, request=request)
        self.searches.append((params["query"], params.get("orientation")))
        return httpx.Response(
            self.status, json={"results": self.results}, headers=headers, request=request
        )


@pytest.fixture
def unsplash(monkeypatch):
    fake = FakeUnsplash()
    monkeypatch.setattr(photos.httpx, "get", fake.get)
    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "test-key")
    monkeypatch.setattr(photos, "_cache", {})
    monkeypatch.setattr(photos, "_remaining", {"requests": 50, "at": 0.0})
    return fake


PAGE = """<html><body>
<section class="hero" data-photo-bg="old town street" style="color:white">Hi</section>
<img data-photo="latte art" alt="A latte">
<img data-photo="latte art" alt="Another latte"/>
</body></html>"""


def test_fills_images_and_backgrounds(unsplash):
    html = photos.fill(PAGE)
    assert 'src="https://images.unsplash.com/photo-1?ixid=abc&w=1200' in html
    assert "photo-2?ixid=abc&w=1200" in html  # the repeated query gets a different photo
    assert "background-image:url('https://images.unsplash.com/photo-1?ixid=abc&w=1920" in html
    assert 'style="background-image' in html and "color:white" in html  # existing style kept
    assert unsplash.searches == [("old town street", "landscape"), ("latte art", None)]


def test_only_the_first_photo_loads_eagerly(unsplash):
    html = photos.fill('<img data-photo="a"><img data-photo="b"><img data-photo="c">')
    assert html.count('fetchpriority="high"') == 1
    assert html.count('loading="lazy"') == 2


def test_credits_photographers_and_unsplash(unsplash):
    html = photos.fill(PAGE)
    credits = html[html.index('class="vf-photo-credits"') :]
    assert "Ann Lee" in credits and "Bo Kim" in credits
    assert credits.count("Ann Lee") == 1  # each photographer once
    assert "https://unsplash.com/?utm_source=vibeforge&amp;utm_medium=referral" in credits or \
        "https://unsplash.com/?utm_source=vibeforge&utm_medium=referral" in credits
    assert html.index("vf-photo-credits") < html.index("</body>")


def test_tells_unsplash_which_photos_were_used(unsplash):
    photos.fill(PAGE)
    assert len(unsplash.downloads) == 3


def test_filling_again_changes_nothing(unsplash):
    once = photos.fill(PAGE)
    searches = len(unsplash.searches)
    assert photos.fill(once) == once  # edits keep their photos and one credits block
    assert len(unsplash.searches) == searches


def test_same_query_is_cached(unsplash):
    photos.fill('<img data-photo="latte art">')
    photos.fill('<img data-photo="latte art">')
    assert unsplash.searches == [("latte art", None)]


def test_no_key_or_failed_search_leaves_the_page_without_photos(unsplash, monkeypatch):
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY")
    html = photos.fill(PAGE)
    assert "src=" not in html and html.count(" hidden") == 2  # empty frames hidden
    assert unsplash.searches == []

    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "test-key")
    unsplash.status = 403
    html = photos.fill(PAGE)
    assert "src=" not in html and "vf-photo-credits" not in html


def test_stops_searching_when_the_hourly_limit_is_nearly_used(unsplash):
    unsplash.remaining = "2"
    photos.fill('<img data-photo="first">')
    photos.fill('<img data-photo="second">')
    assert [q for q, _ in unsplash.searches] == ["first"]


def test_at_most_a_few_photos_per_page(unsplash):
    page = "".join(f'<img data-photo="thing {i}">' for i in range(photos.MAX_PHOTOS_PER_PAGE + 3))
    html = photos.fill(page)
    assert html.count("src=") == photos.MAX_PHOTOS_PER_PAGE


def test_long_description_falls_back_to_shorter_searches(unsplash, monkeypatch):
    real_get = unsplash.get

    def picky_get(url, params=None, headers=None, timeout=None):
        if params and len(params["query"].split()) > 4:
            unsplash.searches.append((params["query"], params.get("orientation")))
            return httpx.Response(200, json={"results": []}, headers={"X-Ratelimit-Remaining": "40"},
                                  request=httpx.Request("GET", url))
        return real_get(url, params, headers, timeout)

    monkeypatch.setattr(photos.httpx, "get", picky_get)
    html = photos.fill('<img data-photo="papaya orange formula 1 racing car details">')
    assert "images.unsplash.com" in html
    assert [q for q, _ in unsplash.searches] == [
        "papaya orange formula 1 racing car details",
        "papaya orange formula 1",
    ]


def test_image_without_a_photo_is_hidden(unsplash):
    unsplash.results = []
    html = photos.fill('<img data-photo="nothing matches" alt="x"><div data-photo-bg="nope"></div>')
    assert '<img data-photo="nothing matches" alt="x" hidden>' in html
    assert '<div data-photo-bg="nope">' in html  # backgrounds just keep their colors
    assert photos.fill(html) == html  # and a hidden image isn't searched again


TILE = (
    '<div class="gallery-item" onclick="open()">'
    '<img data-photo="{q}" alt="x">'
    '<div class="gallery-caption"><span>Місто</span><h3>Лінії</h3></div></div>'
)


def test_tile_around_a_missing_photo_is_hidden_too(unsplash):
    unsplash.results = []
    html = photos.fill(TILE.format(q="nothing matches"))
    assert html.startswith('<div class="gallery-item" onclick="open()" hidden style="display:none">')
    assert photos.fill(html) == html  # second pass changes nothing


def test_tile_keeps_its_own_style_when_hidden(unsplash):
    unsplash.results = []
    html = photos.fill(TILE.replace("class=", 'style="color:red" class=').format(q="nothing"))
    assert 'style="display:none;color:red"' in html and " hidden" in html


def test_tile_with_a_found_photo_stays_visible(unsplash):
    html = photos.fill(TILE.format(q="latte art"))
    assert html.startswith('<div class="gallery-item" onclick="open()"><img')
    assert "display:none" not in html


def test_big_wrapper_with_a_missing_photo_is_left_alone(unsplash):
    unsplash.results = []
    about = (
        '<div class="about"><img data-photo="nothing" alt="me">'
        "<p>" + "Довгий текст про мене. " * 20 + "</p></div>"
    )
    html = photos.fill(about)
    assert html.startswith('<div class="about"><img')  # wrapper not hidden
    two = '<div class="grid"><img data-photo="a"><img data-photo="b"></div>'
    assert photos.fill(two).startswith('<div class="grid"><img')  # grid of several photos stays
