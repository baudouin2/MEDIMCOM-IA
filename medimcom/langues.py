"""What the doctor reads, in the doctor's language (French, English or Arabic).

1. `phrase_patient`: the pictograms chosen by the patient become ONE natural sentence ("I have pain in my belly, 7 out
   of 10"), written by rules: no model, nothing invented. The pictograms themselves stay on screen next to it.
2. `Redacteur`: when a language model is plugged in, it rewrites that sentence more fluently, in the background
   (the rule sentence is shown meanwhile). Its output is checked: a sentence that adds a number, a medicine or a body
   part the patient did not choose is rejected and the rule sentence is kept.
3. `traduire`: the messages of the agents, the conversation and the journal are written in French in the record; at
   display time they are shown in the doctor's language (catalogue `traductions.json`), past messages included.
"""
from __future__ import annotations

import json
import re
import threading
from functools import lru_cache
from pathlib import Path

LANGUES = ("fr", "en", "ar")


def _lib(ident: str, langue: str) -> str:
    from .bibliotheque import libelle
    t = libelle(ident, langue)
    if t == ident and ":" in ident:                       # "MEDICAMENT:paracetamol" not in the catalogue
        t = ident.split(":", 1)[1].replace("_", " ").lower()
    if t == ident:                                        # unknown identifier (other bases): readable form
        t = ident.replace("_", " ").lower()
    return re.sub(r"\s*\([^)]*\)", "", t).strip()          # "médicament (nom)" -> "médicament"


def libelles(pictos: list[str], langue: str) -> str:
    """Readable labels of a pictogram sequence ("medicine paracetamol · 500mg · at most · 3 · times · day")."""
    def un(e: str) -> str:
        base, _, val = e.partition(":")
        if base in ("CHIFFRE", "DOSE"):
            return val
        if base == "MEDICAMENT":
            return val
        return _lib(e, langue)
    return " · ".join(" + ".join(un(e) for e in x.split("+")) for x in pictos)


CORPS = {"TETE", "VENTRE", "POITRINE", "GORGE", "OREILLE", "OEIL", "DENT", "DOS", "BRAS", "JAMBE", "PIED", "MAIN",
         "COEUR", "PEAU", "BAS_VENTRE", "ESTOMAC", "GENOU", "EPAULE", "COU", "NEZ", "BOUCHE", "DOIGT"}
DOULEURS = {"DOULEUR", "MAL", "SANG"}
DUREES = {"JOUR": ("jours", "days", "أيام"), "SEMAINE": ("semaines", "weeks", "أسابيع"), "MOIS": ("mois", "months", "أشهر"),
          "HEURE": ("heures", "hours", "ساعات"), "AN": ("ans", "years", "سنوات"), "ANNEE": ("ans", "years", "سنوات")}
DUREES_AR_1 = {"JOUR": "يوم", "SEMAINE": "أسبوع", "MOIS": "شهر", "HEURE": "ساعة", "AN": "سنة", "ANNEE": "سنة"}
DUREES_AR_2 = {"JOUR": "يومين", "SEMAINE": "أسبوعين", "MOIS": "شهرين", "HEURE": "ساعتين", "AN": "سنتين", "ANNEE": "سنتين"}
DUREES_AR_11 = {"JOUR": "يومًا", "SEMAINE": "أسبوعًا", "MOIS": "شهرًا", "HEURE": "ساعة", "AN": "سنة", "ANNEE": "سنة"}
# French body parts with their preposition: « mal au ventre », « mal à la tête », « mal aux dents »
A_FR = {"TETE": "à la tête", "VENTRE": "au ventre", "POITRINE": "à la poitrine", "GORGE": "à la gorge", "OREILLE": "à l'oreille",
        "OEIL": "à l'œil", "DENT": "aux dents", "DOS": "au dos", "BRAS": "au bras", "JAMBE": "à la jambe", "PIED": "au pied",
        "MAIN": "à la main", "COEUR": "au cœur", "PEAU": "à la peau", "ESTOMAC": "à l'estomac", "GENOU": "au genou",
        "EPAULE": "à l'épaule", "COU": "au cou", "NEZ": "au nez", "BOUCHE": "à la bouche", "DOIGT": "au doigt"}
