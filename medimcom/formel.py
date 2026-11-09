"""Formal verification of the jurist's rules, on the REAL engine (medimcom/regles.py).

Method: exhaustive enumeration over a finite abstract domain (explicit model checking).
The rule conditions only compare a variable with constants written in the rules; two values absent from the
rules therefore always behave the same way. The abstract domain of a variable is: the constants cited by the
rules and the specification, an "other" value that stands for all the rest, and "unknown" (None); for a number,
the cited bounds and their neighbours. Checking every combination of this domain amounts to checking ALL
possible inputs (partition into equivalence classes).
The same properties are proved independently by an SMT solver in medimcom/formel_smt.py.

Each property returns the number of cases examined and at most 3 counter-examples.
"""
import itertools
import json
from pathlib import Path

from .regles import NON_VERDICTS, ORDRE, OPERATEURS_EPISTEMIQUES, OPERATEURS_FACTUELS, conjonction, evaluer

AUTRE = "«autre»"
NIVEAUX = ["CONFORME", "PREUVES_INSUFFISANTES", "A_REVOIR", "BLOQUE"]
NIVEAUX_REGLE = set(NIVEAUX) | NON_VERDICTS
BASES_CONTRAIGNANTES = {"LOI", "NORME"}
FAMILLES = {"regles_partage": "partage", "regles_envoi_patient": "envoi_patient", "regles_etat": "etat",
            "regles_prescription": "prescription"}
SPEC = Path(__file__).resolve().parent.parent / "kb" / "specification_formelle.json"


def rang(v: str) -> int:
    return ORDRE[v]


class Resultat(dict):
    """{id, titre, methode, cas, ok, contre_exemples, reference}"""


def _resultat(id_, titre, methode, cas, contre, reference=""):
    return Resultat(id=id_, titre=titre, methode=methode, cas=cas, ok=not contre, contre_exemples=contre[:3],
                    nb_contre_exemples=len(contre), reference=reference)


# ------------------------------------------------------------------ domaines abstraits
def _constantes(conditions: list) -> tuple[set, set]:
    """Constants and numeric bounds cited by a list of conditions."""
    consts, bornes = set(), set()
    for c in conditions:
        if isinstance(c, dict):
            op, arg = next(iter(c.items()))
            if op in ("dans", "hors"):
                consts |= set(arg)
            elif op == "contient":
                consts.add(arg)
            elif op in ("inferieur_a", "superieur_a"):
                bornes.add(arg)
            elif op == "pas" and not isinstance(arg, bool):
                consts.add(arg)
        elif not isinstance(c, bool):
            consts.add(c)
    return consts, bornes


def domaine(signature: dict, var: str, conditions: list) -> list:
    t = signature.get(var, {"type": "texte"})
    consts, bornes = _constantes(conditions)
    if t["type"] == "booleen":
        return [True, False, None]
    if t["type"] == "nombre":
        vals = sorted({x for b in bornes for x in (b - 1, b, b + 1)}) or [0]
        return [*vals, None]
    if t["type"] == "enum":
        return [*t["valeurs"], *sorted(consts - set(t["valeurs"]), key=str), AUTRE, None]
    return [*sorted(consts, key=str), AUTRE, None]


def _conditions_par_variable(regles: list, extra: list = ()) -> dict:
    par = {}
    for r in [*regles, *extra]:
        for k, c in r["si"].items():
            par.setdefault(k, []).append(c)
    return par


def _spec(pays: str, famille: str) -> list:
    if not SPEC.exists():
        return []
    return [e for e in json.loads(SPEC.read_text(encoding="utf-8"))["exigences"]
            if famille == e["famille"] and pays in e["pays"]]


