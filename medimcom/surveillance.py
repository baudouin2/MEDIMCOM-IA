"""Runtime verification: a monitor rereads the hash-chained journal and checks safety properties written in
past-time temporal logic ("whenever X happens, Y has happened before").

The monitor is independent of the agents: it trusts none of them and only reads the journal, which is
tamper-evident. It is used three times: in tests (scenarios), in automatic exploration (medimcom/exploration.py)
and afterwards on any journal (python outils/verifier_formel.py --journal sortie/journal.json).

References: Leucker & Schallhart, "A brief account of runtime verification", J. Logic and Algebraic
Programming 78(5), 2009; Havelund & Roşu, past-time temporal logic for monitoring.
"""
from .regles import NON_VERDICTS, ORDRE

PROPRIETES = {
    "R1": "Aucun message n'atteint le patient sans avoir été validé avant par un médecin humain, autorisé et actif.",
    "R2": "Aucun message n'atteint le patient sans un verdict « conforme » du juriste, rendu après la validation.",
    "R3": "Un message de traitement n'atteint le patient que si la prescription expliquée est conforme ou maintenue.",
    "R4": "Seule une décision « à revoir » peut être maintenue, par un médecin autorisé et actif, avec une justification écrite.",
    "R5": "Chaque verdict enregistré est le plus strict de ses constats, et chaque constat restrictif cite au moins une fiche.",
    "R6": "Toute décision soumise (prescription, partage, message validé) a reçu au moins un verdict du juriste.",
    "R7": "Le journal est intact (chaîne d'empreintes SHA-256).",
    "R9": "Un maintien ne couvre que les motifs « à revoir » examinés par le médecin : un nouveau motif exige un nouveau maintien.",
    "R10": "Le cycle de vie de chaque décision suit la machine à états spécifiée (aucune transition interdite).",
    "R8": "Le juriste ne juge « conforme » un message au patient que si une validation par un médecin autorisé a été enregistrée avant.",
}


# State machine of a decision's life cycle (specification). Key: current status; value: statuses allowed next.
VERDICTS = {"CONFORME", "PREUVES_INSUFFISANTES", "A_REVOIR", "BLOQUE"}
TRANSITIONS = {
    None: {"a_verifier", "attente_validation"},
    "attente_validation": {"a_verifier", "rejete", "annulee", "BLOQUE"},  # validation, rejection, or content block
                                                                          # by the jurist's pre-check
    "a_verifier": VERDICTS | {"annulee"},                                 # jurist's check
    **{v: VERDICTS | {"annulee"} for v in VERDICTS},                      # new check after a change of state
    "A_REVOIR": VERDICTS | {"annulee", "MAINTENUE"},                      # only "to review" can be overridden
    "CONFORME": VERDICTS | {"annulee", "envoye", "MAINTENUE"},            # only a compliant message is sent; an override
                                                                          # still valid resumes if "to review" comes back
    "MAINTENUE": VERDICTS | {"MAINTENUE", "annulee"},
    "envoye": {"retire"},                                                 # the doctor can remove a sent message
    "retire": set(), "rejete": set(), "annulee": set(),                   # terminal states
}