SIMPLES = {  # whole answers
    ("OUI",): ("Oui.", "Yes.", "نعم."), ("NON",): ("Non.", "No.", "لا."), ("ACCORD",): ("Je suis d'accord.", "I agree.", "أنا موافق."),
    ("NE_PAS", "ACCORD"): ("Je ne suis pas d'accord.", "I do not agree.", "لست موافقًا."),
    ("NON", "ACCORD"): ("Je ne suis pas d'accord.", "I do not agree.", "لست موافقًا."),
    ("NE_PAS", "COMPRENDRE"): ("Je ne comprends pas.", "I do not understand.", "لا أفهم."),
    ("NON", "COMPRENDRE"): ("Je ne comprends pas.", "I do not understand.", "لا أفهم."),
    ("COMPRENDRE",): ("J'ai compris.", "I understand.", "فهمت."), ("URGENCE",): ("C'est une urgence !", "This is an emergency!", "هذه حالة طارئة!"),
    ("STOP",): ("Arrêtez.", "Stop.", "توقّف."), ("ATTENDRE",): ("Attendez.", "Please wait.", "انتظر من فضلك."),
    ("REPETER",): ("Pouvez-vous répéter ?", "Could you repeat?", "هل يمكنك أن تكرّر؟"),
}
TEXTES = {
    "mal": ("J'ai mal {}", "I have pain in {}", "أشعر بألم في {}"),
    "mal_seul": ("J'ai mal", "I am in pain", "أشعر بألم"),
    "mal_fort": ("J'ai très mal {}", "I have severe pain in {}", "أشعر بألم شديد في {}"),
    "sur10": ("{} sur 10", "{} out of 10", "{} من 10"),
    "depuis": ("depuis {} {}", "for {} {}", "منذ {} {}"),
    "jai": ("J'ai {}", "I have {}", "عندي {}"),
    "pris": ("J'ai pris {}", "I took {}", "تناولتُ {}"),
    "prends": ("Je prends {}", "I have been taking {}", "أتناول {}"),
    "enceinte": ("Je suis enceinte", "I am pregnant", "أنا حامل"),
    "pas_enceinte": ("Je ne suis pas enceinte", "I am not pregnant", "لستُ حاملًا"),
    "et": (" et ", " and ", " و"),
    "oui_et": ("Oui : {}", "Yes: {}", "نعم: {}"),
    "non_et": ("Non : {}", "No: {}", "لا: {}"),
    "pas": ("pas de {}", "no {}", "لا {}"),
}
CORPS_AR = {"TETE": "الرأس", "VENTRE": "البطن", "POITRINE": "الصدر", "GORGE": "الحلق", "OREILLE": "الأذن", "OEIL": "العين",
            "DENT": "الأسنان", "DOS": "الظهر", "BRAS": "الذراع", "JAMBE": "الساق", "PIED": "القدم", "MAIN": "اليد",
            "COEUR": "القلب", "PEAU": "الجلد", "ESTOMAC": "المعدة", "GENOU": "الركبة", "EPAULE": "الكتف", "COU": "الرقبة"}
ADVERBES = {"TRES": ("très", "very", "جدًّا"), "BEAUCOUP": ("beaucoup", "a lot", "كثيرًا"), "UN_PEU": ("un peu", "a little", "قليلًا"),
            "PEU": ("un peu", "a little", "قليلًا"), "DIFFICILE": ("difficile", "difficult", "صعب"), "FORT": ("fort", "strong", "قوي"),
            "MIEUX": ("mieux", "better", "أفضل"), "PIRE": ("pire", "worse", "أسوأ"), "PLUS": ("plus", "more", "أكثر"),
            "MOINS": ("moins", "less", "أقل"), "MATIN": ("le matin", "in the morning", "صباحًا"), "SOIR": ("le soir", "in the evening", "مساءً"),
            "NUIT": ("la nuit", "at night", "ليلًا"), "MANGER": ("manger", "eating", "الأكل"), "BOIRE": ("boire", "drinking", "الشرب"),
            "DORMIR": ("dormir", "sleeping", "النوم")}
