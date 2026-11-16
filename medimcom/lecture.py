"""Reads a message as a caregiver would: WHO speaks about WHAT, and TO DO WHAT.

A single word is not enough to judge a message. "Prenez du tramadol" (take tramadol) is an instruction; "Votre
frère a pris du tramadol hier ?" is a question; "Le tramadol peut donner des nausées" is information; "Il s'est
pendu l'an dernier" is a narrative; "Allez vous pendre" is an incitement. This module reads the context (person,
tense, question, negation, reported speech) and returns an intention WITH ITS CLUES: the jurist, the assistant and
the doctor see why a message is read as an instruction or as a narrative. Deterministic, fast, verifiable.

It also corrects typing and dictation errors on what matters for safety:
  - medicine names: "tramadole", "paracetamole", "para c'est tamol" (dictation), "ibuprophène";
  - self-harm words written phonetically: "pandre", "suisider";
  - common words typed on a QWERTY keyboard by an AZERTY user ("sentew" -> "sentez").
A correction is only made when it is safe (phonetic variant or one-character error on a long, distinctive word);
it is always shown ("read as"), never silent.
"""
from __future__ import annotations

import re
import unicodedata


def normaliser(texte: str) -> str:
    t = unicodedata.normalize("NFKD", (texte or "").lower().replace("œ", "oe").replace("’", "'"))
    return re.sub(r"\s+", " ", "".join(c for c in t if not unicodedata.combining(c))).strip()


def mots(texte: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normaliser(texte))


# ------------------------------------------------------------------ typing and dictation errors
def distance(a: str, b: str, maxi: int = 2) -> int:
    """Edit distance with transposition ("tramdaol"), stopped beyond `maxi`."""
    if abs(len(a) - len(b)) > maxi:
        return maxi + 1
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            c = a[i - 1] != b[j - 1]
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


def cle_phonetique(mot: str) -> str:
    """Simplified French pronunciation key: "pandre" = "pendre", "suisider" = "suicider",
    "paracetamole" = "paracetamol", "ibuprophene" = "ibuprofene"."""
    m = normaliser(mot).replace(" ", "")
    for a, b in (("ph", "f"), ("qu", "k"), ("ck", "k"), ("ch", "$"), ("sch", "$"), ("eau", "o"), ("au", "o"),
                 ("ain", "in"), ("ein", "in"), ("aim", "in"), ("an", "en"), ("am", "en"), ("em", "en"), ("y", "i"),
                 ("h", ""), ("z", "s"), ("ce", "se"), ("ci", "si"), ("ca", "ka"), ("co", "ko"), ("cu", "ku"),
                 ("c", "k"), ("ai", "e"), ("ei", "e"), ("er", "e"), ("ez", "e"), ("et", "e")):
        m = m.replace(a, b)
    m = re.sub(r"(.)\1+", r"\1", m)          # doubled letters
    return re.sub(r"[estxd]+$", "", m) or m   # finales muettes


# QWERTY keyboard used by a French speaker used to AZERTY: z<->w, a<->q, m<->;
_CLAVIER = {"w": "z", "z": "w", "q": "a", "a": "q"}


def variantes(mot: str) -> list[str]:
    """Variants of a word for the most frequent errors (keyboard, doubled letter, final e)."""
    m = normaliser(mot)
    v = []
    for i, c in enumerate(m):
        if c in _CLAVIER:
            v.append(m[:i] + _CLAVIER[c] + m[i + 1:])
    v += [re.sub(r"(.)\1", r"\1", m, count=1)]
    v += [m[:-1]] if m.endswith("e") and len(m) > 3 else [m + "e"]
    return [x for x in dict.fromkeys(v) if x and x != m]