# ------------------------------------------------------------------ bonne formation (typage)
def bonne_formation(moteur) -> list[Resultat]:
    kb, sig, base = moteur.kb, moteur.kb.get("signature", {}), moteur.base
    erreurs_type, erreurs_ids, erreurs_bloque, erreurs_pays = [], [], [], []
    ids = {}
    for cle, famille in FAMILLES.items():
        for r in kb[cle]:
            ids.setdefault(r["id"], []).append(cle)
            if r.get("niveau") not in NIVEAUX_REGLE:
                erreurs_type.append(f"{r['id']} : niveau inconnu {r.get('niveau')!r}")
            for k, c in r["si"].items():
                t = sig.get(famille, {}).get(k)
                if t is None:
                    erreurs_type.append(f"{r['id']} : variable « {k} » non déclarée dans la signature « {famille} »")
                    continue
                op = next(iter(c)) if isinstance(c, dict) else "egal"
                if isinstance(c, dict) and op not in OPERATEURS_EPISTEMIQUES | OPERATEURS_FACTUELS:
                    erreurs_type.append(f"{r['id']} : opérateur inconnu {op!r}")
                if t["type"] == "booleen" and op == "egal" and not isinstance(c, bool):
                    erreurs_type.append(f"{r['id']} : {k} est booléen, comparé à {c!r}")
                if t["type"] == "enum":
                    vals = c if op == "egal" else (c.get("dans") or c.get("hors") or [])
                    for v in ([vals] if op == "egal" else vals):
                        if v not in t["valeurs"]:
                            erreurs_type.append(f"{r['id']} : {k} = {v!r} hors des valeurs {t['valeurs']}")
                if op in ("inferieur_a", "superieur_a") and t["type"] != "nombre":
                    erreurs_type.append(f"{r['id']} : comparaison numérique sur {k} ({t['type']})")
    for med, m in kb["medicaments"].items():
        for ci in m.get("contre_indications", []):
            for k in ci["si"]:
                if k not in sig.get("contre_indications", {}):
                    erreurs_type.append(f"contre-indication {med} : variable « {k} » non déclarée")
    erreurs_ids = [f"{i} : défini {len(f)} fois ({', '.join(f)})" for i, f in ids.items() if len(f) > 1]

    def lue(fid):
        f = base.fiches.get(fid)
        return bool(f) and base.sources[f["source"]]["verification"] != "to_confirm"
    for r in moteur._toutes_les_regles():
        if r.get("niveau") == "BLOQUE":
            if r.get("base") not in BASES_CONTRAIGNANTES:
                erreurs_bloque.append(f"{r.get('id', r.get('detail', '')[:40])} : bloque sur une base « {r.get('base')} »")
            elif not any(lue(f) and base.fiches[f]["basis"] in BASES_CONTRAIGNANTES for f in r.get("fiches", [])):
                erreurs_bloque.append(f"{r.get('id', r.get('detail', '')[:40])} : aucune fiche contraignante lue")
        for f in r.get("fiches", []):
            if f in base.fiches and base.fiches[f].get("basis") != "COMPARATIF" and not moteur.applicable(f):
                erreurs_pays.append(f"{r.get('id', '?')} cite {f}, texte d'un autre pays")
    return [
        _resultat("WF1", "Typage : variables déclarées, opérateurs connus, constantes dans leur domaine", "analyse statique",
                  sum(len(kb[c]) for c in FAMILLES), erreurs_type, "signature typée (DMN, Catala)"),
        _resultat("WF2", "Identifiants de règles uniques", "analyse statique", len(ids), erreurs_ids),
        _resultat("WF3", "Seule une loi ou une norme lue peut bloquer", "analyse statique",
                  sum(1 for _ in moteur._toutes_les_regles()), erreurs_bloque, "principe de la hiérarchie des normes"),
        _resultat("WF4", "Chaque règle ne cite que des textes applicables dans son pays", "analyse statique",
                  sum(1 for _ in moteur._toutes_les_regles()), erreurs_pays),
    ]


# ------------------------------------------------------------------ declarative families (sharing, sending)
def _entrees(moteur, famille: str, regles: list, spec: list):
    sig = moteur.kb.get("signature", {}).get(famille, {})
    par = _conditions_par_variable(regles, spec)
    variables = sorted(set(sig) | set(par))
    domaines = [domaine(sig, v, par.get(v, [])) for v in variables]
    if famille == "partage" and "lieu" in variables:
        # place names as a human or a model writes them ("EAU", "Cameroun"…), BEFORE translation
        i = variables.index("lieu")
        bruts = sorted({*moteur.LIEUX, *moteur.kb.get("lieux", {}), "EAU", "hors_EAU"})
        domaines[i] = [*domaines[i][:-1], *[b for b in bruts if b not in domaines[i]], None]
    return variables, domaines, sig