SYMPTOMES = {"FIEVRE", "TOUX", "VOMIR", "DIARRHEE", "FATIGUE", "VERTIGE", "RHUME", "DEMANGEAISON", "BRULURE",
             "GONFLEMENT", "CONSTIPATION", "EVANOUISSEMENT", "ALLERGIE", "SANG", "RESPIRER"}
SYMPTOMES_FR = {"VOMIR": "envie de vomir", "RESPIRER": "du mal à respirer", "SANG": "du sang", "FIEVRE": "de la fièvre",
                "TOUX": "de la toux", "DIARRHEE": "la diarrhée", "FATIGUE": "de la fatigue", "VERTIGE": "des vertiges",
                "RHUME": "un rhume", "DEMANGEAISON": "des démangeaisons", "BRULURE": "une brûlure", "GONFLEMENT": "un gonflement",
                "CONSTIPATION": "de la constipation", "EVANOUISSEMENT": "des évanouissements", "ALLERGIE": "une allergie"}
SYMPTOMES_EN = {"VOMIR": "nausea", "RESPIRER": "difficulty breathing", "SANG": "bleeding", "FIEVRE": "a fever", "TOUX": "a cough",
                "DIARRHEE": "diarrhoea", "FATIGUE": "tiredness", "VERTIGE": "dizziness", "RHUME": "a cold", "DEMANGEAISON": "itching",
                "BRULURE": "a burn", "GONFLEMENT": "swelling", "CONSTIPATION": "constipation", "EVANOUISSEMENT": "fainting",
                "ALLERGIE": "an allergy"}
SYMPTOMES_AR = {"VOMIR": "غثيان", "RESPIRER": "صعوبة في التنفّس", "SANG": "نزيف", "FIEVRE": "حمّى", "TOUX": "سعال",
                "DIARRHEE": "إسهال", "FATIGUE": "تعب", "VERTIGE": "دوار", "RHUME": "زكام", "DEMANGEAISON": "حكّة",
                "BRULURE": "حرق", "GONFLEMENT": "تورّم", "CONSTIPATION": "إمساك", "EVANOUISSEMENT": "إغماء", "ALLERGIE": "حساسية"}


def _i(langue: str) -> int:
    return {"fr": 0, "en": 1, "ar": 2}.get(langue, 0)


