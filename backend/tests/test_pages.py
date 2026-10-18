from app.generation.base import finish_html
from app.generation.pages import pages_in, wants_pages, with_pages

PAGE = """<!doctype html><html lang="uk"><head><title>x</title></head><body>
<header><a href="#/about" data-page-link="about">About</a></header>
<main><section data-page="home"><h1>Home</h1></section>
<section data-page="about"><h1>About</h1></section></main></body></html>"""


def test_adds_switching_and_starts_on_first_page():
    html = with_pages(PAGE)
    assert '<html data-view="home"' in html
    assert 'id="vf-pages-style"' in html and 'id="vf-pages"' in html
    assert 'html[data-view="about"] [data-page]:not([data-page="about"])' in html


def test_idempotent():
    once = with_pages(PAGE)
    assert with_pages(once) == once


def test_single_page_untouched():
    plain = "<html><body><section>one</section></body></html>"
    assert with_pages(plain) == plain
    assert pages_in(plain) == []


def test_removed_when_pages_are_gone():
    html = with_pages(PAGE)
    flat = html.replace(' data-page="home"', "").replace(' data-page="about"', "")
    cleaned = with_pages(flat)
    assert "vf-pages" not in cleaned and "data-view" not in cleaned


def test_a_link_attribute_is_not_a_page():
    assert pages_in('<a data-page-link="x">') == []


def test_finish_html_adds_it():
    assert 'id="vf-pages"' in finish_html(PAGE)


def test_wants_pages():
    assert wants_pages(True, "x", None)
    assert wants_pages(False, "сайт на кілька сторінок", None)
    assert wants_pages(False, "change color", PAGE)
    assert not wants_pages(False, "a cafe site", "<html></html>")