def verifier_famille(moteur, famille: str) -> list[Resultat]:
    """Data sharing and sending to the patient: every input of the abstract domain, on the real engine."""
    cle = {"partage": "regles_partage", "envoi_patient": "regles_envoi_patient"}[famille]
    regles, spec = moteur.kb[cle], _spec(moteur.pays, famille)
    variables, domaines, sig = _entrees(moteur, famille, regles, spec)
    if famille == "partage":
        def juger(x):
            return moteur.verifier_partage_donnees({k: v for k, v in x.items() if v is not None})
    else:
        def juger(x):
            r = moteur._resultat("envoi_au_patient", moteur._appliquer(regles, x, "envoi_patient"), {})
            return r
    table, regles_vues = {}, set()
    for valeurs in itertools.product(*domaines):
        x = dict(zip(variables, valeurs))
        r = juger(x)
        table[valeurs] = (r["verdict"], tuple(c["regle"] for c in r["constats"]))
        regles_vues |= {c["regle"] for c in r["constats"] + r["obligations"] + r["informations"]}
    n = len(table)
    res = []
    lisible = lambda v: {k: x for k, x in zip(variables, v) if x is not None}  # noqa: E731

    # P1 default refusal: nothing is compliant without a rule that explicitly allows it
    permissions = {r["id"] for r in regles if r["niveau"] == "CONFORME"}
    contre = [lisible(v) for v, (verdict, rs) in table.items() if verdict == "CONFORME" and not permissions & set(rs)]
    res.append(_resultat(f"{famille}.P1", "Refus par défaut : rien n'est conforme sans une permission explicite",
                         "énumération exhaustive", n, contre, "politiques « deny by default » (Backes et al., 2018)"))

    # P2 caution: unknown information is never assumed safe
    contre = []
    for i, v in enumerate(variables):
        if sig.get(v, {}).get("monde") == "ferme":
            continue
        for valeurs, (verdict, _) in table.items():
            if valeurs[i] is not None or verdict != "CONFORME":
                continue
            pires = [table[valeurs[:i] + (c,) + valeurs[i + 1:]][0] for c in domaines[i] if c is not None]
            if any(p != "CONFORME" for p in pires):
                contre.append({**lisible(valeurs), "inconnue": v,
                               "si_connue": max(pires, key=rang)})
    res.append(_resultat(f"{famille}.P2", "Prudence : si une information inconnue pouvait rendre la demande non conforme, "
                         "le verdict n'est pas « conforme »", "énumération exhaustive", n, contre,
                         "logique à trois valeurs de Kleene ; hypothèse du monde ouvert"))

    # P3 monotonicity: an additional guarantee (true instead of false) never worsens the verdict
    contre = []
    garanties = [v for v in variables if sig.get(v, {}).get("type") == "booleen" and sig[v].get("monde") != "ferme"]
    for v in garanties:
        i = variables.index(v)
        for valeurs, (verdict, _) in table.items():
            if valeurs[i] is True:
                faux = table[valeurs[:i] + (False,) + valeurs[i + 1:]][0]
                if rang(verdict) > rang(faux):
                    contre.append({**lisible(valeurs), "garantie": v, "avec": verdict, "sans": faux})
    if garanties:
        res.append(_resultat(f"{famille}.P3", f"Monotonie : ajouter une garantie ({', '.join(garanties)}) n'aggrave jamais le verdict",
                             "énumération exhaustive (relation métamorphique)", n * len(garanties), contre,
                             "test métamorphique (Chen et al., 2018)"))

    # P4 requirements of the formal specification (kb/specification_formelle.json)
    lieux = {}
    if famille == "partage" and "lieu" in variables:
        lieux = {l: moteur._normaliser_demande({"lieu": l})["lieu"] for l in domaines[variables.index("lieu")] if l is not None}
    for e in spec:
        contre = []
        for valeurs, (verdict, rs) in table.items():
            x = dict(zip(variables, valeurs))
            if famille == "partage" and x.get("lieu") is not None:
                x["lieu"] = lieux[x["lieu"]]   # the specification speaks of normalised values ("EAU" → dans_le_pays…)
            if not all(evaluer(c, x.get(k)) is True for k, c in e["si"].items()):
                continue
            if (("au_moins" in e and rang(verdict) < rang(e["au_moins"])) or verdict in e.get("jamais", [])
                    or ("au_plus" in e and rang(verdict) > rang(e["au_plus"]))):
                contre.append({**lisible(valeurs), "verdict": verdict})
        attendu = " et ".join(x for x in (f"au moins {e['au_moins']}" if "au_moins" in e else "",
                                          f"au plus {e['au_plus']}" if "au_plus" in e else "",
                                          f"jamais {', '.join(e['jamais'])}" if "jamais" in e else "") if x)
        res.append(_resultat(e["id"], f"{e['enonce']} ({attendu})", "énumération exhaustive", n, contre,
                             "fiches " + ", ".join(e["fiches"])))

    # P5 no dead rule: each rule applies in at least one case
    mortes = [r["id"] for r in regles if r["id"] not in regles_vues]
    res.append(_resultat(f"{famille}.P5", "Aucune règle morte : chaque règle s'applique dans au moins un cas",
                         "énumération exhaustive", len(regles), mortes, "analyse de couverture des tables de décision (DMN)"))
    return res