def phrase_patient(pictos: list[str], langue: str = "fr") -> str:
    """One natural sentence for the pictograms chosen by the patient, in the doctor's language. Only what the patient
    chose: anything the rules cannot place is listed as is, never guessed."""
    i = _i(langue)
    elements = [x for p in pictos for x in p.split("+")]
    cle = tuple(x for x in elements if x != "QUESTION")
    if cle in SIMPLES:
        return SIMPLES[cle][i]
    negatif = bool({"NON", "NE_PAS"} & set(elements[:1]))
    reste = list(elements)
    debut = None
    if reste and reste[0] in ("OUI", "NON"):
        debut = reste.pop(0)
    parties, symptomes, autres, nombre, duree, meds = [], [], [], None, None, []
    douleur = False
    k = 0
    while k < len(reste):
        x = reste[k]
        if x in CORPS:
            parties.append(x)
        elif x in DOULEURS - {"SANG"}:
            douleur = True
        elif x.startswith("CHIFFRE:"):
            n = x.split(":", 1)[1]
            if k + 1 < len(reste) and reste[k + 1] in DUREES:
                duree = (n, reste[k + 1]); k += 1
            else:
                nombre = n
        elif x in DUREES:
            duree = ("1", x)
        elif x.startswith("MEDICAMENT:"):
            meds.append(x.split(":", 1)[1])
        elif x in SYMPTOMES:
            symptomes.append(x)
        elif x == "ENCEINTE":
            symptomes.append("ENCEINTE")
        elif x in ("NE_PAS", "MOI", "VOUS", "QUESTION", "OUI", "NON"):
            pass
        else:
            autres.append(x)
        k += 1
    fort = bool({"TRES", "BEAUCOUP", "FORT", "SEVERE", "TROP"} & set(autres))
    if fort or "DIFFICILE" in autres and "RESPIRER" in symptomes:
        autres = [a for a in autres if a not in ("TRES", "BEAUCOUP", "FORT", "SEVERE", "TROP", "DIFFICILE")]
    et = TEXTES["et"][i]
    morceaux = []
    if douleur or (parties and not symptomes):
        if parties:
            if langue == "fr":
                lieux = et.join(A_FR.get(p, "à : " + _lib(p, "fr")) for p in parties)
                morceaux.append(f"J'ai {'très ' if fort else ''}mal {lieux}")
            else:
                lieux = et.join(("my " + _lib(p, "en")) if langue == "en" else CORPS_AR.get(p, _lib(p, "ar")) for p in parties)
                morceaux.append((TEXTES["mal_fort"] if fort else TEXTES["mal"])[i].format(lieux))
        else:
            morceaux.append(TEXTES["mal_seul"][i])
        fort = False
        if nombre is not None:
            morceaux[-1] += ("، " if langue == "ar" else ", ") + TEXTES["sur10"][i].format(nombre)
            nombre = None
    if "ENCEINTE" in symptomes:
        morceaux.append(TEXTES["pas_enceinte" if negatif else "enceinte"][i])
    noms = [(SYMPTOMES_FR, SYMPTOMES_EN, SYMPTOMES_AR)[i].get(s) or _lib(s, langue) for s in symptomes if s != "ENCEINTE"]
    if fort and noms:
        noms[0] = {"fr": {"du mal à respirer": "beaucoup de mal à respirer", "de la fièvre": "beaucoup de fièvre"}.get(noms[0], noms[0] + " (fort)"),
                   "en": {"difficulty breathing": "great difficulty breathing", "a fever": "a high fever"}.get(noms[0], "severe " + noms[0]),
                   "ar": {"صعوبة في التنفّس": "صعوبة شديدة في التنفّس", "حمّى": "حمّى شديدة"}.get(noms[0], noms[0] + " شديد")}[langue]
    if noms:
        liste = noms[0] if len(noms) == 1 else ", ".join(noms[:-1]) + et + noms[-1]
        morceaux.append(TEXTES["pas" if negatif else "jai"][i].format(liste))
    if meds:
        morceaux.append(TEXTES["prends" if duree else "pris"][i].format(et.join(meds)))
    if duree:              # "J'ai mal à la tête depuis 3 jours": no comma before the duration
        n, u = duree
        depuis = TEXTES["depuis"][i].format(n, DUREES[u][i])
        if langue == "ar" and n in ("1", "2"):          # Arabic singular and dual: « منذ يومين »
            depuis = "منذ " + {"1": DUREES_AR_1, "2": DUREES_AR_2}[n].get(u, DUREES[u][2])
        elif langue == "ar" and n.isdigit() and int(n) > 10:
            depuis = f"منذ {n} " + DUREES_AR_11.get(u, DUREES[u][2])
        if morceaux:
            if langue == "en" and morceaux[-1].startswith("I have ") and not morceaux[-1].startswith("I have been"):
                morceaux[-1] = "I have had " + morceaux[-1][7:]          # "I have had a fever for 2 days"
            morceaux[-1] += " " + depuis
        else:
            morceaux.append(depuis)
    if nombre is not None:
        morceaux.append(nombre)
    if autres:
        morceaux.append(("، " if langue == "ar" else ", ").join(ADVERBES.get(a, ("", "", ""))[i] or _lib(a, langue) for a in autres))
    if not morceaux:
        return ", ".join(_lib(x, langue) for x in elements if x != "QUESTION").capitalize() + "."
    phrase = ("، " if langue == "ar" else ", ").join(m for m in morceaux if m)
    bas = phrase if langue != "fr" else phrase[:1].lower() + phrase[1:]       # English keeps "I"; Arabic has no case
    if debut == "OUI":
        phrase = TEXTES["oui_et"][i].format(bas)
    elif debut == "NON":
        phrase = TEXTES["non_et"][i].format(bas)
    phrase = phrase[:1].upper() + phrase[1:]
    return phrase if phrase.endswith((".", "!", "?")) else phrase + "."


