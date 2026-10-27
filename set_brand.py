"""swap the brand name and domain everywhere on the site in one go.

  py set_brand.py "New Name" newdomain.ca

brand.json holds the current values (placeholders [BRAND] and [DOMAIN] until Gabriel picks a name). every html, xml, txt and
md file gets current -> new, CNAME gets the domain, and brand.json is updated so it can run again later.
og.png still shows the old name: re-render it after picking (ask Claude, the template lives in the session scratchpad).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "brand.json"


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    new_brand, new_domain = sys.argv[1].strip(), sys.argv[2].strip().lower().removeprefix("https://").strip("/")
    cur = json.loads(STATE.read_text(encoding="utf-8"))
    changed = []
    for f in ROOT.rglob("*"):
        if f.suffix not in {".html", ".xml", ".txt", ".md"} or ".git" in f.parts:
            continue
        s = f.read_text(encoding="utf-8")
        t = s.replace(cur["domain"], new_domain).replace(cur["brand"], new_brand)
        if t != s:
            f.write_text(t, encoding="utf-8")
            changed.append(str(f.relative_to(ROOT)))
    (ROOT / "CNAME").write_text(new_domain + "\n", encoding="utf-8")
    STATE.write_text(json.dumps({"brand": new_brand, "domain": new_domain}, indent=2) + "\n", encoding="utf-8")
    print(f"{cur['brand']} -> {new_brand}, {cur['domain']} -> {new_domain}")
    print("changed:", ", ".join(changed) or "nothing")


if __name__ == "__main__":
    main()
