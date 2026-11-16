"""The doctor writes in ENGLISH or ARABIC: the same translation into pictograms as in French.

The forms come from the labels of the pictograms (built-in library, and base_v2 concepts when plugged in), plus a short
list of everyday words per language. The safety rules are those of the French engine: negation, "at most", numbers,
doses and medicines are never lost; a word without a safe pictogram is reported to the doctor, never guessed.
"""
from __future__ import annotations

import re
import unicodedata

# ------------------------------------------------------------------ Arabic normalisation
_TASHKIL = re.compile(r"[ً-ْٰـ]")        # short vowels, tanwin, shadda, sukun, tatweel


def norm_ar(m: str) -> str:
    m = _TASHKIL.sub("", m)
    m = re.sub("[إأآٱ]", "ا", m).replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    return m


def variantes_ar(m: str) -> list[str]:
    """« والألم » -> « والالم », « الالم », « الم »: attached conjunction / preposition / article removed."""
    m = norm_ar(m)
    sortie = [m]
    for pref in ("و", "ف", "ب", "ل", "ك"):
        if m.startswith(pref) and len(m) > 3:
            sortie.append(m[1:])
    for x in list(sortie):
        for art in ("ال", "لل"):
            if x.startswith(art) and len(x) > len(art) + 1:
                sortie.append(x[len(art):])
    for x in list(sortie):
        if x.endswith("ا") and len(x) > 3:          # « صباحًا » -> « صباح »
            sortie.append(x[:-1])
        if x.endswith("ه") and len(x) > 3:          # « حساسيه » -> « حساسي »
            sortie.append(x[:-1])
    return list(dict.fromkeys(sortie))


