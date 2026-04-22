"""Extract {% trans %} + _()/gettext_lazy strings from the repo → unique list.

Runs pure-Python (no xgettext / gettext binary required on Windows) so the
project can maintain .po files even without the system toolchain installed.
Writes to ``locale/strings.json`` — consumed by ``tools/i18n_compile.py`` to
build the .po / .mo files for each enabled LANGUAGES code.

Usage:
    python tools/i18n_extract.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOCALE = BASE / "locale"

TEMPLATE_ROOTS = [BASE / "templates", BASE / "apps"]
PY_ROOTS       = [BASE / "apps", BASE / "config"]

EXCLUDE_DIR_NAMES = {"migrations", "__pycache__", ".venv", "node_modules", "locale"}


# {% trans "..." %}  or  {% trans '...' %}
TRANS_RE = re.compile(r"""\{%\s*trans\s+(['"])(?P<msg>(?:\\.|(?!\1).)*)\1\s*(?:as\s+\w+\s*)?%\}""")

# {% blocktrans ... %}...{% endblocktrans %}  (handles multi-line)
BLOCKTRANS_RE = re.compile(
    r"""\{%\s*blocktrans(?:\s+[^%]*)?\s*%\}(?P<msg>.*?)\{%\s*endblocktrans\s*%\}""",
    re.DOTALL,
)

# _("..."), _('...'), gettext("..."), gettext_lazy("...")
PY_RE = re.compile(
    r"""(?<![\w.])(?:_|gettext|gettext_lazy|ugettext|ugettext_lazy)\(\s*(['"])(?P<msg>(?:\\.|(?!\1).)*)\1\s*[,)]""",
)


def _iter_files(roots: list[Path], suffixes: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in suffixes:
                continue
            if any(part in EXCLUDE_DIR_NAMES for part in path.parts):
                continue
            out.append(path)
    return out


def extract() -> dict[str, list[str]]:
    """Return {msgid: [relative_file_paths_where_seen...]} sorted by key."""
    hits: dict[str, set[str]] = {}

    for tpl in _iter_files(TEMPLATE_ROOTS, (".html",)):
        text = tpl.read_text(encoding="utf-8", errors="replace")
        rel = str(tpl.relative_to(BASE)).replace("\\", "/")
        for rx in (TRANS_RE, BLOCKTRANS_RE):
            for m in rx.finditer(text):
                msg = m.group("msg").strip()
                if msg:
                    hits.setdefault(msg, set()).add(rel)

    for py in _iter_files(PY_ROOTS, (".py",)):
        text = py.read_text(encoding="utf-8", errors="replace")
        rel = str(py.relative_to(BASE)).replace("\\", "/")
        for m in PY_RE.finditer(text):
            msg = m.group("msg").strip()
            # Skip purely technical strings
            if not msg or msg.isdigit():
                continue
            hits.setdefault(msg, set()).add(rel)

    # Normalise (decode simple backslash escapes produced by the regex)
    def _unescape(s: str) -> str:
        return s.replace("\\n", "\n").replace("\\t", "\t").replace("\\'", "'").replace('\\"', '"')

    return {
        _unescape(k): sorted(v)
        for k, v in sorted(hits.items(), key=lambda kv: kv[0].lower())
    }


def main() -> None:
    LOCALE.mkdir(parents=True, exist_ok=True)
    strings = extract()
    out_path = LOCALE / "strings.json"
    out_path.write_text(
        json.dumps(strings, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Extracted {len(strings)} unique strings -> {out_path}")


if __name__ == "__main__":
    main()
