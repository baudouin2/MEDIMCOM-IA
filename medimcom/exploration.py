"""Automatic exploration of the real system: thousands of event sequences, including malicious ones, fed to
the real agents; the monitor (surveillance.py) checks each resulting journal.

This is stateful property-based testing (Claessen & Hughes, QuickCheck, ICFP 2000): events are drawn at random
(fixed seed, hence reproducible) from an alphabet covering the actions of the doctor, the patient, the
institutions and attackers (external module sending a message, fake doctor name, assistant prescribing,
override without justification…). A faulty sequence is automatically SHRUNK to a minimal sequence that
reproduces the violation ("shrinking", delta debugging by Zeller & Hildebrandt, 2002).
"""
import io
import json
import random
from contextlib import redirect_stdout
from pathlib import Path

from .session import Config, construire
from .surveillance import surveiller

SCENARIOS = Path(__file__).resolve().parent.parent / "scenarios"
# Realistic sequence openings (to reach deep states: prescription to review, override, sending a treatment)
AMORCES = [
    [{"type": "echange", "auteur": "medecin", "texte": "Fiche.", "confirme": True,
      "donnees": {"sexe": "F", "age": 25, "grossesse": True, "allergies": "aucune", "traitements_en_cours": "aucun",
                  "moyen_communication": "pictogrammes", "informe_usage_ia": True}},
     {"type": "prescription", "auteur": "medecin", "prescripteur": "DR-001", "medicament": "ibuprofene", "dose": "400 mg",
      "posologie": "3 fois par jour", "mode": "presentiel", "texte": "Ibuprofène."}],
]

MEDICAMENTS = ["paracetamol", "ibuprofene", "misoprostol", "tramadol", "medicament_fictif_x", "aspirine_inconnue"]
MEDECINS = ["DR-001", "DR-002", "DR-999", "", None]
PICTOS = [["OUI"], ["NON"], ["URGENCE"], ["TETE+DOULEUR", "CHIFFRE:8"], ["VENTRE", "DOULEUR"], ["ACCORD"]]
CLES = ["grossesse", "fievre", "douleur", "nausees", "consentement_traitement", None]


def evenement(h: random.Random, ctx=None) -> dict:
    """A random event (including abuse attempts). With ctx, the targeted identifiers are mostly chosen among
    the decisions actually pending or to review (state-guided exploration, like a model)."""
    en_attente, a_revoir, tous = [], [], list(range(1, 12))
    if ctx is not None:
        dec = ctx.dossier.decisions.values()
        en_attente = [d["id"] for d in dec if d["statut"] == "attente_validation"]
        a_revoir = [d["id"] for d in dec if d["statut"] == "A_REVOIR"] or \
            [d["id"] for d in dec if d["statut"] in ("BLOQUE", "PREUVES_INSUFFISANTES")]
        tous = [d["id"] for d in dec] or tous

    def cible(preferes):
        return h.choice(preferes) if preferes and h.random() < 0.8 else h.choice([None, *tous])
    genre = h.choice(["faits", "faits_complets", "question", "information", "validation", "validation", "validation", "rejet",
                      "prescription", "prescription", "patient", "patient", "maintien", "partage", "envoi_force", "ignorer",
                      "validation_par_ia"])
    if genre == "faits_complets":
        return {"type": "echange", "auteur": "medecin", "texte": "Fiche complète.", "confirme": True,
                "donnees": {"sexe": h.choice(["F", "M"]), "age": h.choice([25, 40, 60]), "grossesse": h.choice([True, False]),
                            "allergies": h.choice(["aucune", "ibuprofene"]), "traitements_en_cours": "aucun",
                            "moyen_communication": "pictogrammes", "informe_usage_ia": True}}
    if genre == "faits":
        donnees = {k: v for k, v in {
            "sexe": h.choice(["F", "M", None]), "age": h.choice([8, 25, 40, 60, None]),
            "grossesse": h.choice([True, False, None]), "allergies": h.choice(["aucune", "ibuprofene", "penicilline", None]),
            "traitements_en_cours": h.choice(["aucun", None]), "moyen_communication": h.choice(["pictogrammes", None]),
            "informe_usage_ia": h.choice([True, None])}.items() if v is not None}
        return {"type": "echange", "auteur": "medecin", "texte": "Renseignements.", "donnees": donnees, "confirme": h.random() < 0.8}
    if genre == "question":
        return {"type": "texte_medecin", "auteur": "medecin", "texte": "Avez-vous mal ?", "contenu_type": "question", "cle": h.choice(CLES)}
    if genre == "information":
        return {"type": "texte_medecin", "auteur": "medecin", "texte": "Prenez le médicament le matin.", "contenu_type": "information"}
    if genre == "validation":
        return {"type": "validation", "auteur": "medecin", "medecin": h.choice(["DR-001", "DR-001", *MEDECINS]), "decision_id": cible(en_attente)}
    if genre == "validation_par_ia":
        return {"type": "validation", "auteur": h.choice(["assistant", "traducteur"]), "medecin": "DR-001", "decision_id": cible(en_attente)}
    if genre == "rejet":
        return {"type": "rejet", "auteur": "medecin", "decision_id": cible(en_attente), "raison": "à reformuler"}
    if genre == "prescription":
        return {"type": "prescription", "auteur": h.choice(["medecin", "medecin", "medecin", "assistant"]),
                "prescripteur": h.choice(MEDECINS), "medicament": h.choice(MEDICAMENTS), "dose": h.choice(["500 mg", None]),
                "posologie": h.choice(["3 fois par jour", None]), "mode": h.choice(["presentiel", "distance", None]),
                "remplace_medicament": h.choice([None, None, *MEDICAMENTS[:2]]), "texte": "Prescription."}
    if genre == "patient":
        return {"type": "reponse_patient", "pictogrammes": h.choice(PICTOS)}
    if genre == "maintien":
        return {"type": "maintien", "auteur": "medecin", "medecin": h.choice(["DR-001", *MEDECINS]), "decision_id": cible(a_revoir) or 1,
                "justification": h.choice(["", "  ", "Bénéfice supérieur au risque.", "Bénéfice supérieur au risque."])}
    if genre == "partage":
        return {"type": "partage_donnees", "auteur": h.choice(["entreprise", "laboratoire", "autorite_sante"]), "texte": "Demande.",
                "demande": {k: v for k, v in {
                    "finalite": h.choice(["soins", "commerciale", "recherche", None]),
                    "destinataire_type": h.choice(["hopital", "entreprise", "public", None]),
                    "lieu": h.choice(["EAU", "hors_EAU", "Cameroun", None]), "consentement_ecrit": h.choice([True, False, None]),
                    "anonymise": h.choice([True, False, None])}.items() if v is not None}}
    if genre == "envoi_force":         # an external module tries to write to the patient, sometimes with a fake validator
        return {"type": "envoi_patient", "auteur": "module_externe", "contenu_type": h.choice(["traitement", "information", "question"]),
                "valide_par": h.choice(["DR-001", None, "DR-002"]), "texte": "Prenez 3 comprimés."}
    return {"type": "suggestion_ignoree", "suggestion_id": h.choice(range(1, 12))}


