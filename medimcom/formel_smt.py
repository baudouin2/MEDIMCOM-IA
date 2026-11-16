"""Proofs by SMT solver (Z3): a second verification, independent of the engine's code.

The declarative families (data sharing, sending to the patient) are translated DIRECTLY from the JSON rules file
into logical formulas, following the semantics written in docs/technique/METHODES_FORMELLES.md (Kleene three-valued
logic, open or closed world depending on the signature, verdict = maximum in the lattice, default refusal). The
solver looks for an input that would violate each property, among ALL possible strings and booleans (unbounded
domain): "unsatisfiable" is a proof; otherwise it gives a counter-example. This is the approach of Zelkova for
AWS access policies (Backes et al., FMCAD 2018).

Modelling assumption: inputs are already normalised (lower case, no accents), as the engine does.
The agreement between this encoding and the real engine is checked on a sample (cross-validation).
Optional dependency: pip install z3-solver.
"""
import itertools
import random

from .formel import AUTRE, NIVEAUX, _entrees, _resultat, _spec
from .regles import RESTRICTIFS, normaliser

try:
    import z3
except ImportError:          # the enumeration check (formel.py) remains available
    z3 = None

RANG = {n: i for i, n in enumerate(NIVEAUX)}
FAMILLES = {"partage": "regles_partage", "envoi_patient": "regles_envoi_patient"}


def disponible() -> bool:
    return z3 is not None


class Encodage:
    """Z3 variables of a family: for each variable, "known" (Bool) and "value" (according to its type)."""

    def __init__(self, sig: dict, suffixe: str = ""):
        self.sig, self.v, self.connue = sig, {}, {}
        for nom, t in sig.items():
            self.connue[nom] = z3.Bool(f"{nom}_connue{suffixe}")
            sorte = {"booleen": z3.BoolSort(), "nombre": z3.IntSort()}.get(t["type"], z3.StringSort())
            self.v[nom] = z3.Const(f"{nom}{suffixe}", sorte)

    def contraintes(self) -> list:
        """A known value is never empty (the engine treats an empty string as a missing value)."""
        return [z3.Implies(self.connue[n], self.v[n] != z3.StringVal("")) for n, t in self.sig.items()
                if t["type"] not in ("booleen", "nombre")]

    def copie_sauf(self, var: str, suffixe: str) -> "Encodage":
        e = Encodage.__new__(Encodage)
        e.sig, e.v, e.connue = self.sig, dict(self.v), dict(self.connue)
        t = self.sig[var]
        e.connue[var] = z3.Bool(f"{var}_connue{suffixe}")
        sorte = {"booleen": z3.BoolSort(), "nombre": z3.IntSort()}.get(t["type"], z3.StringSort())
        e.v[var] = z3.Const(f"{var}{suffixe}", sorte)
        return e


def _const(x):
    if isinstance(x, bool):
        return z3.BoolVal(x)
    if isinstance(x, int):
        return z3.IntVal(x)
    return z3.StringVal(str(x))


def condition(e: Encodage, var: str, cond, ferme: bool):
    """(T, U): the condition is true / unknown (otherwise false)."""
    k, v = e.connue[var], e.v[var]
    faux = z3.BoolVal(False)
    if isinstance(cond, dict):
        op, arg = next(iter(cond.items()))
        if op == "absent":
            return (z3.Not(k) if arg else k), faux
        if op == "present":
            return (k if arg else z3.Not(k)), faux
        if op == "pas":
            return z3.Not(z3.And(k, v == _const(arg))), faux
        if op == "dans":
            t = z3.Or(*[v == _const(a) for a in arg]) if arg else faux
        elif op == "hors":
            t = z3.And(*[v != _const(a) for a in arg]) if arg else z3.BoolVal(True)
        elif op == "contient":
            t = z3.Contains(v, z3.StringVal(normaliser(arg)))
        elif op == "inferieur_a":
            t = v < arg
        elif op == "superieur_a":
            t = v > arg
        else:
            raise ValueError(op)
    else:
        t = v == _const(cond)
    return z3.And(k, t), (faux if ferme else z3.Not(k))


def _max(a, b):
    return z3.If(a >= b, a, b)


