#!/usr/bin/env python3
"""Preview README.md the way github.com renders it, in both colour schemes (and optionally at phone width).

    python3 tools/preview.py            # writes .preview/{light,dark}.html and .png
    python3 tools/preview.py --mobile   # also .preview/{light,dark}-m390.png
    python3 tools/preview.py --no-shot  # HTML only (no Chrome needed)

Needs: the GitHub CLI (`gh auth login`) for GitHub's own markdown renderer, Google Chrome for
screenshots, and Pillow (optional: crops the page and cuts 1100px tiles). The raw.githubusercontent
asset URLs in README.md are rewritten to the local assets/ folder, so unpushed assets preview too.
"""
import os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, ".preview")
CHROME = os.environ.get("CHROME") or next((c for c in (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser") if os.path.exists(c)), None)
RAW_PREFIXES = [
    "https://raw.githubusercontent.com/YoctoHan/YoctoHan/main/assets/",
    "https://raw.githubusercontent.com/YoctoHan/YoctoHan/refs/heads/main/assets/",
    "https://github.com/YoctoHan/YoctoHan/blob/main/assets/",
    "https://github.com/YoctoHan/YoctoHan/raw/main/assets/",
]
VIEW_ANCHOR = r'<a target="_blank" rel="noopener noreferrer nofollow" href="[^"]*">'


def gh_markdown(readme_path):
    return subprocess.run(
        ["gh", "api", "markdown", "-f", "mode=markdown", "-f", "context=YoctoHan/YoctoHan", "-F", f"text=@{readme_path}"],
        check=True, capture_output=True, text=True).stdout


def repair_github_markup(html):
    """The markdown API wraps every <img> in a 'view image' anchor and pushes the <img> out of
    <a><picture>…</picture></a>; github.com itself keeps <picture> intact, so undo that here."""
    html = re.sub(r'(<picture>\s*(?:<source[^>]*>\s*)+)</picture>(\s*</themed-picture>\s*</a>)\s*' + VIEW_ANCHOR + r'\s*(<img[^>]*>)\s*</a>',
                  r'\1\3</picture>\2', html, flags=re.S)
    return re.sub(VIEW_ANCHOR + r'\s*(<img[^>]*>)\s*</a>', r'\1', html, flags=re.S)


def pick_theme(html, mode):
    """Resolve every <picture> to a plain <img> for `mode` (headless Chrome's prefers-color-scheme is unreliable)."""
    if mode == "light":
        return re.sub(r'<source\b[^>]*>', '', html)

    def repl(m):
        block = m.group(0)
        src = None
        for s in re.finditer(r'<source\b([^>]*)>', block):
            if re.search(r'media="\(prefers-color-scheme:\s*dark\)"', s.group(1)):
                mm = re.search(r'srcset="([^"]+)"', s.group(1))
                if mm:
                    src = mm.group(1)
                    break
        img = re.search(r'<img\b([^>]*)>', block)
        if not (src and img):
            return block
        return '<img' + re.sub(r'\ssrc="[^"]*"', f' src="{src}"', img.group(1)) + '>'
    return re.sub(r'<picture>.*?</picture>', repl, html, flags=re.S)


def wrap(body, mode):
    bg = "#0d1117" if mode == "dark" else "#ffffff"
    border = "#30363d" if mode == "dark" else "#d0d7de"
    return f"""<!doctype html>
<html lang="en" data-color-mode="{mode}"><head><meta charset="utf-8"><meta name="color-scheme" content="{mode}">
<title>README preview ({mode})</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.8.1/github-markdown-{mode}.min.css">
<style>
  html,body{{margin:0;background:{bg};}}
  .wrap{{max-width:896px;margin:0 auto;padding:24px 0 40px;}}   /* the profile page's README column */
  .markdown-body{{box-sizing:border-box;padding:32px;border:1px solid {border};border-radius:6px;background:{bg};}}
  .markdown-body img{{max-width:100%;}}
</style></head>
<body><div class="wrap"><article class="markdown-body">
{body}
</article></div></body></html>
"""


def chrome_shot(url, png_path, dark):
    if not CHROME:
        raise SystemExit("Chrome not found; set CHROME=/path/to/chrome or use --no-shot")
    with tempfile.TemporaryDirectory() as prof:
        args = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
                f"--user-data-dir={prof}", "--window-size=1100,6000", "--virtual-time-budget=15000",
                "--allow-file-access-from-files", f"--screenshot={png_path}", url]
        if dark:
            args.insert(1, "--force-dark-mode")
        try:
            subprocess.run(args, capture_output=True, timeout=75)
        except subprocess.TimeoutExpired:      # Chrome can linger on a hung request after the shot is written
            subprocess.run(["pkill", "-f", prof], capture_output=True)
    if not os.path.exists(png_path):
        raise SystemExit(f"no screenshot produced for {url}")


def trim(png_path, width=None, tiles=False):
    """Crop trailing background rows (and to `width`), then optionally cut 1100px tiles. Needs Pillow."""
    try:
        from PIL import Image
    except ImportError:
        return
    im = Image.open(png_path).convert("RGB")
    if width:
        im = im.crop((0, 0, width, im.height))
    w, h = im.size
    px = im.load()
    bg = px[5, 5] if width else px[5, h - 5]
    bottom = h
    while bottom > 200 and all(sum(abs(px[x, bottom - 1][c] - bg[c]) for c in range(3)) < 12 for x in range(0, w, 13)):
        bottom -= 1
    im = im.crop((0, 0, w, min(h, bottom + 40)))
    im.save(png_path)
    if tiles:
        for i, top in enumerate(range(0, im.height, 1100), start=1):
            im.crop((0, top, w, min(im.height, top + 1100))).save(f"{png_path[:-4]}-p{i}.png")


def main():
    mobile, noshot = "--mobile" in sys.argv, "--no-shot" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    shutil.rmtree(os.path.join(OUT, "assets"), ignore_errors=True)
    shutil.copytree(os.path.join(REPO, "assets"), os.path.join(OUT, "assets"))
    body = gh_markdown(os.path.join(REPO, "README.md"))
    for p in RAW_PREFIXES:
        body = body.replace(p, "assets/")
    body = repair_github_markup(body)
    for mode in ("light", "dark"):
        html_path = os.path.join(OUT, f"{mode}.html")
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(wrap(pick_theme(body, mode), mode))
        print("wrote", html_path)
        if noshot:
            continue
        png = os.path.join(OUT, f"{mode}.png")
        chrome_shot("file://" + html_path, png, mode == "dark")
        trim(png, tiles=True)
        print("wrote", png)
        if mobile:   # headless Chrome refuses windows narrower than ~500px: render inside a 390px iframe
            wrapper = os.path.join(OUT, f"{mode}-m390.html")
            with open(wrapper, "w", encoding="utf-8") as fh:
                fh.write('<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#888}'
                         'iframe{border:0;display:block;width:390px;height:6000px}</style></head>'
                         f'<body><iframe src="{mode}.html"></iframe></body></html>')
            mpng = os.path.join(OUT, f"{mode}-m390.png")
            chrome_shot("file://" + wrapper, mpng, mode == "dark")
            trim(mpng, width=390)
            print("wrote", mpng)


if __name__ == "__main__":
    main()
