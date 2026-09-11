"""Renders docs/help_data.py into a single self-contained help.html.

Run this whenever help_data.py changes, or whenever a page's behavior
changes enough that the docs would go stale:

    python docs/generate_help.py

Output goes to assets/help.html — the same assets/ folder already bundled
by build/build.py, so the generated file ships with the packaged .exe
automatically. The app opens it via QDesktopServices (see
app/ui/main_window.py's _open_help), which just launches it in the user's
default browser — no embedded browser engine dependency required.

Keep all styling/layout logic here; keep all actual documentation text in
help_data.py. That split is what makes updating the docs for a new page a
content-only change.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from help_data import HELP_VERSION, HELP_DATE, MODULES  # noqa: E402

_OUTPUT_PATH = Path(__file__).resolve().parents[1] / "assets" / "help.html"

_CSS = """
:root {
    --bg: #1e1f26;
    --bg-elevated: #26272f;
    --bg-sidebar: #16171d;
    --border: #2a2b33;
    --text: #e6e6ea;
    --text-muted: #9294a3;
    --accent: #5d72c9;
    --accent-strong: #7d90e0;
    --code-bg: #101116;
    --code-fg: #9fd88a;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
    margin: 0;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg);
    color: var(--text);
    display: flex;
    min-height: 100vh;
}
#sidebar {
    width: 280px;
    flex-shrink: 0;
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border);
    padding: 24px 16px;
    position: sticky;
    top: 0;
    height: 100vh;
    overflow-y: auto;
}
#sidebar .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 8px 20px 8px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 16px;
}
#sidebar .brand-title { font-size: 17px; font-weight: 700; }
#sidebar .brand-sub { font-size: 11px; color: var(--text-muted); }
#search {
    width: 100%;
    padding: 8px 10px;
    margin-bottom: 14px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text);
    font-size: 13px;
}
#search:focus { outline: 1px solid var(--accent); }
#sidebar nav a {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 6px;
    color: var(--text-muted);
    text-decoration: none;
    font-size: 13.5px;
    margin-bottom: 2px;
}
#sidebar nav a:hover { background: var(--bg-elevated); color: var(--text); }
#sidebar nav a.active { background: var(--accent); color: white; font-weight: 600; }
#sidebar nav a .nav-icon { font-size: 15px; width: 20px; text-align: center; }
main {
    flex: 1;
    max-width: 880px;
    padding: 48px 56px 120px 56px;
}
header.page-header {
    margin-bottom: 40px;
    padding-bottom: 24px;
    border-bottom: 1px solid var(--border);
}
header.page-header h1 {
    font-size: 32px;
    margin: 0 0 8px 0;
    background: linear-gradient(90deg, var(--accent-strong), #9fd88a);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
}
header.page-header p { color: var(--text-muted); font-size: 14.5px; margin: 0; }
.badge {
    display: inline-block;
    font-size: 11.5px;
    color: var(--text-muted);
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 3px 10px;
    margin-top: 12px;
}
section.module {
    margin-bottom: 56px;
    scroll-margin-top: 24px;
}
section.module .module-heading {
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 6px;
}
section.module .module-icon { font-size: 22px; }
section.module h2 { font-size: 22px; margin: 0; }
section.module .module-summary {
    color: var(--text-muted);
    font-size: 14px;
    margin: 0 0 18px 0;
    padding-left: 34px;
}
section.module .module-body { padding-left: 34px; }
section.module h3 { font-size: 15.5px; color: var(--accent-strong); margin: 22px 0 8px 0; }
section.module p { line-height: 1.65; font-size: 14.5px; margin: 0 0 12px 0; }
section.module ul, section.module ol { line-height: 1.65; font-size: 14.5px; padding-left: 22px; margin: 0 0 14px 0; }
section.module li { margin-bottom: 6px; }
section.module code {
    background: var(--code-bg);
    color: var(--code-fg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1px 6px;
    font-family: Consolas, monospace;
    font-size: 13px;
}
section.module a { color: var(--accent-strong); }
footer.doc-footer {
    color: var(--text-muted);
    font-size: 12px;
    padding-top: 24px;
    border-top: 1px solid var(--border);
}
.hidden { display: none !important; }
@media (max-width: 900px) {
    body { flex-direction: column; }
    #sidebar { width: 100%; height: auto; position: relative; }
    main { padding: 32px 20px; }
}
"""

_JS = """
const links = document.querySelectorAll('#sidebar nav a');
const sections = document.querySelectorAll('section.module');

function setActive(id) {
    links.forEach(a => a.classList.toggle('active', a.getAttribute('href') === '#' + id));
}

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) setActive(entry.target.id);
    });
}, { rootMargin: '-10% 0px -70% 0px' });
sections.forEach(s => observer.observe(s));

document.getElementById('search').addEventListener('input', (e) => {
    const q = e.target.value.trim().toLowerCase();
    sections.forEach(section => {
        const matches = q === '' || section.innerText.toLowerCase().includes(q);
        section.classList.toggle('hidden', !matches);
    });
    links.forEach(a => {
        const id = a.getAttribute('href').slice(1);
        const section = document.getElementById(id);
        a.classList.toggle('hidden', section && section.classList.contains('hidden'));
    });
});
"""


def _render_nav() -> str:
    items = [
        f'<a href="#{m["id"]}"><span class="nav-icon">{m["icon"]}</span>{m["title"]}</a>'
        for m in MODULES
    ]
    return "\n".join(items)


def _render_sections() -> str:
    parts = []
    for m in MODULES:
        body_html = "\n".join(m["body"])
        parts.append(f"""
<section class="module" id="{m['id']}">
    <div class="module-heading">
        <span class="module-icon">{m['icon']}</span>
        <h2>{m['title']}</h2>
    </div>
    <p class="module-summary">{m['summary']}</p>
    <div class="module-body">
        {body_html}
    </div>
</section>
""")
    return "\n".join(parts)


def generate() -> str:
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FFmpeg Studio — Help</title>
<style>{_CSS}</style>
</head>
<body>
<aside id="sidebar">
    <div class="brand">
        <span style="font-size:22px;">🎬</span>
        <div>
            <div class="brand-title">FFmpeg Studio</div>
            <div class="brand-sub">Help &amp; Documentation</div>
        </div>
    </div>
    <input id="search" type="text" placeholder="Search help…">
    <nav>
        {_render_nav()}
    </nav>
</aside>
<main>
    <header class="page-header">
        <h1>FFmpeg Studio Help</h1>
        <p>A complete guide to every page in the app — what it does, what each option means, and when to reach for it.</p>
        <span class="badge">Documents version: {HELP_VERSION} · Updated {HELP_DATE}</span>
    </header>

    {_render_sections()}

    <footer class="doc-footer">
        Generated from docs/help_data.py by docs/generate_help.py. Regenerate after any page's
        behavior changes — never hand-edit this file directly.
    </footer>
</main>
<script>{_JS}</script>
</body>
</html>
"""
    return html


def main() -> None:
    html = generate()
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Wrote {_OUTPUT_PATH} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
