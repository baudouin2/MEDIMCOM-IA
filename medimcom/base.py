"""Knowledge base of MEDIMCOM IA: sources, provisions and gaps.

- `sources.json`  : manifest of the texts (title, authority, dates, official link, verification level).
- `fiches.jsonl`  : one provision per line (article, summary, short quote, themes).
- `lacunes.json`  : gap catalogue (what exists, what is missing, global examples).

Search is a dependency-free BM25, with a small French → English lexicon (the base is in English, questions may
be in French). It is a measurable reference; hybrid search with vectors can complement it (see
`kb/outils/construire_vecteurs.py`).
"""
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

VERIFICATIONS = {"official_text", "secondary_source", "to_confirm"}

MOTS_VIDES = set("""
a an the of to in on for and or is are be by with from at as it its this that these those can may must shall should
not no do does what which who whom when where how than then there their them they we you i our your his her him
le la les un une des du de d l et ou est sont au aux en dans par pour sur avec sans ce cette ces qui que quoi quel
quelle quels quelles dont il elle ils elles on nous vous je mon ma mes son sa ses leur leurs se s y ne pas plus
peut peuvent doit doivent faut il-y avoir etre fait faire si est-ce
""".split())

# Minimal French -> English lexicon (forms without accents, lower case).
LEXIQUE = {
    "grossesse": "pregnancy pregnant", "enceinte": "pregnant pregnancy", "consentement": "consent",
    "ordonnance": "prescription", "prescrire": "prescribe prescription", "prescription": "prescription",
    "medicament": "medicine medication", "medicaments": "medicine medication", "dose": "dose",
    "posologie": "posology dose usage", "sourd": "deaf", "sourde": "deaf", "sourds": "deaf",
    "malentendant": "deaf hearing", "donnees": "data", "donnee": "data", "etranger": "outside abroad",
    "pays": "state country", "hors": "outside", "urgence": "emergency", "urgences": "emergency",
    "declaration": "notification notify", "declarer": "notify notification", "epidemie": "epidemic outbreak",
    "pictogramme": "pictogram pictograms", "pictogrammes": "pictogram pictograms", "image": "pictogram symbol",
    "responsabilite": "liability accountability", "responsable": "liability accountability responsible",
    "journal": "log logging", "journalisation": "logging log", "tracabilite": "traceability traced",
    "teleconsultation": "telehealth remote", "telemedecine": "telehealth tele-medicine", "distance": "remote distance telehealth",
    "controle": "controlled", "stupefiant": "narcotic narcotics", "stupefiants": "narcotic narcotics",
    "recherche": "research", "assurance": "insurance insurer", "assureur": "insurance insurer",
    "commercial": "commercial", "commerciale": "commercial", "publicite": "commercial advertising",
    "nuage": "cloud", "cloud": "cloud", "hebergement": "hosting storage", "serveur": "server storage",
    "juge": "judicial", "tribunal": "judicial", "incident": "incident", "signalement": "reporting report",
    "signaler": "report reporting", "langue": "language", "signes": "sign", "handicap": "disability determination",
    "handicapees": "disability determination", "avortement": "abortion abortifacient", "medecin": "physician doctor clinician",
    "patient": "patient", "patiente": "patient", "examen": "examination", "clinique": "clinical",
    "suggestion": "suggestion", "ia": "ai", "intelligence": "ai", "artificielle": "ai", "decision": "decision",
    "humain": "human", "humaine": "human", "supervision": "oversight", "validation": "validation validate",
    "valider": "validate validation", "conservation": "retention", "conserver": "retention keep", "ans": "years",
    "amende": "fine penalty", "sanction": "penalty sanctions", "confidentialite": "confidentiality",
    "secret": "confidentiality", "allergie": "allergies", "allergies": "allergies", "antecedents": "history",
    "traitement": "treatment", "traitements": "treatment treatments", "information": "information",
    "informer": "inform information", "comprehension": "comprehension understood", "laboratoire": "laboratory",
    "echantillons": "samples laboratory", "chiffrement": "encryption", "copie": "copy", "isolement": "isolation",
    "crise": "crisis emergency", "pouvoirs": "powers", "autorisation": "approval authorisation marketing",
    "enregistre": "registered approval", "logiciel": "software", "dispositif": "device", "bac": "sandbox",
    "sable": "sandbox", "entrainement": "training", "modele": "model", "biais": "bias", "diversite": "diversity",
    "identite": "identification identity", "identifiants": "identifiers identification", "ibuprofene": "ibuprofen nsaid",
    "paracetamol": "paracetamol acetaminophen", "misoprostol": "misoprostol", "tramadol": "controlled narcotic",
    "plainte": "appeal challenge", "recours": "appeal challenge", "audit": "audit", "notification": "notification",
}


