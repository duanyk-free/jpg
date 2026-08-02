#!/usr/bin/env python3
"""Build a single-file standalone jpg image tool.

Generates: jpg (single executable Python file)
  - Embeds all HTML/CSS/JS from static/ as binary constants
  - Keeps Flask API routes intact
  - Requires: pip install flask pillow rembg

Usage:
  python3 build-standalone.py           # generate ./jpg
  python3 build-standalone.py --run     # generate + immediately launch
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "static"

FILES = {
    "index.html": "text/html; charset=utf-8",
    "app.js":     "application/javascript; charset=utf-8",
    "style.css":  "text/css; charset=utf-8",
}


def embed(path):
    """Read a file and return its base64-encoded bytes representation."""
    data = path.read_bytes()
    # Use repr for safe embedding in Python source
    return repr(data)


def build():
    # Read all assets
    assets = {}
    for fname in FILES:
        fpath = STATIC_DIR / fname
        if not fpath.exists():
            print(f"ERROR: {fpath} not found")
            sys.exit(1)
        assets[fname] = (FILES[fname], embed(fpath))
        print(f"  ✓ embedded {fname}  ({fpath.stat().st_size:,} bytes)")

    # Build embedded dict
    entries = []
    for fname, (ct, literal) in assets.items():
        entries.append(f'        "{fname}": ("{ct}", {literal}),')
    embedded_block = "\n".join(entries)

    # Read the standalone template
    template_path = ROOT / "jpg-standalone.py"
    code = template_path.read_text("utf-8")

    # Replace the _load_static function
    old_load = '''def _load_static():
    """Load static files from disk (dev mode) or use embedded data."""
    global _STATIC
    files = {
        "index.html": "text/html; charset=utf-8",
        "app.js":     "application/javascript; charset=utf-8",
        "style.css":  "text/css; charset=utf-8",
    }
    for filename, ct in files.items():
        path = APP_DIR / filename
        if path.exists():
            _STATIC[filename] = (ct, path.read_bytes())'''

    new_load = f'''def _load_static():
    """Load static files from embedded data (or fallback to disk)."""
    global _STATIC
    # Built-in embedded assets (auto-generated)
    _STATIC = {{
{embedded_block}
    }}
    # If static/ directory exists, prefer disk versions (for development)
    if APP_DIR.is_dir():
        for filename, ct in [
            ("index.html", "text/html; charset=utf-8"),
            ("app.js", "application/javascript; charset=utf-8"),
            ("style.css", "text/css; charset=utf-8"),
        ]:
            path = APP_DIR / filename
            if path.exists():
                _STATIC[filename] = (ct, path.read_bytes())'''

    if old_load in code:
        code = code.replace(old_load, new_load)
    else:
        print("ERROR: Could not find _load_static function to patch")
        sys.exit(1)

    # Write output
    out = ROOT / "jpg"
    out.write_text(code, "utf-8")
    out.chmod(0o755)
    print(f"\n  ✅ {out}  ({out.stat().st_size:,} bytes)")
    print(f"  Usage:")
    print(f"    ./jpg --port 9000")
    print(f"    ./jpg --no-browser")
    return out


def main():
    print("Building standalone jpg tool...\n")
    out = build()
    if "--run" in sys.argv:
        print("\n  Starting...\n")
        import subprocess
        subprocess.run([sys.executable, str(out), "--no-browser"])


if __name__ == "__main__":
    main()
