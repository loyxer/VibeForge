"""What every generated page gets on its way into storage (finish_html)."""
from datetime import date

import pytest

from app.generation import base
from app.generation.base import SAFETY_CSS, finish_html


@pytest.fixture(autouse=True)
def this_year(monkeypatch):
    monkeypatch.setattr(base, "today", lambda: date(2026, 10, 18))


PAGE = "<!doctype html><html><head><title>x</title></head><body>{}</body></html>"


def test_safety_css_goes_into_the_head_once():
    html = finish_html(PAGE.format("hi"))
    assert html.count('id="vf-safety"') == 1
    assert SAFETY_CSS + "</head>" in html
    assert finish_html(html) == html  # an edited page doesn't get a second copy


def test_safety_css_without_a_head_goes_after_body():
    html = finish_html('<html><body class="x">hi</body></html>')
    assert '<body class="x">' + SAFETY_CSS + "hi" in html


def test_fragment_without_head_or_body_is_left_alone():
    assert finish_html("<html>whole</html>") == "<html>whole</html>"


@pytest.mark.parametrize(
    "old, new",
    [
        ("© 2023 Coffee Co.", "© 2026 Coffee Co."),
        ("&copy; 2025 Coffee", "&copy; 2026 Coffee"),
        ("Copyright 2024. All rights reserved.", "Copyright 2026. All rights reserved."),
        ("© 2026 Coffee", "© 2026 Coffee"),  # already right
        ("© 2019–2025 Coffee", "© 2019–2025 Coffee"),  # ranges are left alone
        ("Since 2015, in 2023 we won", "Since 2015, in 2023 we won"),  # not a copyright line
    ],
)
def test_copyright_year_is_brought_up_to_date(old, new):
    assert finish_html(PAGE.format(old)) == finish_html(PAGE.format(new))
    assert new in finish_html(PAGE.format(old))
