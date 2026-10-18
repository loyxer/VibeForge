"""Sites in two languages (Ukrainian + English) with a switcher.

The AI writes every piece of text twice, tagged with its language:

    <h1><span data-l="uk">Кава</span><span data-l="en">Coffee</span></h1>

Everything that makes the switch work is added here, not by the AI, so it
works the same on every site: a stylesheet hiding the language not chosen,
a small script behind the buttons (<button data-set-lang="en">), and — if
the AI forgot the buttons — a floating switcher. The page starts in its
main language, so it's right even before scripts run, and the hand editor
(where scripts are paused) can switch by changing one attribute.
"""
import json
import re

# Told to the AI when a site is (or becomes) bilingual.
BILINGUAL_PROMPT = """This site must be bilingual: Ukrainian (uk) and English (en), and the visitor
can switch between them. The main language is the one the instruction is
written in (or the page's current main language); the other is its pair.
Markup — write EVERY piece of visible text twice, in sibling elements
tagged with their language:
  <h1><span data-l="uk">Кава на Ринку</span><span data-l="en">Coffee on the Square</span></h1>
  <p data-l="uk">Український абзац…</p><p data-l="en">The English paragraph…</p>
Rules:
- All visible text exists in both languages: headings, paragraphs, buttons,
  links, menu items, list items, form labels, FAQ, footer, and messages
  your JavaScript shows. For a message set from JavaScript, pick the text by
  document.documentElement.getAttribute("data-lang") ("uk" or "en").
- Never put both languages inside one element, and never put data-l on
  <html>, <body> or <head>. Names, brands, numbers, phone numbers and
  e-mail addresses are the same in both — write them once, without data-l.
- Input placeholders: keep placeholder="…" in the main language and add
  data-ph-uk="…" and data-ph-en="…". The page title: put
  data-title-uk="…" data-title-en="…" on <html>, next to lang="…" (the main
  language), and write <title> in the main language. Prefer language-neutral
  text inside <option> elements (browsers can't hide options reliably).
- Language buttons, in the header (and inside the mobile menu), exactly:
  <button type="button" data-set-lang="uk">УКР</button>
  <button type="button" data-set-lang="en">ENG</button>
  Style the active one with the selector [aria-pressed="true"]. Do NOT
  write JavaScript or CSS that switches or hides languages — the server adds
  that; if you leave the buttons out, it adds a floating switcher.
- Translate naturally, not word for word, with the same meaning. The layout
  must look right in both languages (English is often shorter or longer).
- On an existing page, change both languages together. When making a
  single-language page bilingual, keep the design and content exactly as
  they are, wrapping each text as above and adding the second language.
  Keep the elements with id "vf-lang-style", "vf-lang" and "vf-lang-switch"
  untouched."""

_ASKS_FOR_TWO_LANGUAGES = re.compile(
    r"bilingual|two languages|both languages|english version|"
    r"двомов|двома мовами|дві мови|двох мов|англійськ\w* верс",
    re.I,
)

_LABELS = {"uk": "УКР", "en": "ENG"}
_OURS = (
    r'\s*<style id="vf-lang-style">.*?</style>',
    r'\s*<script id="vf-lang">.*?</script>',
    r'\s*<div id="vf-lang-switch">.*?</div>',
)


def wants_bilingual(flag: bool, prompt: str, previous_html: str | None) -> bool:
    """Should the AI be told how to write a two-language site?"""
    return flag or bool(
        _ASKS_FOR_TWO_LANGUAGES.search(prompt) or (previous_html and 'data-l="' in previous_html)
    )


def languages_in(html: str) -> list[str]:
    """The languages the page's data-l markup uses, in order of appearance."""
    found: list[str] = []
    for lang in re.findall(r'\bdata-l="(\w+)"', html):
        if lang not in found:
            found.append(lang)
    return found


def _main_language(html: str, langs: list[str]) -> str:
    m = re.search(r"<html\b[^>]*\slang=[\"']?(\w+)", html, re.I)
    return m.group(1).lower() if m and m.group(1).lower() in langs else langs[0]


