"""Lecture du CONTENU d'un message destiné au patient, avant tout envoi (déterministe, vérifiable).

Le juriste ne contrôlait que la forme (« validé par un médecin autorisé ? ») : un message validé partait, quel que
soit son contenu. Ce module repère deux contenus que le juriste doit bloquer AVANT que le médecin puisse valider :

1. une incitation à se faire du mal (« va te pendre », « tue-toi »…) ou des propos violents ou injurieux ;
2. une consigne de prise de médicament (« prends du tramadol », « boire du paracétamol 3 fois par jour ») qui n'est
   rattachée à aucune prescription contrôlée : seul le médecin prescrit, par écrit, avec dose et posologie
   (loi fédérale 4/2016, art. 4-6), et un produit contrôlé n'est délivré que sur ordonnance (décret-loi 38/2024, art. 55).

Une question (« Prenez-vous du tramadol ? ») ou une mise en garde (« Ne prenez pas d'ibuprofène ») n'est PAS une consigne.

    analyser_message("prend du tramadol", medicaments)
    -> {"incitation_au_mal": False, "consigne_medicament": True, "medicament": "tramadol", "medicament_controle": True, ...}
"""
from __future__ import annotations

import re
import unicodedata


def normaliser(texte: str) -> str:
    t = unicodedata.normalize("NFKD", (texte or "").lower().replace("œ", "oe").replace("’", "'"))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " " + re.sub(r"\s+", " ", t).strip() + " "


# ------------------------------------------------------------------ 1. incitation au mal, violence, injures
_TOI = r"(?:toi|vous|te|t)"
INCITATION = [
    (r"\b(?:va|vas|allez|aller)\s+(?:te|vous|t')\s*(?:pendre|tuer|suicider|jeter|noyer|faire du mal|bruler|couper|empoisonner)\b",
     "incitation à se faire du mal"),
    (r"\b(?:pends|pendez|pend|tue|tuez|suicide|suicidez|jette|jetez|noie|noyez|empoisonne|empoisonnez|brule|brulez)[- ]" + _TOI + r"\b",
     "incitation à se faire du mal"),
    (r"\b(?:ouvre|ouvrez|coupe|coupez|taillade|tailladez)[- ]" + _TOI + r"\s+(?:les\s+)?veines\b", "incitation à se faire du mal"),
    (r"\b(?:saute|sautez)\s+(?:par|du|de la|d'un|d'une)\b", "incitation à se faire du mal"),
    (r"\b(?:tu|vous)\s+(?:devrais|devriez|dois|devez|ferais mieux de|feriez mieux de)\s+(?:mourir|te tuer|vous tuer|te pendre|vous pendre|disparaitre)\b",
     "incitation à se faire du mal"),
    (r"\b(?:va|allez)\s+mourir\b|\bcreve[sz]?\b|\bcrevez\b|\bmeurs\b|\bmourez\b", "incitation à se faire du mal"),
    (r"\b(?:kill|hang|hurt|cut)\s+yourself\b|\bkys\b|\bgo\s+(?:die|hang)\b", "incitation à se faire du mal"),
    (r"\bje\s+vais\s+(?:te|vous)\s+(?:tuer|frapper|buter)\b|\b(?:frappe|frappez)[- ](?:le|la|les|lui)\b", "propos violents"),
    (r"\b(?:connard|connasse|salope|salaud|pute|putain|encule|batard|abruti|debile|imbecile|cretin|idiot|idiote|"
     r"nique|ta gueule|ferme ta gueule|grosse vache)\b", "propos injurieux"),
]
_INCITATION = [(re.compile(m), motif) for m, motif in INCITATION]

# ------------------------------------------------------------------ 2. consigne de prise de médicament
VERBES = (r"\b(?:prend|prends|prenez|prendre|prenne|bois|boit|buvez|boire|avale|avales|avalez|avaler|mets|mettez|mettre|"
          r"applique|appliquez|appliquer|injecte|injectez|injecter|utilise|utilisez|utiliser|"
          r"take|drink|swallow|apply|inject)\b")
DOSE = r"\b\d+(?:[.,]\d+)?\s*(?:mg|g|ml|ui|gouttes?|comprimes?|gelules?|cuilleres?|sachets?|fois)\b"
# Noms de médicaments et classes thérapeutiques : « prenez un antibiotique » est un choix de traitement. Les formes
# seules (« prenez le comprimé après le repas ») ne désignent aucun produit : ce sont des consignes d'usage, permises.
NOMS = (r"\b(?:antibiotiques?|antidouleurs?|anti-inflammatoires?|antalgiques?|anxiolytiques?|somniferes?|"
        r"insuline|morphine|codeine|aspirine|amoxicilline|diclofenac|diazepam|tramadol|paracetamol|ibuprofene|"
        r"doliprane|efferalgan|dafalgan|advil|nurofen|metformine|artemether|coartem|quinine)\b")
NEGATION = re.compile(r"\bne\b[^.?!]{0,40}\b(?:pas|jamais|plus|aucun|aucune)\b|\bpas de\b|\bjamais\b|"
                      r"\b(?:arrete[sz]?|arretez|evite[sz]?|evitez|stop|stoppez|interdit|don't|do not|never|avoid)\b")
QUESTION = re.compile(r"\?|\best[- ]ce\b|\b(?:prenez|prends|buvez|bois|avez|as|utilisez|utilises)[- ](?:vous|tu)\b|"
                      r"\bdo you\b|\bare you\b")


def _medicaments_connus(medicaments: dict) -> list[tuple[str, str, dict]]:
    """(forme normalisée, nom, fiche) pour chaque médicament des règles et ses synonymes, du plus long au plus court."""
    sortie = []
    for nom, fiche in (medicaments or {}).items():
        for forme in [nom, *fiche.get("synonymes", [])]:
            f = normaliser(forme.replace("_", " ")).strip()
            if len(f) >= 3:
                sortie.append((f, nom, fiche))
    return sorted(sortie, key=lambda x: -len(x[0]))


def analyser_message(texte: str, medicaments: dict | None = None) -> dict:
    t = normaliser(texte)
    sortie = {"incitation_au_mal": False, "motif": None, "expression": None,
              "consigne_medicament": False, "medicament": None, "medicament_controle": False}
    for motif_re, motif in _INCITATION:
        m = motif_re.search(t)
        if m:
            sortie.update(incitation_au_mal=True, motif=motif, expression=m.group(0).strip())
            break
    # Médicament cité (règles du pays, puis formes et noms courants)
    nom, fiche = None, {}
    for forme, n, f in _medicaments_connus(medicaments or {}):
        if re.search(r"(?<![a-z])" + re.escape(forme) + r"(?![a-z])", t):
            nom, fiche = n, f
            break
    cite = re.search(NOMS, t)
    if not nom and cite:
        nom = cite.group(0)
    consigne = bool(nom) and bool(re.search(VERBES, t) or re.search(DOSE, t))
    if consigne and (NEGATION.search(t) or QUESTION.search(t)):
        consigne = False                  # mise en garde ou question : pas une consigne de prise
    if consigne:
        sortie.update(consigne_medicament=True, medicament=nom,
                      medicament_controle=fiche.get("categorie") in ("controle", "stupefiant", "psychotrope"))
    return sortie
