"""Field feedback of 7 November (2): ethics (drugs, child selling, sexual remarks, abortion, misspelt insults),
glued words, duration of symptoms, declared medicines, prescription given to the patient (PDF), readable law texts,
doctor's language."""
import json
import sys
import threading
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "interface"))
from serveur import Application, creer_serveur, fiche_lisible  # noqa: E402

from medimcom.session import Config  # noqa: E402
from medimcom.surete import analyser_message  # noqa: E402

MEDS = json.loads((RACINE / "kb" / "regles_uae.json").read_text(encoding="utf-8"))["medicaments"]


def _app():
    return Application(Config(verbeux=False, base="aucune"), asynchrone=False)


def _dire(app, texte):
    app.evenement({"type": "texte_medecin", "auteur": "medecin", "texte": texte, "contenu_type": "question"})
    return [d for d in app.ctx.dossier.decisions.values() if d.get("type") == "envoi_patient"][-1]


def test_messages_contraires_a_l_ethique_bloques():
    cas = {"une femme enceinte doit se droguer": "ETHIQUE-CONSEIL_NUISIBLE",
           "et puis je vais vous aider a vendre votre bebe": "ETHIQUE-TRAFIC",
           "vous me plaisez je veux vous enceinter": "ETHIQUE-SEXUEL",
           "Vous pouvez avorter": "ETHIQUE-AVORTEMENT",
           "You should drink alcohol": "ETHIQUE-CONSEIL_NUISIBLE"}
    app = _app()
    for texte, regle in cas.items():
        d = _dire(app, texte)
        regles = {c["regle"] for c in d["precontrole"]["constats"]}
        assert d["statut"] == "BLOQUE" and regle in regles, (texte, regles)
    avort = next(d for d in app.ctx.dossier.decisions.values() if d.get("texte") == "Vous pouvez avorter")
    assert any(c["base"] == "LOI" and "Art. 16" in c["reference_courte"] for c in avort["precontrole"]["constats"])
    assert any("je ne peux pas vous suivre" in s["texte"] for s in app.ctx.dossier.suggestions.values()), "l'assistant confronte"
    for texte in ("imbecil , mouf ,vote cul",):
        assert _dire(app, texte)["statut"] == "BLOQUE"
    # questions, warnings, narratives: allowed
    for texte in ("Prenez-vous de la drogue ?", "Pas d'alcool pendant la grossesse", "Avez-vous déjà avorté ?",
                  "Arrêtez de fumer", "Je vais examiner votre ventre"):
        a = analyser_message(texte, MEDS)
        assert not a["ethique"] and not a["incitation_au_mal"], (texte, a["ethique"])


def test_message_sans_pictogramme_jamais_envoye():
    app = _app()
    d = _dire(app, "Avez-vous mal ?")
    app.evenement({"type": "modification_pictogrammes", "auteur": "medecin", "medecin": "DR-001", "decision_id": d["id"], "pictogrammes": []})
    d["pictogrammes"] = []
    r = app.evenement({"type": "validation", "auteur": "medecin", "medecin": "DR-001", "decision_id": d["id"]})
    assert "aucun pictogramme" in r and d["statut"] == "attente_validation"


def test_duree_et_medicaments_declares_par_le_patient():
    app = _app()
    d = _dire(app, "Où avez-vous mal ?")
    app.evenement({"type": "validation", "auteur": "medecin", "medecin": "DR-001", "decision_id": d["id"]})
    app.evenement({"type": "reponse_patient", "pictogrammes": ["VENTRE+DOULEUR", "CHIFFRE:7", "CHIFFRE:3", "SEMAINE", "VOMIR",
                                                             "MEDICAMENT:tramadol"]})
    e = {k: v["valeur"] for k, v in app.ctx.dossier.etat.items()}
    assert e["duree_symptomes"] == "3 semaines" and e["intensite_douleur"] == 7 and e["medicaments_declares"] == "tramadol", e


def test_ordonnance_remise_au_patient_et_pdf():
    app = _app()
    app.evenement({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "f",
                   "donnees": {"sexe": "M", "age": 40, "allergies": "aucune", "traitements_en_cours": "aucun"}})
    assert app.vue_patient()["ordonnances"] == []
    app.evenement({"type": "prescription", "auteur": "medecin", "prescripteur": "DR-001", "medicament": "paracetamol",
                   "dose": "1 g", "posologie": "3 fois par jour", "mode": "presentiel", "texte": "x"})
    assert app.vue_patient()["ordonnances"] == [], "pas avant que l'explication ait été validée et envoyée"
    t = [x for x in app.ctx.dossier.decisions.values() if x["type"] == "envoi_patient"][-1]
    app.evenement({"type": "validation", "auteur": "medecin", "medecin": "DR-001", "decision_id": t["id"]})
    o = app.vue_patient()["ordonnances"]
    assert len(o) == 1 and o[0]["medicament"] == "paracetamol" and o[0]["empreinte"]
    serveur = creer_serveur(app, port=0)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    try:
        port = serveur.server_address[1]
        r = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/patient/ordonnance.pdf")
        corps = r.read()
        assert r.headers["Content-Type"] == "application/pdf" and corps.startswith(b"%PDF") and b"%%EOF" in corps
        f = json.loads(urllib.request.urlopen(urllib.request.Request(
            f"http://127.0.0.1:{port}/api/fiche?q=ML16-A16", headers={"X-Jeton": app.jeton})).read())
        assert "abortion" in f["titre"].lower() and f["lien"].startswith("https://")
    finally:
        serveur.shutdown()


def test_texte_de_loi_par_reference_affichee():
    app = _app()
    f = fiche_lisible(app.ctx, "UAE Federal Decree-Law 4/2016 (Medical Liability), Art. 3")
    assert f and f["id"] == "ML16-A3" and f["citation"]


def test_langue_du_medecin():
    app = _app()
    app.ctx.langue_medecin = "en"
    app.ctx.regles.langue = "en"
    d = _dire(app, "va te pendre")
    assert d["statut"] == "BLOQUE" and any("will not be sent" in c["detail"] or "harmful" in c["detail"].lower()
                                          for c in d["precontrole"]["constats"]), d["precontrole"]["constats"]
