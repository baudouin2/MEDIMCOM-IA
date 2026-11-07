"""Moteur de règles déterministe de l'agent juriste.

C'est LUI qui rend les verdicts. Le modèle de langage du juriste peut le consulter,
expliquer et négocier, mais il ne peut pas modifier un verdict.

Chaque constat cite des fiches de la base de connaissances (kb/fiches.jsonl) :
la citation complète (texte, article, lien officiel, niveau de vérification) est
reconstruite à partir de la base, jamais écrite à la main dans le code.
"""
import json
import re
import unicodedata
from pathlib import Path

from .base import BaseConnaissances

ORDRE = {"CONFORME": 0, "PREUVES_INSUFFISANTES": 1, "A_REVOIR": 2, "BLOQUE": 3}
NON_VERDICTS = {"OBLIGATION", "INFORMATION"}


def normaliser(nom: str) -> str:
    nom = unicodedata.normalize("NFD", str(nom).lower().strip())
    return "".join(c for c in nom if unicodedata.category(c) != "Mn").replace(" ", "_").replace("-", "_")


def _vide(v) -> bool:
    return v is None or v == "" or v == []


# Sémantique formelle du langage de conditions (voir docs/technique/METHODES_FORMELLES.md).
# - Opérateurs ÉPISTÉMIQUES (sur ce que l'on sait) : absent, present, pas (« il n'est pas établi que… »).
#   Toujours vrais ou faux.
# - Opérateurs FACTUELS (sur le monde) : égalité, dans, contient, inferieur_a, superieur_a.
#   Logique à trois valeurs de Kleene : sur une valeur inconnue, ils valent INCONNU (None).
OPERATEURS_EPISTEMIQUES = {"absent", "present", "pas"}
OPERATEURS_FACTUELS = {"dans", "hors", "contient", "inferieur_a", "superieur_a"}


def evaluer(cond, valeur, monde_ferme: bool = False):
    """Valeur de vérité d'une condition : True, False ou None (inconnu).
    monde_ferme : pour une variable en « monde fermé » (signature du fichier de règles), une valeur absente veut
    dire « aucun » (ex. aucune prescription liée) : les opérateurs factuels valent alors faux, jamais inconnu."""
    if isinstance(cond, dict):
        if len(cond) != 1:
            raise ValueError(f"Condition à un seul opérateur attendue : {cond}")
        op, arg = next(iter(cond.items()))
        if op == "absent":
            return _vide(valeur) == bool(arg)
        if op == "present":
            return (not _vide(valeur)) == bool(arg)
        if op == "pas":
            return valeur != arg
        if op not in OPERATEURS_FACTUELS:
            raise ValueError(f"Condition inconnue : {cond}")
        if _vide(valeur):
            return False if monde_ferme else None
        if op == "dans":
            return valeur in arg
        if op == "hors":                      # liste d'autorisation : toute autre valeur que celles-ci
            return valeur not in arg
        if op == "contient":
            return normaliser(arg) in normaliser(valeur)
        if not isinstance(valeur, (int, float)) or isinstance(valeur, bool):
            return False if monde_ferme else None
        return valeur < arg if op == "inferieur_a" else valeur > arg
    if _vide(valeur):
        return False if monde_ferme else None
    return valeur == cond


def condition_vraie(cond, valeur) -> bool:
    """Vrai seulement si la condition est établie (une condition inconnue n'est pas vraie)."""
    return evaluer(cond, valeur) is True


def conjonction(si: dict, contexte: dict, fermees: frozenset | set = frozenset()):
    """Conjonction de Kleene : False si une condition est fausse, sinon None si l'une est inconnue, sinon True."""
    valeurs = [evaluer(c, contexte.get(k), k in fermees) for k, c in si.items()]
    if False in valeurs:
        return False
    return None if None in valeurs else True


UNITES_MG = {"mcg": 0.001, "µg": 0.001, "ug": 0.001, "mg": 1.0, "g": 1000.0, "gr": 1000.0, "gramme": 1000.0, "grammes": 1000.0,
              "kg": 1_000_000.0}


