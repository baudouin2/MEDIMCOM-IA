"""Deterministic rule engine of the jurist agent.

IT is what returns the verdicts. The jurist's language model may consult it,
explain and negotiate, but it cannot change a verdict.

Each finding cites provisions of the knowledge base (kb/fiches.jsonl):
the full citation (text, article, official link, verification level) is
rebuilt from the base, never hand-written in the code.
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


# Formal semantics of the condition language (see docs/technique/METHODES_FORMELLES.md).
# - EPISTEMIC operators (about what is known): absent, present, pas ("it is not established that…").
#   Always true or false.
# - FACTUAL operators (about the world): equality, dans, contient, inferieur_a, superieur_a.
#   Kleene three-valued logic: on an unknown value, they are UNKNOWN (None).
OPERATEURS_EPISTEMIQUES = {"absent", "present", "pas"}
OPERATEURS_FACTUELS = {"dans", "hors", "contient", "inferieur_a", "superieur_a"}


def evaluer(cond, valeur, monde_ferme: bool = False):
    """Truth value of a condition: True, False or None (unknown).
    monde_ferme: for a "closed-world" variable (signature of the rules file), a missing value means
    "none" (e.g. no linked prescription): factual operators are then false, never unknown."""
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
        if op == "hors":                      # allow-list: any value other than these
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
    """True only if the condition is established (an unknown condition is not true)."""
    return evaluer(cond, valeur) is True


def conjonction(si: dict, contexte: dict, fermees: frozenset | set = frozenset()):
    """Kleene conjunction: False if a condition is false, otherwise None if one is unknown, otherwise True."""
    valeurs = [evaluer(c, contexte.get(k), k in fermees) for k, c in si.items()]
    if False in valeurs:
        return False
    return None if None in valeurs else True


UNITES_MG = {"mcg": 0.001, "µg": 0.001, "ug": 0.001, "mg": 1.0, "g": 1000.0, "gr": 1000.0, "gramme": 1000.0, "grammes": 1000.0,
              "kg": 1_000_000.0}


def lire_dose(dose: str | None, posologie: str | None) -> dict:
    """"50 mg" + "3 fois par jour" -> {"mg": 50, "prises_par_jour": 3, "mg_par_jour": 150}. Also reads common
    typos: "7fois parjours", "3x/j", "toutes les 6 h", "matin et soir"."""
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


# A restrictive rule (A_REVOIR, BLOQUE) that COULD apply if the missing facts were known is never ignored: it gives
# "insufficient evidence" (principle: an unknown is never assumed safe).
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

    # ------------------------------------------------------------------ knowledge-base checks
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
        """Closed-world variables of a rule family (signature of the rules file)."""
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
        # an explicit rule already triggered by the absence of the same information (e.g. "…-INCONNU") is enough
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
        """Axioms contradicted by known values (e.g. sex = M and pregnancy = yes)."""
        out = []
        for ax in self.kb.get("axiomes", []):
            if conjonction(ax["si"], ctx, self.fermees("axiomes")) is True:
                if any(not _vide(ctx.get(k)) and ctx.get(k) != v for k, v in ax["alors"].items()):
                    out.append(ax)
        return out

    def axiomes(self, ctx: dict) -> dict:
        """Background knowledge (rules file, key "axiomes"): fills in an unknown value when it follows from
        known facts (e.g. a man is not pregnant). Never replaces a known value."""
        derives = {}
        for ax in self.kb.get("axiomes", []):
            if conjonction(ax["si"], ctx, self.fermees("axiomes")) is True:
                for k, v in ax["alors"].items():
                    if _vide(ctx.get(k)) and k not in derives:
                        derives[k] = v
        return derives

    @staticmethod
    def _condition_applicable(si: dict, ctx: dict) -> bool:
        """A condition whose elements are unknown is considered applicable (caution)."""
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
        # Typing or dictation error ("tramadole", "doliprane", "para c'est tamol"): careful reading, shown to the doctor
        from .lecture import trouver_medicaments
        lus = [x for x in trouver_medicaments(nom.replace("_", " "), meds) if x["nom"] in meds]
        if len(lus) == 1:
            return lus[0]["nom"], meds[lus[0]["nom"]]
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
        """decision: medicament, prescripteur, auteur, dose, posologie, mode (presentiel|distance),
        urgence, issue_de_suggestion. etat: patient state from the shared record."""
        kb = self.kb
        ctx = {**self._valeurs(etat), **{k: v for k, v in decision.items() if v is not None}}
        nom, med = self._trouver_medicament(normaliser(decision["medicament"]))
        ctx["categorie"] = med.get("categorie") if med else None
        lu_comme = med is not None and normaliser(decision["medicament"]) not in (nom, *[normaliser(x) for x in med.get("synonymes", [])])
        mode_brut = decision.get("mode") or ctx.get("mode_consultation")
        ctx["mode"] = self.MODES.get(normaliser(mode_brut)) if mode_brut else None
        mode_dossier = self.MODES.get(normaliser(ctx["mode_consultation"])) if ctx.get("mode_consultation") else None
        constats = []
        if ctx["mode"] and mode_dossier and ctx["mode"] != mode_dossier:
            constats.append(self._constat("mode_contradictoire", kb["regle_mode_contradictoire"]))
            ctx["mode"] = "distance"   # caution: the teleconsultation rules are applied too
        if ctx["mode"] is None:
            constats.append(self._constat("mode_consultation", kb["regle_mode_inconnu"],
                                          prefixe=f"« {mode_brut} » : " if mode_brut else ""))

        # 1. Who prescribes?
        p = kb["prescripteurs"].get(decision.get("prescripteur"))
        if decision.get("auteur") not in (None, "medecin") or (p and not p.get("humain", False)):
            constats.append(self._constat("prescripteur_humain", kb["regle_prescripteur"]["non_humain"]))
        if p is None:
            constats.append(self._constat("prescripteur_autorise", kb["regle_prescripteur"]["inconnu"],
                                          prefixe=f"{decision.get('prescripteur')} : "))
        elif not p.get("actif", False):
            constats.append(self._constat("prescripteur_actif", kb["regle_prescripteur"]["inactif"],
                                          prefixe=f"{decision.get('prescripteur')} : "))

        # 2. Is the medicine authorised?
        if med is None:
            constats.append(self._constat("medicament_connu", kb["regle_medicament_inconnu"],
                                          prefixe=f"« {decision['medicament']} » : "))
        elif not med.get("amm", False):
            constats.append(self._constat("autorisation_mise_sur_le_marche", {**med, "niveau": med.get("niveau_sans_amm", "BLOQUE")}))
        elif med.get("amm_a_confirmer"):
            constats.append(self._constat("autorisation_a_confirmer", kb["regle_amm_a_confirmer"]))

        # 3. Is the patient's state known well enough?
        manquants = []
        for ch in kb["champs_obligatoires_avant_prescription"]:
            if not self._condition_applicable(ch["si"], ctx):
                continue
            v = etat.get(ch["champ"])
            if v is None or not v["confirme"] or "préciser" in str(v["valeur"]):     # "yes, to be specified": not filled in yet
                manquants.append(ch["champ"])
                constats.append(self._constat(f"champ_obligatoire:{ch['champ']}", {**ch, "niveau": "PREUVES_INSUFFISANTES"}))

        # 4. Contradictory information (e.g. a man recorded as pregnant): never settled silently
        for ax in self.incoherences(ctx):
            constats.append(self._constat(f"incoherence:{ax['id']}", {**ax, "niveau": "PREUVES_INSUFFISANTES"},
                                          prefixe="Informations contradictoires : "))

        # 5. Contraindications and allergies, for every known medicine, authorised or not (with background knowledge: a
        # man is not pregnant)
        constats += self._risques_patient(nom, med, ctx)

        # 5 bis. Is the dose plausible? (reading of dose and rhythm, comparison with the maximum dose)
        dose = lire_dose(decision.get("dose"), decision.get("posologie"))
        constats += self._verifier_dose(nom, med or {}, dose, ctx.get("age"))
        # History not filled in: the contraindications that depend on it are judged on the DECLARED history (what is not
        # written is assumed absent); the jurist says so, for the doctor to check.
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

        # 6. General rules (written form, teleconsultation, consent, information, AI)
        constats += self._appliquer(kb["regles_prescription"], {**ctx, **self.axiomes(ctx)}, "prescription")

        if lu_comme:
            constats.append({"regle": f"lecture:{nom}", "niveau": "INFORMATION", "base": "SURETE", "fiches": [], "source": "-",
                             "reference_courte": "Lecture de MEDIMCOM IA",
                             "detail": f"« {decision['medicament']} » lu comme {nom} (faute de frappe ou de dictée) : vérifiez.",
                             "lacune": None, "juridiction": None, "piste": None})
        alternatives = self._alternatives(med, ctx)
        return self._resultat("prescription", constats, {
            "medicament": decision["medicament"], "prescripteur": decision.get("prescripteur"),
            "informations_manquantes": manquants, "dose_lue": dose, "alternatives": alternatives})

    def _risques_patient(self, nom: str, med: dict | None, ctx: dict) -> list[dict]:
        """Contraindications and allergy of THIS medicine for THIS patient (record state). Used for prescriptions
        and for every message to the patient that mentions the medicine."""
        constats = []
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
                regle = dict(self.kb["regle_allergie"])
                if med.get("allergie_fiches"):          # the product label specifies the contraindication
                    regle["fiches"] = list(dict.fromkeys(regle.get("fiches", []) + med["allergie_fiches"]))
                constats.append(self._constat(f"allergie:{nom}", regle))
        elif self._allergique(ctx.get("allergies"), nom, {}):
            # medicine unknown to the base, but the patient declared an allergy to this very name
            constats.append(self._constat(f"allergie:{nom}", self.kb["regle_allergie"]))
        return constats

    def _alternatives(self, med: dict | None, ctx: dict) -> list[dict]:
        alternatives = []
        if med:
            ctx_ci = {**ctx, **self.axiomes(ctx)}
            for ci in med.get("contre_indications", []):
                if ci.get("alternative") and conjonction(ci["si"], ctx_ci, self.fermees("contre_indications")) is True:
                    alternatives.append({"medicament": ci["alternative"], "fiches": ci.get("fiches_alternative", []),
                                         "source": " ; ".join(self.base.citer_court(f) for f in ci.get("fiches_alternative", [])),
                                         "raison": ci.get("detail", "")})
        return alternatives

    def risques_medicament(self, medicament: str, etat: dict) -> dict:
        """Is this medicine risky for this patient? (assistant watch, messages to the patient, medicines
        declared by the patient). Returns {medicament, connu, constats, alternatives, dose_max_mg}."""
        nom, med = self._trouver_medicament(normaliser(medicament))
        ctx = self._valeurs(etat)
        return {"medicament": nom, "connu": med is not None, "constats": self._risques_patient(nom, med, ctx),
                "alternatives": self._alternatives(med, ctx),
                "dose_max_mg": ((med or {}).get("dose_max_jour_mg") or {}).get("valeur"),
                "fiches_dose_max": ((med or {}).get("dose_max_jour_mg") or {}).get("fiches", [])}

    def _verifier_dose(self, nom, med: dict, dose: dict, age=None) -> list[dict]:
        """Dose safeguards. An impossible unit ("1 kg") or more than twice the maximum daily dose is
        BLOCKED by the system's safety safeguard (probable input error, life-threatening risk); above the maximum
        dose, "to review" with the source of that dose; an unreadable rhythm or dose: missing information."""
        constats, en = [], self.langue == "en"
        # Provisions cited by the safeguard: the country's "written prescription with dose" rule, and the product's
        # maximum dose
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
            maxi = enfant                         # maximum dose for children
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

    # ------------------------------------------------------------------ data
    # NEUTRAL tokens (country-independent): "dans_le_pays" / "hors_du_pays". Country names (UAE,
    # Cameroon…) are translated by each rules file (key "lieux"): "EAU" means "in the country"
    # for the UAE rules, but "outside the country" for the Cameroon rules.
    LIEUX = {"local": "dans_le_pays", "dans_le_pays": "dans_le_pays", "national": "dans_le_pays", "in_country": "dans_le_pays",
             "sur_place": "dans_le_pays", "hors_du_pays": "hors_du_pays", "etranger": "hors_du_pays",
             "a_l_etranger": "hors_du_pays", "abroad": "hors_du_pays", "outside": "hors_du_pays", "international": "hors_du_pays"}
    VRAI = {"oui", "yes", "true", "vrai", "1"}
    FAUX = {"non", "no", "false", "faux", "0"}

    # Role of each country's own sources (kb/sources.json); the other roles (global examples, clinical references, ITU)
    # apply everywhere. A comparative text is never a basis for a decision.
    ROLES_NATIONAUX = {"AE": "primary", "CM": "national_cm"}

    @property
    def pays(self) -> str:
        return self.kb.get("pays", "AE")

    def applicable(self, fiche_id: str) -> bool:
        """True if the provision can ground an answer in the country of the loaded rules."""
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

    # ------------------------------------------------------------------ sending to the patient
    def verifier_envoi_patient(self, message: dict, suppose_valide: bool = False, etat: dict | None = None) -> dict:
        """Form (validated by an authorised doctor?) AND content (medimcom/surete.py: dangerous statements, medicine
        instruction without prescription). `suppose_valide`: pre-check of a proposal the doctor has not validated yet
        ("if it were validated, could it be sent?"); forbidden content is thus blocked BEFORE.
        `etat`: patient state; a medicine advised in the message is checked against their record (pregnancy, age,
        allergies, diseases), like a prescription: the doctor sees WHY, for THIS patient."""
        from .surete import analyser_message
        p = self.kb["prescripteurs"].get(str(message.get("valide_par") or "").strip().upper())
        analyse = analyser_message(message.get("texte", ""), self.kb.get("medicaments", {}))
        ctx = {**message, "valideur_autorise": suppose_valide or bool(p and p.get("humain") and p.get("actif")),
               "incitation_au_mal": analyse["incitation_au_mal"],
               "medicament_controle": analyse["medicament_controle"]}
        if analyse["consigne_medicament"] and ctx.get("contenu_type") not in ("traitement", "diagnostic"):
            ctx["contenu_type"] = "traitement"     # "prends du tramadol" (take tramadol) is a treatment instruction, whatever button was chosen
        constats = self._appliquer(self.kb["regles_envoi_patient"], ctx, "envoi_patient")
        if analyse["incitation_au_mal"] and not any(c["niveau"] == "BLOQUE" and c["regle"] == "ENVOI-PROPOS-DANGEREUX" for c in constats):
            constats.append(self.garde_fou_surete(analyse))
        alternatives = []
        if analyse["consigne_medicament"] and not message.get("statut_prescription_liee"):
            if analyse.get("dose_imprecise"):
                constats.append(self._garde_dose_imprecise(analyse))
            for brut in analyse.get("medicaments") or []:
                risques = self.risques_medicament(brut, etat or {})
                for c in risques["constats"]:
                    if c["niveau"] in ("BLOQUE", "A_REVOIR") and not c.get("potentiel"):
                        constats.append({**c, "detail": ("For this patient: " if self.langue == "en" else "Pour ce patient : ") + c["detail"]})
                alternatives += risques["alternatives"]
        for e in analyse.get("ethique") or []:
            constats.append(self.garde_fou_ethique(e))
        constats += self._lecture_contexte(analyse, message)
        r = self._resultat("envoi_au_patient", constats, {"message": message.get("texte", "")})
        if r["verdict"] != "CONFORME":   # "can be sent" must never accompany a block
            r["constats"] = [c for c in r["constats"] if c["niveau"] != "CONFORME"]
        r["alternatives"] = alternatives
        r["depassement_possible"] = False
        r["analyse_contenu"] = {k: v for k, v in analyse.items() if v}
        return r

    def _lecture_contexte(self, analyse: dict, message: dict) -> list[dict]:
        """What the jurist UNDERSTOOD of the message (narrative, question, warning…), and what it could not settle.
        An uncertain meaning ("pendre" alone, a quoted incitement, a medicine named without a verb) is neither blocked nor
        let through silently: the doctor confirms what they mean, and the confirmation is signed in the journal."""
        sortie, en = [], self.langue == "en"
        fiches = (["DHA21-4.4", "ML16-A3"] if self.pays == "AE" else [f for f in ("CM-DEONTO",) if f in self.base.fiches]) or []
        ref = " ; ".join(self.base.citer_court(f) for f in fiches) or "-"
        ctx = analyse.get("contexte") or {}
        indices = ", ".join(ctx.get("indices") or []) or "aucun indice"
        if analyse.get("a_confirmer"):
            confirme = message.get("contexte_confirme_par")
            sortie.append({"regle": "CONTEXTE-A-CONFIRMER", "niveau": "INFORMATION" if confirme else "A_REVOIR", "base": "SURETE",
                           "fiches": fiches, "source": " ; ".join(self.base.citer(f, self.langue) for f in fiches) or "-",
                           "reference_courte": "Lecture du contexte par MEDIMCOM IA" + (f" ; {ref}" if fiches else ""),
                           "detail": (f"Sens confirmé par {confirme} : ni consigne ni incitation ({analyse['a_confirmer']})."
                                      if confirme else f"Sens à confirmer : {analyse['a_confirmer']}."),
                           "lacune": None, "juridiction": None,
                           "piste": None if confirme else ("Reformulez (qui, quoi, question ou récit), ou confirmez en validant "
                                                           "que ce n'est ni une consigne ni une incitation : votre nom est enregistré.")})
        if analyse.get("evocation") and not message.get("statut_prescription_liee"):
            sortie.append({"regle": "LECTURE-CONTEXTE", "niveau": "INFORMATION", "base": "SURETE", "fiches": [], "source": "-",
                           "reference_courte": "Lecture du contexte par MEDIMCOM IA",
                           "detail": f"Évocation, pas une consigne ni une incitation : {analyse['evocation']} (indices : {indices}).",
                           "lacune": None, "juridiction": None, "piste": None})
        if analyse.get("corrections"):
            sortie.append({"regle": "LECTURE-CORRECTIONS", "niveau": "INFORMATION", "base": "SURETE", "fiches": [], "source": "-",
                           "reference_courte": "Lecture de MEDIMCOM IA",
                           "detail": "Lu comme : " + " ; ".join(f"« {a} » → {b}" for a, b in analyse["corrections"].items()) + ".",
                           "lacune": None, "juridiction": None, "piste": None})
        return sortie

    def _garde_dose_imprecise(self, analyse: dict) -> dict:
        nom = analyse.get("medicament") or "ce médicament"
        _, med = self._trouver_medicament(normaliser(nom))
        maxi = ((med or {}).get("dose_max_jour_mg") or {})
        ecrite = next((r.get("fiches", []) for r in self.kb["regles_prescription"] if r["id"] == "RX-ECRITE-DOSE"), [])
        fiches = ecrite + maxi.get("fiches", [])
        limite = f" (maximum : {maxi['valeur']} mg par jour chez l'adulte)" if maxi.get("valeur") else ""
        return {"regle": "SURETE-DOSE-IMPRECISE", "niveau": "BLOQUE", "base": "SURETE", "fiches": fiches,
                "source": " ; ".join(self.base.citer(f, self.langue) for f in fiches) or "-",
                "reference_courte": "Garde-fou de sûreté de MEDIMCOM IA (dose)"
                                    + (" ; " + " ; ".join(self.base.citer_court(f) for f in fiches) if fiches else ""),
                "detail": f"Quantité imprécise de {nom} (« {analyse.get('expression') or 'beaucoup'} ») : risque de surdosage{limite}.",
                "lacune": None, "juridiction": None,
                "piste": f"Prescrivez {nom} dans l'onglet Ordonnance avec une dose en mg et un rythme précis : le juriste et l'assistant la vérifient."}

    def garde_fou_ethique(self, e: dict) -> dict:
        """Message contrary to medical ethics: it is not sent. Basis: the law when the country has a text that was read
        (abortion in the UAE: Law 4/2016, Art. 16), otherwise the system's safety safeguard, presented as such."""
        if e["categorie"] == "avortement" and self.pays == "AE" and "ML16-A16" in self.base.fiches:
            fiches, base, ref = ["ML16-A16"], "LOI", self.base.citer_court("ML16-A16")
        else:
            fiches = (["ML16-A3"] if self.pays == "AE" else [f for f in ("CM-DEONTO",) if f in self.base.fiches]) or []
            base = "SURETE"
            ref = "Garde-fou éthique de MEDIMCOM IA" + (" ; " + " ; ".join(self.base.citer_court(f) for f in fiches) if fiches else "")
        return {"regle": f"ETHIQUE-{e['categorie'].upper()}", "niveau": "BLOQUE", "base": base, "fiches": fiches,
                "source": " ; ".join(self.base.citer(f, self.langue) for f in fiches) or "-", "reference_courte": ref,
                "detail": f"Message contraire à l'éthique médicale : {e['motif']}. Il ne partira pas.",
                "lacune": None, "juridiction": None, "piste": e["piste"]}

    def garde_fou_surete(self, analyse: dict) -> dict:
        """System SAFETY safeguard, independent of the law: a message inciting the patient to harm themself (or
        insulting them) is never sent, even in a country where no text read so far covers the case. It is presented
        as such (basis "SURETE") and not as a legal verdict."""
        en = self.langue == "en"
        # Cited text: the country's code of ethics or duty of care (not yet read article by article: the block comes
        # from the safeguard, not from this text, which only frames the principle).
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

    # ------------------------------------------------------------------ obligations arising from the state
    def obligations_etat(self, etat: dict) -> list[dict]:
        return self._appliquer(self.kb["regles_etat"], self._valeurs(etat), "etat")