NOMS_LANGUES = {"fr": "French", "en": "English", "ar": "Modern Standard Arabic"}


class Redacteur:
    """Fluent sentence by the language model, in the background, cached; checked against the pictograms."""

    def __init__(self, cerveau=None, rappel=None):
        self.cerveau, self.rappel = cerveau, rappel
        self.cache: dict[tuple, str] = {}
        self.en_cours: set[tuple] = set()
        self.verrou = threading.Lock()

    def phrase(self, pictos: list[str], langue: str, question: str | None = None) -> tuple[str, str]:
        """(sentence, author): the model's sentence if ready and accepted, otherwise the rule sentence."""
        regle = phrase_patient(pictos, langue)
        if not self.cerveau or not hasattr(self.cerveau, "rediger"):
            return regle, "regles"
        cle = (tuple(pictos), langue, question or "")
        with self.verrou:
            if cle in self.cache:
                return (self.cache[cle], "ia") if self.cache[cle] else (regle, "regles")
            if cle not in self.en_cours:
                self.en_cours.add(cle)
                threading.Thread(target=self._rediger, args=(cle, regle), daemon=True, name="redacteur").start()
        return regle, "regles"

    def _rediger(self, cle, regle):
        pictos, langue, question = cle
        libelles = ", ".join(_lib(x, "en") for p in pictos for x in p.split("+"))
        consigne = (
            "A deaf patient answers a doctor by tapping pictograms. Write what the patient says as ONE short, natural "
            f"sentence in {NOMS_LANGUES[langue]}, in the first person, as a patient would say it to the doctor. Use ONLY "
            "the meaning of the pictograms: add no symptom, number, duration, body part or medicine. If the pictograms "
            "are ambiguous, stay literal. Answer with the sentence only, no quotes, no explanation.")
        texte = (f"Doctor's question: {question}\n" if question else "") + f"Pictograms chosen, in order: {libelles}\n" \
                f"Literal reading: {regle}"
        try:
            sortie = (self.cerveau.rediger(consigne, texte) or "").strip().strip('"«»“”').strip()
        except Exception:
            sortie = ""
        sortie = sortie.splitlines()[0].strip() if sortie else ""
        if not self._fidele(sortie, pictos, regle):
            sortie = ""
        with self.verrou:
            self.cache[cle] = sortie
            self.en_cours.discard(cle)
        if sortie and self.rappel:
            try:
                self.rappel()
            except Exception:
                pass

    @staticmethod
    def _fidele(sortie: str, pictos, regle: str) -> bool:
        """Rejects a sentence that adds a number the patient did not choose, or that is far too long."""
        if not sortie or len(sortie) > max(160, 3 * len(regle)):
            return False
        chiffres_patient = {x.split(":", 1)[1] for p in pictos for x in p.split("+") if x.startswith("CHIFFRE:")}
        chiffres_patient |= set(re.findall(r"\d+", regle))
        return set(re.findall(r"\d+", sortie)) <= chiffres_patient | {"10"}