def lire_dose(dose: str | None, posologie: str | None) -> dict:
    """« 50 mg » + « 3 fois par jour » -> {"mg": 50, "prises_par_jour": 3, "mg_par_jour": 150}. Lit aussi les fautes
    courantes : « 7fois parjours », « 3x/j », « toutes les 6 h », « matin et soir »."""
    d = normaliser(dose or "").replace("_", " ").replace(",", ".")
    p = normaliser(posologie or "").replace("_", " ").replace(",", ".")
    for mot, n in (("une", 1), ("un", 1), ("deux", 2), ("trois", 3), ("quatre", 4), ("cinq", 5), ("six", 6), ("sept", 7),
                   ("huit", 8), ("dix", 10), ("demi", 0.5)):
        d = re.sub(rf"\b{mot}\b", str(n), d)
        p = re.sub(rf"\b{mot}\b", str(n), p)
    sortie = {"texte": (dose or "").strip(), "posologie": (posologie or "").strip(), "mg": None, "unite": None,
              "prises_par_jour": None, "mg_par_jour": None}
    m = re.search(r"(\d+(?:\.\d+)?)\s*(mcg|µg|ug|mg|grammes?|gr|g|kg|ml|l|ui|comprimes?|cpr?s?|gelules?|caps|gouttes?|sachets?|[a-z]+)?\b", d)
    sortie["nombre_lu"] = bool(m)
    if m:
        n, u = float(m.group(1)), (m.group(2) or "")
        sortie["unite"] = u or None
        if u in UNITES_MG:
            sortie["mg"] = n * UNITES_MG[u]
    q = re.sub(r"(\d)\s*(fois|x)\b", r"\1 fois", p).replace("parjours", "par jour").replace("parjour", "par jour")
    m = re.search(r"(\d+)\s*fois\s*(?:par|/|le|chaque)?\s*(?:jour|jours|j\b|24)", q) or re.search(r"(\d+)\s*x\s*/\s*j", q)
    if m:
        sortie["prises_par_jour"] = int(m.group(1))
    elif re.search(r"toutes les (\d+)\s*h", q):
        h = int(re.search(r"toutes les (\d+)\s*h", q).group(1))
        sortie["prises_par_jour"] = max(1, round(24 / h)) if h else None
    elif re.search(r"\bmatin(?:,| et) midi et soir\b", q):
        sortie["prises_par_jour"] = 3
    elif re.search(r"\bmatin et soir\b", q):
        sortie["prises_par_jour"] = 2
    elif re.search(r"\b(une fois par jour|1 fois|le matin|le soir|au coucher)\b", q):
        sortie["prises_par_jour"] = 1
    if sortie["mg"] is not None and sortie["prises_par_jour"]:
        sortie["mg_par_jour"] = sortie["mg"] * sortie["prises_par_jour"]
    return sortie


# Une règle restrictive (A_REVOIR, BLOQUE) qui POURRAIT s'appliquer si l'on savait ce qui manque n'est jamais ignorée :
# elle donne « preuves insuffisantes » (principe : une inconnue n'est jamais supposée sans danger).
RESTRICTIFS = {"A_REVOIR", "BLOQUE"}


