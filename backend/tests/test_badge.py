"""The "Made with VibeForge" label on published pages."""
from app.publishing import SANDBOX_CSP, with_badge


def test_badge_goes_before_the_end_of_the_body():
    html = with_badge('<html lang="en"><body><h1>Hi</h1></body></html>')
    assert html.index('id="vf-badge"') < html.index("</body>")
    assert "Made with VibeForge" in html


def test_ukrainian_pages_get_a_ukrainian_badge():
    assert "Зроблено у VibeForge" in with_badge('<html lang="uk"><body></body></html>')


def test_republishing_does_not_add_a_second_badge():
    once = with_badge('<html lang="en"><body><p>x</p></body></html>')
    assert with_badge(once).count('id="vf-badge"') == 1


def test_page_without_body_tag_still_gets_it():
    assert 'id="vf-badge"' in with_badge("<p>just a fragment</p>")


def test_links_may_leave_the_sandbox():
    assert "allow-popups-to-escape-sandbox" in SANDBOX_CSP