def surveiller(journal, regles) -> dict:
    """Replays the journal and returns {property: [violations]}. regles: MoteurRegles (list of prescribers)."""
    autorise = lambda p: bool((regles.kb["prescripteurs"].get(p) or {}).get("humain") and  # noqa: E731
                              (regles.kb["prescripteurs"].get(p) or {}).get("actif"))
    v = {k: [] for k in PROPRIETES}
    decisions, validations, derniers_verdicts, maintiens = {}, {}, {}, {}
    couverts = {}          # decision -> "to review" reasons covered by a still-valid override (None: none)
    statut = {}

    def passer(i, nouveau, n, cause):
        ancien = statut.get(i)
        if nouveau not in TRANSITIONS.get(ancien, set()):
            v["R10"].append(f"ligne {n} : décision #{i} {ancien} → {nouveau} ({cause}) : transition interdite")
        statut[i] = nouveau
    annulees, rejetees = set(), set()
    for ligne in journal.lignes:
        t, c, n = ligne["type"], ligne["contenu"], ligne["n"]
        if t == "decision":
            decisions[c["id"]] = c
            passer(c["id"], c.get("statut"), n, "création")
        elif t == "validation":
            validations[c["id"]] = (n, c.get("valide_par"))
            passer(c["id"], "a_verifier", n, "validation")
        elif t == "decision_annulee":
            annulees.add(c["id"])
            passer(c["id"], "annulee", n, "annulation")
        elif t == "rejet":
            rejetees.add(c["id"])
            passer(c["id"], "rejete", n, "rejet")
        elif t == "message_retire":
            passer(c["id"], "retire", n, "retrait par le médecin")
        elif t == "verdict":
            niveaux = [k["niveau"] for k in c.get("constats", []) if k["niveau"] not in NON_VERDICTS]
            attendu = max(["CONFORME", *niveaux], key=lambda x: ORDRE[x])
            if c["verdict"] != attendu and ORDRE[c["verdict"]] < ORDRE[attendu]:
                v["R5"].append(f"ligne {n} : verdict {c['verdict']} moins strict que ses constats ({attendu})")
            for k in c.get("constats", []):
                if k["niveau"] in ("PREUVES_INSUFFISANTES", "A_REVOIR", "BLOQUE") and not k.get("fiches"):
                    v["R5"].append(f"ligne {n} : constat {k['regle']} sans fiche")
            if c.get("decision_id") is not None:
                i = c["decision_id"]
                derniers_verdicts[i] = (n, c["verdict"])
                motifs = {k["regle"] for k in c.get("constats", []) if k["niveau"] == "A_REVOIR"}
                if couverts.get(i) is not None and not (c["verdict"] in ("A_REVOIR", "CONFORME") and motifs <= couverts[i]):
                    couverts[i] = None              # verdict worsened or new reason: the override no longer holds
                if c.get("statut_decision"):
                    passer(i, c["statut_decision"], n, "verdict")
                if c.get("statut_decision") == "MAINTENUE" and couverts.get(i) is None:
                    v["R9"].append(f"ligne {n} : décision #{i} restée « maintenue » malgré un verdict {c['verdict']} "
                                   f"(motifs {sorted(motifs)})")
                d = decisions.get(c["decision_id"], {})
                val = validations.get(c["decision_id"])
                if d.get("type") == "envoi_patient" and c["verdict"] == "CONFORME" and not (val and autorise(val[1])):
                    v["R8"].append(f"ligne {n} : message #{c['decision_id']} jugé conforme sans validation enregistrée "
                                   f"(valide_par déclaré : {d.get('valide_par')})")
        elif t == "maintien":
            dv = derniers_verdicts.get(c["id"], (0, None))[1]
            if dv != "A_REVOIR" or not autorise(c.get("par")) or not str(c.get("justification", "")).strip():
                v["R4"].append(f"ligne {n} : décision #{c['id']} maintenue (dernier verdict {dv}, par {c.get('par')})")
            maintiens[c["id"]] = n
            couverts[c["id"]] = set(c.get("motifs") or [])
            passer(c["id"], "MAINTENUE", n, "maintien")
        elif t == "envoye_au_patient":
            i = c["id"]
            passer(i, "envoye", n, "envoi")
            val = validations.get(i)
            if not val or not autorise(val[1]) or val[1] != c.get("valide_par"):
                v["R1"].append(f"ligne {n} : message #{i} envoyé sans validation d'un médecin autorisé (validation : {val})")
            dv = derniers_verdicts.get(i)
            if not dv or dv[1] != "CONFORME" or (val and dv[0] < val[0]):
                v["R2"].append(f"ligne {n} : message #{i} envoyé sans verdict conforme postérieur à la validation ({dv})")
            d = decisions.get(i, {})
            if d.get("contenu_type") == "traitement":
                p = d.get("source_prescription")
                pv = derniers_verdicts.get(p, (0, None))
                ok = pv[1] == "CONFORME" or (pv[1] == "A_REVOIR" and couverts.get(p) is not None)
                if p is None or not ok or p in annulees:
                    v["R3"].append(f"ligne {n} : traitement #{i} envoyé ; prescription liée #{p} : {pv[1]}")
    for i, d in decisions.items():
        soumise = d.get("type") in ("prescription", "partage_donnees") or i in validations
        if soumise and i not in annulees and i not in rejetees and i not in derniers_verdicts:
            v["R6"].append(f"décision #{i} ({d.get('type')}) jamais contrôlée par le juriste")
    etat = journal.verifier()
    if etat != "Journal intact":
        v["R7"].append(etat)
    return v


def resume(violations: dict) -> str:
    ko = {k: x for k, x in violations.items() if x}
    if not ko:
        return f"{len(violations)} propriétés vérifiées : aucune violation."
    return "; ".join(f"{k} : {len(x)} violation(s) ({x[0]})" for k, x in ko.items())