def verdict(e: Encodage, moteur, famille: str):
    """Rank of the verdict (0 = CONFORME … 3 = BLOQUE) and auxiliary formulas (triggered rules)."""
    regles = moteur.kb[FAMILLES[famille]]
    fermees = {k for k, t in e.sig.items() if t.get("monde") == "ferme"}
    T, P, Ucond = {}, {}, {}
    for r in regles:
        paires = {k: condition(e, k, c, k in fermees) for k, c in r["si"].items()}
        t = z3.And(*[p[0] for p in paires.values()]) if paires else z3.BoolVal(True)
        non_faux = z3.And(*[z3.Or(p[0], p[1]) for p in paires.values()]) if paires else z3.BoolVal(True)
        u = z3.And(z3.Not(t), non_faux, z3.Or(*[p[1] for p in paires.values()])) if paires else z3.BoolVal(False)
        T[r["id"]], Ucond[r["id"]] = t, {k: p[1] for k, p in paires.items()}
        P[r["id"]] = u if r["niveau"] in RESTRICTIFS else z3.BoolVal(False)
    # coverage: a rule triggered by the absence of information (level >= insufficient evidence)
    couvre = {}
    for r in regles:
        if r["niveau"] in RESTRICTIFS | {"PREUVES_INSUFFISANTES"}:
            for k, c in r["si"].items():
                if c == {"absent": True}:
                    couvre.setdefault(k, []).append(T[r["id"]])
    rang = z3.IntVal(0)
    une_regle = []
    for r in regles:
        if r["niveau"] in RANG:
            rang = _max(rang, z3.If(T[r["id"]], RANG[r["niveau"]], 0))
            une_regle.append(T[r["id"]])
        if r["niveau"] in RESTRICTIFS:
            garde = z3.Or(*[z3.And(u, z3.Not(z3.Or(*couvre.get(k, [z3.BoolVal(False)])))) for k, u in Ucond[r["id"]].items()])
            p = z3.And(P[r["id"]], garde)
            rang = _max(rang, z3.If(p, RANG["PREUVES_INSUFFISANTES"], 0))
            une_regle.append(p)
    if famille == "partage":
        defaut = RANG[moteur.kb["regle_partage_non_couvert"]["niveau"]]
        rang = _max(rang, z3.If(z3.Or(*une_regle), 0, defaut))
    return rang, T


def _lieu_brut(e: Encodage, moteur):
    """The engine translates place names ("eau", "cameroun"…): this table is encoded, on the raw input."""
    table = {**moteur.LIEUX, **{normaliser(k): v for k, v in moteur.kb.get("lieux", {}).items()}}
    brut = z3.String("lieu_brut")
    expr = brut
    for k, v in table.items():
        expr = z3.If(brut == z3.StringVal(k), z3.StringVal(v), expr)
    return brut, expr


def _contre_exemple(modele, e: Encodage, extra=None) -> dict:
    out = {}
    for nom in e.sig:
        k = modele.eval(e.connue[nom], model_completion=True)
        if z3.is_true(k):
            out[nom] = str(modele.eval(e.v[nom], model_completion=True)).strip('"')
    return {**out, **(extra or {})}


def prouver(moteur, famille: str, rapide: bool = False) -> list:
    if z3 is None:
        return []
    sig = moteur.kb.get("signature", {}).get(famille, {})
    regles, spec = moteur.kb[FAMILLES[famille]], _spec(moteur.pays, famille)
    res = []

    def nouveau(suffixe=""):
        e = Encodage(sig, suffixe)
        s = z3.Solver()
        s.add(*e.contraintes())
        if famille == "partage" and "lieu" in sig:       # the place goes through the engine's translation table
            brut, traduit = _lieu_brut(e, moteur)
            s.add(e.v["lieu"] == traduit)
        return e, s
    meth = "preuve SMT (Z3), domaine non borné"

    # P1 default refusal
    e, s = nouveau()
    rang, T = verdict(e, moteur, famille)
    s.add(rang == 0, *[z3.Not(T[r["id"]]) for r in regles if r["niveau"] == "CONFORME"])
    contre = [_contre_exemple(s.model(), e)] if s.check() == z3.sat else []
    res.append(_resultat(f"{famille}.P1", "Refus par défaut (preuve)", meth, "∞", contre, "Backes et al., FMCAD 2018"))

    # P2 caution, P3 monotonicity: two copies of the inputs that differ only by one variable
    contre_p2, contre_p3 = [], []
    for var, t in ([] if rapide else sig.items()):
        e, s = nouveau()
        f = e.copie_sauf(var, "_bis")
        s.add(*f.contraintes())
        r1, _ = verdict(e, moteur, famille)
        r2, _ = verdict(f, moteur, famille)
        if t.get("monde") != "ferme":
            s.push()
            s.add(z3.Not(e.connue[var]), f.connue[var], r1 == 0, r2 > 0)
            if s.check() == z3.sat:
                contre_p2.append(_contre_exemple(s.model(), e, {"inconnue": var, "si_connue": str(s.model().eval(f.v[var]))}))
            s.pop()
            if t["type"] == "booleen":
                s.add(e.connue[var], e.v[var] == True, f.connue[var], f.v[var] == False, r1 > r2)  # noqa: E712
                if s.check() == z3.sat:
                    contre_p3.append(_contre_exemple(s.model(), e, {"garantie": var}))
    if not rapide:
        res.append(_resultat(f"{famille}.P2", "Prudence face à l'inconnu (preuve)", meth, "∞", contre_p2, "logique de Kleene"))
    if not rapide and any(t["type"] == "booleen" and t.get("monde") != "ferme" for t in sig.values()):
        res.append(_resultat(f"{famille}.P3", "Monotonie des garanties (preuve)", meth, "∞", contre_p3, "Chen et al., 2018"))

    # requirements of the specification
    for x in spec:
        e, s = nouveau()
        rang, _ = verdict(e, moteur, famille)
        conds = [condition(e, k, c, False)[0] for k, c in x["si"].items()]
        viol = [rang < RANG[x["au_moins"]]] if "au_moins" in x else []
        viol += [rang == RANG[n] for n in x.get("jamais", [])]
        viol += [rang > RANG[x["au_plus"]]] if "au_plus" in x else []
        s.add(*conds, z3.Or(*viol))
        contre = [_contre_exemple(s.model(), e)] if s.check() == z3.sat else []
        res.append(_resultat(f"{x['id']} (SMT)", x["enonce"], meth, "∞", contre, "fiches " + ", ".join(x["fiches"])))
    return res