# ------------------------------------------------------------------ medicines (with typos and dictation)
# Brand names and common forms -> name used by the rules
NOMS_COURANTS = {"doliprane": "paracetamol", "efferalgan": "paracetamol", "dafalgan": "paracetamol", "panadol": "paracetamol",
                 "acetaminophene": "paracetamol", "advil": "ibuprofene", "nurofen": "ibuprofene", "brufen": "ibuprofene",
                 "aspegic": "aspirine", "kardegic": "aspirine", "glucophage": "metformine", "clamoxyl": "amoxicilline",
                 "augmentin": "amoxicilline", "tramal": "tramadol", "ultram": "tramadol", "contramal": "tramadol",
                 "topalgic": "tramadol", "ixprim": "tramadol"}
AUTRES_MEDICAMENTS = {"insuline", "morphine", "codeine", "diclofenac", "diazepam", "artemether", "coartem", "quinine",
                      "misoprostol", "prednisone", "ciprofloxacine", "metronidazole", "omeprazole", "salbutamol"}
CLASSES = re.compile(r"\b(?:antibiotiques?|antidouleurs?|anti-inflammatoires?|antalgiques?|anxiolytiques?|somniferes?|"
                     r"antidepresseurs?|opioides?|opiaces?|calmants?)\b")


def _formes(medicaments: dict) -> dict[str, str]:
    formes = {}
    for nom, fiche in (medicaments or {}).items():
        for f in [nom, *fiche.get("synonymes", [])]:
            formes[normaliser(f.replace("_", " ")).replace(" ", "")] = nom
    for f, nom in NOMS_COURANTS.items():
        formes.setdefault(f, nom if nom in (medicaments or {}) else nom)
    for f in AUTRES_MEDICAMENTS:
        formes.setdefault(f, f)
    return formes


_VIDES = {"le", "la", "les", "un", "une", "des", "du", "de", "d", "l", "et", "ou", "a", "au", "aux", "en", "vous", "je", "il",
          "elle", "on", "me", "te", "se", "ce", "c", "est", "pas", "ne", "pour", "par", "avec", "sans", "plus"}


def trouver_medicaments(texte: str, medicaments: dict) -> list[dict]:
    """[{nom, lu, corrige}]: medicines mentioned, including misspelt ("tramadole") or mis-dictated ("para c'est
    tamol", "trama dol"). A correction is kept only for a word of at least 6 letters, one error away (two for 9
    letters and more) or with the same pronunciation, and without ambiguity between two medicines."""
    formes = _formes(medicaments)
    cles = {}
    for f, nom in formes.items():
        cles.setdefault(cle_phonetique(f), set()).add(nom)
    jetons = mots(texte)
    trouves, pris = [], set()
    for taille in (1, 4, 3, 2):                   # single words first; then names split by dictation ("trama dol")
        for i in range(len(jetons) - taille + 1):
            if any(k in pris for k in range(i, i + taille)):
                continue
            fenetre = jetons[i:i + taille]
            if taille > 1 and (fenetre[0] in _VIDES or fenetre[-1] in _VIDES or any(w in formes for w in fenetre)):
                continue                          # "du tramadol" is not a typo of "tramadol"
            brut = "".join(jetons[i:i + taille])
            lu = " ".join(jetons[i:i + taille])
            if len(brut) < 5 or (taille > 1 and len(brut) < 7):
                continue
            nom, corrige = formes.get(brut), False
            if nom is None:
                candidats = {n for n in cles.get(cle_phonetique(brut), set())
                             if any(abs(len(f) - len(brut)) <= 2 for f, x in formes.items() if x == n)}
                if len(candidats) != 1 and len(brut) >= 6:
                    maxi = 2 if len(brut) >= 9 else 1
                    proches = {n for f, n in formes.items() if len(f) >= 6 and f[0] == brut[0] and distance(brut, f, maxi) <= maxi}
                    candidats = proches
                if len(candidats) == 1:
                    nom, corrige = next(iter(candidats)), True
            if nom and taille > 1:
                corrige = True                    # name split by dictation and glued back
            if nom and (taille == 1 or corrige):
                trouves.append({"nom": nom, "lu": lu, "corrige": corrige or lu.replace(" ", "") != nom})
                pris.update(range(i, i + taille))
    vus, sortie = set(), []
    for t in sorted(trouves, key=lambda x: texte.lower().find(x["lu"].split()[0])):
        if t["nom"] not in vus:
            vus.add(t["nom"])
            sortie.append(t)
    for c in CLASSES.finditer(normaliser(texte)):
        if c.group(0) not in vus:
            sortie.append({"nom": c.group(0), "lu": c.group(0), "corrige": False})
    return sortie