# ------------------------------------------------------------------ everyday words
MOTS = {
    "en": {"not": "NE_PAS", "no": "NE_PAS", "don't": "NE_PAS", "dont": "NE_PAS", "never": "NE_PAS", "without": "NE_PAS",
           "stop": "STOP", "emergency": "URGENCE", "maximum": "MAXIMUM", "max": "MAXIMUM", "you": "VOUS", "your": "VOUS",
           "i": "MOI", "me": "MOI", "my": "MOI", "yes": "OUI", "pain": "DOULEUR", "hurt": "DOULEUR", "hurts": "DOULEUR",
           "ache": "DOULEUR", "painful": "DOULEUR", "stomach": "VENTRE", "belly": "VENTRE", "tummy": "VENTRE", "abdomen": "VENTRE",
           "headache": "TETE+DOULEUR", "pregnant": "ENCEINTE", "pregnancy": "ENCEINTE", "fever": "FIEVRE", "temperature": "FIEVRE",
           "cough": "TOUX", "vomit": "VOMIR", "vomiting": "VOMIR", "nausea": "VOMIR", "sick": "VOMIR", "breathe": "RESPIRER",
           "breathing": "RESPIRER", "allergic": "ALLERGIE", "allergy": "ALLERGIE", "allergies": "ALLERGIE", "medicine": "MEDICAMENT",
           "medicines": "MEDICAMENT", "medication": "MEDICAMENT", "drug": "MEDICAMENT", "tablet": "COMPRIME", "tablets": "COMPRIME",
           "pill": "COMPRIME", "pills": "COMPRIME", "take": "PRENDRE", "taking": "PRENDRE", "agree": "ACCORD", "understand": "COMPRENDRE",
           "understood": "COMPRENDRE", "morning": "MATIN", "noon": "MIDI", "midday": "MIDI", "evening": "SOIR", "night": "NUIT",
           "day": "JOUR", "days": "JOUR", "daily": "JOUR", "week": "SEMAINE", "weeks": "SEMAINE", "times": "FOIS", "time": "FOIS",
           "more": "PLUS", "less": "MOINS", "before": "AVANT", "after": "APRES", "head": "TETE", "chest": "POITRINE",
           "doctor": "MEDECIN", "hospital": "HOPITAL", "water": "EAU", "eat": "MANGER", "drink": "BOIRE", "sleep": "DORMIR",
           "wait": "ATTENDRE", "blood": "SANG", "baby": "BEBE", "question": "QUESTION", "up": None},
    "ar": {"لا": "NE_PAS", "لم": "NE_PAS", "لن": "NE_PAS", "ليس": "NE_PAS", "بدون": "NE_PAS", "دون": "NE_PAS", "ممنوع": "NE_PAS",
           "نعم": "OUI", "انت": "VOUS", "انتي": "VOUS", "لديك": "VOUS", "عندك": "VOUS", "تشعر": "VOUS", "تشعرين": "VOUS",
           "انا": "MOI", "عندي": "MOI", "الم": "DOULEUR", "وجع": "DOULEUR", "يؤلمك": "DOULEUR", "يولمك": "DOULEUR", "تتالم": "DOULEUR",
           "بطن": "VENTRE", "معده": "VENTRE", "راس": "TETE", "صداع": "TETE+DOULEUR", "صدر": "POITRINE", "حامل": "ENCEINTE",
           "حمل": "ENCEINTE", "حمي": "FIEVRE", "حراره": "FIEVRE", "سعال": "TOUX", "كحه": "TOUX", "تقيو": "VOMIR", "غثيان": "VOMIR",
           "تنفس": "RESPIRER", "حساسيه": "ALLERGIE", "حساسي": "ALLERGIE", "دواء": "MEDICAMENT", "ادويه": "MEDICAMENT",
           "قرص": "COMPRIME", "اقراص": "COMPRIME", "حبه": "COMPRIME", "حبوب": "COMPRIME", "خذ": "PRENDRE", "خذي": "PRENDRE",
           "تناول": "PRENDRE", "تناولي": "PRENDRE", "تتناول": "PRENDRE", "موافق": "ACCORD", "توافق": "ACCORD", "توافقين": "ACCORD",
           "فهمت": "COMPRENDRE", "تفهم": "COMPRENDRE", "افهم": "COMPRENDRE", "صباح": "MATIN", "ظهر": "MIDI", "مساء": "SOIR",
           "ليل": "NUIT", "يوم": "JOUR", "ايام": "JOUR", "يوميا": "JOUR", "اسبوع": "SEMAINE", "مرات": "FOIS", "مره": "FOIS",
           "اكثر": "PLUS", "اقل": "MOINS", "قبل": "AVANT", "بعد": "APRES", "طبيب": "MEDECIN", "مستشفي": "HOPITAL", "ماء": "EAU",
           "طوارئ": "URGENCE", "توقف": "STOP", "انتظر": "ATTENDRE", "دم": "SANG", "اقصي": "MAXIMUM", "حد": None},
}
VIDES = {
    "en": {"the", "a", "an", "of", "to", "is", "are", "am", "do", "does", "did", "be", "it", "this", "that", "and", "or", "in", "on",
           "at", "for", "with", "have", "has", "had", "will", "would", "please", "some", "any", "can", "could", "where", "how", "what",
           "much", "many", "since", "from", "per", "each", "every", "feel", "got", "get", "there", "here", "now", "today", "also"},
    "ar": {"هل", "في", "من", "على", "الي", "عن", "هذا", "هذه", "ما", "ماذا", "اين", "كيف", "كم", "منذ", "مع", "او", "ثم", "كل",
           "الان", "اليوم", "ايضا", "يا", "لمده", "مده", "خلال", "من فضلك", "فضلك", "بال", "به", "بها", "لك", "كان", "يكون", "تكون", "انه", "انها"},
}
MEDICAMENTS = {
    "en": {"acetaminophen": "paracetamol", "paracetamol": "paracetamol", "tylenol": "paracetamol", "ibuprofen": "ibuprofene",
           "advil": "ibuprofene", "aspirin": "aspirine", "amoxicillin": "amoxicilline", "metformin": "metformine",
           "tramadol": "tramadol", "misoprostol": "misoprostol"},
    "ar": {"باراسيتامول": "paracetamol", "بنادول": "paracetamol", "ايبوبروفين": "ibuprofene", "بروفين": "ibuprofene",
           "اسبرين": "aspirine", "اموكسيسيلين": "amoxicilline", "ميتفورمين": "metformine", "ترامادول": "tramadol",
           "ميزوبروستول": "misoprostol"},
}
MEDICAMENTS["ar"].update(MEDICAMENTS["en"])            # names written in Latin letters inside an Arabic sentence
MEDICAMENTS["ar"].update({m: m for m in ("ibuprofene", "aspirine", "amoxicilline", "metformine")})
MEDICAMENTS["en"].update({m: m for m in ("ibuprofene", "aspirine", "amoxicilline", "metformine")})
GARDES = ("NE_PAS", "STOP", "URGENCE", "MAXIMUM")       # safety pictograms: always kept whole


def _jetons(texte: str, langue: str) -> list[str]:
    texte = (texte or "").replace("’", "'").replace("؟", " ? ").replace("،", " , ")
    texte = re.sub(r"(\d+)\s*(mg|g|ml|ملغ|مغ)\b", lambda m: m.group(1) + ("mg" if m.group(2) in ("ملغ", "مغ") else m.group(2)), texte)
    texte = texte.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    if langue == "ar":
        return re.findall(r"[\w']+|\?", norm_ar(texte))
    return re.findall(r"[a-z0-9']+|\?", texte.lower())


