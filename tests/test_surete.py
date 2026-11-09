"""Content of messages to the patient: a dangerous message or a medicine instruction without prescription is blocked
by the jurist AS SOON AS it is proposed, before the doctor can validate it; nothing reaches the patient."""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "interface"))
from medimcom.regles import MoteurRegles  # noqa: E402
from medimcom.session import Config  # noqa: E402
from medimcom.surete import analyser_message  # noqa: E402
from serveur import Application  # noqa: E402

MEDS = json.loads((RACINE / "kb" / "regles_uae.json").read_text(encoding="utf-8"))["medicaments"]


def test_lecture_du_contenu():
    assert analyser_message("va te pendre", MEDS)["incitation_au_mal"]
    assert analyser_message("Pends-toi", MEDS)["incitation_au_mal"]
    a = analyser_message("boire tramadol", MEDS)
    assert a["consigne_medicament"] and a["medicament"] == "tramadol" and a["medicament_controle"]
    assert analyser_message("Prenez 2 comprimés de paracétamol 3 fois par jour", MEDS)["consigne_medicament"]
    for permis in ("Prenez-vous du tramadol ?", "Ne prenez pas d'ibuprofène", "Prenez le comprimé après le repas",
                   "Le paracétamol peut donner des nausées", "Avez-vous mal au ventre ?", "Allez vous reposer",
                   "Buvez beaucoup d'eau", "Lavez-vous les mains sales"):
        a = analyser_message(permis, MEDS)
        assert not a["incitation_au_mal"] and not a["consigne_medicament"], permis


def _app():
    return Application(Config(verbeux=False, base="aucune"), asynchrone=False)


def test_bloque_avant_validation_et_rien_ne_part():
    app = _app()
    for texte in ("prend du tramadol", "va te pendre", "Avez-vous mal ?"):
        app.evenement({"type": "texte_medecin", "auteur": "medecin", "texte": texte, "contenu_type": "question"})
    decs = {d["texte"]: d for d in app.ctx.dossier.decisions.values() if d.get("type") == "envoi_patient"}
    for texte in ("prend du tramadol", "va te pendre"):
        d = decs[texte]
        assert d["statut"] == "BLOQUE" and d["precontrole"]["verdict"] == "BLOQUE", texte
        retour = app.evenement({"type": "validation", "auteur": "medecin", "medecin": "DR-001", "decision_id": d["id"]})
        assert "Refusé" in retour and d["statut"] == "BLOQUE"
    regles = {c["regle"] for c in decs["prend du tramadol"]["precontrole"]["constats"]}
    assert {"ENVOI-PRODUIT-CONTROLE", "ENVOI-TRAITEMENT-SANS-PRESCRIPTION"} <= regles
    assert decs["va te pendre"]["precontrole"]["constats"][0]["regle"] == "ENVOI-PROPOS-DANGEREUX"
    app.evenement({"type": "validation", "auteur": "medecin", "medecin": "DR-001", "decision_id": decs["Avez-vous mal ?"]["id"]})
    assert [m["texte"] for m in app.vue_patient()["messages"]] == ["Avez-vous mal ?"], "un message dangereux est arrivé au patient"
    alertes = [m.contenu for m in app.ctx.messagerie.historique if m.a == "medecin" and m.de == "juriste" and m.type == "alerte"]
    assert any("va te pendre" in a and "BLOQUÉ" in a and "Piste conforme" in a for a in alertes)
    assert any(v.get("precontrole") and v["verdict"] == "BLOQUE" for v in app.ctx.dossier.verdicts), "verdict absent du journal"


def test_garde_fou_de_surete_au_cameroun():
    m = MoteurRegles(RACINE / "kb" / "regles_cm.json")
    r = m.verifier_envoi_patient({"texte": "va te pendre", "contenu_type": "information", "valide_par": "DR-001"})
    assert r["verdict"] == "BLOQUE" and r["constats"][-1]["base"] == "SURETE"
    r = m.verifier_envoi_patient({"texte": "Avez-vous de la fièvre ?", "contenu_type": "question", "valide_par": "DR-001"})
    assert r["verdict"] == "CONFORME"


def test_tramadol_patiente_enceinte_mineure_bloque_et_alternative():
    """The case seen in a demo: tramadol "1 kg, 7 times a day" for a pregnant 15-year-old patient."""
    app = _app()
    d = app.ctx.dossier
    app.evenement({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "Renseignements saisis par le médecin.",
                   "donnees": {"sexe": "F", "age": 15, "grossesse": True, "allergies": "aucune", "traitements_en_cours": "aucun",
                               "poids": 55, "mode_consultation": "presentiel", "moyen_communication": "pictogrammes"}})
    app.evenement({"type": "prescription", "auteur": "medecin", "prescripteur": "DR-001", "medicament": "Tramadol",
                   "dose": "1kg", "posologie": "7fois parjours", "mode": "presentiel"})
    app.evenement({"type": "prescription", "auteur": "medecin", "prescripteur": "DR-001", "medicament": "tramadol",
                   "dose": "50 mg", "posologie": "3 fois par jour", "mode": "presentiel"})
    rx = [x for x in d.decisions.values() if x.get("type") == "prescription"]
    assert [x["statut"] for x in rx] == ["BLOQUE", "A_REVOIR"]
    regles = {c["regle"] for v in d.verdicts if v.get("decision_id") == rx[0]["id"] for c in v["constats"]}
    assert {"SURETE-DOSE", "contre_indication:tramadol:grossesse", "contre_indication:tramadol:age"} <= regles
    # the assistant says it at once (without a model), with a sourced alternative
    sugg = list(d.suggestions.values()) if isinstance(d.suggestions, dict) else d.suggestions
    alt = [s for s in sugg if s.get("type") == "traitement_alternatif"]
    assert alt and "Ne pas prescrire Tramadol" in alt[0]["texte"] and "paracetamol" in alt[0]["texte"]
    assert "grossesse" in alt[0]["texte"] and "FDA" in alt[0]["source"]
    # nothing was explained or sent to the patient
    assert not any(x.get("source_prescription") for x in d.decisions.values())
    assert app.vue_patient()["messages"] == []


def test_dose_maximale_et_lecture_des_rythmes():
    from medimcom.regles import lire_dose
    assert lire_dose("50 mg", "7fois parjours")["mg_par_jour"] == 350
    assert lire_dose("100mg", "toutes les 6 h")["mg_par_jour"] == 400
    assert lire_dose("1 g", "matin et soir")["mg_par_jour"] == 2000
    m = MoteurRegles(RACINE / "kb" / "regles_uae.json")
    etat = {k: {"valeur": v, "confirme": True} for k, v in
            {"sexe": "M", "age": 40, "allergies": "aucune", "traitements_en_cours": "aucun", "mode_consultation": "presentiel"}.items()}
    r = m.verifier_prescription({"medicament": "tramadol", "prescripteur": "DR-001", "auteur": "medecin",
                                 "dose": "100 mg", "posologie": "6 fois par jour", "mode": "presentiel"}, etat)
    assert r["verdict"] == "A_REVOIR" and any(c["regle"] == "dose_max:tramadol" for c in r["constats"])
    r = m.verifier_prescription({"medicament": "tramadol", "prescripteur": "DR-001", "auteur": "medecin",
                                 "dose": "500 mg", "posologie": "4 fois par jour", "mode": "presentiel"}, etat)
    assert r["verdict"] == "BLOQUE" and any(c["regle"] == "SURETE-DOSE" for c in r["constats"])