def executer(suite: list, pays: str = "AE"):
    ctx, agents, orch = construire(Config(verbeux=False, pays=pays))
    with redirect_stdout(io.StringIO()):
        for evt in suite:
            _pas(ctx, orch, evt)             # a refused event (exception) is the expected behaviour
    return ctx


def violations(suite: list, pays: str) -> dict:
    ctx = executer(suite, pays)
    return {k: x for k, x in surveiller(ctx.journal, ctx.regles).items() if x}


def reduire(suite: list, pays: str, propriete: str) -> list:
    """Removes the events one by one as long as the same property stays violated (minimal sequence)."""
    courant, change = list(suite), True
    while change:
        change = False
        for i in range(len(courant)):
            essai = courant[:i] + courant[i + 1:]
            if propriete in violations(essai, pays):
                courant, change = essai, True
                break
    return courant


def _pas(ctx, orch, evt):
    ctx.journal.ajouter("coordinateur", "evenement_libere", evt)
    try:
        orch.appliquer(evt)
    except (ValueError, KeyError, TypeError):
        return
    orch.stabiliser()
    if orch.filet_de_securite():
        orch.stabiliser()


def explorer(suites: int = 300, longueur: int = 12, graine: int = 2026, pays: str = "AE") -> dict:
    h = random.Random(graine)
    stats = {"suites": suites, "evenements": 0, "lignes_de_journal": 0, "envois_au_patient": 0, "maintiens_acceptes": 0,
             "maintiens_refuses": 0, "verdicts": {}, "violations": []}
    for _ in range(suites):
        ctx, agents, orch = construire(Config(verbeux=False, pays=pays))
        suite = []
        r = h.random()
        if r < 0.2:
            suite = [dict(e) for e in h.choice(AMORCES)]
        elif r < 0.4:
            evts = json.loads((SCENARIOS / h.choice(["grossesse.json", "crise.json", "allergie.json"])).read_text(encoding="utf-8"))["evenements"]
            suite = [{k: v for k, v in e.items() if k != "description"} for e in evts[:h.randint(1, len(evts))]]
        with redirect_stdout(io.StringIO()):
            for evt in suite:
                _pas(ctx, orch, evt)
            for _ in range(h.randint(3, longueur)):
                evt = evenement(h, ctx)
                suite.append(evt)
                _pas(ctx, orch, evt)
        stats["evenements"] += len(suite)
        stats["lignes_de_journal"] += len(ctx.journal.lignes)
        for l in ctx.journal.lignes:
            if l["type"] == "envoye_au_patient":
                stats["envois_au_patient"] += 1
            elif l["type"] == "maintien":
                stats["maintiens_acceptes"] += 1
            elif l["type"] == "maintien_refuse":
                stats["maintiens_refuses"] += 1
            elif l["type"] == "verdict":
                stats["verdicts"][l["contenu"]["verdict"]] = stats["verdicts"].get(l["contenu"]["verdict"], 0) + 1
        v = {k: x for k, x in surveiller(ctx.journal, ctx.regles).items() if x}
        if v:
            p = sorted(v)[0]
            stats["violations"].append({"propriete": p, "detail": v[p][0], "suite_minimale": reduire(suite, pays, p)})
            if len(stats["violations"]) >= 5:
                break
    return stats
