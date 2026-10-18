// Editing a site by hand, right in the preview — no AI involved: its text,
// and by clicking an element also its colors, photo and link.
//
// The preview is a sandboxed iframe we can't reach into, so for editing
// the page gets a small helper script of its own: it makes text editable
// and, when asked over postMessage, sends back the page's HTML with every
// trace of itself removed. The site's own scripts are paused while editing
// (so clicking a button puts the cursor in its label instead of opening a
// menu) and switched back on in the HTML that's saved — which therefore
// differs from the original only in the text that was changed.

const EDITOR_SCRIPT = `
(function () {
  var TEXT = 'h1,h2,h3,h4,h5,h6,p,li,a,button,span,td,th,label,small,strong,em,b,i,blockquote,figcaption,dt,dd,cite,q';
  document.querySelectorAll(TEXT).forEach(function (el) {
    if (!el.closest('[contenteditable]')) el.setAttribute('contenteditable', 'true');
  });

  var selected = null;   // the element the toolbar acts on
  var photo = null;      // an image (or background photo) under the last click
  var undo = [];         // [{ key, at, changes: [[element, attribute, old value]] }]

  function hex(css) {
    var m = /rgba?\\(([^)]+)\\)/.exec(css || '');
    if (!m) return null;
    var p = m[1].split(',').map(parseFloat);
    if (p.length > 3 && p[3] === 0) return null;
    return '#' + p.slice(0, 3).map(function (n) { return ('0' + Math.round(n).toString(16)).slice(-2); }).join('');
  }
  function bgUrl(el) { return /url\\(/.test(getComputedStyle(el).backgroundImage || ''); }
  function photoAt(x, y) {
    var list = document.elementsFromPoint(x, y);
    for (var i = 0; i < list.length; i++) {
      var el = list[i];
      if (el.tagName === 'IMG' || (el.tagName !== 'HTML' && bgUrl(el))) return el;
    }
    return null;
  }

  // A two-language site: tell the toolbar, so the person can edit either one.
  var langs = [];
  document.querySelectorAll('[data-l]').forEach(function (e) {
    var l = e.getAttribute('data-l');
    if (langs.indexOf(l) < 0) langs.push(l);
  });
  var originalLang = document.documentElement.getAttribute('data-lang');
  function reportLangs() {
    if (langs.length > 1) parent.postMessage({ type: 'vf-langs', languages: { all: langs, current: document.documentElement.getAttribute('data-lang') } }, '*');
  }
  reportLangs();

  function report() {
    var el = selected, link = el && el.closest('a');
    var cs = el && getComputedStyle(el);
    parent.postMessage({
      type: 'vf-select',
      info: !el ? null : {
        label: (el.innerText || el.getAttribute('alt') || '').trim().slice(0, 40) || el.tagName.toLowerCase(),
        color: hex(cs.color) || '#000000',
        bg: hex(cs.backgroundColor),
        photo: !!photo,
        href: link ? (link.getAttribute('href') || '') : null,
        canUp: el !== document.body,
        canUndo: undo.length > 0
      }
    }, '*');
  }
  function mark() {
    document.querySelectorAll('[data-vf-sel],[data-vf-photo]').forEach(function (e) {
      e.removeAttribute('data-vf-sel'); e.removeAttribute('data-vf-photo');
    });
    if (selected) selected.setAttribute('data-vf-sel', '');
    if (photo && photo !== selected) photo.setAttribute('data-vf-photo', '');
  }
  function select(el, ph) {
    selected = el; photo = ph; mark(); report();
  }

  // Remember what's about to change so Undo can put it back. Changes to the
  // same thing in quick succession (dragging a color picker) count as one.
  function record(key, el, attrs, also) {
    var last = undo[undo.length - 1], now = Date.now();
    if (last && last.key === key && last.el === el && now - last.at < 1500) { last.at = now; return; }
    var pairs = attrs.map(function (a) { return [el, a]; }).concat(also || []);
    undo.push({ key: key, el: el, at: now, changes: pairs.map(function (p) { return [p[0], p[1], p[0].getAttribute(p[1])]; }) });
  }

  window.addEventListener('click', function (e) {
    e.preventDefault(); e.stopPropagation();
    var el = e.target;
    if (el.nodeType !== 1) el = el.parentElement;
    if (!el) return;
    if (el === document.documentElement) el = document.body;
    select(el, photoAt(e.clientX, e.clientY));
  }, true);
  window.addEventListener('submit', function (e) { e.preventDefault(); e.stopPropagation(); }, true);

  function apply(cmd, value) {
    if (cmd === 'ping') return reportLangs();
    if (cmd === 'lang') {
      if (langs.indexOf(value) >= 0) { document.documentElement.setAttribute('data-lang', value); reportLangs(); }
      return;
    }
    if (cmd === 'undo') {
      var step = undo.pop();
      if (step) step.changes.forEach(function (c) {
        if (c[2] === null) c[0].removeAttribute(c[1]); else c[0].setAttribute(c[1], c[2]);
      });
      return report();
    }
    if (cmd === 'up') {
      if (selected && selected.parentElement && selected !== document.body) select(selected.parentElement, photo);
      return;
    }
    if (!selected) return;
    if (cmd === 'color' || cmd === 'bg') {
      record(cmd, selected, ['style']);
      if (cmd === 'color') selected.style.setProperty('color', value, 'important');
      else selected.style.setProperty('background', value, 'important');
    } else if (cmd === 'href') {
      var a = selected.closest('a');
      if (!a) return;
      record('href', a, ['href']);
      a.setAttribute('href', value);
    } else if (cmd === 'photo' && photo) {
      if (photo.tagName === 'IMG') {
        var sources = photo.parentElement && photo.parentElement.tagName === 'PICTURE'
          ? Array.prototype.map.call(photo.parentElement.querySelectorAll('source'), function (s) { return [s, 'srcset']; })
          : [];
        record('photo', photo, ['src', 'srcset', 'sizes', 'data-photo', 'data-photo-credit', 'hidden'], sources);
        photo.setAttribute('src', value);
        ['srcset', 'sizes', 'data-photo', 'data-photo-credit', 'hidden'].forEach(function (a) { photo.removeAttribute(a); });
        sources.forEach(function (p) { p[0].setAttribute('srcset', value); });
      } else {
        record('photo', photo, ['style', 'data-photo-bg', 'data-photo-credit']);
        var layers = getComputedStyle(photo).backgroundImage;
        // Keep any gradient laid over the photo; swap only the photo itself.
        var next = layers.replace(/url\\((["']?)[^)]*\\1\\)/, 'url("' + value + '")');
        photo.style.setProperty('background-image', next, 'important');
        photo.removeAttribute('data-photo-bg');
        photo.removeAttribute('data-photo-credit');
      }
    }
    report();
  }

  window.addEventListener('message', function (e) {
    if (!e.data) return;
    if (e.data.type === 'vf-cmd') return apply(e.data.cmd, e.data.value);
    if (e.data.type !== 'vf-get-html') return;
    var doc = document.documentElement.cloneNode(true);
    doc.querySelectorAll('[contenteditable]').forEach(function (el) { el.removeAttribute('contenteditable'); });
    // Looking at the other language mustn't change which one the site starts in.
    if (originalLang) doc.setAttribute('data-lang', originalLang);
    doc.querySelectorAll('[data-vf-sel],[data-vf-photo]').forEach(function (el) {
      el.removeAttribute('data-vf-sel'); el.removeAttribute('data-vf-photo');
    });
    doc.querySelectorAll('#vf-editor, #vf-editor-style').forEach(function (el) { el.remove(); });
    doc.querySelectorAll('script[data-vf-type]').forEach(function (s) {
      var type = s.getAttribute('data-vf-type');
      if (type) s.setAttribute('type', type); else s.removeAttribute('type');
      s.removeAttribute('data-vf-type');
    });
    parent.postMessage({ type: 'vf-html', id: e.data.id, html: '<!doctype html>\\n' + doc.outerHTML }, '*');
  });
})();
`

