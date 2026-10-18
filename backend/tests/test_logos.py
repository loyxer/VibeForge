"""AI logos: the safety check on SVG, building the logo, putting it on a page."""
import pytest
from fastapi.testclient import TestClient

from app import logos, projects, versions
from app.main import app

ICON = '<svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="40" fill="#ff9f1c"/></svg>'
CONCEPT = {"icon": ICON, "color": "#222222", "font": "serif", "caps": False, "tagline": "кав'ярня"}

PAGE = (
    '<!doctype html><html><head><title>x</title></head><body>'
    '<header><a class="logo" href="#/home">Крихта</a><nav><a href="#/about">Про нас</a></nav></header>'
    "<main><h1>Hi</h1></main><footer><a class=\"brand\">footer brand</a></footer></body></html>"
)


# ---------------------------------------------------------- cleaning SVG


@pytest.mark.parametrize(
    "bad",
    [
        '<svg viewBox="0 0 10 10"><script>alert(1)</script></svg>',
        '<svg viewBox="0 0 10 10" onload="alert(1)"><circle r="5" onclick="x()"/></svg>',
        '<svg viewBox="0 0 10 10"><foreignObject><div/></foreignObject></svg>',
        '<svg viewBox="0 0 10 10"><a href="https://evil.example"><circle r="5"/></a></svg>',
        '<svg viewBox="0 0 10 10"><use href="https://evil.example/x.svg#a"/></svg>',
        '<svg viewBox="0 0 10 10"><image href="https://evil.example/p.png"/></svg>',
        '<svg viewBox="0 0 10 10"><circle r="5" fill="url(https://evil.example/x)"/></svg>',
        '<svg viewBox="0 0 10 10"><style>@import url(https://evil.example)</style><circle r="5"/></svg>',
        '<!DOCTYPE svg [<!ENTITY a "b">]><svg viewBox="0 0 10 10"><circle r="5"/></svg>',
        "<svg viewBox=\"0 0 10 10\"><circle r=\"5\" fill=\"javascript:alert(1)\"/></svg>",
        '<div>not svg</div>',
        "not xml at all",
        '<svg><circle r="5"/></svg>',  # no viewBox
        '<svg viewBox="0 0 10 10"></svg>',  # nothing drawn
    ],
)
def test_unsafe_or_useless_svg_is_refused(bad):
    out = logos.clean_svg(bad)
    assert out is None or ("script" not in out and "onload" not in out and "evil" not in out)
    if "<circle" not in bad:
        assert out is None


def test_dangerous_parts_are_dropped_but_safe_ones_kept():
    out = logos.clean_svg(
        '<svg viewBox="0 0 10 10" onload="x()"><script>x()</script><circle r="5" cx="5" cy="5" '
        'fill="#fff" onclick="x()" style="background:url(http://e)"/></svg>'
    )
    assert out == (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        '<circle r="5" cx="5" cy="5" fill="#fff"></circle></svg>'
    )


def test_icon_cannot_carry_text():
    assert logos.clean_svg('<svg viewBox="0 0 9 9"><text x="1" y="1">hi</text></svg>', allow_text=False) is None


def test_huge_svg_is_refused():
    assert logos.clean_svg('<svg viewBox="0 0 9 9">' + '<circle r="1"/>' * 2000 + "</svg>") is None


# ------------------------------------------------------------- composing


def test_compose_builds_a_logo_with_the_name():
    svg = logos.compose("Крихта", CONCEPT)
    assert svg.startswith("<svg") and "Крихта" in svg and "кав&#x27;ярня" in svg or "кав'ярня" in svg
    assert 'textLength="' in svg and "scale(" in svg
    assert logos.clean_svg(svg) == svg  # already clean


def test_long_names_are_fitted_not_cut_off():
    svg = logos.compose("Дуже довга назва компанії «Північний вітер»", CONCEPT)
    width = float(svg.split('viewBox="0 0 ')[1].split(" ")[0])
    text_len = int(svg.split('textLength="')[1].split('"')[0])
    assert 120 + text_len <= width


def test_caps_dark_and_bad_color_fallbacks():
    svg = logos.compose("Борода", {**CONCEPT, "caps": True, "color": "red; evil", "tagline": ""}, dark=True)
    assert "БОРОДА" in svg and 'fill="#f5f5f5"' in svg


