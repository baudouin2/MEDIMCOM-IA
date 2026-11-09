"""Reads the CONTENT of a message meant for the patient, before anything is sent (deterministic, verifiable).

The jurist used to check only the form ("validated by an authorised doctor?"): a validated message was sent,
whatever its content. This module spots two contents the jurist must block BEFORE the doctor can validate:

1. an incitement to self-harm ("va te pendre", "tue-toi"…) or violent or insulting statements;
2. an instruction to take a medicine ("prends du tramadol", "boire du paracétamol 3 fois par jour") that is not
   linked to any checked prescription: only the doctor prescribes, in writing, with dose and dosage
   (Federal Law 4/2016, Art. 4-6), and a controlled product is only dispensed on prescription (Decree-Law 38/2024, Art. 55).

A question ("Prenez-vous du tramadol ?") or a warning ("Ne prenez pas d'ibuprofène") is NOT an instruction.

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


# ------------------------------------------------------------------ 1. incitement to harm, violence, insults
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

# Self-harm mentioned in the 2nd person ("et vous pendre", "vous tuer"): dangerous, EXCEPT in a suicide-risk screening
# question, which the doctor must be able to ask ("Avez-vous des idées de vous tuer ?").
ATTEINTE = re.compile(r"\b(?:vous|te|t'|se|s')\s*(?:pendre|tuer|suicider|noyer|empoisonner|egorger|etrangler|"
                      r"jeter (?:par|du|sous)|ouvrir les veines|faire du mal)\b")
DEPISTAGE = re.compile(r"\?|\b(?:idees?|envie|pense[sz]?|pensez|penser|songe[sz]?|songez|voulu|voulez|veux|"
                       r"essaye|essaye[sz]?|tente|deja|risque|est[- ]ce)\b")
# Message reduced to a word of death or violence ("pendre", "suicide"): without context, it is not sent.
MOTS_DE_MORT = {"pendre", "pendez", "pends", "pendu", "pendaison", "suicide", "suicider", "suicidez", "tuer", "tue", "tuez",
                "mourir", "meurs", "mourez", "crever", "creve", "crevez", "egorger", "poignarder", "empoisonner", "etrangler"}
VIDES = {"et", "ou", "vous", "toi", "te", "se", "le", "la", "les", "de", "du", "des", "a", "au", "un", "une", "allez", "va", "aller"}

# ------------------------------------------------------------------ 2. instruction to take a medicine
VERBES = (r"\b(?:prend|prends|prenez|prendre|prenne|bois|boit|buvez|boire|avale|avales|avalez|avaler|mets|mettez|mettre|"
          r"applique|appliquez|appliquer|injecte|injectez|injecter|utilise|utilisez|utiliser|"
          r"take|drink|swallow|apply|inject)\b")
DOSE = r"\b\d+(?:[.,]\d+)?\s*(?:mg|g|ml|ui|gouttes?|comprimes?|gelules?|cuilleres?|sachets?|fois)\b"
# Medicine names and therapeutic classes: "prenez un antibiotique" is a treatment choice. Forms alone ("prenez le
# comprimé après le repas") name no product: they are usage instructions, allowed.
NOMS = (r"\b(?:antibiotiques?|antidouleurs?|anti-inflammatoires?|antalgiques?|anxiolytiques?|somniferes?|"
        r"insuline|morphine|codeine|aspirine|amoxicilline|diclofenac|diazepam|tramadol|paracetamol|ibuprofene|"
        r"doliprane|efferalgan|dafalgan|advil|nurofen|metformine|artemether|coartem|quinine)\b")
# Prescription announced to the patient ("je vais vous prescrire du tramadol", "je vous donne du paracétamol")
ANNONCE = re.compile(r"\b(?:je|on|nous)\s+(?:vais\s+|va\s+|allons\s+)?(?:vous\s+|te\s+|t')?"
                     r"(?:prescri\w*|donne\w*|conseill\w*|recommand\w*|mets|mettre|ajoute\w*)\b|"
                     r"\b(?:vous|te|t')\s*(?:prescri\w*|donne\w*|conseill\w*|recommand\w*)\b")
# Imprecise quantity for a medicine ("beaucoup de paracétamol"): possible overdose, never a valid instruction
QUANTITE_VAGUE = re.compile(r"\b(?:beaucoup|plein|a volonte|autant que|le plus possible|tout le flacon|toute la boite|"
                            r"toute la plaquette|plusieurs boites|double dose|triple dose|une poignee|a fond|max|maximum)\b")
NEGATION = re.compile(r"\bne\b[^.?!]{0,40}\b(?:pas|jamais|plus|aucun|aucune)\b|\bpas de\b|\bjamais\b|"
                      r"\b(?:arrete[sz]?|arretez|evite[sz]?|evitez|stop|stoppez|interdit|don't|do not|never|avoid)\b")
QUESTION = re.compile(r"\?|\best[- ]ce\b|\b(?:prenez|prends|buvez|bois|avez|as|utilisez|utilises)[- ](?:vous|tu)\b|"
                      r"\bdo you\b|\bare you\b")


def _medicaments_connus(medicaments: dict) -> list[tuple[str, str, dict]]:
    """(normalised form, name, provision) for each medicine of the rules and its synonyms, longest first."""
    sortie = []
    for nom, fiche in (medicaments or {}).items():
        for forme in [nom, *fiche.get("synonymes", [])]:
            f = normaliser(forme.replace("_", " ")).strip()
            if len(f) >= 3:
                sortie.append((f, nom, fiche))
    return sorted(sortie, key=lambda x: -len(x[0]))


INJURES = re.compile(r"\b(?:connard|connasse|salope|salaud|pute|putain|encule|batard|abruti|debile|imbecile|cretin|idiot|"
                     r"idiote|nique|ta gueule|ferme ta gueule|grosse vache)\b")


def analyser_message(texte: str, medicaments: dict | None = None) -> dict:
    """Reads a doctor-to-patient message IN CONTEXT (medimcom/lecture.py):
      - incitement, threat or insult ADDRESSED to the patient -> incitation_au_mal (blocked);
      - death word in a narrative, a screening question, a warning -> mere mention (allowed, reported);
      - death word without context ("pendre") or quoted incitement -> a_confirmer (the doctor confirms);
      - medicine: instruction (blocked without prescription) / question, warning, narrative, information (allowed);
      - typing and dictation errors corrected and shown ("tramadole" -> tramadol, "pandre" -> pendre)."""
    from .lecture import INTENTIONS, MOTS_DE_MORT, corriger_mots_de_mort, lire_contexte, mots, trouver_medicaments
    corrige, corrections = corriger_mots_de_mort(texte or "")
    t = normaliser(corrige)
    ctx = lire_contexte(corrige)
    intention = ctx["intention"]
    meds = trouver_medicaments(corrige, medicaments or {})
    corrections.update({m["lu"]: m["nom"] for m in meds if m["corrige"]})
    noms = [m["nom"] for m in meds]
    fiches = {n: (medicaments or {}).get(n, {}) for n in noms}
    sortie = {"incitation_au_mal": False, "motif": None, "expression": None,
              "consigne_medicament": False, "medicament": None, "medicament_controle": False,
              "medicaments": noms, "dose_imprecise": False, "contexte": ctx, "corrections": corrections,
              "evocation": None, "a_confirmer": None}
    jetons = mots(corrige)
    morts = [w for w in jetons if w in MOTS_DE_MORT]
    # 1. Self-harm, violence, insult: depending on context (insult recognised even misspelt: "imbecil")
    from .ethique import _injure, analyser as analyser_ethique
    mot_injure = _injure(" " + t + " ")
    injure = re.search(re.escape(mot_injure), t) if mot_injure else None
    if intention in ("incitation", "menace"):
        sortie.update(incitation_au_mal=True, motif="propos violents" if intention == "menace" else "incitation à se faire du mal",
                      expression=" ".join(morts) or None)
    elif injure and intention not in ("recit", "question"):
        sortie.update(incitation_au_mal=True, motif="propos injurieux", expression=injure.group(0))
    elif morts or injure:
        if intention == "ambigu":
            sortie["a_confirmer"] = (f"« {' '.join(morts) or injure.group(0)} » sans contexte clair : impossible de savoir si "
                                     "c'est une incitation, une question ou un récit")
        else:
            sortie["evocation"] = f"« {' '.join(morts) or injure.group(0)} » cité dans {INTENTIONS[intention]}"
    # 1 bis. Ethics: harmful advice (drugs, alcohol), child or organ trafficking, sexual remarks, abortion
    sortie["ethique"] = [e for e in analyser_ethique(corrige, intention) if e["categorie"] != "injure"]
    # 2. Medicines: instruction or mere mention?
    if noms:
        vides = {"et", "ou", "du", "de", "des", "le", "la", "les", "un", "une", "aussi", "encore", "puis", "avec", "vous", "pour"}
        lus = {w for m in meds for w in m["lu"].split()}
        reste = [w for w in jetons if w not in vides and w not in lus]
        vague = bool(QUANTITE_VAGUE.search(t))
        consigne = intention == "consigne" or (intention == "ambigu" and (len(reste) <= 2 or vague or re.search(DOSE, t)))
        if consigne:
            sortie.update(consigne_medicament=True, medicament=noms[0], dose_imprecise=vague and not re.search(DOSE, t),
                          medicament_controle=any(f.get("categorie") in ("controle", "stupefiant", "psychotrope") for f in fiches.values()))
        elif intention == "ambigu":
            sortie["a_confirmer"] = (sortie["a_confirmer"] or "") + (" ; " if sortie["a_confirmer"] else "") + \
                f"{', '.join(noms)} cité sans que l'on sache si c'est une consigne de prise"
        else:
            sortie["evocation"] = (sortie["evocation"] + " ; " if sortie["evocation"] else "") + \
                f"{', '.join(noms)} cité dans {INTENTIONS[intention]}"
    return sortie