def _sans_accents(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _racine(m: str) -> str:
    for suf, rep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if len(m) > 4 and m.endswith(suf):
            return m[: -len(suf)] + rep
    return m


def jetons(texte: str, traduire: bool = True) -> list[str]:
    mots = re.findall(r"[a-z0-9]+", _sans_accents(texte))
    sortie = []
    for m in mots:
        if m in MOTS_VIDES:
            continue
        if traduire and m in LEXIQUE:
            sortie.extend(_racine(x) for x in LEXIQUE[m].split())
        sortie.append(_racine(m))
    return sortie


class BaseConnaissances:
    def __init__(self, dossier_kb: str | Path):
        d = Path(dossier_kb)
        manifeste = json.loads((d / "sources.json").read_text(encoding="utf-8"))
        self.sources = {s["id"]: s for s in manifeste["sources"]}
        self.fiches = {}
        for ligne in (d / "fiches.jsonl").read_text(encoding="utf-8").splitlines():
            if ligne.strip():
                f = json.loads(ligne)
                self.fiches[f["id"]] = f
        lac = d / "lacunes.json"
        self.lacunes = {l["id"]: l for l in json.loads(lac.read_text(encoding="utf-8"))["gaps"]} if lac.exists() else {}
        self._indexer()

    # ------------------------------------------------------------------ checks
    def problemes(self) -> list[str]:
        """List of inconsistencies of the base (empty if everything is consistent)."""
        p = []
        for s in self.sources.values():
            if s.get("verification") not in VERIFICATIONS:
                p.append(f"source {s['id']} : niveau de vérification inconnu")
            if not s.get("url"):
                p.append(f"source {s['id']} : lien manquant")
        for f in self.fiches.values():
            if f["source"] not in self.sources:
                p.append(f"fiche {f['id']} : source {f['source']} absente du manifeste")
        for l in self.lacunes.values():
            for x in l["existing_texts"] + l["global_examples"]:
                if x["fiche"] not in self.fiches:
                    p.append(f"lacune {l['id']} : fiche {x['fiche']} inconnue")
        return p

    # ------------------------------------------------------------------ citations
    NIVEAUX = {"fr": {"official_text": "texte officiel", "secondary_source": "source secondaire", "to_confirm": "à confirmer"},
               "en": {"official_text": "official text", "secondary_source": "secondary source", "to_confirm": "to confirm"}}

    def citer(self, fiche_id: str, langue: str = "fr") -> str:
        f = self.fiches.get(fiche_id)
        if not f:
            return f"[référence inconnue : {fiche_id}]"
        s = self.sources[f["source"]]
        niveau = self.NIVEAUX[langue][s["verification"]]
        return f"{s['title']}, {f['ref']} ({niveau}) {s['url']}"

    def citer_court(self, fiche_id: str) -> str:
        f = self.fiches.get(fiche_id)
        if not f:
            return fiche_id
        s = self.sources[f["source"]]
        return f"{s.get('short_title') or s['title']}, {f['ref']}"

    # ------------------------------------------------------------------ recherche
    def _texte(self, f: dict) -> str:
        s = self.sources[f["source"]]
        return " ".join([f["title"], f["text"], " ".join(f["themes"]), f["ref"], s["title"], f.get("quote") or ""])

    def _indexer(self):
        self._docs = {fid: Counter(jetons(self._texte(f), traduire=False)) for fid, f in self.fiches.items()}
        self._long = {fid: sum(c.values()) for fid, c in self._docs.items()}
        self._moy = sum(self._long.values()) / max(1, len(self._long))
        df = Counter()
        for c in self._docs.values():
            df.update(c.keys())
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - k + 0.5) / (k + 0.5)) for t, k in df.items()}

    # ------------------------------------------------------------------ recherche vectorielle (facultative)
    _vect = None

    def brancher_vecteurs(self, index, encodeur) -> None:
        """Enables hybrid search: BM25 (words) + vectors (meaning), merged by reciprocal ranks."""
        ids = {m["id"] for m in index.morceaux}
        manquantes = set(self.fiches) - ids
        if manquantes:
            raise ValueError(f"index vectoriel périmé : {len(manquantes)} fiche(s) absente(s), le reconstruire "
                             "(python kb/outils/construire_vecteurs.py)")
        self._vect = (index, encodeur)

    def chercher(self, question: str, k: int = 5, mode: str | None = None, k1: float = 1.4, b: float = 0.75,
                 methode: str | None = None) -> list[dict]:
        """methode: "bm25", "vecteurs" or "hybride" (default: hybrid if an index is plugged in, otherwise bm25)."""
        methode = methode or ("hybride" if self._vect else "bm25")
        if methode != "bm25":
            if not self._vect:
                raise ValueError("aucun index vectoriel branché")
            index, enc = self._vect
            filtre = lambda m: m["id"] in self.fiches and (not mode or mode in self.fiches[m["id"]]["modes"])
            vect = [i for i, _ in index.chercher(question, enc, k=max(20, k), filtre=filtre)]
            if methode == "vecteurs":
                classement = [(i, 0.0) for i in vect]
            else:
                from .vecteurs import fusion_rangs
                bm = [r["fiche"] for r in self._bm25(question, max(20, k), mode, k1, b)]
                classement = fusion_rangs(bm, vect)
            return [self._resultat(fid, sc) for fid, sc in classement[:k]]
        return [self._resultat(fid, sc) for fid, sc in
                [(r["fiche"], r["score"]) for r in self._bm25(question, k, mode, k1, b)]]

    def _resultat(self, fid: str, score: float) -> dict:
        return {"fiche": fid, "score": round(score, 4), "titre": self.fiches[fid]["title"],
                "texte": self.fiches[fid]["text"], "base": self.fiches[fid]["basis"], "citation": self.citer(fid)}

    def _bm25(self, question: str, k: int, mode, k1: float, b: float) -> list[dict]:
        q = jetons(question)
        scores = []
        for fid, c in self._docs.items():
            if mode and mode not in self.fiches[fid]["modes"]:
                continue
            s = 0.0
            for t in set(q):
                if t in c:
                    tf = c[t]
                    s += self._idf[t] * tf * (k1 + 1) / (tf + k1 * (1 - b + b * self._long[fid] / self._moy))
            if s > 0:
                scores.append((s, fid))
        scores.sort(reverse=True)
        return [{"fiche": fid, "score": round(s, 3)} for s, fid in scores[:k]]

    def lacunes_liees(self, fiches: list[str], minimum: int = 1) -> list[str]:
        """Gaps citing at least `minimum` of the given provisions, most linked first."""
        ens = set(fiches)
        comptes = [(len(ens & {x["fiche"] for x in l["existing_texts"] + l["global_examples"]}), l["id"])
                   for l in self.lacunes.values()]
        return [lid for n, lid in sorted(comptes, key=lambda c: -c[0]) if n >= minimum]