# ------------------------------------------------------------------ words of harm to self or others
MOTS_DE_MORT = {"pendre", "pendez", "pends", "pendu", "pendue", "pendaison", "suicide", "suicider", "suicidez", "suicidaire",
                "tuer", "tue", "tuez", "tuee", "mourir", "meurs", "mourez", "mort", "morte", "crever", "creve", "crevez",
                "egorger", "poignarder", "empoisonner", "etrangler", "noyer", "noyez", "defenestrer"}
# Phonetic correction only towards long words without a common homophone ("noyer" ~ "noix": excluded)
_CORRIGIBLES = ["pendre", "suicider", "suicide", "mourir", "crever", "egorger", "poignarder", "empoisonner", "etrangler",
                "defenestrer", "pendue", "pendaison", "suicidaire", "pendez", "suicidez"]       # infinitifs d'abord
_CLES_MORT: dict = {}
for _m in _CORRIGIBLES:
    _CLES_MORT.setdefault(cle_phonetique(_m), _m)


def corriger_mots_de_mort(texte: str) -> tuple[str, dict]:
    """"pandre" -> "pendre", "suisider" -> "suicider": only with the SAME PRONUNCIATION (never "prendre",
    "rendre" or "vendre", which are not pronounced the same)."""
    corrections = {}

    def remplacer(m):
        w = m.group(0)
        n = normaliser(w)
        if n in MOTS_DE_MORT or len(n) < 6:
            return w
        cible = _CLES_MORT.get(cle_phonetique(n))
        if cible:
            corrections[w] = cible
            return cible
        return w
    return re.sub(r"[A-Za-zÀ-ÿ]+", remplacer, texte), corrections


# ------------------------------------------------------------------ context reading
# Interrogative inversion ("avez-vous", "prenez-vous"): only with these verbs, otherwise it is a reflexive
# imperative ("lavez-vous les mains", "pendez-vous")
_VERBES_QUESTION = (r"avez|as|a|etes|es|est|sont|ont|pouvez|peux|voulez|veux|prenez|prends|buvez|bois|sentez|sens|faites|fais|"
                    r"dormez|mangez|savez|sais|connaissez|souffrez|toussez|vomissez|saignez|allez|vas|va|habitez|fumez|"
                    r"travaillez|comprenez|entendez|voyez|vivez|utilisez|aviez|etiez|prenait|prenez")
QUESTION = re.compile(r"\?|\best[- ]ce\b|\b(?:" + _VERBES_QUESTION + r")-(?:t-)?(?:vous|tu|il|elle|ils|elles)\b|"
                      r"^\s*(?:qu|quel|quelle|quels|quelles|comment|pourquoi|quand|ou|combien|avez|as|etes)\b")
NEGATION = re.compile(r"\bne\b[^.?!]{0,40}\b(?:pas|jamais|plus|aucun|aucune)\b|\bn'[a-z]+ (?:pas|jamais|plus)\b|\bpas de\b|\bpas d'|\bsans\b|"
                      r"\bjamais\b|\b(?:arrete[sz]?|arretez|evite[sz]?|evitez|stop|stoppez|interdit|dangereux|attention|"
                      r"don't|do not|never|avoid)\b")
CONSIGNE = re.compile(
    r"\b(?:prenez|prends|buvez|bois|avalez|avale|mettez|appliquez|injectez|utilisez|continuez|commencez|reprenez|"
    r"doublez|augmentez|take|drink|swallow)\b|"
    r"\b(?:il faut|faut)\s+(?:que vous\s+|que tu\s+)?(?:prendre|preniez|boire|buviez|avaler|mettre)\b|"
    r"\b(?:vous|tu)\s+(?:devez|dois|allez|vas|pouvez|peux)\s+(?:en\s+)?(?:prendre|boire|avaler|mettre|utiliser)\b|"
    r"\b(?:vous|tu)\s+(?:prenez|prends|buvez|bois|avalez)\b|"
    r"\b(?:je|on|nous)\s+(?:vais\s+|va\s+|allons\s+)?(?:vous\s+|te\s+|t')?(?:prescri\w*|donne\w*|conseill\w*|recommand\w*|"
    r"mets|mettre|ajoute\w*)\b|"
    r"\ba prendre\b|\b\d+\s*(?:fois|x)\s*(?:par|/)\s*(?:jour|j)\b")
