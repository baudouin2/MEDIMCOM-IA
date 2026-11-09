"""A click of the doctor or the patient must never wait for the agents to finish (slow online model)."""
import sys
import threading
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "interface"))
from medimcom.session import Config  # noqa: E402
from serveur import Application  # noqa: E402


def test_clic_immediat_pendant_que_les_agents_travaillent():
    app = Application(Config(verbeux=False), asynchrone=True)
    origine = app.orch.stabiliser
    occupe = threading.Event()

    def lent(*a, **k):
        occupe.set()
        time.sleep(1.5)                      # an online model that takes time to answer
        return origine(*a, **k)

    app.orch.stabiliser = lent
    app.evenement({"type": "texte_medecin", "auteur": "medecin", "texte": "Avez-vous de la fièvre ?", "contenu_type": "question"})
    assert occupe.wait(2)
    t0 = time.time()
    retour = app.evenement({"type": "texte_medecin", "auteur": "medecin", "texte": "Avez-vous mal ?", "contenu_type": "question"})
    assert time.time() - t0 < 0.5 and "traitement en cours" in retour, "le second clic a attendu les agents"
    t0 = time.time()
    vue = app.vue_medecin()
    assert time.time() - t0 < 0.6 and vue["travail_en_cours"] is True
    for _ in range(100):
        if not app.vue_medecin()["travail_en_cours"]:
            break
        time.sleep(0.1)
    props = [d for d in app.ctx.dossier.decisions.values() if d["statut"] == "attente_validation"]
    assert len(props) == 2, "les deux messages du médecin attendent sa validation"


def test_medecin_modifie_les_pictogrammes_avant_validation():
    app = Application(Config(verbeux=False), asynchrone=False)
    app.evenement({"type": "texte_medecin", "auteur": "medecin", "texte": "Ne prenez pas d'ibuprofène", "contenu_type": "information"})
    d = next(x for x in app.ctx.dossier.decisions.values() if x["statut"] == "attente_validation")
    assert "NE_PAS" in d["pictogrammes"]
    sans_negation = [p for p in d["pictogrammes"] if p != "NE_PAS"]
    app.evenement({"type": "modification_pictogrammes", "auteur": "medecin", "medecin": "DR-001", "decision_id": d["id"], "pictogrammes": sans_negation})
    assert "NE_PAS" in d["pictogrammes"], "la négation ne peut pas être retirée"
    app.evenement({"type": "modification_pictogrammes", "auteur": "medecin", "medecin": "DR-001", "decision_id": d["id"],
                   "pictogrammes": d["pictogrammes"] + ["INCONNU_XYZ"]})
    assert "INCONNU_XYZ" not in d["pictogrammes"], "pictogramme inconnu refusé"
    nouveau = d["pictogrammes"] + ["OUI"]
    app.evenement({"type": "modification_pictogrammes", "auteur": "medecin", "medecin": "DR-001", "decision_id": d["id"], "pictogrammes": nouveau})
    assert d["pictogrammes"] == nouveau and d["pictogrammes_choisis_par"].startswith("médecin") and d["statut"] == "attente_validation"
    app.evenement({"type": "validation", "auteur": "medecin", "medecin": "DR-001", "decision_id": d["id"]})
    assert d["statut"] == "envoye" and app.vue_patient()["messages"][-1]["pictogrammes"] == nouveau


def _post(port, chemin, corps, jeton=None):
    import json
    import urllib.request
    req = urllib.request.Request(f"http://127.0.0.1:{port}{chemin}", data=json.dumps(corps).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **({"X-Jeton": jeton} if jeton else {})})
    ouvreur = urllib.request.build_opener(urllib.request.ProxyHandler({}))     # 127.0.0.1: never through a proxy
    with ouvreur.open(req, timeout=10) as r:
        return json.loads(r.read())


def test_fiche_libre_traduction_patient_et_doublons():
    import os
    from serveur import creer_serveur
    app = Application(Config(verbeux=False), asynchrone=False)
    serveur = creer_serveur(app, port=0)
    port = serveur.server_address[1]
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    try:
        _post(port, "/api/medecin/faits", {"donnees": {"antecedents": "diabète, HTA, insuffisance rénale", "tabac": "10 cigarettes par jour"}}, app.jeton)
        etat = app.ctx.dossier.etat
        assert etat["antecedents"]["valeur"].startswith("diabète") and etat["tabac"]["valeur"] == "10 cigarettes par jour"
        assert set(etat["maladies_connues"]["valeur"]) >= {"diabète", "hypertension", "insuffisance rénale"} and etat["maladie_renale"]["valeur"] is True
        r = _post(port, "/api/patient/traduire", {"texte": "j'ai mal au ventre"})
        assert "VENTRE+DOULEUR" in r["pictogrammes"], r
        a = _post(port, "/api/patient/reponse", {"pictogrammes": ["OUI"]})
        b = _post(port, "/api/patient/reponse", {"pictogrammes": ["OUI"]})
        assert "Déjà envoyé" in b["retour"] and "Déjà" not in a["retour"], "un double clic n'envoie pas deux fois"
        m1 = _post(port, "/api/medecin/message", {"texte": "Avez-vous de la fièvre ?", "question": True}, app.jeton)
        m2 = _post(port, "/api/medecin/message", {"texte": "Avez-vous de la fièvre ?", "question": True}, app.jeton)
        assert "Déjà transmis" in m2["retour"] and "Déjà" not in m1["retour"]
        sauve, sauve_groq = os.environ.pop("XAI_API_KEY", None), os.environ.pop("GROQ_API_KEY", None)
        try:
            from urllib.error import HTTPError
            try:
                _post(port, "/api/medecin/dictee", {"audio": "UklGRg==", "langue": "fr"}, app.jeton)
                raise AssertionError("dictée sans clé : erreur attendue")
            except HTTPError as e:
                assert e.code == 400 and "XAI_API_KEY" in e.read().decode()
        finally:
            if sauve:
                os.environ["XAI_API_KEY"] = sauve
            if sauve_groq:
                os.environ["GROQ_API_KEY"] = sauve_groq
        assert app.vue_patient()["messages"] == [] or "texte" in app.vue_patient()["messages"][0]
    finally:
        serveur.shutdown()
