"""Constitue, sur votre ordinateur, la base de connaissances complète de MEDIMCOM IA, bien rangée.

    python outils/constituer_base.py                                  # -> ~/MEDIMCOM_base (tout, avec téléchargements)
    python outils/constituer_base.py --sortie D:/MEDIMCOM_base        # autre dossier
    python outils/constituer_base.py --sans-reseau                    # sans Internet : Markdown, rangement, jeu de données
    python outils/constituer_base.py --etapes juridique               # une seule étape (juridique, pictogrammes, donnees)

Dossier produit :

    MEDIMCOM_base/
    ├── LISEZMOI.md                       sommaire, chiffres, licences, date
    ├── 1_textes_juridiques/
    │   ├── index.md                      tous les textes : titre, niveau de vérification, lien officiel, fichier local
    │   ├── AE_Emirats/  CM_Cameroun/  International/
    │   │   ├── <ID>.md                   le texte en Markdown : métadonnées, dispositions (article, résumé, citation),
    │   │   │                             règles du juriste et lacunes qui le citent
    │   │   └── originaux/<ID>.pdf        le texte officiel téléchargé (quand un lien de téléchargement existe)
    ├── 2_pictogrammes/
    │   ├── catalogue.csv  catalogue.md   chaque idée : catégorie, libellés fr / en / ar, description, sources disponibles
    │   ├── planche.html                  toutes les idées, avec l'image de chaque source côte à côte
    │   ├── par_source/<base>/            images telles que téléchargées (+ LICENCE.md de la base)
    │   └── par_idee/<catégorie>/<ID>/    description.md + une image par source (<base>.png) + icône de démonstration
    ├── 3_jeu_de_donnees_assistant/       cas fictifs, conversations d'entraînement / validation / test,
    │                                     tableau à faire valider par un médecin, fiche de données
    └── journal_constitution.json         ce qui a été téléchargé (empreinte SHA-256), copié, refusé, avec la date

Les images ARASAAC sont téléchargées par pictogrammes/bases/telecharger_arasaac.py (lancé ici sauf avec --sans-reseau) ;
les images Tawasol, Mulberry ou Sclera déposées à la main sont importées par importer_fichiers.py. Relancer le script
met tout à jour sans rien dupliquer.
"""
import argparse
import csv
import hashlib
import html
import json
import re
import shutil
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils"))
from medimcom.base import BaseConnaissances  # noqa: E402
from medimcom import bibliotheque as B  # noqa: E402

KB = RACINE / "kb"
BASES = RACINE / "pictogrammes" / "bases"
DOSSIERS_PAYS = {"AE": "AE_Emirats", "CM": "CM_Cameroun"}
NIVEAUX = {"official_text": "texte officiel (lu sur le site de l'éditeur officiel)",
           "secondary_source": "source secondaire (cabinet, presse, base juridique) : lire le texte officiel avant usage réel",
           "to_confirm": "à confirmer : contenu pas encore lu"}
CATEGORIES = {"reponse": "1_reponses", "personne": "2_personnes", "corps": "3_corps", "symptome": "4_symptomes",
              "emotion": "5_ressenti", "soin": "6_soins", "temps": "7_temps", "nombre": "8_nombres"}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _pays(s: dict) -> str:
    if s["role"] == "national_cm" or s["id"].startswith("CM-"):
        return "CM"
    if s["role"] == "primary" or s["id"].startswith("AE-"):
        return "AE"
    return "International"


def _nom_fichier(texte: str) -> str:
    return re.sub(r"[^\w.-]+", "_", texte).strip("_")


