"""Text ⇄ pictogram translation: INTERFACE + demo implementation.

Agent 1 (translator) only uses two methods; any engine can provide them:

    traduire(texte: str) -> {"pictogrammes": [str], "non_traduits": [str], "couverture": float}
    interpreter(pictogrammes: list[str]) -> str

`LexiquePictogrammes` is a minimal dictionary-based version, without AI, to run the scenarios. The team-mate who
develops agent 1 replaces it with their model (pictogram selection or generation) while keeping these two
methods: see docs/technique/CONTRAT_AGENT1.md.
A pictogram is designated by an identifier, e.g. "DOULEUR" or "MEDICAMENT:paracetamol" (generic pictogram +
label). Several pictograms can form ONE combined image: "TETE+DOULEUR" (the first one large, the others as
badges). Negation, the "at most" limit and emergency are never combined: they always stay whole pictograms.
"""
import re
import unicodedata
from typing import Protocol


class Pictogrammeur(Protocol):
    def traduire(self, texte: str) -> dict: ...
    def interpreter(self, pictogrammes: list[str]) -> str: ...


def _norm(m: str) -> str:
    m = unicodedata.normalize("NFD", m.lower())
    return "".join(c for c in m if unicodedata.category(c) != "Mn")


MOTS = {
    # body and symptoms
    "douleur": "DOULEUR", "mal": "DOULEUR", "ventre": "VENTRE", "tete": "TETE", "poitrine": "POITRINE",
    "fievre": "FIEVRE", "toux": "TOUX", "vomir": "VOMIR", "nausee": "VOMIR", "nausees": "VOMIR",
    "respirer": "RESPIRER", "respiration": "RESPIRER", "sang": "SANG", "allergie": "ALLERGIE", "allergies": "ALLERGIE",
    "enceinte": "ENCEINTE", "grossesse": "ENCEINTE", "bebe": "BEBE",
    # soins
    "medicament": "MEDICAMENT", "medicaments": "MEDICAMENT", "comprime": "COMPRIME", "comprimes": "COMPRIME",
    "prendre": "PRENDRE", "prenez": "PRENDRE", "traitement": "MEDICAMENT", "medecin": "MEDECIN",
    "hopital": "HOPITAL", "urgence": "URGENCE", "urgences": "URGENCE", "analyse": "ANALYSE", "examen": "EXAMEN",
    "manger": "MANGER", "boire": "BOIRE", "eau": "EAU", "dormir": "DORMIR", "repos": "DORMIR",
    # temps
    "matin": "MATIN", "midi": "MIDI", "soir": "SOIR", "nuit": "NUIT", "jour": "JOUR", "jours": "JOUR",
    "semaine": "SEMAINE", "fois": "FOIS", "par": None, "plus": "PLUS", "moins": "MOINS", "maximum": "MAXIMUM", "max": "MAXIMUM", "avant": "AVANT", "apres": "APRES",
    # negation: never removed
    "pas": "NE_PAS", "jamais": "NE_PAS", "aucun": "NE_PAS", "aucune": "NE_PAS", "sans": "NE_PAS", "rien": "NE_PAS",
    # exchange
    "oui": "OUI", "non": "NON", "vous": "VOUS", "je": "MOI", "moi": "MOI", "accord": "ACCORD", "pendant": None, "a": None, "comprendre": "COMPRENDRE",
    "compris": "COMPRENDRE", "stop": "STOP", "attendre": "ATTENDRE",
}
# Medical vocabulary of the existing databases (pictogrammes/bases/vocabulaire_medical.json): used only if the matching
# image is available; otherwise the word is reported to the doctor as "without pictogram".
MOTS_BASES = {
    "gorge": "GORGE", "oreille": "OREILLE", "oreilles": "OREILLE", "oeil": "OEIL", "yeux": "OEIL", "dent": "DENT", "dents": "DENT",
    "dos": "DOS", "bras": "BRAS", "jambe": "JAMBE", "jambes": "JAMBE", "pied": "PIED", "pieds": "PIED", "main": "MAIN",
    "mains": "MAIN", "coeur": "COEUR", "peau": "PEAU", "vertige": "VERTIGE", "vertiges": "VERTIGE", "fatigue": "FATIGUE",
    "fatiguee": "FATIGUE", "diarrhee": "DIARRHEE", "constipation": "CONSTIPATION", "constipe": "CONSTIPATION",
    "constipee": "CONSTIPATION", "demangeaison": "DEMANGEAISON", "demangeaisons": "DEMANGEAISON", "brulure": "BRULURE",
    "brulures": "BRULURE", "gonflement": "GONFLEMENT", "gonfle": "GONFLEMENT", "gonflee": "GONFLEMENT", "rhume": "RHUME",
    "enrhume": "RHUME", "evanouissement": "EVANOUISSEMENT", "evanoui": "EVANOUISSEMENT", "peur": "PEUR",
    "inquiet": "INQUIET", "inquiete": "INQUIET", "inquietude": "INQUIET", "triste": "TRISTE", "content": "CONTENT",
    "contente": "CONTENT", "heureux": "CONTENT", "colere": "COLERE", "piqure": "INJECTION", "injection": "INJECTION",
    "vaccin": "VACCIN", "pansement": "PANSEMENT", "ordonnance": "ORDONNANCE", "pharmacie": "PHARMACIE",
    "thermometre": "THERMOMETRE", "tension": "TENSION", "radio": "RADIO", "radiographie": "RADIO",
    "echographie": "ECHOGRAPHIE", "operation": "OPERATION", "chirurgie": "OPERATION", "sirop": "SIROP",
    "pommade": "POMMADE", "creme": "POMMADE", "gouttes": "GOUTTES", "ambulance": "AMBULANCE", "infirmier": "INFIRMIER",
    "infirmiere": "INFIRMIER", "famille": "FAMILLE", "enfant": "ENFANT", "enfants": "ENFANT", "interprete": "INTERPRETE",
    "aide": "AIDE", "aider": "AIDE", "repeter": "REPETER",
}
MOTS_OUTILS = set("""
le la les un une des du de d l et ou est etes sont au aux en dans pour sur avec a ce cette ces qui que quoi quel
quelle avez avoir il elle on y ne votre vos mon ma mes ton ta tes son sa ses qu se si mais
""".split())
MEDICAMENTS = {"paracetamol", "ibuprofene", "misoprostol", "tramadol", "amoxicilline", "aspirine", "metformine"}


