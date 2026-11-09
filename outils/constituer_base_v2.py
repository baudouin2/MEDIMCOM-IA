"""Constitue sur votre ordinateur une base de connaissances MEDIMCOM IA plus volumineuse, filtrée et rangée
selon les exigences du hackathon UIT AI for Good.

    python outils/constituer_base_v2.py                                   # tout -> ~/MEDIMCOM_base_v2
    python outils/constituer_base_v2.py --ancienne-base ~/MEDIMCOM_base   # facultatif : reprend aussi les PDF déposés dans une ancienne base
    python outils/constituer_base_v2.py --audit-pictos                    # inventaire des étiquettes ARASAAC, sans images
    python outils/constituer_base_v2.py --etapes juridique                # une seule étape : juridique, pictogrammes, donnees
    python outils/constituer_base_v2.py --sans-reseau                     # rangement + fichiers déposés à la main uniquement

Ce que fait le script

1. Base juridique (catalogue : kb/corpus/catalogue_sources.json, 87 documents officiels et ouverts)
   Cameroun d'abord (santé, handicap, numérique, cybersécurité, données, institutions), puis ONU, OMS, UNESCO, OCDE,
   Conseil de l'Europe, Union africaine et pays hôte. Pour chaque document : téléchargement (ou recherche du PDF dans
   la page officielle), empreinte SHA-256, extraction du texte, découpage par article, fiche de métadonnées et morceaux
   prêts pour la recherche (RAG). Ce qui ne se télécharge pas est listé dans a_telecharger_a_la_main.md ; déposez le
   fichier dans entrees_manuelles/<ID>.pdf et relancez.
2. Pictogrammes de consultation (vocabulaire : kb/corpus/vocabulaire_consultation.json, tri :
   kb/corpus/filtres_pictogrammes.json). ARASAAC par correspondance exacte de mot-clé pour chaque notion, plus les
   pictogrammes dont les étiquettes relèvent de la santé ; liste noire (animaux, plantes, lieux d'Aragon, loisirs,
   maquillage…) ; Mulberry (catégories santé) et OpenMoji (santé, corps, visages malades). Tout refus est tracé.
3. Références médicales construites de zéro : fiches OMS fr / en / ar, MedlinePlus, lexique Wikidata (base_v2_references.py).
4. Jeu de données de l'assistant (cas fictifs) et jeux d'entraînement avec fiche de données (base_v2_entrainement.py).
   Aucune ancienne base n'est nécessaire ; --ancienne-base reprend seulement, en plus, ce qui y avait été déposé à la main.

Relancer le script reprend là où il s'était arrêté : rien n'est retéléchargé si le fichier et son empreinte sont là.
"""
import argparse
import csv
import hashlib
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CORPUS = RACINE / "kb" / "corpus"
UA = "Mozilla/5.0 (compatible; MEDIMCOM-IA/2.0; hackathon UIT AI for Good; usage non commercial)"
ARASAAC_API = os.environ.get("MEDIMCOM_ARASAAC_API", "https://api.arasaac.org/v1")
ARASAAC_IMG = os.environ.get("MEDIMCOM_ARASAAC_IMG", "https://static.arasaac.org/pictograms/{id}/{id}_300.png")
MULBERRY = "https://raw.githubusercontent.com/mulberrysymbols/mulberry-symbols/master/"
OPENMOJI = "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/"
LICENCES = {
    "arasaac": ("CC BY-NC-SA 4.0", "Pictogrammes : Sergio Palao. Origine : ARASAAC (https://arasaac.org). Licence : CC BY-NC-SA. "
                "Propriété : Gouvernement d'Aragon (Espagne). Usage commercial interdit."),
    "mulberry": ("CC BY-SA 2.0 UK", "Mulberry Symbols (https://mulberrysymbols.org), Steve Lee, licence CC BY-SA 2.0 UK."),
    "openmoji": ("CC BY-SA 4.0", "OpenMoji (https://openmoji.org), HfG Schwäbisch Gmünd, licence CC BY-SA 4.0."),
}
TITRES_CATEGORIES_EXTRA = {"99_sante_divers": "Santé — divers (à trier)",
                           "90_vocabulaire_general": "Vocabulaire général (tous domaines)",
                           "91_emojis_symboles": "Émojis et symboles (OpenMoji)",
                           "98_sensible": "Contenus sensibles (sexualité, violence) — recherche seulement"}
SANTE_STRICTE = ("09_corps_anatomie", "11_douleur_description", "12_symptomes", "17_chirurgie_operations", "13_maladies_antecedents", "15_examens_actes", "16_medicaments_posologie",
                 "18_materiel_medical", "19_lieux_services_parcours", "23_grossesse_enfant_sexualite", "24_handicap_aides", "29_urgence_securite")
RE_ARTICLE = re.compile(
    r"^\s*(?:\*\*)?\s*(?:ARTICLE|Article|ART\.|Art\.)\s*[(\[]?\s*(premier|1er|\d+(?:[-.]\d+)?(?:\s*(?:bis|ter|quater))?)\b\s*[)\]]?[\s.:\-–—)]*",
    re.MULTILINE)


# ============================================================================================ outils communs
def maintenant() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(donnees: bytes) -> str:
    return hashlib.sha256(donnees).hexdigest()


def normaliser(texte: str) -> str:
    t = unicodedata.normalize("NFKD", str(texte).lower().replace("œ", "oe").replace("’", "'"))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w' -]", " ", t)).strip()


def slug(texte: str, n: int = 40) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", normaliser(texte)).strip("_").upper()[:n] or "X"


def ecrire(chemin: Path, contenu, binaire: bool = False) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    if binaire:
        chemin.write_bytes(contenu)
    else:
        chemin.write_text(contenu, encoding="utf-8")