def test_unusable_symbol_gives_nothing():
    assert logos.compose("X", {**CONCEPT, "icon": "<svg><script/></svg>"}) is None


# ------------------------------------------------------------ on the page


def test_logo_replaces_the_text_name_in_the_header():
    svg = logos.compose("Крихта", CONCEPT)
    html = logos.with_logo(PAGE, svg)
    assert '<a class="logo" href="#/home"><svg id="vf-logo"' in html
    assert ">Крихта</a>" not in html.split("<nav>")[0].replace("Крихта</text>", "")
    assert "footer brand" in html  # the footer is left alone
    assert html.count('id="vf-logo-style"') == 1


def test_logo_can_be_swapped_and_swapping_adds_nothing_else():
    first = logos.with_logo(PAGE, logos.compose("Крихта", CONCEPT))
    second = logos.with_logo(first, logos.compose("Крихта 2", {**CONCEPT, "caps": True}))
    assert second.count('id="vf-logo"') == 1 and second.count('id="vf-logo-style"') == 1
    assert "КРИХТА 2" in second and "<nav>" in second


def test_logo_goes_to_the_header_when_there_is_no_logo_element():
    html = logos.with_logo(
        "<html><body><header><nav><a href='#/a'>A</a></nav></header></body></html>",
        logos.compose("Борода", CONCEPT),
    )
    assert html.index("vf-logo-wrap") < html.index("<nav>") or html.index('id="vf-logo"') < html.index("<nav>")


def test_first_home_link_is_used_as_the_logo():
    html = logos.with_logo(
        '<html><body><header><a href="#">Cafe</a><a href="#menu">Menu</a></header></body></html>',
        logos.compose("Cafe", CONCEPT),
    )
    assert ">Cafe</a>" not in html.replace("Cafe</text>", "") and ">Menu</a>" in html


def test_a_brand_story_section_is_not_mistaken_for_the_logo():
    page = (
        "<html><body><header><a href='#'>X</a></header>"
        '<section class="brand-story"><ul><li>one</li></ul></section></body></html>'
    )
    html = logos.with_logo(page, logos.compose("X", CONCEPT))
    assert "<li>one</li>" in html


def test_page_without_header_still_gets_it():
    html = logos.with_logo("<html><body><p>hi</p></body></html>", logos.compose("X", CONCEPT))
    assert 'id="vf-logo"' in html and html.index("vf-logo-wrap") < html.index("<p>")


def test_bad_svg_never_reaches_the_page():
    with pytest.raises(logos.LogoError):
        logos.with_logo(PAGE, '<svg viewBox="0 0 9 9"><script>1</script></svg>')


# ------------------------------------------------------------------- API


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(projects, "_STORE_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(versions, "_STORE_PATH", tmp_path / "versions.json")
    logos._recent.clear()
    return TestClient(app)


def test_make_and_save_a_logo(client):
    res = client.post("/api/logos", json={"name": "Крихта", "brief": "кав'ярня, тепло"})
    assert res.status_code == 200
    found = res.json()["logos"]
    assert len(found) == 3 and all(s.startswith("<svg") for s in found)

    project_id = projects.create_project("local", PAGE, "сайт")
    saved = client.post(f"/api/projects/{project_id}/logo", json={"svg": found[0]})
    assert saved.status_code == 200 and 'id="vf-logo"' in saved.json()["html"]
    assert saved.json()["history"][-1] == "🎨 Added logo"
    assert len(versions.list_versions(project_id, "local")) >= 1


def test_logo_needs_a_name_and_is_rate_limited(client):
    assert client.post("/api/logos", json={"name": " "}).status_code == 400
    codes = [client.post("/api/logos", json={"name": "Крихта"}).status_code for _ in range(13)]
    assert codes[:12] == [200] * 12 and codes[12] == 429


def test_saving_a_malicious_svg_is_refused(client):
    project_id = projects.create_project("local", PAGE, "сайт")
    res = client.post(
        f"/api/projects/{project_id}/logo",
        json={"svg": '<svg viewBox="0 0 9 9"><script>alert(1)</script></svg>'},
    )
    assert res.status_code == 400
    assert "alert" not in projects.get_project(project_id, "local")["html"]


def test_logo_for_someone_elses_project_is_404(client):
    assert client.post("/api/projects/nope/logo", json={"svg": "<svg/>"}).status_code == 404
