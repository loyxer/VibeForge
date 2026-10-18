"""What messengers show for a shared link to a published site."""
from app.publishing import with_link_preview

URL = "https://vibe.example/s/abcd1234"


def page(head="", body=""):
    return f"<!doctype html><html><head><title>Крихта — кав’ярня</title>{head}</head><body>{body}</body></html>"


def test_title_description_and_first_photo():
    html = with_link_preview(
        page(
            body='<section style="background-image:url(\'https://images.unsplash.com/a?w=1920&q=80\')">'
            "<h1>Hi</h1><p>Short.</p><p>Смачні сніданки, домашня випічка і кава зі свіжообсмаженого зерна щодня.</p>"
            '<img src="https://x.supabase.co/storage/v1/object/public/site-photos/u/p.jpg"></section>'
        ),
        URL,
    )
    assert '<meta property="og:title" content="Крихта — кав’ярня">' in html
    assert '<meta property="og:url" content="https://vibe.example/s/abcd1234">' in html
    assert 'og:description" content="Смачні сніданки, домашня випічка' in html  # skips the short one
    assert 'og:image" content="https://images.unsplash.com/a?w=1920&amp;q=80"' in html
    assert '<meta name="twitter:card" content="summary_large_image">' in html
    assert html.index("og:title") < html.index("</head>")


def test_meta_description_wins_and_ai_written_tags_are_replaced():
    html = with_link_preview(
        page(
            head='<meta name="description" content="Затишна кав’ярня в центрі">'
            '<meta property="og:image" content="images/og-cover.jpg">'
        ),
        URL,
    )
    assert 'og:description" content="Затишна кав’ярня в центрі"' in html
    assert "og-cover.jpg" not in html
    assert "og:image" not in html  # no real photo on this page
    assert '<meta name="twitter:card" content="summary">' in html


def test_republishing_does_not_pile_up_tags():
    once = with_link_preview(page(body="<p>" + "word " * 20 + "</p>"), URL)
    assert with_link_preview(once, URL).count("og:title") == 1


def test_page_without_head_is_left_alone():
    assert with_link_preview("<html>whole</html>", URL) == "<html>whole</html>"


def test_long_text_is_cut_at_a_word():
    html = with_link_preview(page(body="<p>" + "довге слово " * 40 + "</p>"), URL)
    description = html.split('og:description" content="')[1].split('"')[0]
    assert description.endswith("…") and len(description) <= 201