def ecrire_jsonl(chemin: Path, lignes) -> None:
    ecrire(chemin, "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lignes))


def ecrire_csv(chemin: Path, entetes, lignes) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(entetes)
        w.writerows(lignes)


class Reseau:
    """Téléchargements polis : nouvelles tentatives, pause entre requêtes, aucun accès si désactivé."""

    def __init__(self, actif: bool = True, pause: float = 0.4, essais: int = 3, delai: int = 60):
        self.actif, self.pause, self.essais, self.delai = actif, pause, essais, delai
        self.requetes = 0
        self.pannes = {}   # hôte -> échecs réseau consécutifs (au-delà de 4, l'hôte est considéré injoignable pour l'exécution)

    def get(self, url: str) -> tuple[bytes, str, str]:
        if not self.actif:
            raise RuntimeError("réseau désactivé (--sans-reseau)")
        hote = urllib.parse.urlsplit(url).netloc
        if self.pannes.get(hote, 0) >= 4:
            raise RuntimeError(f"hôte {hote} injoignable pendant cette exécution (relancer plus tard)")
        derniere = None
        for i in range(self.essais):
            try:
                if self.requetes:
                    time.sleep(self.pause)
                self.requetes += 1
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", "Accept-Language": "fr,en;q=0.8"})
                with urllib.request.urlopen(req, timeout=self.delai) as r:
                    self.pannes[hote] = 0
                    return r.read(), r.headers.get("Content-Type", ""), r.geturl()
            except urllib.error.HTTPError as e:
                derniere = f"HTTP {e.code}"
                if e.code < 500:
                    self.pannes[hote] = 0   # le serveur répond : ce document-là seulement est absent ou refusé
                    break
            except Exception as e:  # noqa: BLE001 — coupure, délai, DNS : on réessaie
                derniere = f"{type(e).__name__}: {e}"
            if i + 1 < self.essais:
                time.sleep(1.5 * (i + 1))
        self.pannes[hote] = self.pannes.get(hote, 0) + 1
        raise RuntimeError(derniere or "échec")

    def json(self, url: str):
        donnees, _, _ = self.get(url)
        return json.loads(donnees.decode("utf-8"))


class Journal:
    def __init__(self, chemin: Path):
        self.chemin = chemin
        self.d = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
        self.d.setdefault("documents", {})
        self.d.setdefault("images", {})
        self.d.setdefault("executions", [])

    def sauver(self) -> None:
        ecrire(self.chemin, json.dumps(self.d, ensure_ascii=False, indent=1) + "\n")


# ============================================================================================ extraction de texte
class _TexteHTML(HTMLParser):
    BLOCS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "table", "dd", "dt"}
    IGNORER = {"script", "style", "nav", "header", "footer", "noscript", "svg", "form", "button"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.morceaux, self.liens, self.meta, self._ignorer = [], [], {}, 0
        self.titre, self._dans_titre = "", False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.IGNORER:
            self._ignorer += 1
        if tag == "title":
            self._dans_titre = True
        if tag == "a" and a.get("href"):
            self.liens.append((a["href"], ""))
        if tag == "meta" and a.get("name") and a.get("content"):
            self.meta[a["name"].lower()] = a["content"]
        if tag in self.BLOCS:
            self.morceaux.append("\n")
        if tag in ("h1", "h2", "h3"):
            self.morceaux.append("\n## " if tag != "h1" else "\n# ")

    def handle_endtag(self, tag):
        if tag in self.IGNORER and self._ignorer:
            self._ignorer -= 1
        if tag == "title":
            self._dans_titre = False
        if tag in self.BLOCS:
            self.morceaux.append("\n")

    def handle_data(self, data):
        if self._dans_titre:
            self.titre += data
        if self._ignorer:
            return
        if self.liens and self.liens[-1][1] == "" and self.get_starttag_text() and self.get_starttag_text().startswith("<a"):
            self.liens[-1] = (self.liens[-1][0], data.strip())
        self.morceaux.append(data)


def analyser_html(donnees: bytes) -> _TexteHTML:
    p = _TexteHTML()
    try:
        p.feed(donnees.decode("utf-8", errors="replace"))
    except Exception:  # noqa: BLE001 — HTML cassé : on garde ce qui a été lu
        pass
    return p


def texte_html(donnees: bytes) -> str:
    p = analyser_html(donnees)
    t = html.unescape("".join(p.morceaux))
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n\s*\n\s*\n+", "\n\n", t)
    return "\n".join(l.strip() for l in t.splitlines()).strip()


def texte_pdf(donnees: bytes) -> tuple[str, str]:
    """Renvoie (texte, outil). pypdf d'abord, pdftotext (poppler) ensuite."""
    try:
        import pypdf  # noqa: PLC0415
        lecteur = pypdf.PdfReader(io.BytesIO(donnees))
        pages = []
        for i, page in enumerate(lecteur.pages, 1):
            pages.append(f"\n\n<!-- page {i} -->\n" + (page.extract_text() or ""))
        t = "".join(pages)
        if len(re.sub(r"\s|<!--.*?-->", "", t)) > 200:
            return t, "pypdf"
    except Exception:  # noqa: BLE001
        pass
    if shutil.which("pdftotext"):
        try:
            r = subprocess.run(["pdftotext", "-layout", "-", "-"], input=donnees, capture_output=True, timeout=180)
            t = r.stdout.decode("utf-8", errors="replace")
            if len(t.strip()) > 200:
                return t.replace("\f", "\n\n<!-- saut de page -->\n"), "pdftotext"
        except Exception:  # noqa: BLE001
            pass
    return "", "aucun (PDF scanné : OCR nécessaire, ou installer pypdf : pip install pypdf)"


def est_pdf(donnees: bytes) -> bool:
    return donnees[:1024].lstrip().startswith(b"%PDF")


def est_html(donnees: bytes, type_contenu: str = "") -> bool:
    return "html" in type_contenu.lower() or donnees[:2048].lstrip().lower().startswith((b"<!doctype html", b"<html"))


def decouper_articles(texte: str) -> list[dict]:
    """Découpe en articles (« Article 12 », « Art. 3 », « Article premier ») ; sinon en sections de taille régulière."""
    positions = [(m.start(), m.group(1)) for m in RE_ARTICLE.finditer(texte)]
    articles = []
    if len(positions) >= 3:
        if positions[0][0] > 200:
            articles.append({"numero": "preambule", "texte": texte[:positions[0][0]].strip()})
        for i, (debut, num) in enumerate(positions):
            fin = positions[i + 1][0] if i + 1 < len(positions) else len(texte)
            corps = texte[debut:fin].strip()
            num = "1" if num.lower() in ("premier", "1er") else re.sub(r"\s+", " ", num)
            articles.append({"numero": num, "texte": corps})
        vus = {}
        for a in articles:  # « Article 5 » cité dans un autre article : on numérote les doublons
            vus[a["numero"]] = vus.get(a["numero"], 0) + 1
            if vus[a["numero"]] > 1:
                a["numero"] = f"{a['numero']} ({vus[a['numero']]})"
        return [a for a in articles if len(a["texte"]) > 20]
    paragraphes = [p.strip() for p in re.split(r"\n\s*\n", texte) if p.strip()]
    bloc, n = "", 0
    for p in paragraphes:
        if len(bloc) + len(p) > 2500 and bloc:
            n += 1
            articles.append({"numero": f"section {n}", "texte": bloc.strip()})
            bloc = ""
        bloc += p + "\n\n"
    if bloc.strip():
        articles.append({"numero": f"section {n + 1}", "texte": bloc.strip()})
    return articles


def morceaux(texte: str, taille: int = 1800, recouvrement: int = 200) -> list[str]:
    if len(texte) <= taille:
        return [texte]
    sortie, i = [], 0
    while i < len(texte):
        fin = min(len(texte), i + taille)
        coupe = texte.rfind("\n", i + taille // 2, fin) if fin < len(texte) else fin
        coupe = coupe if coupe > i else fin
        sortie.append(texte[i:coupe].strip())
        if coupe >= len(texte):
            break
        i = max(coupe - recouvrement, i + 1)
    return [s for s in sortie if s]


# ============================================================================================ 1. base juridique
def chercher_pdf_dans_page(donnees: bytes, url_page: str, source: dict) -> list[str]:
    """Liens candidats vers le document dans une page officielle (dépôt OMS, bibliothèque ONU, UA…), du plus probable au moins probable."""
    p = analyser_html(donnees)
    candidats = {}
    for nom in ("citation_pdf_url", "dc.identifier", "og:document"):
        if p.meta.get(nom, "").lower().split("?")[0].endswith(".pdf"):
            candidats[urllib.parse.urljoin(url_page, p.meta[nom])] = 100
    mots = {m for m in normaliser(source["titre"] + " " + source["id"]).split() if len(m) > 3}
    langues = [l for l in re.split(r"[/,]", source.get("langue", "")) if l]
    for href, libelle in p.liens:
        if href.startswith(("mailto:", "javascript:", "#")):
            continue
        u = urllib.parse.urljoin(url_page, html.unescape(href))
        bas = u.lower()
        score = 0
        if bas.split("?")[0].endswith(".pdf"):
            score += 10
        if any(k in bas for k in ("/files/", "/download", "bitstream", "/bitstreams/", "/content", "/documents/", "attachment")):
            score += 4
        if any(k in normaliser(libelle) for k in ("download", "telecharger", "pdf", "texte integral", "full text")):
            score += 3
        if score == 0:
            continue
        score += 2 * len(mots & set(normaliser(urllib.parse.unquote(u) + " " + libelle).split()))
        if langues and any(f"-{l}." in bas or f"_{l}." in bas or f"-{l}_" in bas or f"lang={l}" in bas for l in langues):
            score += 3
        if any(k in bas for k in ("summary", "resume", "annex", "corrigendum", "flyer", "infographic", "poster")):
            score -= 4
        candidats[u] = max(candidats.get(u, -99), score)
    return [u for u, s in sorted(candidats.items(), key=lambda x: -x[1]) if s >= 8][:4]


def obtenir_document(source: dict, dossier_doc: Path, manuels: Path, reseau: Reseau, journal: Journal, forcer: bool):
    """Renvoie (octets, extension, origine, url) ou lève RuntimeError avec la liste des tentatives."""
    for f in sorted(manuels.glob(f"{source['id']}.*")):
        if f.suffix.lower() in (".pdf", ".html", ".htm", ".txt", ".md"):
            return f.read_bytes(), f.suffix.lower().lstrip("."), "dépôt manuel", str(f)
    deja = journal.d["documents"].get(source["id"], {})
    for f in dossier_doc.glob("original.*"):
        if not forcer and deja.get("sha256") == sha256(f.read_bytes()):
            return f.read_bytes(), f.suffix.lstrip("."), "déjà présent", deja.get("url", "")
    tentatives = []
    adresses = [(u, False) for u in source.get("urls", [])] + ([(source["page"], True)] if source.get("page") else [])
    garde_html = None
    for url, est_page in adresses:
        try:
            donnees, type_contenu, url_finale = reseau.get(url)
        except RuntimeError as e:
            tentatives.append(f"{url} → {e}")
            continue
        if est_pdf(donnees):
            return donnees, "pdf", "téléchargé", url_finale
        if est_html(donnees, type_contenu):
            for lien in chercher_pdf_dans_page(donnees, url_finale, source):
                try:
                    d2, _, u2 = reseau.get(lien)
                except RuntimeError as e:
                    tentatives.append(f"{lien} (trouvé dans la page) → {e}")
                    continue
                if est_pdf(d2):
                    return d2, "pdf", "téléchargé (PDF trouvé dans la page officielle)", u2
            texte = texte_html(donnees)
            if len(texte) > 3000 and garde_html is None:
                garde_html = (donnees, "html", "téléchargé (page HTML officielle)", url_finale)
            tentatives.append(f"{url} → page HTML{' sans PDF' if est_page else ''} ({len(texte)} caractères de texte)")
            continue
        if "text/plain" in type_contenu and len(donnees) > 2000:
            return donnees, "txt", "téléchargé", url_finale
        tentatives.append(f"{url} → contenu inattendu ({type_contenu or 'type inconnu'}, {len(donnees)} octets)")
    if garde_html:
        return garde_html
    raise RuntimeError(" | ".join(tentatives) or "aucun lien ouvert connu")


def entete_yaml(source: dict, extra: dict) -> str:
    champs = {"id": source["id"], "titre": source["titre"], "juridiction": source["dossier"].split("/")[0],
              "dossier": source["dossier"], "axes": ", ".join(source["axes"]), "autorite": source["autorite"],
              "date": source["date"], "type": source["type"], "langue": source["langue"],
              "verification_lien": source["verification"], **extra}
    lignes = ["---"] + [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in champs.items()] + ["---", ""]
    return "\n".join(lignes)


def etape_juridique(sortie: Path, reseau: Reseau, journal: Journal, forcer: bool, seulement=None) -> dict:
    cat = json.loads((CORPUS / "catalogue_sources.json").read_text(encoding="utf-8"))
    axes = cat["axes"]
    base = sortie / "01_base_juridique"
    manuels = sortie / "entrees_manuelles"
    manuels.mkdir(parents=True, exist_ok=True)
    fiches_projet = {}
    if (RACINE / "kb" / "fiches.jsonl").exists():
        for ligne in (RACINE / "kb" / "fiches.jsonl").read_text(encoding="utf-8").splitlines():
            if ligne.strip():
                f = json.loads(ligne)
                fiches_projet.setdefault(f.get("source"), []).append(f)
    lignes_index, rag, a_la_main, etat = [], [], [], {}
    sources = [s for s in cat["sources"] if not seulement or s["id"] in seulement]
    for n, s in enumerate(sources, 1):
        dossier_doc = base / s["dossier"] / s["id"]
        print(f"  [{n:>2}/{len(sources)}] {s['id']:<22}", end=" ", flush=True)
        try:
            donnees, ext, origine, url = obtenir_document(s, dossier_doc, manuels, reseau, journal, forcer)
        except RuntimeError as e:
            print("à télécharger à la main")
            a_la_main.append((s, str(e)))
            etat[s["id"]] = "manquant"
            journal.d["documents"][s["id"]] = {"etat": "manquant", "raison": str(e), "date": maintenant()}
            ecrire(dossier_doc / "fiche.md", fiche_md(s, None, [], fiches_projet.get(s["id"], []), axes, str(e)))
            lignes_index.append([s["id"], s["dossier"], ", ".join(s["axes"]), s["titre"], s["autorite"], s["date"],
                                 s["langue"], "manquant", "", "", "", (s.get("urls") or [s.get("page", "")])[0]])
            continue
        for ancien in dossier_doc.glob("original.*"):
            if ancien.suffix.lstrip(".") != ext:
                ancien.unlink()
        ecrire(dossier_doc / f"original.{ext}", donnees, binaire=True)
        empreinte = sha256(donnees)
        if ext == "pdf":
            texte, outil = texte_pdf(donnees)
        elif ext in ("html", "htm"):
            texte, outil = texte_html(donnees), "analyse HTML"
        else:
            texte, outil = donnees.decode("utf-8", errors="replace"), "texte brut"
        articles = decouper_articles(texte) if texte.strip() else []
        meta = {"origine": origine, "url_obtenue": url, "sha256": empreinte, "octets": len(donnees), "extraction": outil,
                "articles": len(articles), "caracteres": len(texte), "date_constitution": maintenant()[:10]}
        ecrire(dossier_doc / "texte.md", entete_yaml(s, meta) + f"# {s['titre']}\n\n" + (texte.strip() or
               "_Texte non extrait : PDF image. Lancer un OCR (par exemple `ocrmypdf original.pdf ocr.pdf`) puis déposer "
               f"le résultat dans entrees_manuelles/{s['id']}.pdf._") + "\n")
        lignes_art = []
        for a in articles:
            identifiant = f"{s['id']}#art-{slug(a['numero'], 20).lower()}"
            lignes_art.append({"id": identifiant, "source": s["id"], "article": a["numero"], "texte": a["texte"]})
            for k, m in enumerate(morceaux(a["texte"])):
                rag.append({"id": f"{identifiant}~{k}", "text": m, "metadata": {
                    "source": s["id"], "titre": s["titre"], "article": a["numero"], "juridiction": s["dossier"].split("/")[0],
                    "dossier": s["dossier"], "axes": s["axes"], "themes": s["themes"], "autorite": s["autorite"],
                    "date": s["date"], "langue": s["langue"], "url": url, "sha256": empreinte,
                    "verification": s["verification"]}})
        ecrire_jsonl(dossier_doc / "articles.jsonl", lignes_art)
        ecrire(dossier_doc / "fiche.md", fiche_md(s, meta, articles, fiches_projet.get(s["id"], []), axes, None))
        journal.d["documents"][s["id"]] = {"etat": "obtenu", **meta, "url": url}
        etat[s["id"]] = "obtenu"
        avert = "" if texte.strip() else " (OCR nécessaire)"
        print(f"{origine}, {len(articles)} articles/sections{avert}")
        lignes_index.append([s["id"], s["dossier"], ", ".join(s["axes"]), s["titre"], s["autorite"], s["date"], s["langue"],
                             "obtenu" + avert, origine, len(articles), empreinte[:16],
                             str((dossier_doc / f"original.{ext}").relative_to(sortie))])
        journal.sauver()
    if seulement:
        # Quelques documents seulement (--documents) : on GARDE les autres morceaux et lignes d'index déjà construits.
        ancien_rag = base / "corpus_rag.jsonl"
        if ancien_rag.exists():
            gardes = [json.loads(l) for l in ancien_rag.read_text(encoding="utf-8").splitlines() if l.strip()]
            rag = [m for m in gardes if m.get("metadata", {}).get("source") not in seulement] + rag
        ancien_index = base / "index_sources.csv"
        if ancien_index.exists():
            with ancien_index.open(encoding="utf-8-sig", newline="") as fl:
                lignes = list(csv.reader(fl, delimiter=";"))[1:]
            lignes_index = [l for l in lignes if l and l[0] not in seulement] + lignes_index
    ecrire_csv(base / "index_sources.csv", ["id", "dossier", "axes", "titre", "autorite", "date", "langue", "etat", "origine",
                                            "articles", "sha256_debut", "fichier"], lignes_index)
    ecrire_jsonl(base / "corpus_rag.jsonl", rag)
    ecrire(base / "matrice_exigences.md", matrice(cat, sources, etat))
    ecrire(sortie / "a_telecharger_a_la_main.md", liste_manuelle(a_la_main))
    ecrire(base / "LISEZMOI.md", lisezmoi_juridique(cat, sources, etat, len(rag)))
    return {"documents": len(sources), "obtenus": sum(1 for v in etat.values() if v == "obtenu"),
            "manquants": sum(1 for v in etat.values() if v == "manquant"), "morceaux_rag": len(rag)}


def fiche_md(s: dict, meta, articles, fiches, axes, erreur) -> str:
    l = [f"# {s['id']} — {s['titre']}", "",
         "| Champ | Valeur |", "|---|---|",
         f"| Autorité | {s['autorite']} |", f"| Date | {s['date']} |", f"| Type | {s['type']} |", f"| Langue | {s['langue']} |",
         f"| Exigences du hackathon | {'; '.join(f'{a} {axes[a]}' for a in s['axes'])} |",
         f"| Thèmes | {', '.join(s['themes'])} |",
         f"| Lien(s) officiel(s) | {' ; '.join(f'<{u}>' for u in s.get('urls', []) + ([s['page']] if s.get('page') else [])) or '—'} |",
         f"| Vérification du lien | {s['verification']} |"]
    if meta:
        l += [f"| Obtenu | {meta['origine']} le {meta['date_constitution']} |", f"| Adresse effective | <{meta['url_obtenue']}> |",
              f"| SHA-256 | `{meta['sha256']}` |", f"| Taille | {meta['octets']:,} octets |".replace(",", " "),
              f"| Extraction | {meta['extraction']} — {meta['caracteres']:,} caractères, {meta['articles']} articles ou sections |".replace(",", " ")]
    else:
        l += [f"| État | **à télécharger à la main** — déposer le fichier dans `entrees_manuelles/{s['id']}.pdf` |",
              f"| Tentatives | {erreur} |"]
    l += ["", "## Utilité pour MEDIMCOM IA", "", s["utilite"], ""]
    if s.get("note"):
        l += ["## Note", "", s["note"], ""]
    if fiches:
        l += [f"## Dispositions déjà utilisées par le juriste ({len(fiches)})", ""]
        for f in fiches:
            l.append(f"- **{f.get('id')}** — {f.get('ref', '')} — {f.get('title', '')}")
        l.append("")
    if articles:
        l += ["## Sommaire", ""] + ["- " + a["numero"] + " : " + " ".join(a["texte"].split())[:110] + "…" for a in articles[:400]] + [""]
    l += ["Fichiers : `original.*` (document officiel tel que téléchargé), `texte.md` (texte extrait), "
          "`articles.jsonl` (un article par ligne).", ""]
    return "\n".join(l)


def matrice(cat: dict, sources, etat) -> str:
    axes, dossiers = cat["axes"], cat["dossiers"]
    l = ["# Matrice exigences du hackathon × documents", "",
         "Chaque case : documents **obtenus** / listés. Un document peut couvrir plusieurs exigences. "
         "Une case à 0 pour le Cameroun est une **lacune documentée** : elle doit figurer telle quelle dans le rapport, "
         "avec l'exemple mondial de la même ligne.", "",
         "| Exigence | " + " | ".join(dossiers.values()) + " |", "|---|" + "---|" * len(dossiers)]
    for code, nom in axes.items():
        cases = []
        for d in dossiers:
            docs = [s for s in sources if code in s["axes"] and s["dossier"].startswith(d)]
            ok = sum(1 for s in docs if etat.get(s["id"]) == "obtenu")
            cases.append(f"{ok} / {len(docs)}" if docs else ("**0 — lacune**" if d == "A_cameroun" else "—"))
        l.append(f"| {code} {nom} | " + " | ".join(cases) + " |")
    l += ["", "## Détail par exigence", ""]
    for code, nom in axes.items():
        l += [f"### {code} — {nom}", ""]
        for d, titre in dossiers.items():
            docs = [s for s in sources if code in s["axes"] and s["dossier"].startswith(d)]
            if not docs:
                if d == "A_cameroun":
                    l.append(f"- *{titre}* : aucun document — lacune à documenter.")
                continue
            l.append(f"- *{titre}* :")
            for s in docs:
                marque = "✔" if etat.get(s["id"]) == "obtenu" else "✘ à obtenir"
                l.append(f"  - {marque} `{s['id']}` {s['titre']} ({s['date']})")
        l.append("")
    l += ["## Lacunes connues au 2 novembre 2026", "",
          "- Cameroun : pas de stratégie nationale d'IA publiée en texte officiel ouvert (présentée en juillet 2025).",
          "- Cameroun : loi 2024/017 sur les données personnelles non disponible en téléchargement ouvert ; décrets d'application et autorité de contrôle à suivre.",
          "- Cameroun : aucun texte spécifique sur la télémédecine ni sur les dispositifs médicaux à IA (exemples mondiaux : règlement européen sur l'IA, normes de télésanté de Dubaï et d'Abou Dabi, considérations réglementaires de l'OMS).",
          "- Cameroun : aucun document énergie / infrastructures numériques de santé dédié en dehors de la SND30 et des textes TIC.", ""]
    return "\n".join(l)


def liste_manuelle(a_la_main) -> str:
    l = ["# Documents à télécharger à la main", "",
         "Le script n'a pas pu obtenir ces documents automatiquement (site qui bloque les robots, page dynamique, texte non publié).",
         "Pour chacun : ouvrir le lien dans le navigateur, enregistrer le PDF officiel sous `entrees_manuelles/<ID>.pdf` "
         "(ou `.html`), puis relancer le script : il le traitera comme les autres. Ne jamais déposer un article de presse.", ""]
    for s, raison in a_la_main:
        liens = s.get("urls", []) + ([s["page"]] if s.get("page") else [])
        l += [f"## {s['id']} — {s['titre']}", "", f"- Fichier attendu : `entrees_manuelles/{s['id']}.pdf`",
              f"- Où le chercher : {' ; '.join(f'<{u}>' for u in liens) or 'site officiel de ' + s['autorite']}",
              f"- Pourquoi : {raison}"]
        if s.get("note"):
            l.append(f"- Note : {s['note']}")
        l.append("")
    if not a_la_main:
        l.append("Rien : tous les documents ont été obtenus.")
    return "\n".join(l)


def lisezmoi_juridique(cat, sources, etat, n_rag) -> str:
    l = ["# Base juridique", "", f"{len(sources)} documents officiels et ouverts, rangés par juridiction puis par exigence du hackathon. "
         f"{sum(1 for v in etat.values() if v == 'obtenu')} obtenus ; {n_rag} morceaux indexables dans `corpus_rag.jsonl`.", "",
         "- `matrice_exigences.md` : quelles exigences sont couvertes, et les lacunes.",
         "- `index_sources.csv` : un document par ligne (ouvrable dans un tableur).",
         "- `corpus_rag.jsonl` : morceaux `{id, text, metadata}` pour la base vectorielle (`medimcom/vecteurs.py`).",
         "- Chaque document : `<dossier>/<ID>/fiche.md`, `texte.md`, `articles.jsonl`, `original.pdf|html`.", "",
         "## Arborescence", ""]
    for d, titre in cat["dossiers"].items():
        sous = sorted({s["dossier"] for s in sources if s["dossier"].startswith(d)})
        l.append(f"- `{d}/` — {titre}")
        for x in sous:
            if x != d and x != d + "/":
                l.append(f"  - `{x.split('/', 1)[1]}/` ({sum(1 for s in sources if s['dossier'] == x)} documents)")
    return "\n".join(l) + "\n"


# ============================================================================================ 2. pictogrammes
def charger_vocabulaire() -> tuple[list[dict], dict]:
    v = json.loads((CORPUS / "vocabulaire_consultation.json").read_text(encoding="utf-8"))
    titres = {k: c["titre"] for k, c in v["categories"].items()} | TITRES_CATEGORIES_EXTRA
    notions, vus = [], set()
    for cat, c in v["categories"].items():
        for entree in c["notions"]:
            # « fr|en », « fr|en|alias fr/…|alias en/… » (formes cherchées) ou « fr|en|=ID+ID » (notion composée d'autres notions)
            champs = [x.strip() for x in entree.split("|")]
            fr, en = champs[0], champs[1]
            nid = slug(fr)
            if nid in vus:
                continue
            vus.add(nid)
            n = {"id": nid, "categorie": cat, "groupe": c.get("groupe", ""), "fr": fr, "en": en, "ar": "", "recherche_fr": [fr], "recherche_en": [en],
                 "composition": []}
            if len(champs) > 2 and champs[2].startswith("="):
                n["composition"] = [x.strip() for x in champs[2][1:].split("+") if x.strip()]
                n["recherche_fr"], n["recherche_en"] = [], []
            elif len(champs) > 2:
                n["recherche_fr"] += [a.strip() for a in champs[2].split("/") if a.strip()]
                if len(champs) > 3:
                    n["recherche_en"] += [a.strip() for a in champs[3].split("/") if a.strip()]
            notions.append(n)
    ancien = RACINE / "pictogrammes" / "bases" / "vocabulaire_medical.json"
    correspondance = {"reponse": "02_reponses_accord", "personne": "08_personnes_soignants", "corps": "09_corps_anatomie",
                      "symptome": "12_symptomes", "emotion": "14_emotions_ressenti", "soin": "15_examens_actes",
                      "temps": "26_temps_frequence_duree", "nombre": "27_nombres_quantites_mesures"}
    if ancien.exists():
        par_fr = {normaliser(n["fr"]): n for n in notions}
        for x in json.loads(ancien.read_text(encoding="utf-8"))["vocabulaire"]:
            existant = par_fr.get(normaliser(x["fr"]))
            rech = x.get("recherche", {})
            if existant:
                existant["ar"] = x.get("ar", "")
                existant["id_historique"] = x["id"]
                existant["recherche_fr"] = list(dict.fromkeys(existant["recherche_fr"] + rech.get("fr", [])))
                existant["recherche_en"] = list(dict.fromkeys(existant["recherche_en"] + rech.get("en", [])))
            elif x["id"] not in vus:
                vus.add(x["id"])
                notions.append({"id": x["id"], "categorie": correspondance.get(x.get("categorie"), "99_sante_divers"), "composition": [],
                                "fr": x["fr"], "en": x.get("en", ""), "ar": x.get("ar", ""), "id_historique": x["id"],
                                "recherche_fr": rech.get("fr", [x["fr"]]), "recherche_en": rech.get("en", [x.get("en", "")])})
    return notions, titres


def _jetons(item: dict) -> list[str]:
    t = [str(x).lower() for x in item.get("tags", []) or []] + [str(x).lower() for x in item.get("categories", []) or []]
    return t


def _mots(item: dict) -> list[str]:
    return [k.get("keyword", "") for k in item.get("keywords", []) or [] if isinstance(k, dict)]


def verdict_arasaac(item: dict, regles: dict, mots_en: list[str]) -> tuple[str, str]:
    """('noire'|'blanche'|'neutre', détail). La liste noire l'emporte, sauf motif d'exception (« medical », « health »…)."""
    for drapeau in regles.get("exclure_drapeaux", []):
        if item.get(drapeau):
            return "noire", f"drapeau {drapeau}"
    jetons = _jetons(item)
    texte_jetons = " | ".join(jetons + [normaliser(m) for m in mots_en])
    noir = next((m for m in regles["liste_noire"] if m in texte_jetons), None)
    exception = next((m for m in regles.get("exceptions_liste_noire", []) if m in " | ".join(jetons)), None)
    if noir and not exception:
        return "noire", f"liste noire : {noir}"
    for cat, motifs in regles["liste_blanche"].items():
        m = next((m for m in motifs if m in " | ".join(jetons)), None)
        if m:
            return "blanche", cat if not cat.startswith("_") else "99_sante_divers"
    return "neutre", ""


def etape_audit_pictos(sortie: Path, reseau: Reseau) -> dict:
    regles = json.loads((CORPUS / "filtres_pictogrammes.json").read_text(encoding="utf-8"))["arasaac"]
    items = charger_arasaac_tout(sortie, reseau, "fr")
    en = {i["_id"]: _mots(i) for i in charger_arasaac_tout(sortie, reseau, "en")} if items else {}
    compte, verdicts = {}, {"noire": 0, "blanche": 0, "neutre": 0}
    for it in items:
        v, _ = verdict_arasaac(it, regles, en.get(it.get("_id"), []))
        verdicts[v] += 1
        for j in set(_jetons(it)):
            c = compte.setdefault(j, [0, {"noire": 0, "blanche": 0, "neutre": 0}])
            c[0] += 1
            c[1][v] += 1
    audit = sortie / "02_pictogrammes" / "audit"
    ecrire_csv(audit / "etiquettes_arasaac.csv", ["etiquette", "pictogrammes", "dont_gardes", "dont_exclus", "dont_neutres"],
               [[k, c[0], c[1]["blanche"], c[1]["noire"], c[1]["neutre"]] for k, c in sorted(compte.items(), key=lambda x: -x[1][0])])
    print(f"  {len(items)} pictogrammes ARASAAC, {len(compte)} étiquettes : {verdicts['blanche']} gardés par étiquette, "
          f"{verdicts['noire']} exclus, {verdicts['neutre']} neutres (gardés seulement s'ils correspondent à une notion).")
    print(f"  Inventaire : {audit / 'etiquettes_arasaac.csv'} — ajustez kb/corpus/filtres_pictogrammes.json puis relancez sans --audit-pictos.")
    return {"pictogrammes_arasaac": len(items), "etiquettes": len(compte), **verdicts}


def charger_arasaac_tout(sortie: Path, reseau: Reseau, langue: str) -> list[dict]:
    cache = sortie / "02_pictogrammes" / "_cache" / f"arasaac_all_{langue}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < 30 * 86400:
        return json.loads(cache.read_text(encoding="utf-8"))
    try:
        items = reseau.json(f"{ARASAAC_API}/pictograms/all/{langue}")
    except (RuntimeError, ValueError) as e:
        print(f"  (catalogue ARASAAC complet indisponible en {langue} : {e} ; recherche notion par notion)")
        return []
    ecrire(cache, json.dumps(items, ensure_ascii=False))
    return items


def chercher_arasaac(reseau: Reseau, langue: str, terme: str):
    """Liste des résultats ; [] si aucun résultat (404) ; None si le serveur est injoignable."""
    try:
        r = reseau.json(f"{ARASAAC_API}/pictograms/{langue}/search/{urllib.parse.quote(terme)}")
        return r if isinstance(r, list) else []
    except ValueError:
        return []
    except RuntimeError as e:
        return [] if "HTTP 404" in str(e) else None


def etape_pictogrammes(sortie: Path, reseau: Reseau, journal: Journal, max_images: int = 0, objectif: int = 3000,
                       tous: bool = False, paralleles: int = 6) -> dict:
    filtres = json.loads((CORPUS / "filtres_pictogrammes.json").read_text(encoding="utf-8"))
    regles = filtres["arasaac"]
    notions, titres = charger_vocabulaire()
    dossier = sortie / "02_pictogrammes"
    choisis = {}   # clé "source:id" -> entrée de catalogue
    rejets = []

    def ajouter(source, ident, cat, url, ext, mots_fr, mots_en, notion=None, raison="", rang=99, etiquettes=()):
        cle = f"{source}:{ident}"
        if cle in choisis:
            if notion and notion not in choisis[cle]["notions"]:
                choisis[cle]["notions"].append(notion)
                choisis[cle]["rangs"][notion] = rang
            return
        choisis[cle] = {"cle": cle, "source": source, "id": str(ident), "categorie": cat, "url": url, "ext": ext, "popularite": 0,
                        "mots_fr": [m for m in dict.fromkeys(mots_fr) if m][:8], "mots_en": [m for m in dict.fromkeys(mots_en) if m][:8],
                        "notions": [notion] if notion else [], "raison": raison, "rangs": {notion: rang} if notion else {},
                        "etiquettes": list(etiquettes)[:12],
                        "licence": LICENCES[source][0], "attribution": LICENCES[source][1]}

    # --- ARASAAC
    print("  ARASAAC : catalogue complet (fr, en)…")
    tout_fr = charger_arasaac_tout(sortie, reseau, "fr")
    mots_en_par_id = {i["_id"]: _mots(i) for i in charger_arasaac_tout(sortie, reseau, "en")} if tout_fr else {}
    par_id = {i["_id"]: i for i in tout_fr}
    index_fr = {}
    for it in tout_fr:
        for m in _mots(it):
            index_fr.setdefault(normaliser(m), []).append(it["_id"])
    index_en = {}
    for i, mots in mots_en_par_id.items():
        for m in mots:
            index_en.setdefault(normaliser(m), []).append(i)
    n_var = regles.get("variantes_par_notion", 3)
    sans_image, pannes, reserve_notions, reserve_cat = [], 0, {}, {}
    for k, no in enumerate(notions, 1):
        candidats = []
        for terme in no["recherche_fr"]:
            candidats += index_fr.get(normaliser(terme), [])
        if not candidats:
            for terme in no["recherche_en"]:
                candidats += index_en.get(normaliser(terme), [])
        if not candidats and not tout_fr and pannes < 5:   # repli : API de recherche, correspondance exacte d'abord
            for terme in no["recherche_fr"]:
                resultats = chercher_arasaac(reseau, "fr", terme)
                if resultats is None:
                    pannes += 1
                    if pannes == 5:
                        print("  ARASAAC injoignable : pictogrammes ARASAAC ignorés pour cette exécution (relancer plus tard).")
                    break
                pannes = 0
                for it in resultats:
                    par_id.setdefault(it["_id"], it)
                    if normaliser(terme) in {normaliser(m) for m in _mots(it)}:
                        candidats.append(it["_id"])
                if candidats:
                    break
        candidats = list(dict.fromkeys(candidats))
        gardes = []
        for i in candidats:
            it = par_id.get(i, {"_id": i})
            v, detail = verdict_arasaac(it, regles, mots_en_par_id.get(i, []))
            if v == "noire" and detail.startswith("drapeau"):
                rejets.append(["arasaac", i, f"notion {no['id']} : {detail}", ", ".join(_jetons(it))])
                continue
            gardes.append(i)
        # Classement : le bon sens du mot d'abord. « jambe » peut désigner une patte de cheval : une image dont les étiquettes
        # relèvent de la liste noire (animal, plante…) passe après les autres, et disparaît pour le corps, la douleur et les
        # symptômes dès qu'une image convenable existe. Puis : étiquette de la même catégorie, mot-clé principal de l'image,
        # dessin non schématique, popularité.
        termes = {normaliser(t) for t in no["recherche_fr"] + no["recherche_en"]}

        def score(i):
            it = par_id.get(i, {"_id": i})
            v, detail = verdict_arasaac(it, regles, mots_en_par_id.get(i, []))
            mots = [normaliser(m) for m in _mots(it)] + [normaliser(m) for m in mots_en_par_id.get(i, [])[:1]]
            principal = bool(mots) and mots[0] in termes
            return (v == "noire", not (v == "blanche" and detail == no["categorie"]), not principal,
                    bool(it.get("schematic")), -int(it.get("downloads", 0) or 0))
        gardes.sort(key=score)
        humain = no["categorie"][:2] in ("09", "11", "12", "14", "08")
        if humain and any(not score(i)[0] for i in gardes):
            for i in [i for i in gardes if score(i)[0]]:
                rejets.append(["arasaac", i, f"notion {no['id']} : autre sens du mot (liste noire)", ", ".join(_jetons(par_id.get(i, {})))])
            gardes = [i for i in gardes if not score(i)[0]]
        reserve_notions[no["id"]] = (no, gardes[n_var:])
        for rang, i in enumerate(gardes[:n_var]):
            it = par_id.get(i, {})
            ajouter("arasaac", i, no["categorie"], ARASAAC_IMG.format(id=i), "png", _mots(it) or [no["fr"]],
                    mots_en_par_id.get(i, []) or [no["en"]], notion=no["id"], raison="notion du vocabulaire (mot-clé exact)",
                    rang=rang, etiquettes=_jetons(it))
        if not gardes:
            sans_image.append(no)
        if k % 100 == 0:
            print(f"    {k}/{len(notions)} notions")
    if regles.get("collecte_par_etiquettes", True) and tout_fr:
        par_cat = {}
        for it in tout_fr:
            if f"arasaac:{it['_id']}" in choisis:
                continue
            v, detail = verdict_arasaac(it, regles, mots_en_par_id.get(it["_id"], []))
            if v == "noire":   # chaque exclusion est tracée (auditabilité)
                rejets.append(["arasaac", it["_id"], detail, ", ".join(_jetons(it))])
                continue
            if v == "blanche":
                par_cat.setdefault(detail, []).append(it)
        for cat, liste in par_cat.items():
            liste.sort(key=lambda it: -int(it.get("downloads", 0) or 0))
            for it in liste[:regles.get("max_par_categorie", 450)]:
                ajouter("arasaac", it["_id"], cat, ARASAAC_IMG.format(id=it["_id"]), "png", _mots(it),
                        mots_en_par_id.get(it["_id"], []), raison="étiquette santé : " + ", ".join(_jetons(it))[:120])
            reserve_cat[cat] = liste[regles.get("max_par_categorie", 450):]
    print(f"  ARASAAC : {sum(1 for c in choisis.values() if c['source'] == 'arasaac')} pictogrammes retenus")

    # --- notions par libellé anglais exact (pour Mulberry et OpenMoji)
    notion_en = {}
    for no in notions:
        for t in no["recherche_en"]:
            if t:
                notion_en.setdefault(normaliser(t), no)

    # --- Mulberry
    m = filtres["mulberry"]
    try:
        donnees, _, _ = reseau.get(MULBERRY + "scripts/data/symbol-info-en.csv")
        lignes = list(csv.DictReader(io.StringIO(donnees.decode("utf-8-sig"))))
    except RuntimeError as e:
        print(f"  Mulberry indisponible : {e}")
        lignes = []
    for x in lignes:
        nom, categorie = x.get("symbol", ""), x.get("category", "")
        if any(e in nom.lower() for e in m.get("noms_exclus", [])) and not tous:
            rejets.append(["mulberry", nom, "nom exclu (hors consultation)", categorie])
            continue
        nom_en = normaliser(re.sub(r"_\d+[a-z]?(?=_|$)", "", nom.lower().replace("_,_to", "").replace(",_to", "")).replace("_", " "))
        no = notion_en.get(nom_en)
        if no:
            ajouter("mulberry", nom, no["categorie"], MULBERRY + "EN/" + urllib.parse.quote(nom) + ".svg", "svg", [], [nom_en],
                    notion=no["id"], raison=f"notion « {no['fr']} » (nom anglais exact)")
            choisis[f"mulberry:{nom}"]["par_notion"] = True
            continue
        cat = m["categories_gardees"].get(categorie)
        if not cat and categorie == "People Profession" and any(p in nom.lower() for p in m["professions_sante"]):
            cat = "08_personnes_soignants"
        if not cat and categorie == "Verb" and any(nom.lower().startswith(v) for v in m["verbes_sante"]):
            cat = "15_examens_actes"
        if cat or tous:
            mots = nom.replace("_", " ").replace(" , to", "").strip()
            ajouter("mulberry", nom, cat or "90_vocabulaire_general", MULBERRY + "EN/" + urllib.parse.quote(nom) + ".svg", "svg", [], [mots],
                    raison=f"catégorie Mulberry : {categorie}" + ("" if cat else " (tout le catalogue)"), etiquettes=[categorie.lower()])
    print(f"  Mulberry : {sum(1 for c in choisis.values() if c['source'] == 'mulberry')} symboles retenus")

    # --- OpenMoji
    o = filtres["openmoji"]
    try:
        emojis = reseau.json(OPENMOJI + "data/openmoji.json")
    except (RuntimeError, ValueError) as e:
        print(f"  OpenMoji indisponible : {e}")
        emojis = []
    for x in emojis:
        if o.get("exclure_teintes") and x.get("skintone"):
            continue
        annotation = x.get("annotation", "").lower()
        if any(e in annotation for e in o.get("annotations_exclues", [])) and not tous:
            continue
        no = notion_en.get(normaliser(annotation))
        if no:
            ajouter("openmoji", x["hexcode"], no["categorie"], OPENMOJI + f"color/618x618/{x['hexcode']}.png", "png", [],
                    [x.get("annotation", "")] + [t.strip() for t in x.get("tags", "").split(",")], notion=no["id"],
                    raison=f"notion « {no['fr']} » (annotation anglaise exacte)")
            choisis[f"openmoji:{x['hexcode']}"]["par_notion"] = True
            continue
        sg = x.get("subgroups", "")
        cat = o["sous_groupes_gardes"].get(sg)
        if cat and sg in o.get("sous_groupes_filtres", {}) and not any(k in annotation for k in o["sous_groupes_filtres"][sg]):
            cat = None
        if not cat and any(re.search(r"\b" + re.escape(mot) + r"\b", annotation) for mot in o["mots_role_sante"]):
            cat = "99_sante_divers"
        if cat:
            ajouter("openmoji", x["hexcode"], cat, OPENMOJI + f"color/618x618/{x['hexcode']}.png", "png", [],
                    [x.get("annotation", "")] + [t.strip() for t in x.get("tags", "").split(",")],
                    raison=f"OpenMoji {x.get('group')}/{x.get('subgroups')}")
        elif tous:   # le reste en SVG (léger, net à toutes les tailles)
            ajouter("openmoji", x["hexcode"], "91_emojis_symboles", OPENMOJI + f"color/svg/{x['hexcode']}.svg", "svg", [],
                    [x.get("annotation", "")] + [t.strip() for t in x.get("tags", "").split(",")],
                    raison=f"OpenMoji {x.get('group')}/{x.get('subgroups')} (tout le catalogue)",
                    etiquettes=[str(x.get("group", "")), str(x.get("subgroups", ""))])
    print(f"  OpenMoji : {sum(1 for c in choisis.values() if c['source'] == 'openmoji')} pictogrammes retenus")

    # --- reclassement par motif du nom (Mulberry, OpenMoji)
    for c in choisis.values():
        if c["source"] != "arasaac" and not c.get("par_notion"):
            nom = (c["id"] + " " + " ".join(c["mots_en"][:1])).lower()
            for motif, cat in filtres.get("reclassement", {}).get("regles", []):
                if motif in nom:
                    c["categorie"] = cat
                    break

    # --- objectif de volume : si la sélection stricte ne suffit pas, on élargit par paliers, toujours dans le domaine santé
    paliers = []
    if objectif and len(choisis) < objectif and tout_fr:
        avant = len(choisis)
        for _ in range(5):   # palier 1 : plus de variantes pour chaque notion (tour à tour, pour rester équilibré)
            for nid, (no, reste) in reserve_notions.items():
                if reste and len(choisis) < objectif:
                    i = reste.pop(0)
                    it = par_id.get(i, {})
                    ajouter("arasaac", i, no["categorie"], ARASAAC_IMG.format(id=i), "png", _mots(it) or [no["fr"]],
                            mots_en_par_id.get(i, []), notion=nid, raison="variante supplémentaire de la notion (objectif de volume)")
        paliers.append(f"variantes de notions : +{len(choisis) - avant}")
        avant = len(choisis)
        termes = {}
        for no in notions:
            if no["categorie"] in SANTE_STRICTE:
                for t in no["recherche_fr"]:
                    if len(normaliser(t)) >= 4:
                        termes.setdefault(normaliser(t), no)
        for it in sorted(tout_fr, key=lambda it: -int(it.get("downloads", 0) or 0)):   # palier 2 : mot-clé qui contient une notion santé
            if len(choisis) >= objectif:
                break
            if f"arasaac:{it['_id']}" in choisis or verdict_arasaac(it, regles, mots_en_par_id.get(it["_id"], []))[0] == "noire":
                continue
            mots = " | ".join(normaliser(m) for m in _mots(it))
            no = next((no for t, no in termes.items() if re.search(r"(^|[ |])" + re.escape(t) + r"($|[ |])", mots)), None)
            if no:
                ajouter("arasaac", it["_id"], no["categorie"], ARASAAC_IMG.format(id=it["_id"]), "png", _mots(it),
                        mots_en_par_id.get(it["_id"], []), notion=no["id"], raison=f"mot-clé contenant « {no['fr']} » (objectif de volume)")
        paliers.append(f"mots-clés contenant une notion santé : +{len(choisis) - avant}")
        avant = len(choisis)
        for cat, reste in reserve_cat.items():   # palier 3 : au-delà des plafonds par étiquette santé
            while reste and len(choisis) < objectif:
                it = reste.pop(0)
                ajouter("arasaac", it["_id"], cat, ARASAAC_IMG.format(id=it["_id"]), "png", _mots(it),
                        mots_en_par_id.get(it["_id"], []), raison="étiquette santé, au-delà du plafond (objectif de volume)")
        paliers.append(f"au-delà des plafonds : +{len(choisis) - avant}")
        print(f"  Objectif {objectif} : élargissement par paliers — " + " ; ".join(paliers) + f" → {len(choisis)}")
    # --- TOUT le catalogue (--tous-pictos) : au-delà de la santé, tous les domaines. Les contenus marqués « sexualité » ou
    # « violence » par ARASAAC sont gardés (utiles pour dire un abus, l'anatomie intime) mais rangés à part : jamais dans
    # les onglets du patient, seulement par la recherche.
    if tous:
        avant = len(choisis)
        for nid, (no, reste) in reserve_notions.items():
            for i in reste:
                it = par_id.get(i, {})
                ajouter("arasaac", i, no["categorie"], ARASAAC_IMG.format(id=i), "png", _mots(it) or [no["fr"]],
                        mots_en_par_id.get(i, []), notion=nid, raison="variante de la notion (tout le catalogue)")
        for cat, reste in reserve_cat.items():
            for it in reste:
                ajouter("arasaac", it["_id"], cat, ARASAAC_IMG.format(id=it["_id"]), "png", _mots(it),
                        mots_en_par_id.get(it["_id"], []), raison="étiquette santé (tout le catalogue)")
            reste.clear()
        for it in tout_fr:
            if f"arasaac:{it['_id']}" in choisis:
                continue
            sensible = [d for d in ("sex", "violence") if it.get(d)]
            ajouter("arasaac", it["_id"], "98_sensible" if sensible else "90_vocabulaire_general", ARASAAC_IMG.format(id=it["_id"]),
                    "png", _mots(it), mots_en_par_id.get(it["_id"], []),
                    raison=("contenu sensible : " + ", ".join(sensible)) if sensible else "tout le catalogue ARASAAC",
                    etiquettes=(["sensible"] + sensible if sensible else []) + _jetons(it))
        for it in tout_fr:
            if f"arasaac:{it['_id']}" in choisis:
                choisis[f"arasaac:{it['_id']}"]["popularite"] = int(it.get("downloads", 0) or 0)
        paliers.append(f"tout le catalogue ARASAAC : +{len(choisis) - avant}")
        print(f"  ARASAAC, tout le catalogue : +{len(choisis) - avant}")
    for cat, reste in reserve_cat.items():
        for it in reste:
            rejets.append(["arasaac", it["_id"], f"au-delà du plafond de {cat}", ", ".join(_jetons(it))])

    # --- rattacher les symboles Mulberry/OpenMoji aux notions par mot anglais exact
    par_en = {}
    for no in notions:
        for t in no["recherche_en"]:
            par_en.setdefault(normaliser(t), no["id"])
    for c in choisis.values():
        if c["source"] != "arasaac":
            for mot in c["mots_en"]:
                nid = par_en.get(normaliser(mot))
                if nid and nid not in c["notions"]:
                    c["notions"].append(nid)

    # --- libellé français des symboles Mulberry et OpenMoji (noms anglais) : repris du mot français de l'image ARASAAC
    # qui porte le même mot-clé anglais (« ambulance » -> « ambulance », « tooth » -> « dent »)
    en_vers_fr = {}
    for i, mots in mots_en_par_id.items():
        fr = _mots(par_id.get(i, {}))
        for m in mots[:2]:
            if fr and normaliser(m) not in en_vers_fr:
                en_vers_fr[normaliser(m)] = fr[0]
    for c in choisis.values():
        if c["source"] != "arasaac" and not c["mots_fr"]:
            fr = [en_vers_fr[normaliser(m)] for m in c["mots_en"][:3] if normaliser(m) in en_vers_fr]
            c["mots_fr"] = list(dict.fromkeys(fr))[:4]

    # --- téléchargement des images
    liste = sorted(choisis.values(), key=lambda c: (c["categorie"], c["source"], c["id"]))
    if max_images:
        liste = liste[:max_images]
    print(f"  Téléchargement de {len(liste)} images ({paralleles} en parallèle ; reprise automatique si vous relancez)…")
    ok = deja = echec = 0
    a_telecharger = []
    for c in liste:
        nom = f"{c['source']}_{re.sub(r'[^A-Za-z0-9_-]+', '_', c['id'])}.{c['ext']}"
        chemin = dossier / c["categorie"] / nom
        c["fichier"] = str(chemin.relative_to(dossier)).replace(os.sep, "/")
        prec = journal.d["images"].get(c["cle"])
        if chemin.exists() and prec and prec.get("sha256") == sha256(chemin.read_bytes()):
            deja += 1
            c["sha256"] = prec["sha256"]
            continue
        if not chemin.exists():
            anciens = [a for a in dossier.glob(f"*/{nom}") if a != chemin]   # catégorie changée : on déplace, sans retélécharger
            if anciens and prec and prec.get("sha256") == sha256(anciens[0].read_bytes()):
                chemin.parent.mkdir(parents=True, exist_ok=True)
                anciens[0].replace(chemin)
                c["sha256"] = prec["sha256"]
                journal.d["images"][c["cle"]] = {**prec, "fichier": c["fichier"]}
                deja += 1
                continue
        a_telecharger.append((c, chemin))

    def telecharger(c_chemin):
        c, chemin = c_chemin
        try:
            donnees, _, _ = reseau.get(c["url"])
            return c, chemin, donnees, None
        except RuntimeError as e:
            return c, chemin, None, str(e)

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max(1, paralleles)) as ex:
        for k, (c, chemin, donnees, erreur) in enumerate(ex.map(telecharger, a_telecharger), 1):
            if donnees is not None:
                ecrire(chemin, donnees, binaire=True)
                c["sha256"] = sha256(donnees)
                journal.d["images"][c["cle"]] = {"sha256": c["sha256"], "fichier": c["fichier"], "date": maintenant()}
                ok += 1
            else:
                c["fichier"], c["erreur"] = "", erreur
                echec += 1
            if k % 250 == 0:
                print(f"    {k}/{len(a_telecharger)} téléchargées")
                journal.sauver()
    journal.sauver()
    presents = [c for c in liste if c.get("fichier")]

    # --- catalogue, correspondance notions, planches, licences
    ecrire_csv(dossier / "catalogue.csv", ["fichier", "source", "id", "categorie", "mots_fr", "mots_en", "notions", "licence", "raison", "url"],
               [[c["fichier"], c["source"], c["id"], c["categorie"], " / ".join(c["mots_fr"]), " / ".join(c["mots_en"]),
                 " ".join(c["notions"]), c["licence"], c["raison"], c["url"]] for c in presents])
    ecrire_jsonl(dossier / "catalogue.jsonl", [{k: c.get(k) for k in ("fichier", "source", "id", "categorie", "mots_fr", "mots_en", "notions",
                                                                      "rangs", "etiquettes", "popularite", "licence", "attribution", "sha256")}
                                               for c in presents])
    par_notion = {}
    for c in sorted(presents, key=lambda c: (c["source"] != "arasaac", min(c.get("rangs", {}).values() or [99]))):
        for nid in c["notions"]:
            par_notion.setdefault(nid, []).append((c.get("rangs", {}).get(nid, 99), c["source"] != "arasaac", c["fichier"]))
    par_notion = {nid: [f for _, _, f in sorted(v)] for nid, v in par_notion.items()}
    par_id_notion = {n["id"]: n for n in notions}

    def images_de(nid, profondeur=0):
        """Images d'une notion ; pour une notion composée, la première image de chaque composant, dans l'ordre."""
        n = par_id_notion.get(nid)
        if n and n["composition"] and profondeur < 3:
            sortie = []
            for comp in n["composition"]:
                im = images_de(comp, profondeur + 1)
                sortie.append(im[0] if im else f"[{comp}]")
            return sortie
        return par_notion.get(nid, [])

    def illustree(n):
        im = images_de(n["id"])
        return bool(im) and not any(i.startswith("[") for i in im)

    ecrire_csv(dossier / "notions.csv", ["notion", "groupe", "categorie", "fr", "en", "ar", "id_historique", "composition", "images"],
               [[n["id"], n.get("groupe", ""), n["categorie"], n["fr"], n["en"], n["ar"], n.get("id_historique", ""), " + ".join(n["composition"]),
                 (" + " if n["composition"] else " ").join(images_de(n["id"]))] for n in notions])
    ecrire_csv(dossier / "audit" / "rejets.csv", ["source", "id", "raison", "etiquettes"], rejets)
    ecrire_csv(dossier / "audit" / "notions_sans_image.csv", ["notion", "categorie", "fr", "en"],
               [[n["id"], n["categorie"], n["fr"], n["en"]] for n in notions if not illustree(n)])
    for cat in sorted({c["categorie"] for c in presents}):
        ecrire(dossier / "planches" / f"{cat}.html", planche(cat, titres.get(cat, cat), [c for c in presents if c["categorie"] == cat], notions))
    ecrire(dossier / "planches" / "index.html", "<!doctype html><meta charset='utf-8'><title>Pictogrammes MEDIMCOM IA</title>"
           "<body style='font-family:system-ui;margin:24px'><h1>Pictogrammes de consultation</h1><ul>" +
           "".join(f"<li><a href='{cat}.html'>{html.escape(titres.get(cat, cat))}</a> — "
                   f"{sum(1 for c in presents if c['categorie'] == cat)} images</li>" for cat in sorted({c['categorie'] for c in presents})) + "</ul>")
    ecrire(dossier / "LICENCES.md", "# Licences des pictogrammes\n\n" + "\n".join(
        f"## {s}\n\n- Licence : **{l}**\n- Attribution obligatoire : {a}\n- Images : {sum(1 for c in presents if c['source'] == s)}\n"
        for s, (l, a) in LICENCES.items()) + "\nUne image modifiée ou combinée garde la licence de sa source (clause SA). "
        "ARASAAC interdit tout usage commercial : à revoir avant toute commercialisation.\n")
    resume = {"notions": len(notions), "notions_composees": sum(1 for n in notions if n["composition"]),
              "notions_illustrees": sum(1 for n in notions if illustree(n)),
              "images": len(presents), "telechargees": ok, "deja_presentes": deja, "echecs": echec, "rejets_traces": len(rejets),
              "par_source": {s: sum(1 for c in presents if c["source"] == s) for s in LICENCES},
              "objectif": objectif, "objectif_atteint": len(presents) >= objectif if objectif else None, "paliers": paliers}
    ecrire(dossier / "LISEZMOI.md", lisezmoi_pictos(resume, titres, presents))
    return resume


def planche(cat, titre, items, notions) -> str:
    noms = {n["id"]: n["fr"] for n in notions}
    cases = []
    for c in sorted(items, key=lambda c: (not c["notions"], c["notions"][:1], c["source"])):
        etiquette = ", ".join(noms.get(n, n) for n in c["notions"][:3]) or (c["mots_fr"] or c["mots_en"] or [c["id"]])[0]
        cases.append(f"<figure><img loading='lazy' src='../{html.escape(c['fichier'])}' alt='{html.escape(etiquette)}'>"
                     f"<figcaption><b>{html.escape(etiquette)}</b><br><small>{c['source']} {html.escape(c['id'])}</small></figcaption></figure>")
    return ("<!doctype html><meta charset='utf-8'><title>" + html.escape(titre) + "</title><style>body{font-family:system-ui;margin:24px}"
            "main{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:12px}figure{margin:0;border:1px solid #ddd;"
            "border-radius:8px;padding:8px;text-align:center}img{width:100%;height:110px;object-fit:contain}figcaption{font-size:12px}"
            "</style><body><p><a href='index.html'>← toutes les catégories</a></p><h1>" + html.escape(titre) +
            f"</h1><p>{len(items)} images</p><main>" + "".join(cases) + "</main>")


def lisezmoi_pictos(r, titres, presents) -> str:
    l = ["# Pictogrammes de consultation médicale", "",
         f"{r['images']} images rangées en {len({c['categorie'] for c in presents})} catégories de consultation ; "
         f"{r['notions_illustrees']} notions sur {r['notions']} illustrées (dont {r['notions_composees']} notions composées : "
         f"une suite de pictogrammes, par exemple « où avez-vous mal » = OÙ + AVOIR MAL). Objectif de volume : {r['objectif']} "
         f"({'atteint' if r['objectif_atteint'] else 'non atteint — voir les paliers ci-dessous et relancer quand ARASAAC est joignable'}).",
         "", "Élargissement : " + ("; ".join(r["paliers"]) if r["paliers"] else "aucun (sélection stricte suffisante)") + ".", "",
         "| Catégorie | Images |", "|---|---|"]
    for cat in sorted({c["categorie"] for c in presents}):
        l.append(f"| `{cat}/` {titres.get(cat, '')} | {sum(1 for c in presents if c['categorie'] == cat)} |")
    l += ["", "- `catalogue.csv` / `catalogue.jsonl` : chaque image, ses mots-clés fr/en, ses notions, sa licence.",
          "- `notions.csv` : chaque notion du vocabulaire et ses images (c'est ce que lit l'agent traducteur).",
          "- `planches/index.html` : tout voir dans le navigateur.",
          "- `audit/rejets.csv` : ce qui a été écarté et pourquoi ; `audit/notions_sans_image.csv` : notions à illustrer.",
          "- `LICENCES.md` : attribution obligatoire par source.", "",
          "Tri : `kb/corpus/filtres_pictogrammes.json` ; vocabulaire : `kb/corpus/vocabulaire_consultation.json`. "
          "Lancer `--audit-pictos` pour voir les étiquettes ARASAAC et ajuster les listes.", ""]
    return "\n".join(l)


# ============================================================================================ 3. données et migration
def etape_donnees(sortie: Path, variantes: int) -> dict:
    sys.path.insert(0, str(RACINE))
    sys.path.insert(0, str(RACINE / "outils"))
    try:
        import jeu_assistant  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        print(f"  jeu de données non généré : {e}")
        return {}
    cible = sortie / "04_jeu_de_donnees_assistant"
    r = jeu_assistant.construire(cible, variantes)
    src = RACINE / "donnees" / "presentations_cliniques.json"
    if src.exists():
        shutil.copy2(src, cible / "presentations_cliniques.json")
    return r if isinstance(r, dict) else {"cas": r}


def etape_migration(ancienne: Path, sortie: Path) -> dict:
    """Reprend de l'ancienne base ce qui reste utile ; les anciens pictogrammes ne sont pas repris (ils sont refaits filtrés)."""
    cat = json.loads((CORPUS / "catalogue_sources.json").read_text(encoding="utf-8"))
    ids = sorted((s["id"] for s in cat["sources"]), key=len, reverse=True)
    manuels, a_classer = sortie / "entrees_manuelles", sortie / "01_base_juridique" / "E_anciens_a_classer"
    r = {"textes_rattaches": 0, "textes_a_classer": 0, "dossiers_copies": []}
    ancien_jur = ancienne / "1_textes_juridiques"
    if ancien_jur.exists():
        for f in sorted(ancien_jur.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in (".pdf", ".html", ".htm", ".docx", ".txt"):
                continue
            nom = f.stem.upper().replace("_", "-")
            ident = next((i for i in ids if nom == i or nom.startswith(i + "-") or nom.startswith(i + ".")), None)
            if ident and f.suffix.lower() in (".pdf", ".html", ".htm", ".txt"):
                dest = manuels / f"{ident}{f.suffix.lower()}"
                if not any(manuels.glob(f"{ident}.*")):
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dest)
                    r["textes_rattaches"] += 1
            else:
                dest = a_classer / f.relative_to(ancien_jur)
                if not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dest)
                    r["textes_a_classer"] += 1
    copies = {"3_jeu_de_donnees_assistant/references": "03_references_medicales",
              "3_jeu_de_donnees_assistant": "04_jeu_de_donnees_assistant"}
    for src, dst in copies.items():
        s = ancienne / src
        if s.exists():
            ignorer = shutil.ignore_patterns("references") if src == "3_jeu_de_donnees_assistant" else None
            shutil.copytree(s, sortie / dst, dirs_exist_ok=True, ignore=ignorer)
            r["dossiers_copies"].append(f"{src} → {dst}")
    return r