class LexiquePictogrammes:
    """Demo: one word → one pictogram, numbers as digits, medicines labelled."""

    def traduire(self, texte: str) -> dict:
        pictos, manquants = [], []
        texte = re.sub(r"(\d+)\s*(mg|g|ml|mcg|µg)\b", r"\1\2", texte, flags=re.IGNORECASE)   # « 500 mg » -> « 500mg »
        for brut in re.findall(r"[\w'’]+|\?", texte):
            m0 = _norm(brut).replace("’", "'")
            if m0.startswith("jusqu"):                       # "jusqu'à 3 fois" (up to 3 times): a limit, never lost
                pictos.append("MAXIMUM")
                continue
            m = re.sub(r"^(d|l|qu|j|s|n|c)'", "", m0)
            if m == "?":
                pictos.append("QUESTION")
            elif m.isdigit():
                pictos.append(f"CHIFFRE:{m}")
            elif re.fullmatch(r"\d+(mg|g|ml|mcg|µg)", m):
                pictos.append(f"DOSE:{m}")
            elif m in MEDICAMENTS:
                pictos.append(f"MEDICAMENT:{m}")
            elif m in MOTS:
                if MOTS[m]:
                    pictos.append(MOTS[m])
            elif m in MOTS_BASES:
                from .bibliotheque import connu
                (pictos if connu(MOTS_BASES[m]) else manquants).append(MOTS_BASES[m] if connu(MOTS_BASES[m]) else brut)
            elif m in MOTS_OUTILS:
                pass
            else:
                manquants.append(brut)
        # "pas plus de 4" = at most 4 (not "do not" + "more")
        i = 0
        while i < len(pictos) - 1:
            if pictos[i] == "NE_PAS" and pictos[i + 1] == "PLUS":
                pictos[i:i + 2] = ["MAXIMUM"]
            i += 1
        pictos = combiner_automatiquement(pictos)
        compte = len(pictos) + len(manquants)
        return {"pictogrammes": pictos, "non_traduits": manquants,
                "couverture": round(len(pictos) / compte, 2) if compte else 0.0}

    def interpreter(self, pictogrammes: list[str]) -> str:
        mot = lambda p: p.split(":", 1)[-1].lower() if ":" in p else p.lower()
        return " ".join("(" + " + ".join(mot(x) for x in p.split("+")) + ")" if "+" in p else mot(p) for p in pictogrammes)


PARTIES_DU_CORPS = {"TETE", "VENTRE", "POITRINE", "GORGE", "OREILLE", "OEIL", "DENT", "DOS", "BRAS", "JAMBE", "PIED",
                    "MAIN", "COEUR", "PEAU"}
SIGNES = {"DOULEUR", "SANG"}


def combiner_automatiquement(pictos: list[str]) -> list[str]:
    """Merges into one image the pairs that read better together: body part + pain (or blood), in either
    order ("mal au ventre", "ventre douloureux"). Everything else is left as is."""
    from .bibliotheque import combinaison_valide
    sortie, i = [], 0
    while i < len(pictos):
        a, b = pictos[i], pictos[i + 1] if i + 1 < len(pictos) else None
        if b and a in PARTIES_DU_CORPS and b in SIGNES and combinaison_valide(f"{a}+{b}"):
            sortie.append(f"{a}+{b}"); i += 2
        elif b and a in SIGNES and b in PARTIES_DU_CORPS and combinaison_valide(f"{b}+{a}"):
            sortie.append(f"{b}+{a}"); i += 2
        else:
            sortie.append(a); i += 1
    return sortie
