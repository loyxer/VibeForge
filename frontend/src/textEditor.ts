// Editing a site's text by hand, right in the preview — no AI involved.
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
  // Clicks place the cursor; they don't follow links or run the page's handlers.
  ['click', 'submit'].forEach(function (type) {
    window.addEventListener(type, function (e) { e.preventDefault(); e.stopPropagation(); }, true);
  });
  window.addEventListener('message', function (e) {
    if (!e.data || e.data.type !== 'vf-get-html') return;
    var doc = document.documentElement.cloneNode(true);
    doc.querySelectorAll('[contenteditable]').forEach(function (el) { el.removeAttribute('contenteditable'); });
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