def validation_croisee(moteur, famille: str, n: int = 400, graine: int = 7):
    """Do the Z3 encoding and the real engine give the same verdict? (sample of the abstract domain)"""
    if z3 is None:
        return None
    from .formel import NIVEAUX as N
    regles, spec = moteur.kb[FAMILLES[famille]], _spec(moteur.pays, famille)
    variables, domaines, sig = _entrees(moteur, famille, regles, spec)
    hasard = random.Random(graine)
    tous = list(itertools.product(*domaines))
    echantillon = tous if len(tous) <= n else hasard.sample(tous, n)
    e = Encodage(sig)
    rang, _ = verdict(e, moteur, famille)
    brut = traduit = None
    if famille == "partage" and "lieu" in sig:
        brut, traduit = _lieu_brut(e, moteur)
    desaccords = []
    for valeurs in echantillon:
        x = dict(zip(variables, valeurs))
        if famille == "partage":
            attendu = moteur.verifier_partage_donnees({k: v for k, v in x.items() if v is not None})["verdict"]
        else:
            attendu = moteur._resultat("x", moteur._appliquer(regles, x, "envoi_patient"), {})["verdict"]
        subs = []
        for k in sig:
            val = x.get(k)
            subs.append((e.connue[k], z3.BoolVal(val is not None and val != "")))
            if val is not None and val != "":
                if k == "lieu" and brut is not None:
                    subs.append((brut, z3.StringVal(normaliser(val))))
                    continue
                normalise = famille == "partage" and k in ("finalite", "destinataire_type")   # like the engine
                c = val if isinstance(val, (bool, int)) else "zz_autre" if val == AUTRE else normaliser(val) if normalise else val
                subs.append((e.v[k], _const(c)))
            elif k == "lieu" and brut is not None:
                subs.append((brut, z3.StringVal("")))
        expr = rang
        if brut is not None:
            expr = z3.substitute(expr, (e.v["lieu"], traduit))
        obtenu = N[z3.simplify(z3.substitute(expr, *subs)).as_long()]
        if obtenu != attendu:
            desaccords.append({**{k: v for k, v in x.items() if v is not None}, "moteur": attendu, "z3": obtenu})
    return _resultat(f"{famille}.X", "Validation croisée : l'encodage logique et le moteur réel rendent le même verdict",
                     f"comparaison sur {len(echantillon)} entrées", len(echantillon), desaccords, "N-version / double implémentation")


def analyse_mutations(moteur, famille: str, avec_prudence: bool = False) -> dict:
    """Mutation analysis (DeMillo et al., 1978; Jia & Harman, 2011): faults are deliberately introduced into the
    rules (rule removed, level weakened by one step, condition removed) and we check that the specification detects
    them. A "surviving" mutant points either to a redundant rule (its effect is already guaranteed by the semantics
    or by another rule), or to a behaviour the specification does not fix."""
    import copy
    if z3 is None:
        return {}
    cle = FAMILLES[famille]
    regles = moteur.kb[cle]
    mutants = []
    for i, r in enumerate(regles):
        mutants.append((f"{r['id']} supprimée", lambda kb, i=i: kb[cle].pop(i)))
        if r["niveau"] in RANG and RANG[r["niveau"]] > 0:
            plus_faible = NIVEAUX[RANG[r["niveau"]] - 1]
            mutants.append((f"{r['id']} : {r['niveau']} → {plus_faible}",
                            lambda kb, i=i, n=plus_faible: kb[cle][i].__setitem__("niveau", n)))
        if r["niveau"] == "CONFORME":
            for k in r["si"]:
                mutants.append((f"{r['id']} : condition « {k} » retirée", lambda kb, i=i, k=k: kb[cle][i]["si"].pop(k)))
    tues, survivants = 0, []
    for nom, muter in mutants:
        m = copy.copy(moteur)
        m.kb = copy.deepcopy(moteur.kb)
        muter(m.kb)
        if any(not r["ok"] for r in prouver(m, famille, rapide=not avec_prudence)):
            tues += 1
        else:
            survivants.append(nom)
    return {"famille": famille, "mutants": len(mutants), "tues": tues, "survivants": survivants,
            "score": round(100 * tues / max(len(mutants), 1))}