class MoteurRegles:
    def __init__(self, chemin_regles: str | Path, base: BaseConnaissances | None = None, langue: str = "fr"):
        chemin_regles = Path(chemin_regles)
        self.kb = json.loads(chemin_regles.read_text(encoding="utf-8"))
        self.base = base or BaseConnaissances(chemin_regles.parent)
        self.langue = langue
        manquantes = self.references_inconnues()
        if manquantes:
            raise ValueError(f"Règles citant des fiches absentes de la base : {sorted(manquantes)}")

    # ------------------------------------------------------------------ contrôle de la base
    def _toutes_les_regles(self):
        kb = self.kb
        yield from kb["regle_prescripteur"].values()
        yield from kb["champs_obligatoires_avant_prescription"]
        for m in kb["medicaments"].values():
            if not m.get("amm", True):
                yield m
            yield from m.get("contre_indications", [])
        for cle in ("regle_medicament_inconnu", "regle_amm_a_confirmer", "regle_allergie", "regle_partage_non_couvert",
                    "regle_mode_inconnu", "regle_mode_contradictoire"):
            yield kb[cle]
        for cle in ("regles_prescription", "regles_partage", "regles_envoi_patient", "regles_etat"):
            yield from kb[cle]

    def references_inconnues(self) -> set:
        refs = {f for r in self._toutes_les_regles() for f in r.get("fiches", [])}
        lac = {r["lacune"] for r in self._toutes_les_regles() if r.get("lacune")}
        return {f for f in refs if f not in self.base.fiches} | {l for l in lac if l not in self.base.lacunes}

    # ------------------------------------------------------------------ outils internes
    @staticmethod
    def _pire(a: str, b: str) -> str:
        return a if ORDRE[a] >= ORDRE[b] else b

    @staticmethod
    def _valeurs(etat: dict) -> dict:
        return {k: v["valeur"] for k, v in etat.items()}

    def _constat(self, regle_id: str, r: dict, niveau: str | None = None, prefixe: str = "") -> dict:
        detail = r.get("detail_en") if self.langue == "en" and r.get("detail_en") else r.get("detail", "")
        fiches = r.get("fiches", [])
        return {"regle": regle_id, "niveau": niveau or r["niveau"], "base": r.get("base", "-"),
                "fiches": fiches, "source": " ; ".join(self.base.citer(f, self.langue) for f in fiches) or "-",
                "reference_courte": " ; ".join(self.base.citer_court(f) for f in fiches) or "-",
                "detail": prefixe + detail, "lacune": r.get("lacune"), "juridiction": r.get("juridiction"),
                "piste": (r.get("piste_en") if self.langue == "en" and r.get("piste_en") else r.get("piste"))}

    def fermees(self, famille: str) -> frozenset:
        """Variables en monde fermé d'une famille de règles (signature du fichier de règles)."""
        sig = self.kb.get("signature", {}).get(famille, {})
        return frozenset(k for k, v in sig.items() if v.get("monde") == "ferme")

    def _appliquer(self, regles: list, contexte: dict, famille: str) -> list[dict]:
        sortie, potentiels, fermees = [], [], self.fermees(famille)
        for r in regles:
            v = conjonction(r["si"], contexte, fermees)
            if v is True:
                sortie.append(self._constat(r["id"], r))
            elif v is None and r["niveau"] in RESTRICTIFS:
                potentiels.append(self._potentiel(r["id"], r, r["si"], contexte, fermees))
        # une règle explicite déjà déclenchée sur l'absence de la même information (ex. « …-INCONNU ») suffit
        couvertes = {k for r in regles if conjonction(r["si"], contexte, fermees) is True
                     and r["niveau"] in RESTRICTIFS | {"PREUVES_INSUFFISANTES"}
                     for k, c in r["si"].items() if c == {"absent": True}}
        return sortie + [c for c in potentiels if not set(c["manquants"]) <= couvertes]

    def _potentiel(self, regle_id: str, r: dict, si: dict, contexte: dict, fermees=frozenset()) -> dict:
        manquants = [k for k, c in si.items() if evaluer(c, contexte.get(k), k in fermees) is None]
        en = self.langue == "en"
        prefixe = (f"Missing information ({', '.join(manquants)}) needed to rule out: " if en
                   else f"Information manquante ({', '.join(manquants)}) pour écarter : ")
        c = self._constat(f"{regle_id}?", r, niveau="PREUVES_INSUFFISANTES", prefixe=prefixe)
        c["manquants"] = manquants
        return c

    def incoherences(self, ctx: dict) -> list[dict]:
        """Axiomes contredits par des valeurs connues (ex. sexe = M et grossesse = oui)."""
        out = []
        for ax in self.kb.get("axiomes", []):
            if conjonction(ax["si"], ctx, self.fermees("axiomes")) is True:
                if any(not _vide(ctx.get(k)) and ctx.get(k) != v for k, v in ax["alors"].items()):
                    out.append(ax)
        return out

    def axiomes(self, ctx: dict) -> dict:
        """Connaissances de fond (fichier de règles, clé « axiomes ») : complètent une valeur inconnue quand elle
        découle de faits connus (ex. un homme n'est pas enceint). Ne remplacent jamais une valeur connue."""
        derives = {}
        for ax in self.kb.get("axiomes", []):
            if conjonction(ax["si"], ctx, self.fermees("axiomes")) is True:
                for k, v in ax["alors"].items():
                    if _vide(ctx.get(k)) and k not in derives:
                        derives[k] = v
        return derives

    @staticmethod
    def _condition_applicable(si: dict, ctx: dict) -> bool:
        """Une condition dont on ne connaît pas les éléments est considérée comme applicable (prudence)."""
        sexe, age = ctx.get("sexe"), ctx.get("age")
        if "sexe" in si and sexe is not None and sexe != si["sexe"]:
            return False
        if "age_min" in si and age is not None and age < si["age_min"]:
            return False
        if "age_max" in si and age is not None and age > si["age_max"]:
            return False
        return True

    def _resultat(self, objet: str, constats: list[dict], extra: dict, defaut: str = "CONFORME") -> dict:
        verdict = defaut
        for c in constats:
            if c["niveau"] not in NON_VERDICTS:
                verdict = self._pire(verdict, c["niveau"])
        bloquants = [c for c in constats if c["niveau"] not in NON_VERDICTS]
        return {"objet": objet, **extra, "verdict": verdict, "constats": bloquants,
                "obligations": [c for c in constats if c["niveau"] == "OBLIGATION"],
                "informations": [c for c in constats if c["niveau"] == "INFORMATION"],
                "lacunes_liees": sorted({c["lacune"] for c in constats if c.get("lacune")}),
                "depassement_possible": verdict == "A_REVOIR"}

    # ------------------------------------------------------------------ prescription
    MODES = {"presentiel": "presentiel", "en_personne": "presentiel", "in_person": "presentiel", "sur_place": "presentiel",
             "distance": "distance", "a_distance": "distance", "teleconsultation": "distance", "telesante": "distance",
             "telehealth": "distance", "telemedecine": "distance", "remote": "distance", "video": "distance"}
    NEGATIONS = ("aucun", "aucune", "pas", "non", "none", "no", "nil", "neant")

    def _trouver_medicament(self, nom: str):
        meds = self.kb["medicaments"]
        if nom in meds:
            return nom, meds[nom]
        for cle, m in meds.items():
            if nom in m.get("synonymes", []):
                return cle, m
        return nom, None

    def _allergique(self, allergies, nom: str, med: dict) -> bool:
        if not isinstance(allergies, str):
            return False
        a = normaliser(allergies)
        if a.split("_")[0] in self.NEGATIONS:
            return False
        termes = [nom, *med.get("synonymes", []), *med.get("classes", [])]
        return any(t in a for t in termes)

    def verifier_prescription(self, decision: dict, etat: dict) -> dict:
        """decision : medicament, prescripteur, auteur, dose, posologie, mode (presentiel|distance),
        urgence, issue_de_suggestion. etat : état du patient du dossier partagé."""
        kb = self.kb
        ctx = {**self._valeurs(etat), **{k: v for k, v in decision.items() if v is not None}}
        nom, med = self._trouver_medicament(normaliser(decision["medicament"]))
        ctx["categorie"] = med.get("categorie") if med else None
        mode_brut = decision.get("mode") or ctx.get("mode_consultation")
        ctx["mode"] = self.MODES.get(normaliser(mode_brut)) if mode_brut else None
        mode_dossier = self.MODES.get(normaliser(ctx["mode_consultation"])) if ctx.get("mode_consultation") else None
        constats = []
        if ctx["mode"] and mode_dossier and ctx["mode"] != mode_dossier:
            constats.append(self._constat("mode_contradictoire", kb["regle_mode_contradictoire"]))
            ctx["mode"] = "distance"   # prudence : on applique aussi les règles de la téléconsultation
        if ctx["mode"] is None:
            constats.append(self._constat("mode_consultation", kb["regle_mode_inconnu"],
                                          prefixe=f"« {mode_brut} » : " if mode_brut else ""))

        # 1. Qui prescrit ?
        p = kb["prescripteurs"].get(decision.get("prescripteur"))
        if decision.get("auteur") not in (None, "medecin") or (p and not p.get("humain", False)):
            constats.append(self._constat("prescripteur_humain", kb["regle_prescripteur"]["non_humain"]))
        if p is None:
            constats.append(self._constat("prescripteur_autorise", kb["regle_prescripteur"]["inconnu"],
                                          prefixe=f"{decision.get('prescripteur')} : "))
        elif not p.get("actif", False):
            constats.append(self._constat("prescripteur_actif", kb["regle_prescripteur"]["inactif"],
                                          prefixe=f"{decision.get('prescripteur')} : "))

        # 2. Le médicament est-il autorisé ?
        if med is None:
            constats.append(self._constat("medicament_connu", kb["regle_medicament_inconnu"],
                                          prefixe=f"« {decision['medicament']} » : "))
        elif not med.get("amm", False):
            constats.append(self._constat("autorisation_mise_sur_le_marche", {**med, "niveau": med.get("niveau_sans_amm", "BLOQUE")}))
        elif med.get("amm_a_confirmer"):
            constats.append(self._constat("autorisation_a_confirmer", kb["regle_amm_a_confirmer"]))

        # 3. L'état du patient est-il assez connu ?
        manquants = []
        for ch in kb["champs_obligatoires_avant_prescription"]:
            if not self._condition_applicable(ch["si"], ctx):
                continue
            v = etat.get(ch["champ"])
            if v is None or not v["confirme"]:
                manquants.append(ch["champ"])
                constats.append(self._constat(f"champ_obligatoire:{ch['champ']}", {**ch, "niveau": "PREUVES_INSUFFISANTES"}))

        # 4. Informations contradictoires (ex. un homme noté enceint) : jamais tranchées en silence
        for ax in self.incoherences(ctx):
            constats.append(self._constat(f"incoherence:{ax['id']}", {**ax, "niveau": "PREUVES_INSUFFISANTES"},
                                          prefixe="Informations contradictoires : "))

        # 5. Contre-indications et allergies, pour tout médicament connu, autorisé ou non
        #    (avec les connaissances de fond : un homme n'est pas enceint)
        if med:
            ctx_ci, fermees = {**ctx, **self.axiomes(ctx)}, self.fermees("contre_indications")
            for ci in med.get("contre_indications", []):
                v = conjonction(ci["si"], ctx_ci, fermees)
                rid = f"contre_indication:{nom}:{'+'.join(sorted(ci['si']))}"      # ex. contre_indication:tramadol:grossesse
                if v is True:
                    constats.append(self._constat(rid, ci))
                elif v is None and ci["niveau"] in RESTRICTIFS:
                    constats.append(self._potentiel(rid, ci, ci["si"], ctx_ci, fermees))
            if self._allergique(ctx.get("allergies"), nom, med):
                regle = dict(kb["regle_allergie"])
                if med.get("allergie_fiches"):          # la notice du produit précise la contre-indication
                    regle["fiches"] = list(dict.fromkeys(regle.get("fiches", []) + med["allergie_fiches"]))
                constats.append(self._constat(f"allergie:{nom}", regle))
        elif self._allergique(ctx.get("allergies"), nom, {}):
            # médicament inconnu de la base, mais le patient a déclaré une allergie à ce nom même
            constats.append(self._constat(f"allergie:{nom}", kb["regle_allergie"]))

        # 5 bis. La dose est-elle plausible ? (lecture de la dose et du rythme, comparaison à la dose maximale)
        dose = lire_dose(decision.get("dose"), decision.get("posologie"))
        constats += self._verifier_dose(nom, med or {}, dose, ctx.get("age"))
        # Antécédents non renseignés : les contre-indications qui en dépendent sont jugées sur les antécédents DÉCLARÉS
        # (ce qui n'est pas écrit est supposé absent) ; le juriste le dit, pour que le médecin vérifie.
        drapeaux = {k for c in (med or {}).get("contre_indications", []) for k in c["si"]} & {
            "maladie_renale", "maladie_hepatique", "ulcere_digestif", "anticoagulant", "maladie_cardiaque"}
        if drapeaux and not any(k in etat for k in ("antecedents", "maladies_connues", *drapeaux)):
            noms = {"maladie_renale": "maladie des reins", "maladie_hepatique": "maladie du foie", "ulcere_digestif": "ulcère",
                    "anticoagulant": "anticoagulant", "maladie_cardiaque": "maladie du cœur"}
            constats.append({"regle": f"antecedents_non_renseignes:{nom}", "niveau": "INFORMATION", "base": "LOI",
                             "fiches": ["ML16-A4-2"] if self.pays == "AE" else [], "source": "-",
                             "reference_courte": self.base.citer_court("ML16-A4-2") if self.pays == "AE" else "-",
                             "detail": f"Antécédents non renseignés : vérifiez l'absence de {', '.join(noms[k] for k in sorted(drapeaux))} avant {nom}.",
                             "lacune": None, "juridiction": None, "piste": "Remplissez « Maladies connues, antécédents » dans la fiche (même « aucun »)."})

        # 6. Règles générales (écrit, téléconsultation, consentement, information, IA)
        constats += self._appliquer(kb["regles_prescription"], {**ctx, **self.axiomes(ctx)}, "prescription")

        alternatives = []
        if med:
            ctx_ci = {**ctx, **self.axiomes(ctx)}
            for ci in med.get("contre_indications", []):
                if ci.get("alternative") and conjonction(ci["si"], ctx_ci, self.fermees("contre_indications")) is True:
                    alternatives.append({"medicament": ci["alternative"], "fiches": ci.get("fiches_alternative", []),
                                         "source": " ; ".join(self.base.citer_court(f) for f in ci.get("fiches_alternative", [])),
                                         "raison": ci.get("detail", "")})
        return self._resultat("prescription", constats, {
            "medicament": decision["medicament"], "prescripteur": decision.get("prescripteur"),
            "informations_manquantes": manquants, "dose_lue": dose, "alternatives": alternatives})

    def _verifier_dose(self, nom, med: dict, dose: dict, age=None) -> list[dict]:
        """Garde-fous de dose. Une unité impossible (« 1 kg ») ou plus du double de la dose maximale par jour est
        BLOQUÉE par le garde-fou de sûreté du système (erreur de saisie probable, risque vital) ; au-delà de la dose
        maximale, « à revoir » avec la source de cette dose ; un rythme ou une dose illisible : information manquante."""
        constats, en = [], self.langue == "en"
        # Fiches citées par le garde-fou : la règle « prescription écrite avec dose » du pays, et la dose maximale du produit
        ecrite = next((r.get("fiches", []) for r in self.kb["regles_prescription"] if r["id"] == "RX-ECRITE-DOSE"), [])
        fiches_max = (med.get("dose_max_jour_mg") or {}).get("fiches", [])

        def garde(detail, piste, fiches):
            return {"regle": "SURETE-DOSE", "niveau": "BLOQUE", "base": "SURETE", "fiches": fiches,
                    "source": " ; ".join(self.base.citer(f, self.langue) for f in fiches) or "-",
                    "reference_courte": "Garde-fou de sûreté de MEDIMCOM IA (dose)"
                                        + (" ; " + " ; ".join(self.base.citer_court(f) for f in fiches) if fiches else ""),
                    "detail": detail, "lacune": None, "juridiction": None, "piste": piste}
        if dose.get("unite") in ("kg", "l"):
            constats.append(garde(f"Dose impossible ({dose['texte']}) : erreur de saisie probable, risque vital.",
                                  "Corrigez la dose (en mg ou en g) et le rythme (« 3 fois par jour »).", ecrite + fiches_max))
            return constats
        if dose.get("texte") and not dose.get("nombre_lu"):
            constats.append({"regle": "DOSE-ILLISIBLE", "niveau": "PREUVES_INSUFFISANTES", "base": "LOI", "fiches": ["ML16-A4-6"],
                             "source": self.base.citer("ML16-A4-6", self.langue), "reference_courte": self.base.citer_court("ML16-A4-6"),
                             "detail": f"Dose illisible (« {dose['texte']} ») : la prescription écrite doit préciser la dose.",
                             "lacune": None, "juridiction": None, "piste": "Écrivez par exemple « 500 mg »."})
        maxi = (med.get("dose_max_jour_mg") or {})
        enfant = med.get("dose_max_jour_mg_enfant")
        if enfant and isinstance(age, (int, float)) and age < enfant.get("age_inferieur_a", 18):
            maxi = enfant                         # dose maximale de l'enfant
        if maxi and dose.get("mg_par_jour"):
            m, j = maxi["valeur"], dose["mg_par_jour"]
            if j > 2 * m:
                constats.append(garde(f"{nom} : {j:g} mg par jour, soit {j / m:.0f} fois la dose maximale ({m} mg/j) : surdosage dangereux.",
                                      f"Ne dépassez pas {m} mg par jour ; vérifiez la dose et le nombre de prises.", fiches_max + ecrite))
            elif j > m:
                constats.append(self._constat(f"dose_max:{nom}", {
                    "niveau": "A_REVOIR", "base": "RECOMMANDATION", "fiches": maxi.get("fiches", []),
                    "detail": f"{nom} : {j:g} mg par jour, au-delà de la dose maximale de {m} mg par jour.",
                    "detail_en": f"{nom}: {j:g} mg per day, above the maximum of {m} mg per day."}))
        elif maxi and dose.get("mg") and dose.get("prises_par_jour") is None and dose.get("posologie"):
            constats.append({"regle": "RYTHME-ILLISIBLE", "niveau": "PREUVES_INSUFFISANTES", "base": "LOI", "fiches": ["ML16-A4-6"],
                             "source": self.base.citer("ML16-A4-6", self.langue), "reference_courte": self.base.citer_court("ML16-A4-6"),
                             "detail": f"Rythme des prises illisible (« {dose['posologie']} ») : impossible de vérifier la dose par jour.",
                             "lacune": None, "juridiction": None, "piste": "Écrivez par exemple « 3 fois par jour » ou « toutes les 8 heures »."})
        return constats

    # ------------------------------------------------------------------ données
    # Jetons NEUTRES (indépendants du pays) : « dans_le_pays » / « hors_du_pays ». Les noms de pays (Émirats,
    # Cameroun…) sont traduits par chaque fichier de règles (clé « lieux ») : « EAU » veut dire « dans le pays »
    # pour les règles des Émirats, mais « hors du pays » pour celles du Cameroun.
    LIEUX = {"local": "dans_le_pays", "dans_le_pays": "dans_le_pays", "national": "dans_le_pays", "in_country": "dans_le_pays",
             "sur_place": "dans_le_pays", "hors_du_pays": "hors_du_pays", "etranger": "hors_du_pays",
             "a_l_etranger": "hors_du_pays", "abroad": "hors_du_pays", "outside": "hors_du_pays", "international": "hors_du_pays"}
    VRAI = {"oui", "yes", "true", "vrai", "1"}
    FAUX = {"non", "no", "false", "faux", "0"}

    # Rôle des sources propres à chaque pays (kb/sources.json) ; les autres rôles (exemples mondiaux, références
    # cliniques, UIT) s'appliquent partout. Un texte comparatif n'est jamais une base de décision.
    ROLES_NATIONAUX = {"AE": "primary", "CM": "national_cm"}

    @property
    def pays(self) -> str:
        return self.kb.get("pays", "AE")

    def applicable(self, fiche_id: str) -> bool:
        """Vrai si la fiche peut fonder une réponse dans le pays des règles chargées."""
        f = self.base.fiches.get(fiche_id)
        if not f or f.get("basis") == "COMPARATIF":
            return False
        role = self.base.sources[f["source"]]["role"]
        return role not in self.ROLES_NATIONAUX.values() or role == self.ROLES_NATIONAUX.get(self.pays)

    def _normaliser_demande(self, demande: dict) -> dict:
        d = dict(demande)
        if isinstance(d.get("lieu"), str):
            lieux = {**self.LIEUX, **{normaliser(k): v for k, v in self.kb.get("lieux", {}).items()}}
            d["lieu"] = lieux.get(normaliser(d["lieu"]), d["lieu"])
        for k in ("consentement_ecrit", "chiffrement", "copie_eau", "anonymise", "autorisation_autorite"):
            if isinstance(d.get(k), str):
                v = normaliser(d[k])
                d[k] = True if v in self.VRAI else False if v in self.FAUX else d[k]
        for k in ("finalite", "destinataire_type"):
            if isinstance(d.get(k), str):
                d[k] = normaliser(d[k])
        return d

    def verifier_partage_donnees(self, demande: dict) -> dict:
        demande = self._normaliser_demande(demande)
        constats = self._appliquer(self.kb["regles_partage"], demande, "partage")
        if not [c for c in constats if c["niveau"] not in NON_VERDICTS]:
            constats.append(self._constat("partage_non_couvert", self.kb["regle_partage_non_couvert"]))
        r = self._resultat("partage_de_donnees", constats, {"demande": demande})
        r["depassement_possible"] = r["verdict"] == "A_REVOIR"
        return r

    # ------------------------------------------------------------------ envoi au patient
    def verifier_envoi_patient(self, message: dict, suppose_valide: bool = False) -> dict:
        """Forme (validé par un médecin autorisé ?) ET contenu (medimcom/surete.py : propos dangereux, consigne de
        médicament sans prescription). `suppose_valide` : pré-contrôle d'une proposition que le médecin n'a pas encore
        validée (« si elle était validée, pourrait-elle partir ? ») ; un contenu interdit est ainsi bloqué AVANT."""
        from .surete import analyser_message
        p = self.kb["prescripteurs"].get(str(message.get("valide_par") or "").strip().upper())
        analyse = analyser_message(message.get("texte", ""), self.kb.get("medicaments", {}))
        ctx = {**message, "valideur_autorise": suppose_valide or bool(p and p.get("humain") and p.get("actif")),
               "incitation_au_mal": analyse["incitation_au_mal"],
               "medicament_controle": analyse["medicament_controle"]}
        if analyse["consigne_medicament"] and ctx.get("contenu_type") not in ("traitement", "diagnostic"):
            ctx["contenu_type"] = "traitement"     # « prends du tramadol » est une consigne de traitement, quel que soit le bouton choisi
        constats = self._appliquer(self.kb["regles_envoi_patient"], ctx, "envoi_patient")
        if analyse["incitation_au_mal"] and not any(c["niveau"] == "BLOQUE" and c["regle"] == "ENVOI-PROPOS-DANGEREUX" for c in constats):
            constats.append(self.garde_fou_surete(analyse))
        r = self._resultat("envoi_au_patient", constats, {"message": message.get("texte", "")})
        r["depassement_possible"] = False
        r["analyse_contenu"] = {k: v for k, v in analyse.items() if v}
        return r

    def garde_fou_surete(self, analyse: dict) -> dict:
        """Garde-fou de SÛRETÉ du système, indépendant du droit : un message qui incite le patient à se faire du mal
        (ou qui l'injurie) ne part jamais, même dans un pays dont aucun texte lu ne couvre encore ce cas. Il est
        présenté comme tel (base « SURETE ») et non comme un verdict juridique."""
        en = self.langue == "en"
        # Texte cité : la déontologie ou le devoir de soin du pays (non encore lu article par article : le blocage
        # vient du garde-fou, pas de ce texte, qui situe seulement le principe).
        fiches = ["ML16-A3"] if self.pays == "AE" else [f for f in ("CM-DEONTO",) if f in self.base.fiches]
        return {"regle": "SURETE-PROPOS-DANGEREUX", "niveau": "BLOQUE", "base": "SURETE", "fiches": fiches,
                "source": " ; ".join(self.base.citer(f, self.langue) for f in fiches) or "-",
                "reference_courte": ("MEDIMCOM IA safety guard (no law read yet covers this case here)" if en
                                     else "Garde-fou de sûreté de MEDIMCOM IA (aucun texte lu ne couvre encore ce cas dans ce pays)"),
                "detail": (f"Message harmful to the patient ({analyse.get('motif')}): it will not be sent." if en
                           else f"Message dangereux pour le patient ({analyse.get('motif')}) : il ne partira pas."),
                "lacune": None, "juridiction": None,
                "piste": ("Withdraw this message. If the patient seems distressed, tell them you are there to help and call emergency services."
                          if en else "Retirez ce message. Si le patient semble en détresse, dites-lui que vous êtes là pour l'aider et appelez les secours.")}

    # ------------------------------------------------------------------ maintien nominatif
    def autoriser_maintien(self, statut: str, medecin: str, justification: str) -> tuple[bool, str]:
        if statut == "BLOQUE":
            return False, "décision bloquée par une règle contraignante : aucune dérogation possible."
        if statut != "A_REVOIR":
            return False, f"seule une décision « à revoir » peut être maintenue (statut actuel : {statut})."
        p = self.kb["prescripteurs"].get(medecin)
        if not p or not p.get("humain") or not p.get("actif"):
            return False, f"{medecin} n'est pas un praticien autorisé et actif."
        if not (justification or "").strip():
            return False, "une justification écrite est obligatoire."
        return True, "maintien autorisé"

    # ------------------------------------------------------------------ obligations liées à l'état
    def obligations_etat(self, etat: dict) -> list[dict]:
        return self._appliquer(self.kb["regles_etat"], self._valeurs(etat), "etat")