# STRONG incitement: imperative addressed to the patient ("allez vous pendre", "pendez-vous", "tu devrais mourir")
INCITATION = re.compile(r"\b(?:va|vas|allez|aller)\s+(?:te|vous|t')\s*(?:pendre|tuer|suicider|jeter|noyer|empoisonner)\b|"
                        r"\b(?:pends|pendez|tue|tuez|suicide|suicidez|noie|noyez|jette|jetez)[- ](?:toi|vous)\b|"
                        r"\b(?:tu|vous)\s+(?:devrais|devriez|dois|devez|ferais mieux de|feriez mieux de)\s+"
                        r"(?:mourir|te tuer|vous tuer|te pendre|vous pendre|disparaitre|en finir)\b|"
                        r"\b(?:va|allez)\s+mourir\b|\b(?:kill|hang)\s+yourself\b")
# WEAK incitement: "(et) vous pendre" — infinitive addressed to the patient, without question or narrative
ATTEINTE = re.compile(r"\b(?:vous|te|t')\s*(?:pendre|tuer|suicider|noyer|empoisonner|etrangler|jeter par)\b")
MENACE = re.compile(r"\bje\s+(?:vais\s+)?(?:te|vous)\s+(?:tuer|frapper|buter|etrangler)\b")
DEPISTAGE = re.compile(r"\b(?:idees?|envie|pense[sz]?|pensez|penser|songe[sz]?|songez|voulu|voulez|veux|essaye|tente|"
                       r"deja|risque|est[- ]ce)\b")
PASSE = re.compile(r"\b(?:ai|as|a|avons|avez|ont|avait|avais|avaient|aviez|avions|etait|etais|etaient|est|es|sont|"
                   r"s'est|se sont|m'a|t'a|l'a|lui a|leur a)\s+(?:deja\s+|voulu\s+|essaye\s+de\s+|tente\s+de\s+)?"
                   r"(?:pris|bu|mis|avale|voulu|essaye|tente|dit|fait|eu|ete|mort|morte|pendu|pendue|suicide|suicidee|tue|tuee|"
                   r"(?!\w*(?:er|re|ir)\b)\w+(?:e|i|u|is|it)s?)\b|"      # participle, not an infinitive ("à vendre", "à manger")
                   r"\b(?:hier|avant-hier|la semaine derniere|le mois dernier|l'an dernier|l'annee derniere|il y a|autrefois|"
                   r"jadis|quand j'etais|quand il etait|quand elle etait|en \d{4})\b|\b\w{3,}(?:ait|aient)\b")
TIERS = re.compile(r"\b(?:il|elle|ils|elles)\b|\b(?:mon|ma|mes|ton|ta|tes|son|sa|ses|votre|vos|leur|leurs|notre|nos|un|une|le|la)\s+"
                   r"(?:pere|mere|frere|soeur|fils|fille|enfant|enfants|mari|femme|epouse|epoux|voisin|voisine|ami|amie|"
                   r"cousin|cousine|oncle|tante|collegue|patient|patiente|grand-pere|grand-mere|bebe|famille|parent|parents)\b|"
                   r"\bquelqu'un\b|\bpersonne de\b")
RAPPORTE = re.compile(r"\b(?:dit|dites|disait|disent|raconte|racontez|racontait|explique|expliquait|selon|d'apres|parait|"
                      r"entendu|lu dans|film|histoire|roman|reve|cauchemar|cite|ecrit)\b")
