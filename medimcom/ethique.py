"""ETHICAL safeguards of a doctor-to-patient message (deterministic, explained, verifiable).

A message may be correct in form and grammatically harmless, yet contrary to medical ethics:
  - advising drugs, alcohol or tobacco ("une femme enceinte doit se droguer");
  - offering to sell a child or an organ ("je vais vous aider à vendre votre bébé");
  - making sexual remarks to the patient ("vous me plaisez, je veux vous enceinter");
  - proposing an abortion by message (strictly regulated by law: in the UAE, Art. 16 of Law 4/2016);
  - insulting, including with a typo ("imbecil").
CONTEXT matters (medimcom/lecture.py): a question ("Prenez-vous de la drogue ?"), a warning ("Pas d'alcool
pendant la grossesse") or a narrative ("On m'a proposé d'acheter mon bébé") is not advice: it stays allowed.
Each block says WHY and WHAT TO DO instead.
"""
from __future__ import annotations

import re

from .lecture import distance, normaliser

# Harmful practices a caregiver never advises
NUISIBLES = re.compile(r"\b(?:se droguer|vous droguer|te droguer|droguer|drogues?|cannabis|marijuana|cocaine|heroine|crack|"
                       r"ecstasy|shit|alcool|alcools|biere|bieres|vin|whisky|vodka|boire de l'alcool|se souler|"
                       r"vous souler|fumer|cigarettes?|tabac|chicha|narguile|"
                       r"drugs?|heroin|alcohol|beer|wine|smoke|smoking|get drunk)\b")      # and in English
# Forms of ADVICE or injunction (in addition to the direct instruction read by lecture.py)
CONSEIL = re.compile(r"\b(?:doit|doivent|devez|dois|devrait|devriez|faut|il faut|conseill\w*|recommand\w*|pouvez|peux|peut|"
                     r"est bon|c'est bon|bon de|bien de|mieux de|n'hesitez pas a|essayez|continuez a|continuez de|"
                     r"je vais vous aider a|on va vous aider a|je vous aide a|"
                     r"should|must|need to|have to|can|it's good to|try|keep|i will help you)\b")
TRAFIC = re.compile(r"\b(?:vendre|vend|vendez|vendu|acheter|achetez|monnayer|ceder contre|echanger contre|sell|buy)\b[^.?!]{0,30}"
                    r"\b(?:bebes?|enfants?|nourrissons?|fils|fille|reins?|organes?|foie|cornee|ovocytes?|baby|child|kidney|organs?)\b")
SEXUEL = re.compile(r"\b(?:vous me plaisez|tu me plais|je vous desire|je te desire|je vous aime|je t'aime|coucher avec|"
                    r"faire l'amour|sexe avec|relation sexuelle avec moi|vous embrasser|t'embrasser|enceinter|"
                    r"vous mettre enceinte|te mettre enceinte|sortir avec moi|votre numero perso|vous etes belle|tu es belle|"
                    r"vous etes sexy|cul|bite|chatte|nichons|zizi|baiser avec|vous baiser|te baiser|"
                    r"i love you|you are beautiful|you're beautiful|sexy|have sex|sleep with|make love|kiss you|get you pregnant)\b")
AVORTEMENT = re.compile(r"\b(?:avort\w*|ivg|interruption volontaire de grossesse|faire passer (?:le|la|votre|ce) "
                        r"(?:bebe|grossesse|enfant)|misoprostol|cytotec|abortion|abort)\b")
INJURES = ["connard", "connasse", "salope", "salaud", "pute", "putain", "encule", "batard", "abruti", "debile", "imbecile",
           "cretin", "idiot", "idiote", "nique", "gueule", "con", "conne", "bouffon", "minable", "grosse vache", "pouffiasse",
           "trouduc", "enfoire", "merde", "mouf", "moufle", "stupid", "moron", "bitch", "bastard", "fuck", "asshole"]


def _injure(t: str) -> str | None:
    """Insult, even misspelt ("imbecil", "conard"): one error away on a word of at least 6 letters."""
    for i in INJURES:
        if " " in i and i in t:
            return i
    for w in re.findall(r"[a-z]+", t):
        if w in INJURES:
            return w
        if len(w) >= 6 and any(len(i) >= 6 and w[:3] == i[:3] and distance(w, i, 1) <= 1 for i in INJURES):
            return w
    return None


def analyser(texte: str, intention: str) -> list[dict]:
    """[{categorie, expression, motif, piste}]: what is contrary to ethics in the message, according to its
    intention (instruction, question, narrative…). A question, a warning or a narrative is not advice."""
    t = " " + normaliser(texte) + " "
    permis = intention in ("question", "mise_en_garde", "recit")
    sortie = []
    m = NUISIBLES.search(t)
    if m and not permis and (intention in ("consigne", "incitation", "ambigu") or CONSEIL.search(t)):
        grossesse = re.search(r"\b(?:enceinte|grossesse|allait\w*|bebe|enfant)\b", t)
        sortie.append({"categorie": "conseil_nuisible", "expression": m.group(0).strip(),
                       "motif": f"conseil de consommer « {m.group(0).strip()} »" + (" pendant la grossesse ou à un enfant" if grossesse else ""),
                       "piste": ("Un soignant ne conseille jamais drogue, alcool ni tabac" + (" — encore moins pendant la grossesse" if grossesse else "")
                                 + ". Si le patient en consomme : en parler sans jugement et proposer un accompagnement (addictologie).")})
    m = TRAFIC.search(t)
    recit_tiers = intention == "recit" and re.search(r"\b(?:on m'a|il m'a|elle m'a|ils m'ont|quelqu'un|propose|dit|raconte)\b", t)
    if m and intention not in ("question", "mise_en_garde") and not recit_tiers:
        sortie.append({"categorie": "trafic", "expression": m.group(0).strip(),
                       "motif": "proposition de vendre ou d'acheter un enfant ou un organe : infraction pénale grave",
                       "piste": "Retirez ce message. Si le patient évoque une telle situation, protégez-le et alertez les services "
                                "de protection de l'enfance ou les autorités."})
    m = SEXUEL.search(t)
    if m and intention not in ("recit",):
        sortie.append({"categorie": "sexuel", "expression": m.group(0).strip(),
                       "motif": "propos à caractère sexuel ou intime adressés au patient : abus de la relation de soin",
                       "piste": "Retirez ce message. La relation de soin exclut tout propos de séduction ou sexuel. "
                                "Un examen intime s'annonce, s'explique et se fait avec l'accord du patient, si possible avec un témoin."})
    m = AVORTEMENT.search(t)
    if m and not permis:
        sortie.append({"categorie": "avortement", "expression": m.group(0).strip(),
                       "motif": "proposition d'avortement par message : acte strictement encadré par la loi",
                       "piste": "Pas par message. Aux Émirats, seules deux exceptions (danger pour la vie de la mère ; malformation "
                                "grave du fœtus avant 120 jours), décidées par un gynécologue-obstétricien et un comité, avec "
                                "l'accord écrit des époux. Ailleurs : vérifiez la loi du pays."})
    w = _injure(t)
    if w and intention not in ("recit", "question"):
        sortie.append({"categorie": "injure", "expression": w, "motif": f"propos injurieux (« {w} »)",
                       "piste": "Retirez ce message : le respect du patient est un devoir du soignant."})
    return sortie
