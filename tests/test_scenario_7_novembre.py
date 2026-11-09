"""Replay of the journal of 7 November (fictitious 22-year-old patient, pregnant, diabetic, online model
unavailable): what got through that day must no longer get through, and the assistant must be present even without
an online model."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "interface"))
from serveur import Application  # noqa: E402

from medimcom.session import Config  # noqa: E402


def _app():
    app = Application(Config(verbeux=False, base="aucune"), asynchrone=False)
    app.evenement({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "Renseignements saisis par le médecin.",
                   "donnees": {"sexe": "F", "age": 22, "poids": 55, "allergies": "non", "grossesse": True,
                               "traitements_en_cours": "contre le diabethe", "antecedents": "diabete"}})
    return app


def _dire(app, texte):
    app.evenement({"type": "texte_medecin", "auteur": "medecin", "texte": texte, "contenu_type": "question"})
    return [d for d in app.ctx.dossier.decisions.values() if d.get("type") == "envoi_patient"][-1]


def _suggestions(app):
    return [s["texte"] for s in app.ctx.dossier.suggestions.values() if s["statut"] == "proposee_au_medecin"]


def test_medicaments_dans_les_messages_et_fiche_du_patient():
    app = _app()
    d = _dire(app, "et du tramadol")
    assert d["statut"] == "BLOQUE", d["precontrole"]
    regles = {c["regle"] for c in d["precontrole"]["constats"]}
    assert "contre_indication:tramadol:grossesse" in regles and "ENVOI-PRODUIT-CONTROLE" in regles, regles
    assert not any(c["niveau"] == "CONFORME" for c in d["precontrole"]["constats"]), "« peut être envoyé » à côté d'un blocage"
    s = _suggestions(app)
    assert any("ne pas conseiller tramadol" in x and "grossesse" in x.lower() and "paracetamol" in x for x in s), s

    d = _dire(app, "je vais vous prescrire beaucoup de paracetamol")
    assert d["statut"] == "BLOQUE" and "SURETE-DOSE-IMPRECISE" in {c["regle"] for c in d["precontrole"]["constats"]}
    assert any("préciser la dose de paracetamol" in x and "4000" in x for x in _suggestions(app)), _suggestions(app)

    for texte in ("et vous pendre", "je vais vous tuer"):
        d = _dire(app, texte)
        assert d["statut"] == "BLOQUE", texte
        assert "Refusé" in app.evenement({"type": "validation", "auteur": "medecin", "medecin": "DR-001", "decision_id": d["id"]})
    # "pendre" alone: unknown meaning -> not sent without the doctor's named confirmation
    d = _dire(app, "pendre")
    assert d["statut"] == "attente_validation" and d["precontrole"]["verdict"] == "A_REVOIR"
    assert "Refusé" in app.evenement({"type": "validation", "auteur": "medecin", "medecin": "DR-001", "decision_id": d["id"]})
    assert app.vue_patient()["messages"] == [], "rien de tout cela ne doit arriver au patient"
    # a real screening question is sent
    d = _dire(app, "Avez-vous des idées de vous tuer ?")
    assert d["statut"] == "attente_validation", d.get("precontrole")
    # current treatment without a medicine name: the assistant asks to specify
    assert any("Préciser le traitement en cours" in x for x in _suggestions(app))


def test_medicament_declare_par_le_patient_et_questions():
    app = _app()
    d = _dire(app, "Qu'avez-vous pris comme médicament ?")
    app.evenement({"type": "validation", "auteur": "medecin", "medecin": "DR-001", "decision_id": d["id"]})
    assert d["statut"] == "envoye"
    q = next(q for q in app.ctx.dossier.questions_a_poser if q["id"] == d["source_question"])
    assert q["statut"] == "posee", "une question envoyée n'est plus « à poser »"
    app.evenement({"type": "reponse_patient", "pictogrammes": ["MEDICAMENT:tramadol"]})
    assert app.ctx.dossier.etat["medicaments_declares"]["valeur"] == "tramadol"
    assert q["statut"] == "repondue"
    assert any("Le patient dit prendre tramadol" in x and "grossesse" in x.lower() for x in _suggestions(app)), _suggestions(app)

    # cancelling a proposal: it is NOT proposed again automatically (the doctor rephrases if they want)
    d = _dire(app, "ou avez vous mal")
    app.evenement({"type": "rejet", "auteur": "medecin", "decision_id": d["id"], "raison": "à reformuler"})
    envois = [x for x in app.ctx.dossier.decisions.values() if x.get("type") == "envoi_patient" and x.get("texte") == "ou avez vous mal"]
    assert len(envois) == 1 and envois[0]["statut"] == "rejete", "la proposition annulée a été refaite"

    # remove a sent message from the patient screen, then hide it from the conversation
    envoye = next(x for x in app.ctx.dossier.decisions.values() if x.get("statut") == "envoye")
    app.evenement({"type": "retrait_message", "auteur": "medecin", "medecin": "DR-001", "decision_id": envoye["id"]})
    assert envoye["statut"] == "retire" and app.vue_patient()["messages"] == []
    app.evenement({"type": "masquage_message", "auteur": "medecin", "decision_id": envoye["id"]})
    assert envoye["masque"] is True
    from medimcom.surveillance import surveiller
    viol = surveiller(app.ctx.journal, app.ctx.regles)
    assert not any(viol.values()), viol


def test_fiche_completee_apres_coup_recontrole():
    """The message is proposed BEFORE the doctor enters the pregnancy: the jurist checks it again with the new record."""
    app = Application(Config(verbeux=False, base="aucune"), asynchrone=False)
    d = _dire(app, "Prenez-vous de l'ibuprofène ?")        # question : permise
    assert d["statut"] == "attente_validation"
    v0 = d["precontrole"]["etat_version"]
    app.evenement({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "fiche", "donnees": {"grossesse": True, "sexe": "F", "age": 30}})
    assert d["precontrole"]["etat_version"] != v0, "le pré-contrôle n'a pas été refait après la mise à jour de la fiche"


def test_grok_indisponible_message_clair():
    import io
    import urllib.error

    from medimcom.cerveaux import lire_erreur
    e = urllib.error.HTTPError("u", 400, "Bad Request", {}, io.BytesIO(
        b'{"code":"Client specified an invalid argument","error":"Incorrect API key provided: xai-abcdefghijklmnop. You can obtain an API key from https://console.x.ai."}'))
    m = lire_erreur(e)
    assert "Incorrect API key" in m and "abcdefghijklmnop" not in m, m


def test_modele_absent_remplace_et_alias_acceptes():
    import json as _json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from medimcom.cerveaux import CerveauOpenAI

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            b = _json.dumps({"data": [{"id": "grok-4.20-0309-non-reasoning", "aliases": ["grok-4.20-non-reasoning"]},
                                      {"id": "grok-4.20-0309-reasoning"}, {"id": "grok-2-image-1212"}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def log_message(self, *a):
            pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/v1"
        c = CerveauOpenAI(url, "grok-4.20-non-reasoning", cle="x")
        assert c.verifier() == (True, "ok"), "un alias est un nom valide"
        c = CerveauOpenAI(url, "grok-4.7", cle="x")
        ok, msg = c.verifier()
        assert ok and c.modele == "grok-4.20-0309-non-reasoning" and "instead" in msg
    finally:
        srv.shutdown()