# ============================================================================================ programme principal
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Constitue la base de connaissances MEDIMCOM IA (version 2 : santé, Cameroun, international).")
    p.add_argument("--sortie", default=str(Path.home() / "MEDIMCOM_base_v2"), help="dossier de sortie (défaut : ~/MEDIMCOM_base_v2)")
    p.add_argument("--ancienne-base", help="dossier de l'ancienne base à reprendre (textes déposés, jeu de données, références)")
    p.add_argument("--etapes", nargs="*", default=["migration", "juridique", "references", "pictogrammes", "donnees", "entrainement"],
                   choices=["migration", "juridique", "references", "pictogrammes", "donnees", "entrainement"])
    p.add_argument("--objectif-pictos", type=int, default=3000, help="nombre de pictogrammes visé (élargissement par paliers, 0 = aucun)")
    p.add_argument("--tous-pictos", action="store_true",
                   help="TOUS les pictogrammes d'ARASAAC, Mulberry et OpenMoji, tous domaines (~20 000 images, plusieurs centaines de Mo)")
    p.add_argument("--paralleles", type=int, default=6, help="téléchargements d'images simultanés")
    p.add_argument("--documents", nargs="*", help="ne traiter que ces identifiants du catalogue (ex. CM-SANTE-1996)")
    p.add_argument("--audit-pictos", action="store_true", help="inventaire des étiquettes ARASAAC seulement, sans images")
    p.add_argument("--max-images", type=int, default=0, help="limiter le nombre d'images (essai rapide)")
    p.add_argument("--forcer", action="store_true", help="retélécharger même ce qui est déjà présent")
    p.add_argument("--sans-reseau", action="store_true", help="aucun téléchargement")
    p.add_argument("--pause", type=float, default=0.4, help="secondes entre deux requêtes (politesse envers les serveurs)")
    p.add_argument("--variantes", type=int, default=30, help="cas fictifs par présentation clinique")
    a = p.parse_args(argv)
    sortie = Path(a.sortie).expanduser().resolve()
    sortie.mkdir(parents=True, exist_ok=True)
    reseau = Reseau(actif=not a.sans_reseau, pause=a.pause)
    journal = Journal(sortie / "journal.json")
    debut = maintenant()
    if a.audit_pictos:
        print("Audit des étiquettes ARASAAC")
        r = etape_audit_pictos(sortie, reseau)
        journal.d["executions"].append({"debut": debut, "fin": maintenant(), "audit_pictos": r})
        journal.sauver()
        return 0
    resume = {}
    if "migration" in a.etapes and a.ancienne_base:
        print("0/5 Reprise de l'ancienne base (facultatif)")
        resume["migration"] = etape_migration(Path(a.ancienne_base).expanduser().resolve(), sortie)
    if "juridique" in a.etapes:
        print("1/5 Base juridique (Cameroun, international, Afrique, pays hôte)")
        resume["juridique"] = etape_juridique(sortie, reseau, journal, a.forcer, set(a.documents) if a.documents else None)
    if "references" in a.etapes:
        print("2/5 Références médicales (OMS, MedlinePlus, Wikidata)")
        import base_v2_references  # noqa: PLC0415
        resume["references"] = base_v2_references.etape_references(sortie, reseau, journal)
    if "pictogrammes" in a.etapes:
        print("3/5 Pictogrammes de consultation")
        resume["pictogrammes"] = etape_pictogrammes(sortie, reseau, journal, a.max_images, a.objectif_pictos, a.tous_pictos, a.paralleles)
    if "donnees" in a.etapes and not (sortie / "04_jeu_de_donnees_assistant" / "FICHE_DE_DONNEES.md").exists():
        print("4/5 Jeu de données de l'assistant (cas fictifs)")
        resume["donnees"] = etape_donnees(sortie, a.variantes)
    if "entrainement" in a.etapes:
        print("5/5 Jeux d'entraînement et fiche de données")
        import base_v2_entrainement  # noqa: PLC0415
        resume["entrainement"] = base_v2_entrainement.etape_entrainement(sortie)
    journal.d["executions"].append({"debut": debut, "fin": maintenant(), "reseau": reseau.actif, "requetes": reseau.requetes, "resume": resume})
    journal.sauver()
    ecrire(sortie / "00_LISEZMOI.md", lisezmoi_general(sortie, resume))
    print(f"\nBase constituée dans {sortie}")
    print(json.dumps(resume, ensure_ascii=False, indent=1))
    if (sortie / "a_telecharger_a_la_main.md").exists() and resume.get("juridique", {}).get("manquants"):
        print(f"→ {resume['juridique']['manquants']} document(s) à déposer à la main : voir a_telecharger_a_la_main.md")
    return 0


