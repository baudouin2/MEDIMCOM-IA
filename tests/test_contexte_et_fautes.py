"""Les agents lisent le CONTEXTE (consigne, incitation, question, mise en garde, récit, information) et corrigent les
fautes de frappe et de dictée. Et la sécurité clinique vaut pour tous les profils, pas seulement la grossesse."""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "interface"))
from serveur import Application  # noqa: E402

from medimcom.regles import MoteurRegles  # noqa: E402
from medimcom.session import Config  # noqa: E402
from medimcom.surete import analyser_message  # noqa: E402

MEDS = json.loads((RACINE / "kb" / "regles_uae.json").read_text(encoding="utf-8"))["medicaments"]


def test_lecture_du_contexte():
    bloques = ["Allez vous pendre", "et vous pendre", "Pendez-vous", "je vais vous tuer", "espèce d'idiot", "allez vous pandre"]
    for t in bloques:
        assert analyser_message(t, MEDS)["incitation_au_mal"], t
    permis = {  # récit, question, information, mise en garde : on peut en parler
        "Il s'est pendu l'an dernier": "recit",
        "Votre frère a voulu se pendre, c'est ça qui vous inquiète": "recit",
        "Avez-vous des idées de vous tuer ?": "question",
        "Il m'a traité d'idiot": "recit",
        "Le paracétamol peut donner des nausées": "information",
        "Prenez-vous du tramadol ?": "question",
        "Ne prenez pas d'ibuprofène": "mise_en_garde",
        "Vous m'avez dit avoir pris du tramadol hier": "recit",
        "Mon voisin a pris trop de paracétamol et il est mort": "recit",
    }
    for t, intention in permis.items():
        a = analyser_message(t, MEDS)
        assert not a["incitation_au_mal"] and not a["consigne_medicament"] and not a["a_confirmer"], (t, a)
        assert a["contexte"]["intention"] == intention, (t, a["contexte"])
    for t in ("Prenez du tramadol", "je vais vous prescrire beaucoup de paracetamol", "et du tramadol",
              "Vous prenez du paracétamol 3 fois par jour"):
        assert analyser_message(t, MEDS)["consigne_medicament"], t
    for t in ("pendre", "tramadol pour la douleur de votre dos", "Il m'a dit : va te pendre"):
        assert analyser_message(t, MEDS)["a_confirmer"], t


def test_fautes_de_frappe_et_de_dictee():
    for t, nom in (("prenez du tramadole", "tramadol"), ("prenez du paracetamole", "paracetamol"),
                   ("prenez du para c'est tamol", "paracetamol"), ("prenez de l'ibuprophène", "ibuprofene"),
                   ("prenez du doliprane", "paracetamol"), ("prenez du trama dol", "tramadol")):
        a = analyser_message(t, MEDS)
        assert a["consigne_medicament"] and a["medicament"] == nom and a["corrections"], (t, a)
    for juste in ("prendre", "rendre", "vendre", "pendant", "noix", "Du riz et de l'eau"):
        a = analyser_message(juste, MEDS)
        assert not a["corrections"] and not a["incitation_au_mal"], juste
    m = MoteurRegles(RACINE / "kb" / "regles_uae.json")
    v = m.verifier_prescription({"medicament": "tramadole", "prescripteur": "DR-001", "auteur": "medecin", "mode": "presentiel",
                                 "dose": "50 mg", "posologie": "3 fois par jour"},
                                {"grossesse": {"valeur": True, "confirme": True}, "sexe": {"valeur": "F", "confirme": True},
                                 "age": {"valeur": 25, "confirme": True}})
    assert any(c["regle"] == "contre_indication:tramadol:grossesse" for c in v["constats"]), "tramadole lu comme tramadol"
    assert any("lu comme tramadol" in c["detail"] for c in v["informations"])
    from medimcom.faits import extraire_faits
    f = extraire_faits("diabhete, insufisance renale, enseinte")
    assert f.get("maladie_renale") and f.get("grossesse") is True and "diabète" in f.get("maladies_connues", []), f


def _app(donnees):
    app = Application(Config(verbeux=False, base="aucune"), asynchrone=False)
    app.evenement({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "fiche", "donnees": donnees})
    return app


