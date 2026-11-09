"""Functional inspection (7 November): valid consent, missing information obtained, refusal of the AI respected,
"I don't understand", emergency handled, journal filters."""
import json
import sys
import threading
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "interface"))
from serveur import MESSAGE_ACCUEIL, Application, creer_serveur  # noqa: E402

from medimcom.session import Config  # noqa: E402


def _app():
    return Application(Config(verbeux=False, base="aucune"), asynchrone=False)


def _derniere_proposition(app):
    return [d for d in app.ctx.dossier.decisions.values() if d.get("type") == "envoi_patient"][-1]


def _valider(app, d):
    app.evenement({"type": "validation", "auteur": "medecin", "medecin": "DR-001", "decision_id": d["id"]})


def test_informations_manquantes_obtenues_aupres_du_patient():
    app = _app()
    app.evenement({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "fiche", "donnees": {"sexe": "M", "age": 40}})
    app.evenement({"type": "prescription", "auteur": "medecin", "prescripteur": "DR-001", "medicament": "paracetamol",
                   "dose": "1 g", "posologie": "3 fois par jour", "mode": "presentiel", "texte": "x"})
    d = app.ctx.dossier
    rx = next(x for x in d.decisions.values() if x["type"] == "prescription")
    assert rx["statut"] == "PREUVES_INSUFFISANTES"
    questions = {q["cle"]: q for q in d.questions_a_poser}
    assert {"allergies", "traitements_en_cours"} <= set(questions), "l'assistant fait poser les questions manquantes"
    sugg = [s for s in d.suggestions.values() if s["statut"] == "proposee_au_medecin"]
    assert any("traitements en cours" in s["texte"] and "traitements_en_cours" not in s["texte"] for s in sugg), "libellés lisibles"
    assert not [x for x in d.decisions.values() if x.get("type") == "envoi_patient"], "rien dans la conversation sans le médecin"
    # the doctor clicks "Send" in the Assistant tab; the patient answers NO -> the prescription becomes compliant
    for cle in ("allergies", "traitements_en_cours"):
        app.evenement({"type": "poser_question", "auteur": "medecin", "medecin": "DR-001", "question_id": questions[cle]["id"]})
        p = next(x for x in d.decisions.values() if x.get("source_question") == questions[cle]["id"])
        assert p["statut"] == "envoye" and p["valide_par"] == "DR-001", p["statut"]
        app.evenement({"type": "reponse_patient", "pictogrammes": ["NON"]})
    assert d.etat["allergies"]["valeur"] == "aucune" and d.etat["traitements_en_cours"]["valeur"] == "aucun"
    assert rx["statut"] == "CONFORME", rx["statut"]
    assert not any(s["statut"] == "proposee_au_medecin" and "il manque" in s["texte"] for s in d.suggestions.values()), \
        "la suggestion périmée est retirée"


def test_oui_sans_detail_ne_vaut_pas_renseigne():
    from medimcom.regles import MoteurRegles
    m = MoteurRegles(RACINE / "kb" / "regles_uae.json")
    etat = {k: {"valeur": v, "confirme": True} for k, v in
            {"sexe": "M", "age": 40, "allergies": "oui, à préciser", "traitements_en_cours": "aucun"}.items()}
    v = m.verifier_prescription({"medicament": "paracetamol", "prescripteur": "DR-001", "auteur": "medecin", "mode": "presentiel",
                                 "dose": "1 g", "posologie": "3 fois par jour"}, etat)
    assert "allergies" in v["informations_manquantes"]


def test_consentement_seulement_si_l_accord_a_ete_montre():
    app = _app()
    app.evenement({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "fiche",
                   "donnees": {"sexe": "M", "age": 40, "allergies": "aucune", "traitements_en_cours": "aucun"}})
    app.evenement({"type": "prescription", "auteur": "medecin", "prescripteur": "DR-001", "medicament": "paracetamol",
                   "dose": "1 g", "posologie": "3 fois par jour", "mode": "presentiel", "texte": "x"})
    p = _derniere_proposition(app)
    assert any("ACCORD" in x for x in p["pictogrammes"]), p["pictogrammes"]
    # the doctor removes the agreement image: the question becomes "you?" -> a YES is NOT consent
    app.evenement({"type": "modification_pictogrammes", "auteur": "medecin", "medecin": "DR-001", "decision_id": p["id"],
                   "pictogrammes": [x for x in p["pictogrammes"] if "ACCORD" not in x]})
    _valider(app, p)
    app.evenement({"type": "reponse_patient", "pictogrammes": ["OUI"]})
    d = app.ctx.dossier
    assert "consentement_traitement" not in d.etat, "consentement enregistré sans que l'accord ait été montré"
    assert any(m.de == "traducteur" and "NON enregistrée comme accord" in m.contenu for m in app.ctx.messagerie.historique)


