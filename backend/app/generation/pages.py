"""Sites with several pages (Home / About / Contact …) in ONE html file.

Every page is a section of the same document:

    <section data-page="home">…</section>
    <section data-page="about">…</section>
    <a href="#/about" data-page-link="about">About</a>

Header and footer stay outside the sections and are shared. Showing only the
current page is done here, not by the AI, so it works the same on every site:
a stylesheet hides the pages that aren't current (<html data-view="…">) and a
small script switches pages when a `#/page` link is clicked, on back/forward
and when the site is opened as `…#/about`. Keeping one file means history,
editing, publishing, client review, forms and languages all work unchanged.
"""
import json
import re

# Told to the AI when a site is (or becomes) multi-page.
PAGES_PROMPT = """This site has several pages, all inside ONE html file. Markup:
  <body>
    <header>… logo and menu, shared by all pages …</header>
    <main>
      <section data-page="home">…</section>
      <section data-page="about">…</section>
      <section data-page="contact">…</section>
    </main>
    <footer>… shared …</footer>
  </body>
Rules:
- 3 to 6 pages. Each page is a top-level <section data-page="id"> (a direct
  child of <main> or <body>), id in lowercase latin letters, digits or
  hyphens; the first one is "home". Header, navigation and footer are
  OUTSIDE all page sections.
- Menu links go to pages like this: <a href="#/about" data-page-link="about">About</a>.
  The logo links to "#/home". Every button or link that leads to another
  page uses the same form, href="#/id". Style the current menu link with
  the selector [aria-current="page"].
- Each page has its own purpose and real content (its own <h1>, at least two
  blocks), not a copy of the home page. Home is a summary that leads to the
  other pages. Keep every page compact so the whole file stays reasonably short.
- Do NOT write JavaScript or CSS that shows, hides or switches pages — the
  server adds that. Your JavaScript must not break on hrefs like "#/about":
  smooth-scroll code has to ignore links whose href starts with "#/" and
  never pass them to querySelector. Links like href="#prices" are only for
  blocks on the same page.
- On an existing page, keep the page ids; when you add a page, add it to the
  menu. When making a one-page site multi-page, keep the design and
  content, spreading the existing sections over pages. Keep the elements with
  id "vf-pages-style" and "vf-pages" untouched."""

_ASKS_FOR_PAGES = re.compile(
    r"multi-?page|several pages|multiple pages|separate pages|few pages|"
    r"багатосторінк|кілька сторінок|декілька сторінок|окрем\w* сторін",
    re.I,
)

_OURS = (
    r'\s*<style id="vf-pages-style">.*?</style>',
    r'\s*<script id="vf-pages">.*?</script>',
)
_VIEW_ATTR = r'(<html\b[^>]*?)\sdata-view="[\w-]*"'


def wants_pages(flag: bool, prompt: str, previous_html: str | None) -> bool:
    """Should the AI be told how to write a multi-page site?"""
    return flag or bool(
        _ASKS_FOR_PAGES.search(prompt) or (previous_html and 'data-page="' in previous_html)
    )


def pages_in(html: str) -> list[str]:
    """The page ids of a multi-page site, in order of appearance."""
    found: list[str] = []
    for page in re.findall(r'\sdata-page="([\w-]+)"', html):
        if page not in found:
            found.append(page)
    return found


def with_pages(html: str) -> str:
    """Add the page switching to a page that has data-page sections (and take
    it off a page that no longer has them)."""
    for pattern in _OURS:
        html = re.sub(pattern, "", html, flags=re.S)
    pages = pages_in(html)
    html = re.sub(_VIEW_ATTR, r"\1", html, count=1, flags=re.I)
    if len(pages) < 2:
        return html
    html = re.sub(r"<html\b", f'<html data-view="{pages[0]}"', html, count=1, flags=re.I)

    css = "".join(
        f'html[data-view="{p}"] [data-page]:not([data-page="{p}"]){{display:none!important}}'
        for p in pages
    )
    style = f'<style id="vf-pages-style">{css}</style>'
    script = f'<script id="vf-pages">{_SCRIPT.replace("__PAGES__", json.dumps(pages))}</script>'

    head = re.search(r"</head>", html, re.I)
    if head:
        html = html[: head.start()] + style + html[head.start() :]
    else:
        html = style + html
    body = re.search(r"</body>", html, re.I)
    at = body.start() if body else len(html)
    return html[:at] + script + html[at:]


_SCRIPT = (
    "(function(){var d=document.documentElement,P=__PAGES__;"
    "function show(id,top){if(P.indexOf(id)<0)id=P[0];d.setAttribute('data-view',id);"
    "document.querySelectorAll('[data-page-link]').forEach(function(a){"
    "if(a.getAttribute('data-page-link')===id)a.setAttribute('aria-current','page');"
    "else a.removeAttribute('aria-current');});"
    "if(top)window.scrollTo(0,0);}"
    "function fromHash(){var m=/^#\\/([\\w-]+)/.exec(location.hash);return m?m[1]:null;}"
    "window.__vfShowPage=show;"
    "document.addEventListener('click',function(e){"
    "var a=e.target.closest&&e.target.closest('a[href^=\"#\"]');if(!a)return;"
    "var h=a.getAttribute('href'),m=/^#\\/([\\w-]+)/.exec(h);"
    "if(m){if(P.indexOf(m[1])<0)return;e.preventDefault();show(m[1],true);"
    "try{history.pushState(null,'',h);}catch(_){}return;}"
    # a plain #anchor that lives on another page: open that page first
    "var t=h.length>1&&document.getElementById(decodeURIComponent(h.slice(1)));"
    "var s=t&&t.closest('[data-page]');if(s)show(s.getAttribute('data-page'),false);},true);"
    "function sync(){show(fromHash()||d.getAttribute('data-view'),true);}"
    "window.addEventListener('hashchange',sync);window.addEventListener('popstate',sync);"
    "show(fromHash()||d.getAttribute('data-view'),false);})();"
)
