"""Feedback of 9 November: (1) the record filled in by the doctor must serve the jurist AT ONCE, even when the
assistant's online model is slow; (2) the patient can send a photo or a file useful to the doctor."""
import base64
import sys
import threading
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RACINE), str(RACINE / "interface"), str(RACINE / "tests")]
from medimcom.session import Config  # noqa: E402
from serveur import Application, creer_serveur  # noqa: E402
from test_interface_reactivite import _post  # noqa: E402

PRESCRIPTION = {"type": "prescription", "auteur": "medecin", "prescripteur": "DR-001", "medicament": "paracetamol",
                "dose": "500 mg", "posologie": "toutes les 6 heures si besoin, 4 fois par jour au maximum", "mode": "presentiel"}


def test_fiche_du_medecin_utilisee_sans_attendre_l_assistant():
    app = Application(Config(verbeux=False, base="aucune"), asynchrone=True)
    assistant = next(a for a in app.agents if a.nom == "assistant")
    origine, bloque = assistant.tour, threading.Event()

    def lent(*a, **k):                      # the assistant (online model) takes long to answer
        bloque.wait(20)
        return origine(*a, **k)
    assistant.tour = lent
    app.lents = frozenset({"assistant"})
    app.evenement({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "Renseignements saisis par le médecin.",
                   "donnees": {"sexe": "F", "age": 45, "grossesse": False, "allergies": "non", "traitements_en_cours": "contre le diabete"}})
    app.evenement(PRESCRIPTION)
    try:
        for _ in range(60):
            p = [d for d in app.ctx.dossier.decisions.values() if d.get("type") == "prescription"]
            if p and p[-1]["statut"] != "proposee":
                break
            time.sleep(0.1)
        etat = app.ctx.dossier.etat
        assert etat["allergies"]["confirme"] and etat["traitements_en_cours"]["valeur"] == "contre le diabete"
        assert p[-1]["statut"] == "CONFORME", (p[-1]["statut"], "fiche remplie mais « information manquante »")
    finally:
        bloque.set()


def test_document_suggere_mais_ne_remplace_pas_la_fiche():
    app = Application(Config(verbeux=False, base="aucune"), asynchrone=False)
    app.evenement({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "fiche", "donnees": {"allergies": "non"}})
    app.evenement({"type": "echange", "auteur": "document", "confirme": False, "texte": "Lecture du document",
                   "donnees": {"allergies": "pénicilline", "medicaments_declares": "metformine"}})
    e = app.ctx.dossier.etat
    assert e["allergies"]["valeur"] == "non" and e["allergies"]["confirme"], "un document ne remplace pas ce que le médecin a saisi"
    assert e["medicaments_declares"]["valeur"] == "metformine" and not e["medicaments_declares"]["confirme"]


def test_le_patient_envoie_un_document():
    app = Application(Config(verbeux=False, base="aucune"), asynchrone=False)
    serveur = creer_serveur(app, port=0)
    port = serveur.server_address[1]
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    try:
        texte = base64.b64encode("Ordonnance : Doliprane 1 g, 3 fois par jour pendant 3 jours.".encode()).decode()
        r = _post(port, "/api/patient/document", {"nom": "ordo.txt", "type": "ordonnance", "mime": "text/plain", "contenu": texte})
        assert "envoyé au médecin" in r["retour"], r              # without a token: this is the patient screen
        assert "déjà" in _post(port, "/api/patient/document", {"nom": "x.txt", "type": "ordonnance", "mime": "text/plain",
                                                                "contenu": texte})["retour"], "même fichier : pas de doublon"
        for _ in range(50):
            if app.documents[-1]["extraction"]["statut"] != "en_cours":
                break
            time.sleep(0.1)
        doc = app.documents[-1]
        assert doc["auteur"] == "patient" and [m["nom"] for m in doc["extraction"]["medicaments"]] == ["paracetamol"]
        assert any(e["auteur"] == "patient" and "document" in e["texte"] for e in app.ctx.dossier.fil), "le médecin est prévenu"
        assert app.vue_patient()["documents"] == [{"id": doc["id"], "type": "ordonnance", "lu": True}]
        assert "nom" not in app.vue_patient()["documents"][0]
        # the patient cannot use the doctor's route
        import urllib.error
        try:
            _post(port, "/api/medecin/document", {"nom": "x", "type": "autre", "mime": "text/plain", "contenu": texte})
            raise AssertionError("route médecin sans jeton")
        except urllib.error.HTTPError as e:
            assert e.code == 403
        # limited number (open patient screen)
        for i in range(12):
            c = base64.b64encode(f"doc {i}".encode()).decode()
            try:
                _post(port, "/api/patient/document", {"nom": f"{i}.txt", "type": "autre", "mime": "text/plain", "contenu": c})
            except urllib.error.HTTPError as e:
                assert e.code == 400 and i >= 9
        assert sum(1 for d in app.documents if d["auteur"] == "patient") == app.MAX_DOCUMENTS_PATIENT
        from medimcom.surveillance import surveiller
        viol = surveiller(app.ctx.journal, app.ctx.regles)
        assert not any(viol.values()), viol
    finally:
        serveur.shutdown()