# Names of the facts of the record (keys of the patient state), in the three languages
NOMS_FAITS = {
    "grossesse": ("grossesse", "pregnancy", "الحمل"), "allergies": ("allergies", "allergies", "الحساسية"),
    "traitements_en_cours": ("traitements en cours", "current treatments", "العلاجات الحالية"), "age": ("âge", "age", "العمر"),
    "sexe": ("sexe", "sex", "الجنس"), "poids": ("poids", "weight", "الوزن"), "antecedents": ("antécédents", "medical history", "السوابق المرضية"),
    "douleur": ("douleur", "pain", "الألم"), "fievre": ("fièvre", "fever", "الحمّى"), "nausees": ("nausées", "nausea", "الغثيان"),
    "maladies_connues": ("maladies connues", "known conditions", "الأمراض المعروفة"),
    "medicaments_declares": ("médicaments déclarés", "reported medicines", "الأدوية المُصرَّح بها"),
    "consentement_traitement": ("accord pour le traitement", "agreement to the treatment", "الموافقة على العلاج"),
    "informe_usage_ia": ("informé de l'usage de l'IA", "informed about the use of AI", "أُبلغ باستخدام الذكاء الاصطناعي"),
    "urgence": ("urgence", "emergency", "طوارئ"), "localisation_douleur": ("siège de la douleur", "pain location", "موضع الألم"),
    "intensite_douleur": ("intensité de la douleur", "pain intensity", "شدة الألم"), "mode": ("mode de consultation", "consultation mode", "نوع الاستشارة"),
    "allaitement": ("allaitement", "breastfeeding", "الرضاعة الطبيعية"), "maladie_renale": ("maladie rénale", "kidney disease", "مرض كلوي"),
    "maladie_hepatique": ("maladie du foie", "liver disease", "مرض الكبد"), "ulcere_digestif": ("ulcère digestif", "peptic ulcer", "قرحة هضمية"),
    "anticoagulant": ("anticoagulant", "anticoagulant", "مضاد تخثّر"), "maladie_cardiaque": ("maladie cardiaque", "heart disease", "مرض القلب"),
    "moyen_communication": ("moyen de communication", "means of communication", "وسيلة التواصل"),
    "duree_symptomes": ("durée des symptômes", "duration of symptoms", "مدة الأعراض"), "symptome": ("motif", "reason for visit", "سبب الزيارة"),
    "accord du patient": ("accord du patient", "patient's agreement", "موافقة المريض"),
}


def nom_fait(cle: str, langue: str) -> str:
    return NOMS_FAITS.get(cle, (cle, cle, cle))[_i(langue)]


# ---------------------------------------------------------------- display-time translation of French messages
FICHIER = Path(__file__).with_name("traductions.json")


@lru_cache(maxsize=1)
def _catalogue() -> tuple[dict, list]:
    """Exact sentences, and templates with holes ({0}, {1}…) compiled into anchored regular expressions."""
    if not FICHIER.exists():
        return {}, []
    donnees = json.loads(FICHIER.read_text(encoding="utf-8"))
    exacts, modeles = {}, []
    for fr, cibles in donnees.items():
        # « à « {} » », « .\nContrôlé… », « ; sans dépasser… » are also found as a line or a piece of a longer text
        fr = fr.strip().lstrip(".;؛").strip()
        cibles = {k: v.strip().lstrip(".;؛").strip() for k, v in cibles.items()}
        if "{}" not in fr:
            exacts[fr] = cibles
            continue
        morceaux = fr.split("{}")
        motif = "^" + "(.+?)".join(re.escape(m) for m in morceaux) + "$"
        modeles.append((len(fr) - 2 * fr.count("{}"), re.compile(motif, re.S), cibles, "\n" in fr))
    # templates that start with words come before those that start with a hole (« Sens à confirmer : {} » before
    # « {} cité sans que… »), then the longest first
    modeles.sort(key=lambda x: (x[1].pattern.startswith("^(.+?)"), -x[0]))
    return exacts, modeles




def _appliquer(m, cibles: dict, langue: str, profondeur: int, generique: bool = False) -> str | None:
    trous = [traduire(g, langue, profondeur + 1) if profondeur < 10 else g for g in m.groups()]
    if generique and trous == list(m.groups()):      # « {}, {} » that translates nothing: leave the text as it is
        return None
    sortie = cibles[langue]
    if "{PHR" in sortie:     # the patient's pictograms (a hole) as one natural sentence in the target language
        sortie = re.sub(r"\{PHR(\d)\}", lambda x: phrase_patient(m.group(int(x.group(1)) + 1).split(), langue), sortie)
    if "{LAB" in sortie:     # labels of the pictograms of a hole, in the target language
        sortie = re.sub(r"\{LAB(\d)\}", lambda x: " ".join(_lib(p, langue) for p in m.group(int(x.group(1)) + 1).split()), sortie)
    try:
        return sortie.format(*trous)
    except (IndexError, KeyError):
        return None


