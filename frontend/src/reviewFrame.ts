// The site as a client sees it on the review page: the page itself, working
// normally, plus a small helper script of ours. In "comment mode" a click
// doesn't follow links or run the site's handlers — it picks the element and
// tells the parent page which one (as a path from <body>, so the owner's
// comment can point at the same place). Elements that already have comments
// get numbered badges.

const REVIEW_SCRIPT = `
(function () {
  var commentMode = true, picked = null, marks = [];
  var badges = document.createElement('div');
  badges.id = 'vf-review-badges';
  document.body.appendChild(badges);

  function pathOf(el) {
    var parts = [];
    while (el && el !== document.body && el.nodeType === 1) {
      var tag = el.tagName.toLowerCase(), n = 1, s = el;
      while ((s = s.previousElementSibling)) if (s.tagName === el.tagName) n++;
      parts.unshift(tag + ':nth-of-type(' + n + ')');
      el = el.parentElement;
    }
    return 'body' + (parts.length ? '>' + parts.join('>') : '');
  }
  function labelOf(el) {
    var t = (el.innerText || el.getAttribute('alt') || el.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ');
    if (!t && el.tagName === 'IMG') return 'photo';
    return (t || el.tagName.toLowerCase()).slice(0, 60);
  }
  function target(e) {
    var el = e.target;
    if (el && el.nodeType !== 1) el = el.parentElement;
    if (!el || el === document.documentElement || el.closest('#vf-review-badges') || el.closest('[data-set-lang]') || el.closest('#vf-lang-switch')) return null;
    return el;
  }
  function clear(attr) {
    document.querySelectorAll('[' + attr + ']').forEach(function (e) { e.removeAttribute(attr); });
  }

  document.addEventListener('mouseover', function (e) {
    if (!commentMode) return;
    clear('data-vf-hover');
    var el = target(e);
    if (el) el.setAttribute('data-vf-hover', '');
  }, true);
  document.addEventListener('mouseout', function () { clear('data-vf-hover'); }, true);

  ['click', 'submit'].forEach(function (type) {
    document.addEventListener(type, function (e) {
      if (!commentMode) return;
      var el = type === 'click' ? target(e) : null;
      if (type === 'click' && !el) return;
      e.preventDefault(); e.stopPropagation();
      if (!el) return;
      clear('data-vf-pick');
      el.setAttribute('data-vf-pick', '');
      picked = el;
      parent.postMessage({ type: 'vf-pick', selector: pathOf(el), label: labelOf(el) }, '*');
    }, true);
  });

  function drawMarks() {
    badges.innerHTML = '';
    marks.forEach(function (m) {
      var el = null;
      try { el = document.querySelector(m.selector); } catch (_) {}
      if (!el || !el.getClientRects().length) return; // gone, or on a page that isn't shown
      var r = el.getBoundingClientRect();
      var b = document.createElement('button');
      b.type = 'button';
      b.textContent = m.n;
      b.className = m.resolved ? 'vf-review-badge vf-review-badge--done' : 'vf-review-badge';
      b.style.top = (r.top + window.scrollY - 10) + 'px';
      b.style.left = Math.max(0, r.left + window.scrollX - 10) + 'px';
      b.addEventListener('click', function (e) {
        e.preventDefault(); e.stopPropagation();
        parent.postMessage({ type: 'vf-badge', id: m.id }, '*');
      });
      badges.appendChild(b);
    });
  }
  setInterval(drawMarks, 1000);
  window.addEventListener('resize', drawMarks);

  window.addEventListener('message', function (e) {
    var d = e.data;
    if (!d) return;
    if (d.type === 'vf-mode') {
      commentMode = !!d.on;
      document.documentElement.classList.toggle('vf-review-on', commentMode);
      if (!commentMode) { clear('data-vf-hover'); clear('data-vf-pick'); }
    } else if (d.type === 'vf-marks') {
      marks = d.marks || []; drawMarks();
    } else if (d.type === 'vf-unpick') {
      clear('data-vf-pick');
    } else if (d.type === 'vf-focus') {
      var el = null;
      try { el = document.querySelector(d.selector); } catch (_) {}
      if (el) {
        // On another page of a several-page site: open that page first.
        var pg = el.closest('[data-page]');
        if (pg && window.__vfShowPage) window.__vfShowPage(pg.getAttribute('data-page'), false);
        el.scrollIntoView({ block: 'center', behavior: 'smooth' });
      }
    }
  });
  parent.postMessage({ type: 'vf-ready' }, '*');
})();
`

const REVIEW_STYLE = `
.vf-review-on [data-vf-hover] { outline: 2px dashed #1479b8 !important; outline-offset: 2px; cursor: crosshair !important; }
[data-vf-pick] { outline: 3px solid #ff9f1c !important; outline-offset: 2px; }
#vf-review-badges { position: absolute; top: 0; left: 0; width: 0; height: 0; z-index: 2147483640; }
.vf-review-badge { position: absolute; width: 24px; height: 24px; padding: 0; border: 2px solid #fff; border-radius: 50%;
  background: #ff9f1c; color: #1c1c1c; font: 800 12px/1 system-ui, sans-serif; cursor: pointer; box-shadow: 0 2px 6px rgba(0,0,0,.35); }
.vf-review-badge--done { background: #58cc02; color: #fff; }
`

/** The page as shown on the review page: working, with the helper added. */
export function withReviewHelper(html: string): string {
  const helper =
    `<style id="vf-review-style">${REVIEW_STYLE}</style>` + `<script id="vf-review">${REVIEW_SCRIPT}</script>`
  return /<\/body>/i.test(html) ? html.replace(/<\/body>/i, `${helper}</body>`) : html + helper
}

export type ReviewMark = { id: number; n: number; selector: string; resolved: boolean }