GENERIQUE = re.compile(r"\b(?:peut|peuvent|provoque|provoquent|donne des|sert a|servent a|est un|est une|contient|soulage|"
                       r"effets?|risque de|danger|dangereux|interaction)\b")

LIBELLES = {"question": "question", "negation": "négation ou mise en garde", "consigne": "consigne adressée au patient",
            "incitation": "incitation adressée au patient", "atteinte": "atteinte à soi adressée au patient", "menace": "menace", "passe": "temps passé ou marqueur de temps passé",
            "tiers": "il s'agit d'une autre personne", "rapporte": "propos rapportés ou récit",
            "generique": "phrase générale sur le produit", "depistage": "question de dépistage"}


def lire_contexte(texte: str) -> dict:
    """Context clues of a message (person, tense, question, negation…) and the resulting intention:
    consigne | incitation | menace | question | mise_en_garde | recit | information | ambigu."""
    t = " " + normaliser(texte) + " "
    vus = {nom: bool(rx.search(t)) for nom, rx in (("question", QUESTION), ("negation", NEGATION), ("consigne", CONSIGNE),
                                                    ("incitation", INCITATION), ("atteinte", ATTEINTE), ("menace", MENACE), ("passe", PASSE),
                                                    ("tiers", TIERS), ("rapporte", RAPPORTE), ("generique", GENERIQUE),
                                                    ("depistage", DEPISTAGE))}
    recit = vus["rapporte"] or (vus["passe"] and (vus["tiers"] or not vus["consigne"]))
    cite = vus["rapporte"] and vus["tiers"]           # "il m'a dit d'aller me pendre": an incitement is QUOTED
    if vus["menace"]:
        intention = "menace"
    elif vus["incitation"] and not cite:
        intention = "incitation"       # an imperative stays an incitement, even followed by a question mark
    elif vus["incitation"]:
        intention = "ambigu"           # quoted incitement: the doctor confirms what they mean
    elif vus["question"]:
        intention = "question"
    elif vus["atteinte"] and not recit and not vus["negation"]:
        intention = "incitation"
    elif vus["negation"]:
        intention = "mise_en_garde"
    elif vus["consigne"]:
        intention = "consigne"
    elif recit:
        intention = "recit"
    elif vus["generique"]:
        intention = "information"
    else:
        intention = "ambigu"
    indices = [LIBELLES[k] for k, v in vus.items() if v and k != "depistage"]
    return {"intention": intention, "indices": indices, "depistage": vus["depistage"] and vus["question"]}


INTENTIONS = {"consigne": "une consigne de traitement", "incitation": "une incitation à se faire du mal", "menace": "une menace",
              "question": "une question", "mise_en_garde": "une mise en garde", "recit": "un récit",
              "information": "une information générale", "ambigu": "un message ambigu"}


PREMIERE_PERSONNE = re.compile(r"\b(?:je|j'|me|m'|moi|mon|ma|mes)\b")
DESIR = re.compile(r"\b(?:veux|voudrais|vouloir|envie|pense a|penser a|idee|idees|prefere|preferer|aimerais|vais|va)\b")
MORT_SOI = re.compile(r"\b(?:mourir|mort|morte|suicide|suicider|suicidee|pendre|pendu|pendue|tuer|tue|tuee|en finir|disparaitre|"
                      r"plus vivre|sauter|me tuer|me pendre)\b")


def risque_suicidaire(texte: str) -> dict | None:
    """Does the PATIENT express a thought of death for themself ("moi vouloir mourir", "je veux me pendre")?
    A story about someone else ("mon frère s'est pendu") is not one, but is still reported as information."""
    t = " " + normaliser(texte) + " "
    if not MORT_SOI.search(t):
        return None
    c = lire_contexte(texte)
    soi = bool(PREMIERE_PERSONNE.search(t)) or not TIERS.search(t)
    if soi and not NEGATION.search(t) and (DESIR.search(t) or not c["intention"] == "recit"):
        return {"niveau": "alerte", "indices": c["indices"] + ["la personne parle d'elle-même"]}
    return {"niveau": "information", "indices": c["indices"]}
