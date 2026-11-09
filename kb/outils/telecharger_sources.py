"""Downloads the official texts listed in kb/sources.json and pins their SHA-256 fingerprint.

    python kb/outils/telecharger_sources.py              # downloads what is missing, records the fingerprints
    python kb/outils/telecharger_sources.py --verifier   # recomputes the fingerprints and reports any change

Files go to kb/originaux/ (not versioned); fingerprints to kb/originaux/empreintes.json.
If an official text changes online, --verifier reports it: the related provisions must then be reread.
"""
import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

from _chemin import KB

EXT = {"application/pdf": ".pdf", "text/html": ".html"}


def sha256(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 16), b""):
            h.update(bloc)
    return h.hexdigest()


def telecharger(url: str, dest_sans_ext: Path, delai: int = 60) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": "MEDIMCOM-KB/1.0 (hackathon research)"})
    with urllib.request.urlopen(req, timeout=delai) as rep:
        type_ = rep.headers.get_content_type()
        donnees = rep.read()
    ext = EXT.get(type_, ".pdf" if donnees[:4] == b"%PDF" else ".bin")
    dest = dest_sans_ext.with_suffix(ext)
    dest.write_bytes(donnees)
    return dest


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--verifier", action="store_true")
    p.add_argument("--manifeste", default=str(KB / "sources.json"))
    p.add_argument("--dossier", default=str(KB / "originaux"))
    a = p.parse_args(argv)
    dossier = Path(a.dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    fichier_empreintes = dossier / "empreintes.json"
    empreintes = json.loads(fichier_empreintes.read_text(encoding="utf-8")) if fichier_empreintes.exists() else {}
    sources = [s for s in json.loads(Path(a.manifeste).read_text(encoding="utf-8"))["sources"] if s.get("download_url")]
    problemes = 0
    for s in sources:
        connu = empreintes.get(s["id"])
        try:
            if a.verifier:
                if not connu:
                    print(f"?  {s['id']} : jamais téléchargé")
                    problemes += 1
                    continue
                chemin = telecharger(s["download_url"], dossier / f"{s['id']}.verif")
                nouvelle = sha256(chemin)
                chemin.unlink()
                if nouvelle != connu["sha256"]:
                    print(f"!! {s['id']} : le texte en ligne a changé depuis le {connu['date']} — relire les fiches")
                    problemes += 1
                else:
                    print(f"ok {s['id']} : inchangé")
            elif connu and (dossier / connu["fichier"]).exists():
                print(f"-- {s['id']} : déjà présent")
            else:
                chemin = telecharger(s["download_url"], dossier / s["id"])
                empreintes[s["id"]] = {"url": s["download_url"], "fichier": chemin.name, "sha256": sha256(chemin),
                                       "octets": chemin.stat().st_size, "date": date.today().isoformat()}
                print(f"+  {s['id']} : {chemin.name} ({chemin.stat().st_size} octets)")
        except Exception as e:  # network, 404, timeout…
            print(f"xx {s['id']} : échec ({e.__class__.__name__}: {e})")
            problemes += 1
    fichier_empreintes.write_text(json.dumps(empreintes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(sources)} sources téléchargeables · {problemes} problème(s)")
    return 1 if problemes else 0


if __name__ == "__main__":
    sys.exit(main())
