"""Reads the free-text fields of the patient record ("history", "other information"): the doctor writes what
they want, without an imposed form; the facts the agents can use are extracted from it, deterministically and
verifiably. The free text is always kept as is: the assistant (language model) also reads it in full.

    extraire_faits("diabète de type 2, insuffisance rénale, enceinte de 3 mois")
    -> {"maladies_connues": ["diabète", "insuffisance rénale"], "maladie_renale": True, "grossesse": True}
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Common forms and abbreviations -> (label, possible derived fact)
SYNONYMES = {
    "hta": ("hypertension", None), "tension": ("hypertension", None), "hypertendu": ("hypertension", None),
    "diabetique": ("diabète", None), "dt2": ("diabète", None), "dt1": ("diabète", None),
    "insuffisance renale": ("insuffisance rénale", "maladie_renale"), "maladie renale": ("maladie des reins", "maladie_renale"),
    "maladie des reins": ("maladie des reins", "maladie_renale"), "dialyse": ("dialyse", "maladie_renale"),
    "insuffisance hepatique": ("insuffisance hépatique", "maladie_hepatique"), "cirrhose": ("cirrhose", "maladie_hepatique"),
    "maladie du foie": ("maladie du foie", "maladie_hepatique"), "hepatite": ("hépatite", "maladie_hepatique"),
    "ulcere": ("ulcère", "ulcere_digestif"), "anticoagulant": ("traitement anticoagulant", "anticoagulant"),
    "avk": ("traitement anticoagulant", "anticoagulant"), "insuffisance cardiaque": ("insuffisance cardiaque", "maladie_cardiaque"),
    "infarctus": ("infarctus", "maladie_cardiaque"), "drepanocytaire": ("drépanocytose", None), "seropositif": ("VIH", None),
    "asthmatique": ("asthme", None), "epileptique": ("épilepsie", None), "allaite": ("allaitement", "allaitement"),
    "allaitement": ("allaitement", "allaitement"),
    # common anticoagulants (current treatments): bleeding risk with aspirin and NSAIDs
    "warfarine": ("traitement anticoagulant", "anticoagulant"), "coumadine": ("traitement anticoagulant", "anticoagulant"),
    "acenocoumarol": ("traitement anticoagulant", "anticoagulant"), "sintrom": ("traitement anticoagulant", "anticoagulant"),
    "fluindione": ("traitement anticoagulant", "anticoagulant"), "previscan": ("traitement anticoagulant", "anticoagulant"),
    "apixaban": ("traitement anticoagulant", "anticoagulant"), "eliquis": ("traitement anticoagulant", "anticoagulant"),
    "rivaroxaban": ("traitement anticoagulant", "anticoagulant"), "xarelto": ("traitement anticoagulant", "anticoagulant"),
    "dabigatran": ("traitement anticoagulant", "anticoagulant"), "heparine": ("traitement anticoagulant", "anticoagulant"),
    "enoxaparine": ("traitement anticoagulant", "anticoagulant"), "lovenox": ("traitement anticoagulant", "anticoagulant"),
    "ulcere gastrique": ("ulcère", "ulcere_digestif"), "ulcere duodenal": ("ulcère", "ulcere_digestif"),
    "hemorragie digestive": ("hémorragie digestive", "ulcere_digestif"), "cardiopathie": ("maladie du cœur", "maladie_cardiaque"),
    "maladie cardiaque": ("maladie du cœur", "maladie_cardiaque"), "insuffisance renale chronique": ("insuffisance rénale", "maladie_renale"),
}
GROSSESSE_OUI = re.compile(r"\b(enceinte|grossesse en cours|est enceinte|gestante)\b")
GROSSESSE_NON = re.compile(r"\b(pas enceinte|non enceinte|n'est pas enceinte|pas de grossesse)\b")


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower().replace("œ", "oe").replace("’", "'"))
    return re.sub(r"\s+", " ", "".join(c for c in t if not unicodedata.combining(c))).strip()


@lru_cache(maxsize=1)
def _maladies() -> dict:
    """Diseases of the consultation vocabulary (category 13): normalised form -> label."""
    v = RACINE / "kb" / "corpus" / "vocabulaire_consultation.json"
    sortie = {}
    if v.exists():
        for e in json.loads(v.read_text(encoding="utf-8"))["categories"].get("13_maladies_antecedents", {}).get("notions", []):
            champs = e.split("|")
            if len(champs) > 2 and champs[2].startswith("="):
                continue
            fr = champs[0].strip()
            if fr.lower() in ("antécédents", "antécédents familiaux", "maladie chronique", "contagieux", "héréditaire",
                              "carnet de vaccination", "déjà opéré", "déjà hospitalisé"):
                continue
            sortie[_norm(fr)] = fr
            for a in (champs[2].split("/") if len(champs) > 2 else []):
                if a.strip():
                    sortie[_norm(a)] = fr
    return sortie


@lru_cache(maxsize=1)
def _vocabulaire() -> frozenset:
    mots = set()
    for forme in list(_maladies()) + list(SYNONYMES) + ["enceinte", "grossesse", "gestante", "allergie", "allergique", "aucune", "aucun"]:
        mots.update(w for w in re.findall(r"[a-z]+", forme) if len(w) >= 4)
    return frozenset(mots)


def corriger_fautes(texte: str) -> tuple[str, dict]:
    """"diabhete" -> diabete, "insufisance" -> insuffisance, "enseinte" -> enceinte: same pronunciation or one
    letter away on a long word, and only towards a known medical word; never an ambiguous correction."""
    from .lecture import cle_phonetique, distance
    voc = _vocabulaire()
    cles = {}
    for w in voc:
        cles.setdefault(cle_phonetique(w), set()).add(w)
    corrections = {}

    def corriger(m):
        w = m.group(0)
        if w in voc or len(w) < 5:
            return w
        cands = cles.get(cle_phonetique(w), set())
        if len(cands) != 1 and len(w) >= 6:
            cands = {v for v in voc if v[0] == w[0] and len(v) >= 6 and distance(w, v, 1) <= 1}
        if len(cands) == 1:
            corrections[w] = next(iter(cands))
            return corrections[w]
        return w
    return re.sub(r"[a-z]+", corriger, _norm(texte)), corrections


def extraire_faits(texte: str) -> dict:
    texte, _ = corriger_fautes(texte)
    t = " " + _norm(texte) + " "
    trouves, faits = [], {}
    for forme, libelle in sorted(_maladies().items(), key=lambda x: -len(x[0])):
        if len(forme) >= 3 and re.search(r"(?<![a-z])" + re.escape(forme) + r"(?![a-z])", t) and libelle not in trouves:
            trouves.append(libelle)
    for forme, (libelle, fait) in SYNONYMES.items():
        if re.search(r"(?<![a-z])" + re.escape(forme) + r"(?![a-z])", t):
            if libelle not in trouves:
                trouves.append(libelle)
            if fait:
                faits[fait] = True
    if GROSSESSE_NON.search(t):
        faits["grossesse"] = False
    elif GROSSESSE_OUI.search(t):
        faits["grossesse"] = True
    if trouves:
        faits["maladies_connues"] = trouves
    return faits
