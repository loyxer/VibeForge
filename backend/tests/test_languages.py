"""Two-language sites: the switching machinery added around the AI's markup."""
from app.generation import languages
from app.generation.base import finish_html
from app.generation.languages import primary_only, wants_bilingual, with_languages
from app.publishing import with_badge, with_link_preview, with_seo_basics

PAGE = (
    '<!doctype html><html lang="uk"><head><title>Кава</title></head><body>'
    '<h1><span data-l="uk">Кава на Ринку</span><span data-l="en">Coffee on the Square</span></h1>'
    '<p data-l="uk">' + "Смачна кава щодня зранку. " * 3 + "</p>"
    '<p data-l="en">' + "Tasty coffee every morning. " * 3 + "</p>"
    "</body></html>"
)


def test_a_two_language_page_gets_its_switching_machinery():
    html = with_languages(PAGE)
    assert '<html data-lang="uk" lang="uk">' in html
    assert 'html[data-lang="en"] [data-l]:not([data-l="en"]){display:none!important}' in html
    assert 'id="vf-lang"' in html and 'id="vf-lang-switch"' in html  # AI left out the buttons
    assert 'data-set-lang="en"' in html


def test_no_floating_switcher_when_the_ai_wrote_buttons():
    page = PAGE.replace("<h1>", '<button data-set-lang="uk">УКР</button><button data-set-lang="en">ENG</button><h1>')
    html = with_languages(page)
    assert 'id="vf-lang-switch"' not in html
    assert 'id="vf-lang"' in html


def test_it_is_idempotent_and_follows_the_edited_page():
    once = with_languages(PAGE)
    twice = with_languages(once)
    assert twice == once
    assert twice.count('id="vf-lang-style"') == 1 and twice.count('data-lang=') >= 1


def test_a_page_that_lost_its_second_language_is_cleaned():
    html = with_languages(PAGE)
    only_uk = html.replace('<span data-l="en">Coffee on the Square</span>', "").replace(
        '<p data-l="en">' + "Tasty coffee every morning. " * 3 + "</p>", ""
    )
    cleaned = with_languages(only_uk)
    assert "vf-lang" not in cleaned and "data-lang" not in cleaned


def test_plain_pages_are_untouched():
    plain = "<html lang='uk'><body><h1>Привіт</h1></body></html>"
    assert with_languages(plain) == plain


def test_main_language_comes_from_the_html_tag():
    html = with_languages(PAGE.replace('lang="uk"', 'lang="en"'))
    assert 'data-lang="en"' in html


def test_finish_html_adds_it():
    assert 'id="vf-lang"' in finish_html(PAGE)


def test_title_and_description_use_one_language():
    assert primary_only(PAGE).count("Coffee") == 0
    seo = with_seo_basics(PAGE.replace("<title>Кава</title>", ""), "https://x.example/s/abcd1234")
    assert "<title>Кава на Ринку</title>" in seo
    assert "Смачна кава" in seo.split("</head>")[0] and "Tasty" not in seo.split("</head>")[0]
    preview = with_link_preview(PAGE, "https://x.example/s/abcd1234")
    assert "Coffee on the Square" not in preview.split("</head>")[0]


def test_badge_speaks_both_languages_on_a_two_language_page():
    html = with_badge(with_languages(PAGE))
    assert '<span data-l="uk">Зроблено у VibeForge</span><span data-l="en">Made with VibeForge</span>' in html


def test_ai_is_told_how_when_asked():
    assert wants_bilingual(True, "кав'ярня", None)
    assert wants_bilingual(False, "Зроби сайт двома мовами", None)
    assert wants_bilingual(False, "change the color", PAGE)  # already bilingual: keep both in sync
    assert not wants_bilingual(False, "англійський сад", None)
    assert "data-l" in languages.BILINGUAL_PROMPT