# --------------------------------------------------------------------------------------------- 1. textes juridiques
def etape_juridique(sortie: Path, reseau: bool, journal: dict) -> int:
    base = BaseConnaissances(KB)
    regles = {}
    for fichier in ("regles_uae.json", "regles_cm.json"):
        r = json.loads((KB / fichier).read_text(encoding="utf-8"))
        for chemin, x in _regles(r):
            for fid in x.get("fiches", []):
                regles.setdefault(fid, []).append(f"{fichier.replace('regles_', '').replace('.json', '').upper()} · "
                                                  f"{x.get('id', chemin)} → {x.get('niveau', '?')} : {x.get('detail', '')}")
    lacunes = {}
    for l in base.lacunes.values():
        for x in l["existing_texts"] + l["global_examples"]:
            lacunes.setdefault(x["fiche"], []).append(f"{l['id']} — {l['title']}")
    dossier = sortie / "1_textes_juridiques"
    lignes_index = ["# Textes juridiques de MEDIMCOM IA", "",
                    f"{len(base.sources)} textes, {len(base.fiches)} dispositions. Le texte arabe des lois des Émirats prévaut ; "
                    "chaque fichier indique son niveau de vérification.", "",
                    "| Pays | Identifiant | Texte | Vérification | Fichier | Original | Lien |", "|---|---|---|---|---|---|---|"]
    for s in sorted(base.sources.values(), key=lambda s: (_pays(s), s["id"])):
        pays = _pays(s)
        rep = dossier / DOSSIERS_PAYS.get(pays, "International")
        rep.mkdir(parents=True, exist_ok=True)
        fiches = [f for f in base.fiches.values() if f["source"] == s["id"]]
        md = [f"---", f"id: {s['id']}", f"titre: \"{s['title']}\"", f"titre_court: \"{s.get('short_title', '')}\"",
              f"pays: {pays}", f"autorite: \"{s.get('authority', '')}\"", f"type: {s.get('type', '')}",
              f"date: {str(s.get('date_issued', '')).split(' ')[0]}", f"en_vigueur: \"{s.get('date_in_force', '')}\"",
              f"verification: {s['verification']}", f"role: {s['role']}", f"lien: {s['url']}", f"---", "",
              f"# {s['title']}", "",
              f"- **Autorité :** {s.get('authority', '')}", f"- **Date :** {str(s.get('date_issued', '')).split(' ')[0]}",
              f"- **Statut :** {s.get('legal_status', '')}", f"- **Niveau de vérification :** {NIVEAUX[s['verification']]}",
              f"- **Lien ({'officiel' if s['verification'] == 'official_text' else 'source consultée'}) :** <{s['url']}>"]
        if s.get("note"):
            md.append(f"- **Note :** {s['note']}")
        if s.get("used_for"):
            md.append(f"- **Utilisé pour :** {'; '.join(s['used_for'])}")
        md += ["", f"## Dispositions ({len(fiches)})", ""]
        for f in fiches:
            md += [f"### {f['id']} — {f['ref']} — {f['title']}", "", f["text"], ""]
            if f.get("quote"):
                md += [f"> « {f['quote']} »", ""]
            md += [f"*Base juridique : {f['basis']} · thèmes : {', '.join(f['themes'])} · utilisé en : {', '.join(f['modes'])}*", ""]
            if regles.get(f["id"]):
                md += ["Règles du juriste qui citent cette disposition :", ""] + [f"- {r}" for r in regles[f["id"]]] + [""]
            if lacunes.get(f["id"]):
                md += ["Lacunes du droit liées :", ""] + [f"- {l}" for l in lacunes[f["id"]]] + [""]
        (rep / f"{_nom_fichier(s['id'])}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        original = "—"
        if reseau and s.get("download_url"):
            original = _telecharger_original(s, rep / "originaux", journal)
        elif (rep / "originaux").exists():
            existants = list((rep / "originaux").glob(f"{_nom_fichier(s['id'])}.*"))
            original = f"[{existants[0].name}]({DOSSIERS_PAYS.get(pays, 'International')}/originaux/{existants[0].name})" if existants else "—"
        lignes_index.append(f"| {pays} | {s['id']} | {s['title'].replace('|', '/')} | {s['verification']} | "
                            f"[{s['id']}.md]({DOSSIERS_PAYS.get(pays, 'International')}/{_nom_fichier(s['id'])}.md) | {original} | <{s['url']}> |")
    (dossier / "index.md").write_text("\n".join(lignes_index) + "\n", encoding="utf-8")
    return len(base.sources)


def _regles(r: dict):
    for cle, v in r.items():
        if isinstance(v, list):
            for x in v:
                if isinstance(x, dict) and "fiches" in x:
                    yield cle, x
        elif isinstance(v, dict):
            if "fiches" in v:
                yield cle, v
            for k2, x in v.items():
                if isinstance(x, dict) and "fiches" in x:
                    yield f"{cle}.{k2}", x
                if isinstance(x, dict):
                    for c in x.get("contre_indications", []):
                        yield f"{cle}.{k2}", c


def _telecharger(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "MEDIMCOM-KB/1.0 (hackathon UIT, recherche)"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read(), r.headers.get_content_type()


def _module(nom: str):
    """Charge un script de pictogrammes/bases/ en le faisant travailler sur le dossier BASES."""
    import importlib
    if str(BASES) not in sys.path:
        sys.path.insert(0, str(BASES))
    m = importlib.import_module(nom)
    m.ICI = BASES
    return m


def _telecharger_original(s: dict, rep: Path, journal: dict) -> str:
    rep.mkdir(parents=True, exist_ok=True)
    nom = _nom_fichier(s["id"])
    existants = list(rep.glob(f"{nom}.*"))
    if existants:
        journal["textes"].append({"id": s["id"], "fichier": str(existants[0]), "sha256": _sha(existants[0]), "etat": "déjà présent"})
        return f"[{existants[0].name}](originaux/{existants[0].name})"
    try:
        donnees, type_ = _telecharger(s["download_url"])
        ext = ".pdf" if donnees[:4] == b"%PDF" or type_ == "application/pdf" else ".html" if "html" in type_ else ".bin"
        f = rep / f"{nom}{ext}"
        f.write_bytes(donnees)
        journal["textes"].append({"id": s["id"], "url": s["download_url"], "fichier": str(f), "sha256": _sha(f), "etat": "téléchargé"})
        print(f"  ✔ {s['id']} : {f.name} ({len(donnees) // 1024} Ko)")
        return f"[{f.name}](originaux/{f.name})"
    except Exception as e:
        journal["textes"].append({"id": s["id"], "url": s["download_url"], "etat": f"échec : {e}"})
        print(f"  ✖ {s['id']} : téléchargement impossible ({e})")
        return "échec (voir journal)"


# --------------------------------------------------------------------------------------------- 2. pictogrammes
def etape_pictogrammes(sortie: Path, reseau: bool, journal: dict) -> int:
    if reseau:
        print("Recherche et téléchargement des pictogrammes ARASAAC (quelques minutes)…")
        try:
            _module("telecharger_arasaac").main([])
        except (Exception, SystemExit) as e:
            journal["pictogrammes"].append({"etape": "arasaac", "etat": f"échec : {e}"})
            print(f"  ✖ ARASAAC indisponible ({e}) : on continue avec ce qui est déjà présent")
    _module("importer_fichiers").main([])          # images Tawasol, Mulberry, Sclera déposées à la main
    B.charger_bases(BASES)
    bases = json.loads((BASES / "bases.json").read_text(encoding="utf-8"))["bases"]
    manifeste = json.loads((BASES / "manifeste_externe.json").read_text(encoding="utf-8")) if (BASES / "manifeste_externe.json").exists() else {"pictogrammes": {}}
    # toutes les images disponibles, par source : celles du manifeste, plus toutes celles déposées dans images/<base>/
    par_source: dict[str, dict[str, Path]] = {}
    for d in sorted((BASES / "images").glob("*")) if (BASES / "images").exists() else []:
        for f in sorted(d.iterdir()) if d.is_dir() else []:
            motif = _refus(d.name, f, bases)
            if motif:
                journal["pictogrammes"].append({"fichier": str(f), "etat": f"écarté : {motif}"})
            else:
                par_source.setdefault(d.name, {})[f.stem.upper()] = f
    dossier = sortie / "2_pictogrammes"
    for base_nom, images in par_source.items():
        rep = dossier / "par_source" / base_nom
        rep.mkdir(parents=True, exist_ok=True)
        b = bases.get(base_nom, {})
        (rep / "LICENCE.md").write_text(f"# {b.get('nom', base_nom)}\n\n- Site : {b.get('url', '')}\n- Licence : {b.get('licence', '?')}\n"
                                        f"- Usage commercial : {b.get('commercial')}\n- Attribution obligatoire : {b.get('attribution', '')}\n",
                                        encoding="utf-8")
        for ident, f in images.items():
            _copier(f, rep / f"{ident}{f.suffix.lower()}", journal)
    lignes_csv, cartes, md = [], [], ["# Catalogue des pictogrammes par idée", "",
                                      "| Catégorie | Identifiant | Français | English | العربية | Sources disponibles | Description |",
                                      "|---|---|---|---|---|---|---|"]
    for ident, v in sorted(B.VOCABULAIRE.items(), key=lambda x: (CATEGORIES.get(x[1]["categorie"], "9"), x[0])):
        cat = CATEGORIES.get(v["categorie"], "9_autres")
        rep = dossier / "par_idee" / cat / ident
        rep.mkdir(parents=True, exist_ok=True)
        sources = []
        for base_nom, images in par_source.items():
            if ident in images:
                _copier(images[ident], rep / f"{base_nom}{images[ident].suffix.lower()}", journal)
                m = manifeste["pictogrammes"].get(ident, {})
                sources.append({"base": base_nom, "fichier": f"{base_nom}{images[ident].suffix.lower()}",
                                "lien": m.get("url", "") if m.get("base") == base_nom else bases.get(base_nom, {}).get("url", ""),
                                "licence": bases.get(base_nom, {}).get("licence", "?"), "utilisee_par_le_prototype": m.get("base") == base_nom})
        if ident in B.CATALOGUE:
            (rep / "icone_demonstration.svg").write_text(B._cadre(B.CATALOGUE[ident][0], B.CATALOGUE[ident][4], v["fr"]) , encoding="utf-8")
        desc = [f"# {v['fr']} ({ident})", "", f"- **Catégorie :** {v['categorie']}", f"- **Français :** {v['fr']}",
                f"- **English :** {v['en']}", f"- **العربية :** {v['ar']} (à faire relire par un locuteur natif)", "",
                "## Description", "", v.get("description", ""), "",
                "## Mots de recherche dans les bases", "", f"- fr : {', '.join(v['recherche']['fr'])}", f"- en : {', '.join(v['recherche']['en'])}", "",
                "## Images disponibles", ""]
        desc += [f"- `{s['fichier']}` — {s['base']} ({s['licence']})" + (" — **utilisée par le prototype**" if s["utilisee_par_le_prototype"] else "")
                 + (f" — {s['lien']}" if s["lien"] else "") for s in sources] or ["- aucune image de base installée (lancer le script avec Internet)"]
        if ident in B.CATALOGUE:
            desc.append("- `icone_demonstration.svg` — icône de démonstration du prototype (générée par code)")
        (rep / "description.md").write_text("\n".join(desc) + "\n", encoding="utf-8")
        noms = ", ".join(s["base"] for s in sources) or "—"
        lignes_csv.append([ident, v["categorie"], v["fr"], v["en"], v["ar"], v.get("description", ""), noms,
                           f"par_idee/{cat}/{ident}/", "oui" if v.get("nouveau") else "non"])
        md.append(f"| {v['categorie']} | [{ident}](par_idee/{cat}/{ident}/description.md) | {v['fr']} | {v['en']} | {v['ar']} | {noms} | {v.get('description', '')} |")
        imgs = "".join(f'<figure><img src="par_idee/{cat}/{ident}/{s["fichier"]}" alt=""><figcaption>{html.escape(s["base"])}</figcaption></figure>' for s in sources)
        if ident in B.CATALOGUE:
            imgs += f'<figure><img src="par_idee/{cat}/{ident}/icone_demonstration.svg" alt=""><figcaption>démonstration</figcaption></figure>'
        cartes.append(f'<section><h3>{html.escape(v["fr"])} <small>{ident} · {html.escape(v["categorie"])}</small></h3>'
                      f'<p>{html.escape(v.get("description", ""))}</p>{imgs or "<p><i>aucune image</i></p>"}</section>')
    with open(dossier / "catalogue.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["identifiant", "categorie", "francais", "anglais", "arabe", "description", "sources_disponibles", "dossier", "notion_ajoutee"])
        w.writerows(lignes_csv)
    (dossier / "catalogue.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (dossier / "planche.html").write_text(f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Pictogrammes MEDIMCOM IA</title>
<style>body{{font:14px system-ui;margin:16px;background:#fff;color:#1E2B31}}section{{border-top:1px solid #ddd;padding:6px 0}}
h3{{margin:4px 0}}small{{color:#5A6A72;font-weight:400}}figure{{display:inline-block;margin:0 8px 4px 0;text-align:center}}
img{{width:96px;height:96px;object-fit:contain;border:1px solid #eee;border-radius:8px}}figcaption{{font-size:11px;color:#5A6A72}}</style></head>
<body><h1>Pictogrammes par idée</h1><p>Chaque idée avec l'image de chaque source disponible. Attributions : voir par_source/*/LICENCE.md.</p>
{"".join(cartes)}</body></html>""", encoding="utf-8")
    return len(B.VOCABULAIRE)


def _refus(base_nom: str, f: Path, bases: dict) -> str:
    """Mêmes contrôles qu'importer_fichiers.py : base déclarée et autorisée, identifiant connu, vrai fichier image sûr."""
    b, ext = bases.get(base_nom), f.suffix.lower()
    if b is None:
        return "base non déclarée dans bases.json"
    if b.get("autorisation_ecrite_requise") and not b.get("autorisation_ecrite_obtenue"):
        return f"{b['nom']} : accord écrit de l'éditeur non obtenu"
    if f.stem.upper() not in B.VOCABULAIRE:
        return "identifiant absent du vocabulaire"
    if ext == ".svg":
        return "" if B._svg_sur(f.read_text(encoding="utf-8", errors="replace")) else "SVG non sûr"
    signature = {".png": b"\x89PNG", ".jpg": b"\xff\xd8", ".jpeg": b"\xff\xd8"}.get(ext)
    if signature is None:
        return "format non accepté (PNG, JPEG ou SVG)"
    return "" if f.read_bytes().startswith(signature) else f"faux fichier {ext}"


def _copier(src: Path, dest: Path, journal: dict) -> None:
    if not dest.exists() or _sha(dest) != _sha(src):
        shutil.copy2(src, dest)
        journal["pictogrammes"].append({"fichier": str(dest), "source": str(src), "sha256": _sha(dest)})


# --------------------------------------------------------------------------------------------- 3. jeu de données
def etape_donnees(sortie: Path, variantes: int, journal: dict) -> int:
    import jeu_assistant
    r = jeu_assistant.construire(sortie / "3_jeu_de_donnees_assistant", variantes)
    shutil.copy2(RACINE / "donnees" / "presentations_cliniques.json", sortie / "3_jeu_de_donnees_assistant" / "presentations_cliniques.json")
    journal["donnees"] = r
    return r["cas"]


def main(argv=None):
    p = argparse.ArgumentParser(description="Constitue la base de connaissances MEDIMCOM IA sur cet ordinateur.")
    p.add_argument("--sortie", default=str(Path.home() / "MEDIMCOM_base"))
    p.add_argument("--sans-reseau", action="store_true", help="ne rien télécharger")
    p.add_argument("--etapes", nargs="*", default=["juridique", "pictogrammes", "donnees"],
                   choices=["juridique", "pictogrammes", "donnees"])
    p.add_argument("--variantes", type=int, default=30, help="cas fictifs par présentation clinique")
    a = p.parse_args(argv)
    sortie = Path(a.sortie).expanduser().resolve()
    sortie.mkdir(parents=True, exist_ok=True)
    journal = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "reseau": not a.sans_reseau,
               "textes": [], "pictogrammes": [], "donnees": {}}
    resume = {}
    if "juridique" in a.etapes:
        print("1/3 Textes juridiques en Markdown" + ("" if a.sans_reseau else " + originaux officiels"))
        resume["textes"] = etape_juridique(sortie, not a.sans_reseau, journal)
    if "pictogrammes" in a.etapes:
        print("2/3 Pictogrammes par source et par idée")
        resume["idees"] = etape_pictogrammes(sortie, not a.sans_reseau, journal)
    if "donnees" in a.etapes:
        print("3/3 Jeu de données de l'assistant")
        resume["cas"] = etape_donnees(sortie, a.variantes, journal)
    (sortie / "journal_constitution.json").write_text(json.dumps(journal, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    originaux = sum(1 for t in journal["textes"] if t["etat"] in ("téléchargé", "déjà présent"))
    images = sum(1 for f in (sortie / "2_pictogrammes" / "par_source").rglob("*.*") if f.suffix.lower() != ".md") if (sortie / "2_pictogrammes" / "par_source").exists() else 0
    (sortie / "LISEZMOI.md").write_text(f"""# Base de connaissances MEDIMCOM IA

Constituée le {journal['date'][:10]} par `outils/constituer_base.py` ({'avec' if not a.sans_reseau else 'sans'} téléchargement).

| Dossier | Contenu |
|---|---|
| `1_textes_juridiques/` | {resume.get('textes', '—')} textes en Markdown (Émirats, Cameroun, international), {originaux} originaux officiels téléchargés ; commencer par `index.md` |
| `2_pictogrammes/` | {resume.get('idees', '—')} idées, rangées par source (`par_source/`) et par idée (`par_idee/`), avec description ; {images} fichiers d'images ; `planche.html` pour tout voir |
| `3_jeu_de_donnees_assistant/` | {resume.get('cas', '—')} cas fictifs pour l'assistant (questions complémentaires, signes d'alerte, pistes à évoquer) ; lire `FICHE_DE_DONNEES.md` |
| `journal_constitution.json` | Chaque fichier téléchargé ou copié, avec son empreinte SHA-256 |

**À respecter.**
- **Textes juridiques :** vérifier le niveau de chacun (officiel, secondaire, à confirmer). Le texte arabe des lois des Émirats prévaut.
- **Pictogrammes :** chaque base a sa licence, avec attribution obligatoire (`par_source/*/LICENCE.md`). ARASAAC interdit l'usage commercial, et toute image modifiée garde sa licence.
- **Jeu de données :** cas fictifs uniquement, à faire valider par un médecin avant tout entraînement.

Relancer `python outils/constituer_base.py` après chaque modification de la base : le dossier est mis à jour.
""", encoding="utf-8")
    print(f"\nBase constituée dans {sortie}")
    for k, v in resume.items():
        print(f"  {k} : {v}")
    echecs = [t for t in journal["textes"] if t["etat"].startswith("échec")]
    if echecs:
        print(f"  {len(echecs)} téléchargement(s) de texte en échec (voir journal_constitution.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