def formes(labels: dict[str, dict], langue: str) -> dict[tuple, str]:
    """{(tokens of a label): pictogram id} from {id: {"en": …, "ar": …, "recherche": {"en": [...]}}}."""
    sortie: dict[tuple, str] = {}
    for ident, n in labels.items():
        noms = [n.get(langue) or ""] + list((n.get("recherche") or {}).get(langue) or [])
        for nom in noms:
            nom = re.sub(r"\s*\([^)]*\)", "", nom)            # « take (swallow) » -> « take »
            cle = tuple(_jetons(nom, langue))
            if cle and cle not in sortie:
                sortie[cle] = ident
    return sortie


def traduire(texte: str, langue: str, formes_langue: dict[tuple, str], disponible=lambda i: True) -> dict:
    """Same output as the French engines: {"pictogrammes", "non_traduits", "couverture"}."""
    mots, meds, vides = MOTS[langue], MEDICAMENTS[langue], VIDES[langue]
    jetons = _jetons(texte, langue)
    pictos, manquants, i = [], [], 0
    while i < len(jetons):
        m = jetons[i]
        if m == "?":
            pictos.append("QUESTION"); i += 1; continue
        if m == ",":
            i += 1; continue
        if m.isdigit():
            pictos.append(f"CHIFFRE:{m}"); i += 1; continue
        if re.fullmatch(r"\d+(?:[.,]\d+)?(mg|g|ml|ui)", m):
            pictos.append(f"DOSE:{m}"); i += 1; continue
        if langue == "en" and m == "up" and i + 1 < len(jetons) and jetons[i + 1] == "to":     # "up to 3 times" = at most
            pictos.append("MAXIMUM"); i += 2; continue
        variantes = variantes_ar(m) if langue == "ar" else [m, m.rstrip("s")] if len(m) > 3 else [m]
        med = next((meds[v] for v in variantes if v in meds), None)
        if med:
            pictos.append(f"MEDICAMENT:{med}"); i += 1; continue
        garde = next((mots[v] for v in variantes if mots.get(v) in GARDES), None)
        if garde:
            pictos.append(garde); i += 1; continue
        trouve = None
        for L in range(min(5, len(jetons) - i), 0, -1):          # longest expression first
            for v in (variantes if L == 1 else [m]):
                ident = formes_langue.get(tuple([v] + jetons[i + 1:i + L]))
                if ident and disponible(ident):
                    trouve = (ident, L); break
            if trouve:
                break
        if trouve:
            pictos.append(trouve[0]); i += trouve[1]; continue
        connu = next((v for v in variantes if v in mots), None)
        if connu is not None:
            if mots[connu] and all(disponible(x) for x in mots[connu].split("+")):
                pictos.append(mots[connu])
            elif mots[connu]:
                manquants.append(m)
        elif not any(v in vides for v in variantes):
            manquants.append(m)
        i += 1
    pictos = [p for k, p in enumerate(pictos) if k == 0 or p != pictos[k - 1] or p.startswith("CHIFFRE:")]
    compte = len(pictos) + len(manquants)
    return {"pictogrammes": pictos, "non_traduits": manquants, "couverture": round(len(pictos) / compte, 2) if compte else 0.0}


_ARABE = re.compile(r"[\u0600-\u06FF]")
_FRANCAIS = re.compile(r"[éèêàùçôîâœ]|\b(vous|êtes|etes|avez|est|les|des|du|une|je|pas|pendant|jusqu|fois|jours?|matin|soir|"
                       r"médicament|medicament|d'accord|accord|oui|non|où|mal|ventre|tête)\b", re.I)


def langue_du_texte(texte: str, defaut: str) -> str:
    """Language a text is written in: Arabic script, French words, else the doctor's language. The system writes its
    own texts (welcome message, assistant's questions, treatment explanations) in French; the doctor types in theirs."""
    if _ARABE.search(texte or ""):
        return "ar"
    if defaut != "fr" and _FRANCAIS.search(texte or ""):
        return "fr"
    return defaut


def traduire_dans_sa_langue(pictogrammeur, texte: str) -> dict:
    """pictogrammeur.traduire(texte) in the language the text is written in."""
    defaut = getattr(pictogrammeur, "langue_saisie", "fr")
    langue = langue_du_texte(texte, defaut)
    if langue == defaut or not hasattr(pictogrammeur, "langue_saisie"):
        return pictogrammeur.traduire(texte)
    pictogrammeur.langue_saisie = langue
    try:
        return pictogrammeur.traduire(texte)
    finally:
        pictogrammeur.langue_saisie = defaut