def test_message_d_accueil_et_refus_de_l_ia():
    app = _app()
    app.evenement({"type": "texte_medecin", "auteur": "medecin", "texte": MESSAGE_ACCUEIL, "contenu_type": "question", "cle": "informe_usage_ia"})
    p = _derniere_proposition(app)
    assert any("ACCORD" in x for x in p["pictogrammes"]) and p["statut"] == "attente_validation"
    _valider(app, p)
    app.evenement({"type": "reponse_patient", "pictogrammes": ["NON"]})
    d = app.ctx.dossier
    assert d.etat["informe_usage_ia"]["valeur"] is False
    assert any(s["type"] == "alerte_urgence" and "Respectez son choix" in s["texte"] for s in d.suggestions.values())


def test_je_ne_comprends_pas_et_urgence():
    app = _app()
    app.evenement({"type": "texte_medecin", "auteur": "medecin", "texte": "Avez-vous mal ?", "contenu_type": "question"})
    _valider(app, _derniere_proposition(app))
    app.evenement({"type": "reponse_patient", "pictogrammes": ["NE_PAS", "COMPRENDRE"]})
    d = app.ctx.dossier
    assert any("ne comprend pas" in s["texte"] and "interprète" in s["texte"] for s in d.suggestions.values())
    assert "douleur" not in d.etat, "« je ne comprends pas » n'est pas une réponse"
    app.evenement({"type": "reponse_patient", "pictogrammes": ["URGENCE"]})
    assert app.vue_patient()["urgence"] == "signalee"
    app.evenement({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "Urgence prise en charge.", "donnees": {"urgence": False}})
    assert app.vue_patient()["urgence"] == "prise_en_charge"


def test_filtres_du_journal_autorises():
    app = _app()
    serveur = creer_serveur(app, port=0)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    try:
        port = serveur.server_address[1]
        r = urllib.request.urlopen(f"http://127.0.0.1:{port}/journal?jeton={app.jeton}")
        csp = r.headers.get("Content-Security-Policy") or ""
        page = r.read().decode("utf-8")
        assert "<script>" in page and "'sha256-" in csp, csp
    finally:
        serveur.shutdown()


def test_propositions_et_alertes_perimees_retirees():
    app = _app()
    app.evenement({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "fiche", "donnees": {"sexe": "M", "age": 40}})
    app.evenement({"type": "prescription", "auteur": "medecin", "prescripteur": "DR-001", "medicament": "paracetamol",
                   "dose": "1 g", "posologie": "3 fois par jour", "mode": "presentiel", "texte": "x"})
    d = app.ctx.dossier
    qid = next(q["id"] for q in d.questions_a_poser if q.get("cle") == "allergies")
    app.evenement({"type": "poser_question", "auteur": "medecin", "medecin": "DR-001", "question_id": qid, "modifier": True})
    attente = [x for x in d.decisions.values() if x.get("type") == "envoi_patient" and x["statut"] == "attente_validation"]
    assert len(attente) == 1
    # the doctor fills in the record themself: the question becomes useless; the proposal is withdrawn, the other
    # question too
    app.evenement({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "fiche",
                   "donnees": {"allergies": "aucune", "traitements_en_cours": "aucun"}})
    assert all(x["statut"] == "annulee" for x in attente), [x["statut"] for x in attente]
    assert all(q["statut"] == "repondue" for q in d.questions_a_poser if q.get("cle") in ("allergies", "traitements_en_cours"))
    # the doctor refuses an assistant question: it disappears
    d.ajouter_question("assistant", "Avez-vous de la fièvre ?", "test", "fievre")
    q = d.questions_a_poser[-1]
    app.evenement({"type": "refus_question", "auteur": "medecin", "question_id": q["id"]})
    assert q["statut"] == "refusee"
    # emergency handled: the assistant's alert is withdrawn
    app.evenement({"type": "reponse_patient", "pictogrammes": ["URGENCE"]})
    assert any(s["type"] == "alerte_urgence" and s["statut"] == "proposee_au_medecin" for s in d.suggestions.values())
    app.evenement({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "Urgence prise en charge.", "donnees": {"urgence": False}})
    assert not any(s["type"] == "alerte_urgence" and s["statut"] == "proposee_au_medecin" for s in d.suggestions.values())
    from medimcom.surveillance import surveiller
    assert not any(surveiller(app.ctx.journal, app.ctx.regles).values())