def _un(texte: str, langue: str, profondeur: int = 0, generiques: bool = False) -> str | None:
    """The whole text as ONE known sentence or template (with or without its final full stop), else None."""
    exacts, modeles = _catalogue()
    nu = texte.strip()
    if not nu:
        return texte
    candidats = [(nu, "")]
    if nu[-1] in ".:" and len(nu) > 2:
        candidats.append((nu[:-1].rstrip(), nu[-1]))
    for cand, fin in candidats:
        if cand in exacts and exacts[cand].get(langue):
            t = exacts[cand][langue]
            return texte.replace(nu, (t.rstrip(".:") + fin) if fin else t)
    multi = "\n" in nu
    for generique in ((True,) if generiques else (False,)):     # « {} : {} », « {}, {} » only as a last resort
        for longueur, motif, cibles, multi_modele in modeles:
            if (longueur <= 3) != generique or (multi and not multi_modele) or not cibles.get(langue):
                continue
            for cand, fin in candidats:
                m = motif.match(cand)
                if m:
                    t = _appliquer(m, cibles, langue, profondeur, generique)
                    if t is not None:
                        return texte.replace(nu, (t.rstrip(".:") + fin) if fin else t)
    return None


@lru_cache(maxsize=8)
def _fragments(langue: str) -> list[tuple[str, str]]:
    """Fixed phrases long enough to be replaced inside a longer sentence (« toutes les 6 heures si besoin… »)."""
    exacts, _ = _catalogue()
    return sorted(((fr, c[langue]) for fr, c in exacts.items() if c.get(langue) and len(fr) >= 14 and " " in fr),
                  key=lambda x: -len(x[0]))


def _par_morceaux(texte: str, langue: str) -> str:
    for fr, cible in _fragments(langue):
        if fr in texte:
            texte = texte.replace(fr, cible)
    return texte


LIGNES = re.compile(r"(\n+)")
PHRASES = re.compile(r"(\s;\s|(?<=[.!?])\s+(?=[A-ZÀ-ÖÉÈ«#•]))")


@lru_cache(maxsize=20000)
def traduire(texte: str, langue: str, profondeur: int = 0) -> str:
    """A message written in French by the system, in the doctor's language. Unknown text (what the doctor typed,
    names, legal quotes) is returned unchanged."""
    if langue == "fr" or not isinstance(texte, str) or not texte.strip():
        return texte
    entier = _un(texte, langue, profondeur)
    if entier is not None:
        return entier
    if profondeur > 10:
        return texte
    for coupe in (LIGNES, PHRASES):              # line by line, then sentence by sentence
        morceaux = coupe.split(texte)
        if len(morceaux) > 1:
            return "".join(m if (i % 2 or not m.strip()) else traduire(m, langue, profondeur + 1) for i, m in enumerate(morceaux))
    debut = re.match(r"^(\s*[•\-;]\s*)(.+)$", texte, re.S)     # "• item", "; piece"
    if debut:
        return debut.group(1) + traduire(debut.group(2), langue, profondeur + 1)
    generique = _un(texte, langue, profondeur, generiques=True)
    return generique if generique is not None else _par_morceaux(texte, langue)


def traduire_tout(objet, langue: str, ignorer: frozenset = frozenset()):
    """Translates every string of a view (dict / list), except the keys in `ignorer`."""
    if langue == "fr":
        return objet
    if isinstance(objet, str):
        return traduire(objet, langue)
    if isinstance(objet, list):
        return [traduire_tout(x, langue, ignorer) for x in objet]
    if isinstance(objet, dict):
        return {k: (v if k in ignorer else traduire_tout(v, langue, ignorer)) for k, v in objet.items()}
    return objet