# ------------------------------------------------------------------ prescription
def verifier_prescription(moteur) -> list[Resultat]:
    kb = moteur.kb
    meds = list(kb["medicaments"]) + ["medicament_inconnu"]
    prescripteurs = list(kb["prescripteurs"]) + ["DR-INCONNU"]
    ages = sorted({b + d for ch in kb["champs_obligatoires_avant_prescription"] for k in ("age_min", "age_max")
                   if k in ch["si"] for b in [ch["si"][k]] for d in (-1, 0, 1)}) + [30, None]
    ages = sorted({a for a in ages if a is not None}) + [None]
    grossesses = [("inconnue", None), ("oui", True), ("oui_non_confirmee", "nc"), ("non", False)]
    dimensions = {
        "prescripteur": prescripteurs, "auteur": ["medecin", "assistant"], "medicament": meds,
        "sexe": ["F", "M", None], "age": ages, "grossesse": [g for _, g in grossesses],
        "allergies": [None, "aucune", "MEME"], "traitements": [None, "aucun"],
        "mode": ["presentiel", "distance", None], "ecrit": ["complet", "sans_dose"],
    }
    noms = list(dimensions)
    actif = lambda p: bool(kb["prescripteurs"].get(p, {}).get("humain") and kb["prescripteurs"].get(p, {}).get("actif"))  # noqa: E731
    contre = {k: [] for k in ("PR1", "PR2", "PR3", "PR4", "PR5", "PR6", "PR7", "PR8", "PR9")}
    n = 0
    cache = {}

    def etat_de(x, confirme_grossesse=True):
        e = {}
        if x["sexe"]:
            e["sexe"] = {"valeur": x["sexe"], "confirme": True}
        if x["age"] is not None:
            e["age"] = {"valeur": x["age"], "confirme": True}
        if x["grossesse"] == "nc":
            e["grossesse"] = {"valeur": True, "confirme": False}
        elif x["grossesse"] is not None:
            e["grossesse"] = {"valeur": x["grossesse"], "confirme": confirme_grossesse}
        if x["allergies"]:
            e["allergies"] = {"valeur": x["medicament"] if x["allergies"] == "MEME" else x["allergies"], "confirme": True}
        if x["traitements"]:
            e["traitements_en_cours"] = {"valeur": x["traitements"], "confirme": True}
        return e

    def juger(x, etat=None):
        dec = {"medicament": x["medicament"], "prescripteur": x["prescripteur"], "auteur": x["auteur"],
               "dose": "500 mg" if x["ecrit"] == "complet" else None, "posologie": "3 fois par jour", "mode": x["mode"]}
        return moteur.verifier_prescription(dec, etat if etat is not None else etat_de(x))

    def requis(x):
        out = []
        for ch in kb["champs_obligatoires_avant_prescription"]:
            if moteur._condition_applicable(ch["si"], {"sexe": x["sexe"], "age": x["age"]}):
                out.append(ch["champ"])
        return out

    for valeurs in itertools.product(*dimensions.values()):
        x = dict(zip(noms, valeurs))
        r = juger(x)
        v = r["verdict"]
        cache[valeurs] = v
        n += 1
        med = kb["medicaments"].get(x["medicament"])
        etat = etat_de(x)
        lis = {k: val for k, val in x.items() if val is not None}
        if v == "CONFORME":
            if not (actif(x["prescripteur"]) and x["auteur"] == "medecin"):
                contre["PR1"].append(lis)
            if not (med and med.get("amm")):
                contre["PR2"].append(lis)
            if any(not etat.get(c, {}).get("confirme") for c in requis(x)):
                contre["PR3"].append(lis)
        if med:
            for ci in med.get("contre_indications", []):
                if ci["si"] == {"grossesse": True}:
                    if x["grossesse"] is True and rang(v) < rang(ci["niveau"]):
                        contre["PR4"].append({**lis, "verdict": v, "attendu": ci["niveau"]})
                    femme_possible = x["sexe"] in ("F", None) and (x["age"] is None or 12 <= x["age"] <= 50)
                    if x["grossesse"] is None and femme_possible and v == "CONFORME":
                        contre["PR5"].append(lis)
                    if x["sexe"] == "M" and x["grossesse"] is None and any(c["regle"].startswith("contre_indication") and "grossesse" in c["regle"] for c in r["constats"]):
                        contre["PR8"].append(lis)
        if x["sexe"] == "M" and x["grossesse"] in (True, "nc"):
            if v == "CONFORME" or not any(c["regle"].startswith("incoherence") for c in r["constats"]):
                contre["PR9"].append({**lis, "verdict": v})
            if x["allergies"] == "MEME" and rang(v) < rang(kb["regle_allergie"]["niveau"]):
                contre["PR6"].append({**lis, "verdict": v})
        if x["grossesse"] == "nc":                    # confirming a piece of information must never worsen the verdict
            confirme = {**etat, "grossesse": {"valeur": True, "confirme": True}}
            vc = juger(x, confirme)["verdict"]
            if rang(vc) > rang(v):
                contre["PR7"].append({**lis, "avant": v, "apres_confirmation": vc})
    m = "énumération exhaustive"
    return [
        _resultat("prescription.PR1", "Une prescription conforme vient d'un médecin humain, autorisé et actif", m, n, contre["PR1"],
                  "contrôle humain (AI Act, art. 14)"),
        _resultat("prescription.PR2", "Une prescription conforme porte sur un médicament connu et autorisé (AMM)", m, n, contre["PR2"]),
        _resultat("prescription.PR3", "Une prescription conforme suppose les informations obligatoires connues et confirmées", m, n, contre["PR3"],
                  "fiches des champs obligatoires"),
        _resultat("prescription.PR4", "Grossesse confirmée et contre-indication : verdict au moins celui de la contre-indication", m, n, contre["PR4"]),
        _resultat("prescription.PR5", "Grossesse inconnue chez une femme qui peut être enceinte : jamais conforme avec un médicament contre-indiqué", m, n,
                  contre["PR5"], "logique de Kleene"),
        _resultat("prescription.PR6", "Allergie au médicament prescrit : verdict au moins celui de la règle d'allergie", m, n, contre["PR6"]),
        _resultat("prescription.PR7", "Confirmer une information n'aggrave jamais le verdict", m + " (relation métamorphique)", n, contre["PR7"],
                  "test métamorphique (Chen et al., 2018)"),
        _resultat("prescription.PR8", "Pas de fausse alerte : grossesse non renseignée chez un homme, aucune contre-indication liée à la grossesse",
                  m, n, contre["PR8"], "connaissances de fond (axiomes), Semantic DMN (Calvanese et al.)"),
        _resultat("prescription.PR9", "Informations contradictoires (homme noté enceint) : signalées, jamais conformes", m, n, contre["PR9"],
                  "cohérence des faits avec les axiomes"),
    ]