def _dire(app, texte):
    app.evenement({"type": "texte_medecin", "auteur": "medecin", "texte": texte, "contenu_type": "question"})
    return [d for d in app.ctx.dossier.decisions.values() if d.get("type") == "envoi_patient"][-1]


def test_tous_les_profils_pas_seulement_la_grossesse():
    cas = [({"age": 8, "sexe": "M", "poids": 25}, "Prenez de l'aspirine", "contre_indication:aspirine:age"),
           ({"age": 40, "sexe": "M", "allergies": "amoxicilline"}, "Prenez de l'amoxicilline", "allergie:amoxicilline"),
           ({"age": 55, "sexe": "M", "antecedents": "ulcère de l'estomac"}, "Prenez de l'ibuprofène", "contre_indication:ibuprofene:ulcere_digestif"),
           ({"age": 60, "sexe": "F", "antecedents": "insuffisance rénale"}, "prenez de la metformine", "contre_indication:metformine:maladie_renale")]
    for fiche, texte, regle in cas:
        app = _app({**fiche, **({"antecedents": fiche["antecedents"]} if "antecedents" in fiche else {})})
        if "antecedents" in fiche:
            from medimcom.faits import extraire_faits
            app.evenement({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "faits",
                           "donnees": extraire_faits(fiche["antecedents"])})
        d = _dire(app, texte)
        regles = {c["regle"] for c in d["precontrole"]["constats"]}
        assert d["statut"] == "BLOQUE" and regle in regles, (texte, regles)
        sugg = [s["texte"] for s in app.ctx.dossier.suggestions.values()]
        assert any("ne pas conseiller" in s for s in sugg), (texte, sugg)


def test_recit_permis_et_agents_informes():
    app = _app({"sexe": "F", "age": 30, "grossesse": True})
    d = _dire(app, "Votre frère a voulu se pendre, c'est ça qui vous inquiète")
    assert d["statut"] == "attente_validation" and d["precontrole"]["verdict"] == "CONFORME", d["precontrole"]
    assert any(c["regle"] == "LECTURE-CONTEXTE" for c in d["precontrole"]["lecture"])
    msgs = [m for m in app.ctx.messagerie.historique if m.de == "juriste" and m.a == "assistant"]
    assert any("récit" in m.contenu for m in msgs), "le juriste dit à l'assistant ce qu'il a compris"
    app.evenement({"type": "validation", "auteur": "medecin", "medecin": "DR-001", "decision_id": d["id"]})
    assert d["statut"] == "envoye"
    # sens incertain : part seulement avec la confirmation signée du médecin
    d = _dire(app, "pendre")
    assert "Refusé" in app.evenement({"type": "validation", "auteur": "medecin", "medecin": "DR-001", "decision_id": d["id"]})
    app.evenement({"type": "validation", "auteur": "medecin", "medecin": "DR-001", "decision_id": d["id"], "confirme_contexte": True})
    assert d["statut"] == "envoye" and d["contexte_confirme_par"] == "DR-001"
    assert any(l["type"] == "contexte_confirme" for l in app.ctx.journal.lignes)


def test_patient_qui_exprime_une_idee_de_mort():
    from medimcom.lecture import risque_suicidaire
    assert risque_suicidaire("moi vouloir mourir")["niveau"] == "alerte"
    assert risque_suicidaire("je veux me pendre")["niveau"] == "alerte"
    assert risque_suicidaire("mon frère s'est pendu")["niveau"] == "information"
    assert risque_suicidaire("j'ai mal à la tête") is None


def test_assistant_lit_le_contexte():
    app = _app({"sexe": "F", "age": 30, "grossesse": True})
    _dire(app, "Vous m'avez dit avoir pris du tramadole hier")
    sugg = [s["texte"] for s in app.ctx.dossier.suggestions.values()]
    assert any("évoque une prise de tramadol" in s and "grossesse" in s.lower() for s in sugg), sugg
    app2 = _app({"sexe": "M", "age": 40})
    app2.ctx.dossier.ajouter_echange("traducteur", "Réponse du patient", {}, True,
                                     details={"pictogrammes": ["MOI", "VOULOIR", "MOURIR"], "interpretation": "moi vouloir mourir"})
    app2.evenement({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "x", "donnees": {"poids": 70}})
    assert any(s["type"] == "alerte_urgence" and "risque suicidaire" in s["texte"] for s in app2.ctx.dossier.suggestions.values())