const EDITOR_STYLE = `
[contenteditable]:hover { outline: 2px dashed rgba(91, 141, 239, 0.8); outline-offset: 2px; cursor: text; }
[contenteditable]:focus { outline: 2px solid #5b8def; outline-offset: 2px; }
img:hover { outline: 2px dashed rgba(91, 141, 239, 0.8); outline-offset: -2px; cursor: pointer; }
[data-vf-photo] { outline: 3px solid #1479b8 !important; outline-offset: -3px; }
[data-vf-sel] { outline: 3px solid #ff9f1c !important; outline-offset: 2px; }
`

/** The page as shown while editing: its scripts paused, the helper added. */
export function withEditor(html: string): string {
  const paused = html.replace(/<script\b([^>]*)>/gi, (_tag, attrs: string) => {
    const type = /\btype\s*=\s*["']([^"']*)["']/i.exec(attrs)?.[1] ?? ''
    const rest = attrs.replace(/\btype\s*=\s*["'][^"']*["']/i, '')
    return `<script data-vf-type="${type}" type="text/plain"${rest}>`
  })
  const helper =
    `<style id="vf-editor-style">${EDITOR_STYLE}</style>` +
    `<script id="vf-editor">${EDITOR_SCRIPT}</script>`
  return /<\/body>/i.test(paused) ? paused.replace(/<\/body>/i, `${helper}</body>`) : paused + helper
}

/** Ask the editing iframe for its page, cleaned of the helper. */
export function requestEditedHtml(frame: HTMLIFrameElement): Promise<string> {
  const id = Math.random().toString(36).slice(2)
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      window.removeEventListener('message', onMessage)
      reject(new Error('The preview did not respond — try again.'))
    }, 3000)
    function onMessage(event: MessageEvent) {
      if (event.source !== frame.contentWindow || event.data?.type !== 'vf-html' || event.data.id !== id) return
      clearTimeout(timer)
      window.removeEventListener('message', onMessage)
      resolve(event.data.html)
    }
    window.addEventListener('message', onMessage)
    frame.contentWindow?.postMessage({ type: 'vf-get-html', id }, '*')
  })
}

/** What the toolbar needs to know about the clicked element. */
export type Selection = {
  label: string
  color: string // text color, #rrggbb
  bg: string | null // background color, null = transparent
  photo: boolean // there is a photo here that can be replaced
  href: string | null // the link this element is in, if any
  canUp: boolean
  canUndo: boolean
}

export type EditorCommand =
  | { cmd: 'color' | 'bg' | 'href' | 'photo' | 'lang'; value: string }
  | { cmd: 'up' | 'undo' }

/** A site with two languages: all of them, and the one shown right now. */
export type SiteLanguages = { all: string[]; current: string }