def lisezmoi_general(sortie: Path, r: dict) -> str:
    j, p = r.get("juridique", {}), r.get("pictogrammes", {})
    return f"""# Base de connaissances MEDIMCOM IA — version 2

Constituée le {maintenant()[:10]} par `outils/constituer_base_v2.py`. Rangée selon les exigences du hackathon UIT AI for Good :
lois et réglementations, stratégies IA / numérique / cybersécurité, protection des données, mandats institutionnels,
engagements multilatéraux, énergie et infrastructures.

| Dossier | Contenu |
|---|---|
| `01_base_juridique/` | {j.get('obtenus', '—')} documents officiels obtenus sur {j.get('documents', '—')} (Cameroun d'abord, puis ONU, OMS, UNESCO, OCDE, Conseil de l'Europe, Union africaine, pays hôte) ; {j.get('morceaux_rag', '—')} morceaux pour la recherche. Commencer par `matrice_exigences.md` |
| `02_pictogrammes/` | {p.get('images', '—')} pictogrammes de consultation, {p.get('notions_illustrees', '—')} notions illustrées ; `planches/index.html` |
| `03_references_medicales/` | fiches d'information de l'OMS en français, anglais et arabe, résumés MedlinePlus, lexique Wikidata fr / en / ar avec codes CIM-10 ({r.get('references', {}).get('oms', {}).get('pages', '—')} pages OMS) |
| `04_jeu_de_donnees_assistant/` | {r.get('donnees', {}).get('cas', 'cas')} cas fictifs pour l'assistant médical, à faire valider par un médecin |
| `05_jeux_entrainement/` | jeux prêts pour entraîner ou évaluer un modèle (images ⇄ libellés, pictogrammes ⇄ phrases, classification et recherche juridiques, questions-réponses OMS, lexique) ; lire `FICHE_DE_DONNEES.md` |
| `entrees_manuelles/` | déposer ici `<ID>.pdf` pour les documents à télécharger à la main |
| `a_telecharger_a_la_main.md` | la liste de ces documents, avec les liens où les chercher |
| `journal.json` | chaque document et image : adresse, date, empreinte SHA-256 (auditabilité) |

**Règles.** Uniquement des documents officiels et ouverts, jamais de presse ; une lacune se documente, elle ne s'invente pas.
Pictogrammes : attribution obligatoire (`02_pictogrammes/LICENCES.md`), ARASAAC non commercial. Données de patients : fictives uniquement.

Relancer le script complète la base sans rien retélécharger.
"""


if __name__ == "__main__":
    sys.exit(main())