# ------------------------------------------------------------------ maintien nominatif
def verifier_maintien(moteur) -> list[Resultat]:
    statuts = NIVEAUX + ["MAINTENUE", "annulee", "a_verifier", AUTRE]
    medecins = list(moteur.kb["prescripteurs"]) + ["DR-INCONNU", "", None]
    justifs = ["", "   ", "Bénéfice supérieur au risque, patiente informée."]
    contre1, contre2, n = [], [], 0
    for s, m, j in itertools.product(statuts, medecins, justifs):
        n += 1
        ok, _ = moteur.autoriser_maintien(s, m, j)
        p = moteur.kb["prescripteurs"].get(m) or {}
        if s == "BLOQUE" and ok:
            contre1.append({"statut": s, "medecin": m, "justification": j})
        if ok and not (s == "A_REVOIR" and p.get("humain") and p.get("actif") and j.strip()):
            contre2.append({"statut": s, "medecin": m, "justification": j})
    return [
        _resultat("maintien.MA1", "Une décision bloquée ne peut jamais être maintenue", "énumération exhaustive", n, contre1,
                  "hiérarchie des normes"),
        _resultat("maintien.MA2", "Un maintien exige une décision « à revoir », un médecin autorisé et actif, et une justification écrite",
                  "énumération exhaustive", n, contre2, "contrôle humain (AI Act, art. 14)"),
    ]


def verifier_tout(moteur) -> list[Resultat]:
    return [*bonne_formation(moteur), *verifier_famille(moteur, "partage"), *verifier_famille(moteur, "envoi_patient"),
            *verifier_prescription(moteur), *verifier_maintien(moteur)]