def primary_only(html: str) -> str:
    """The page with the secondary language's texts left out — for working
    out its title and description, which should be in one language."""
    langs = languages_in(html)
    if len(langs) < 2:
        return html
    main = _main_language(html, langs)
    return re.sub(
        r'<(\w+)\b[^>]*\bdata-l="(?!%s")\w+"[^>]*>.*?</\1>' % re.escape(main),
        "",
        html,
        flags=re.S,
    )


def with_languages(html: str) -> str:
    """Add the switching machinery to a page that has data-l markup (and take
    it off a page that no longer has it)."""
    for pattern in _OURS:
        html = re.sub(pattern, "", html, flags=re.S)
    langs = languages_in(html)
    if len(langs) < 2:
        html = re.sub(r'(<html\b[^>]*?)\sdata-lang="\w+"', r"\1", html, count=1, flags=re.I)
        return html
    main = _main_language(html, langs)

    html = re.sub(r'(<html\b[^>]*?)\sdata-lang="\w+"', r"\1", html, count=1, flags=re.I)
    html = re.sub(r"<html\b", f'<html data-lang="{main}"', html, count=1, flags=re.I)

    css = "".join(
        f'html[data-lang="{lang}"] [data-l]:not([data-l="{lang}"]){{display:none!important}}'
        for lang in langs
    )
    has_buttons = "data-set-lang" in html
    if not has_buttons:
        css += (
            "#vf-lang-switch{position:fixed;left:12px;bottom:12px;z-index:2147483646;display:flex;"
            "gap:2px;padding:3px;border-radius:999px;background:#fff;border:2px solid #e5e5e5}"
            "#vf-lang-switch button{border:0;background:none;padding:4px 10px;border-radius:999px;"
            "cursor:pointer;color:#222;font:700 13px/1.2 system-ui,sans-serif}"
            '#vf-lang-switch button[aria-pressed="true"]{background:#222;color:#fff}'
            "@media print{#vf-lang-switch{display:none}}"
        )
    style = f'<style id="vf-lang-style">{css}</style>'
    script = f'<script id="vf-lang">{_SCRIPT.replace("__LANGS__", json.dumps(langs))}</script>'
    switch = ""
    if not has_buttons:
        buttons = "".join(
            f'<button type="button" data-set-lang="{lang}" aria-pressed="false">'
            f"{_LABELS.get(lang, lang.upper())}</button>"
            for lang in langs
        )
        switch = f'<div id="vf-lang-switch">{buttons}</div>'

    head = re.search(r"</head>", html, re.I)
    if head:
        html = html[: head.start()] + style + html[head.start() :]
    else:
        html = style + html
    body = re.search(r"</body>", html, re.I)
    at = body.start() if body else len(html)
    return html[:at] + switch + script + html[at:]


_SCRIPT = (
    "(function(){var d=document.documentElement,L=__LANGS__;"
    "function set(l){d.setAttribute('data-lang',l);d.setAttribute('lang',l);"
    "document.querySelectorAll('[data-set-lang]').forEach(function(b){"
    "b.setAttribute('aria-pressed',b.getAttribute('data-set-lang')===l?'true':'false');});"
    "document.querySelectorAll('[data-ph-'+l+']').forEach(function(e){"
    "e.setAttribute('placeholder',e.getAttribute('data-ph-'+l));});"
    "var t=d.getAttribute('data-title-'+l);if(t)document.title=t;}"
    "document.addEventListener('click',function(e){"
    "var b=e.target.closest&&e.target.closest('[data-set-lang]');"
    "if(b){e.preventDefault();set(b.getAttribute('data-set-lang'));}});"
    "var q=/[?&]lang=(\\w+)/.exec(location.search),start=d.getAttribute('data-lang');"
    "set(q&&L.indexOf(q[1])>=0?q[1]:start);})();"
)
