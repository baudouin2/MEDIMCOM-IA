"""Tests of the core, of the jurist's rules and of the knowledge base. Run: python -m pytest -q   (or: python tests/test_noyau.py)"""
import io
import json
import os
import sys
import threading
from contextlib import redirect_stdout
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

ICI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ICI))
os.environ.setdefault("MEDIMCOM_BASE", "aucune")   # tests independent of the installed base_v2
sys.path.insert(0, str(ICI / "kb" / "outils"))

from medimcom.agents import (Assistant, AutoriteSante, CelluleCrise, Contexte, Hopital, Juriste,  # noqa: E402
                             Traducteur)
from main import BOITES  # noqa: E402
from medimcom.base import BaseConnaissances  # noqa: E402
from medimcom.cerveaux import CerveauSimule  # noqa: E402
from medimcom.dossier import Dossier  # noqa: E402
from medimcom.journal import Journal  # noqa: E402
from medimcom.messagerie import Messagerie  # noqa: E402
from medimcom.orchestrateur import Orchestrateur  # noqa: E402
from medimcom.regles import MoteurRegles  # noqa: E402

KB = ICI / "kb"
BASE = BaseConnaissances(KB)
R = MoteurRegles(KB / "regles_uae.json", BASE)

PATIENTE = dict(sexe="F", age=25, allergies="aucune", traitements_en_cours="aucun", informe_usage_ia=True)


def etat(**kw):
    return {k: {"valeur": v, "source": "test", "confirme": True} for k, v in kw.items()}


def rx(medicament, prescripteur="DR-001", **kw):
    d = {"medicament": medicament, "prescripteur": prescripteur, "auteur": "medecin",
         "dose": "1 cp", "posologie": "2 fois par jour", "mode": "presentiel"}
    d.update(kw)
    return d


# ---------------------------------------------------------------- journal and messaging
def test_journal_detecte_une_modification():
    j = Journal()
    contenu = {"statut": "en_attente"}
    j.ajouter("a", "x", contenu)
    j.ajouter("b", "y", {"z": 2})
    contenu["statut"] = "modifie_apres_coup"      # the original object changes: the journal must not move
    assert j.verifier() == "Journal intact"
    j.lignes[0]["contenu"]["statut"] = "falsifie"  # falsification directe
    assert j.verifier() == "Ligne 1 modifiée"


def test_messagerie_refuse_type_et_destinataire_inconnus():
    m = Messagerie(Journal(), {"assistant", "juriste"})
    assert m.envoyer("assistant", "juriste", "ordre", "x").startswith("Refusé")
    assert m.envoyer("assistant", "inconnu", "demande", "x").startswith("Refusé")
    assert m.envoyer("assistant", "juriste", "demande", "x").startswith("Message")


# ---------------------------------------------------------------- knowledge base
def test_base_coherente():
    import verifier_kb
    _, problemes = verifier_kb.controler()
    assert problemes == []


def test_chaque_constat_cite_un_texte_avec_lien():
    v = R.verifier_prescription(rx("ibuprofene"), etat(**PATIENTE, grossesse=True))
    for c in v["constats"] + v["obligations"]:
        assert c["fiches"] and "http" in c["source"], c


def test_recherche_rappel_a_5_au_moins_90_pourcent():
    import evaluer_recherche
    qs = [json.loads(l) for l in (KB / "questions_test.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    r = evaluer_recherche.evaluer(BASE, qs)
    assert r["rappel"]["rappel@5"] >= 0.9, r


# ---------------------------------------------------------------- prescriptions
def test_grossesse_inconnue_donne_preuves_insuffisantes():
    e = etat(**{k: v for k, v in PATIENTE.items()})
    v = R.verifier_prescription(rx("Ibuprofène"), e)
    assert v["verdict"] == "PREUVES_INSUFFISANTES"
    assert v["informations_manquantes"] == ["grossesse"]


def test_grossesse_confirmee_ibuprofene_a_revoir():
    v = R.verifier_prescription(rx("ibuprofene"), etat(**PATIENTE, grossesse=True))
    assert v["verdict"] == "A_REVOIR" and v["depassement_possible"]
    assert any("FDA20-NSAID" in c["fiches"] for c in v["constats"])


def test_misoprostol_femme_enceinte_bloque():
    v = R.verifier_prescription(rx("misoprostol"), etat(**PATIENTE, grossesse=True))
    assert v["verdict"] == "BLOQUE" and not v["depassement_possible"]
    assert any("ML16-A16" in c["fiches"] for c in v["constats"])


def test_paracetamol_conforme_avec_obligations():
    v = R.verifier_prescription(rx("paracetamol"), etat(**PATIENTE, grossesse=True, moyen_communication="pictogrammes"))
    assert v["verdict"] == "CONFORME"
    regles = {o["regle"] for o in v["obligations"]}
    assert {"CONSENTEMENT", "CONSENTEMENT-PICTO", "INFORMATION-PATIENT"} <= regles
    assert "L04" in v["lacunes_liees"]


def test_dose_manquante_preuves_insuffisantes():
    v = R.verifier_prescription(rx("paracetamol", dose=None), etat(**PATIENTE, grossesse=False))
    assert v["verdict"] == "PREUVES_INSUFFISANTES"
    assert any(c["regle"] == "RX-ECRITE-DOSE" for c in v["constats"])


def test_prescripteur_inconnu_ou_inactif_bloque():
    e = etat(sexe="M", age=40, allergies="aucune", traitements_en_cours="aucun")
    assert R.verifier_prescription(rx("paracetamol", "INCONNU"), e)["verdict"] == "BLOQUE"
    assert R.verifier_prescription(rx("paracetamol", "DR-002"), e)["verdict"] == "BLOQUE"


def test_un_agent_ia_ne_prescrit_jamais():
    e = etat(sexe="M", age=40, allergies="aucune", traitements_en_cours="aucun")
    v = R.verifier_prescription(rx("paracetamol", auteur="assistant"), e)
    assert v["verdict"] == "BLOQUE" and v["constats"][0]["regle"] == "prescripteur_humain"


def test_medicament_non_enregistre_bloque_et_inconnu_insuffisant():
    e = etat(sexe="M", age=40, allergies="aucune", traitements_en_cours="aucun")
    assert R.verifier_prescription(rx("medicament_fictif_x"), e)["verdict"] == "BLOQUE"
    assert R.verifier_prescription(rx("produit_absent"), e)["verdict"] == "PREUVES_INSUFFISANTES"


def test_allergie_declaree_a_revoir():
    e = etat(sexe="M", age=40, allergies="Ibuprofène (urticaire)", traitements_en_cours="aucun")
    assert R.verifier_prescription(rx("ibuprofene"), e)["verdict"] == "A_REVOIR"


def test_tramadol_bloque_seulement_a_distance():
    e = etat(sexe="M", age=40, allergies="aucune", traitements_en_cours="aucun")
    assert R.verifier_prescription(rx("tramadol", mode="distance"), e)["verdict"] == "BLOQUE"
    assert R.verifier_prescription(rx("tramadol", mode="presentiel"), e)["verdict"] == "CONFORME"


# ---------------------------------------------------------------- data
def test_partage_commercial_sans_accord_bloque():
    v = R.verifier_partage_donnees({"finalite": "commerciale", "lieu": "EAU", "consentement_ecrit": False})
    assert v["verdict"] == "BLOQUE" and not v["depassement_possible"]


def test_ia_en_ligne_hors_eau_bloquee():
    v = R.verifier_partage_donnees({"destinataire_type": "service_ia_nuage", "finalite": "soins", "lieu": "hors_EAU"})
    assert v["verdict"] == "BLOQUE" and "L06" in v["lacunes_liees"]


def test_exception_laboratoire_etranger():
    ok = {"finalite": "soins", "lieu": "hors_EAU", "exception_res51": "echantillons", "consentement_ecrit": True,
          "chiffrement": True, "copie_eau": True}
    assert R.verifier_partage_donnees(ok)["verdict"] == "A_REVOIR"
    assert R.verifier_partage_donnees({**ok, "copie_eau": False})["verdict"] == "BLOQUE"


def test_partages_permis_et_non_couverts():
    assert R.verifier_partage_donnees({"finalite": "soins", "destinataire_type": "medecin_traitant", "lieu": "EAU"})["verdict"] == "CONFORME"
    assert R.verifier_partage_donnees({"finalite": "recherche", "anonymise": True, "lieu": "EAU"})["verdict"] == "CONFORME"
    assert R.verifier_partage_donnees({"finalite": "autre", "lieu": "EAU"})["verdict"] == "PREUVES_INSUFFISANTES"


# ---------------------------------------------------------------- sending to the patient and state
def test_message_au_patient_doit_etre_valide_par_le_medecin():
    assert R.verifier_envoi_patient({"texte": "x", "valide_par": None})["verdict"] == "BLOQUE"
    assert R.verifier_envoi_patient({"texte": "x", "valide_par": "DR-001"})["verdict"] == "CONFORME"


def test_maintien_nominatif():
    assert R.autoriser_maintien("A_REVOIR", "DR-001", "Bénéfice supérieur au risque, patiente informée.")[0]
    assert not R.autoriser_maintien("BLOQUE", "DR-001", "x")[0]
    assert not R.autoriser_maintien("A_REVOIR", "DR-002", "x")[0]      # licence inactive
    assert not R.autoriser_maintien("A_REVOIR", "DR-001", "  ")[0]     # justification vide


def test_declaration_maladie_groupe_a():
    regles = {o["regle"] for o in R.obligations_etat(etat(maladie_declarable_groupe="A"))}
    assert "DECLARATION-A" in regles


def test_langue_anglaise():
    r_en = MoteurRegles(KB / "regles_uae.json", BASE, langue="en")
    v = r_en.verifier_partage_donnees({"finalite": "commerciale", "lieu": "EAU"})
    assert v["constats"][0]["detail"].startswith("Non-health use")


# ---------------------------------------------------------------- complete scenarios
def _contexte():
    journal = Journal()
    return Contexte(Dossier(journal), Messagerie(journal, set(BOITES)), journal, R, verbeux=False)


def _lancer(nom, **kw):
    from medimcom.session import Config, construire
    ctx, agents, o = construire(Config(verbeux=False, **kw))
    scenario = json.loads((ICI / "scenarios" / nom).read_text(encoding="utf-8"))
    with redirect_stdout(io.StringIO()):
        o.lancer(scenario)
    return ctx


def _lancer_ancien(nom):
    ctx = _contexte()
    c = CerveauSimule()
    agents = [Traducteur(ctx, c), Assistant(ctx, c), Juriste(ctx, c), AutoriteSante(ctx, c), Hopital(ctx, c), CelluleCrise(ctx, c)]
    scenario = json.loads((ICI / "scenarios" / nom).read_text(encoding="utf-8"))
    with redirect_stdout(io.StringIO()):
        Orchestrateur(ctx, agents).lancer(scenario)
    return ctx


def test_scenario_grossesse():
    ctx = _lancer("grossesse.json")
    verdicts = [(v["objet"], v.get("medicament"), v["verdict"]) for v in ctx.dossier.verdicts]
    assert verdicts == [("envoi_au_patient", None, "CONFORME"),                 # question validated then sent
                        ("prescription", "ibuprofene", "PREUVES_INSUFFISANTES"),
                        ("prescription", "ibuprofene", "A_REVOIR"),
                        ("prescription", "paracetamol", "CONFORME"),
                        ("envoi_au_patient", None, "BLOQUE"),                   # external module without validation
                        ("envoi_au_patient", None, "CONFORME"),                 # explanation validated by the doctor
                        ("partage_de_donnees", None, "BLOQUE"), ("partage_de_donnees", None, "BLOQUE")]
    envoyes = [d for d in ctx.dossier.decisions.values() if d["statut"] == "envoye"]
    assert len(envoyes) == 2 and all(d["auteur"] == "traducteur" and d["valide_par"] == "DR-001" for d in envoyes)
    assert {l["id"] for l in ctx.dossier.lacunes} == {"L01", "L03", "L04", "L05", "L06"}
    assert ctx.journal.verifier() == "Journal intact"


def test_scenario_crise():
    ctx = _lancer("crise.json")
    statuts = {d["id"]: (d.get("medicament") or d["demande"].get("destinataire_type"), d["statut"])
               for d in ctx.dossier.decisions.values()}
    assert sorted(statuts.values()) == sorted([("tramadol", "BLOQUE"), ("autorite_sante", "CONFORME"),
                                               ("laboratoire", "MAINTENUE"), ("public", "BLOQUE"), ("public", "CONFORME")])
    bases = {m["base_legale"] for m in ctx.crise.mesures}
    assert bases == {"CD14-A10", "CD14-A18"} and len(ctx.crise.incidents) == 1
    reponses = [m for m in ctx.messagerie.historique if m.de == "juriste" and m.a == "autorite_sante" and m.repond_a]
    assert any("POD06-A7" in m.contenu for m in reponses) and any("CD14-A18" in m.contenu for m in reponses)
    assert {"L08", "L09"} <= {l["id"] for l in ctx.dossier.lacunes}
    assert ctx.journal.verifier() == "Journal intact"


def test_le_traducteur_n_envoie_rien_sans_validation_et_feu_vert():
    ctx = _contexte()
    t = Traducteur(ctx, CerveauSimule())
    t.executer("proposer_au_medecin", {"texte": "Êtes-vous enceinte ?", "contenu_type": "question"})
    did = max(ctx.dossier.decisions)
    assert t.executer("envoyer_au_patient", {"decision_id": did}).startswith("Refusé")
    assert ctx.dossier.decisions[did]["statut"] == "attente_validation"


def test_une_institution_ne_lit_pas_le_dossier_et_agit_avec_une_base_legale():
    ctx = _contexte()
    a = AutoriteSante(ctx, CerveauSimule())
    assert a.executer("lire_dossier", {}).startswith("Refusé")
    assert a.executer("enregistrer_mesure", {"mesure": "x", "base_legale": "INCONNUE", "justification": "y"}).startswith("Refusé")
    assert a.executer("enregistrer_mesure", {"mesure": "x", "base_legale": "AIA-A73", "justification": "y"}).startswith("Refusé")
    assert a.executer("enregistrer_mesure", {"mesure": "x", "base_legale": "CD14-A18", "justification": "y"}).startswith("Mesure")


def test_mandats_des_institutions():
    from medimcom.agents import MANDATS, THEMES_POUVOIRS
    for nom, m in MANDATS["institutions"].items():
        for f in m["bases_legales"]:
            assert f in BASE.fiches, (nom, f)
    ctx = _contexte()
    c, h = CelluleCrise(ctx, CerveauSimule()), Hopital(ctx, CerveauSimule())
    assert c.executer("enregistrer_mesure", {"mesure": "Couvre-feu", "base_legale": "CD14-A18", "justification": "x"}).startswith("Refusé")
    assert h.executer("enregistrer_mesure", {"mesure": "Zone infectée", "base_legale": "CD14-A18", "justification": "x"}).startswith("Refusé")
    assert h.executer("enregistrer_mesure", {"mesure": "Lit d'isolement", "base_legale": "CD14-A10", "justification": "x"}).startswith("Mesure")


def test_publication_nominative_bloquee_avec_piste():
    v = R.verifier_partage_donnees({"destinataire_type": "public", "anonymise": False, "lieu": "EAU", "finalite": "information_publique"})
    assert v["verdict"] == "BLOQUE" and v["constats"][0]["piste"]
    assert R.verifier_partage_donnees({"destinataire_type": "public", "anonymise": True, "lieu": "EAU",
                                       "finalite": "information_publique"})["verdict"] == "CONFORME"


class CerveauFactice:
    """Imitates a language model: calls tools (one of them forbidden), then finishes."""
    nom = "factice"

    def __init__(self, appels):
        self.appels = list(appels)

    def chat(self, messages, outils):
        assert all(o["type"] == "function" for o in outils)
        if self.appels:
            return {"content": "Je contrôle.", "tool_calls": self.appels.pop(0)}
        return {"content": "", "tool_calls": [("terminer", {"raison": "fini"})]}


def test_boucle_llm_du_juriste_et_garde_fous():
    ctx = _contexte()
    journal = ctx.journal
    for k, v in PATIENTE.items():
        ctx.dossier.maj_etat("test", k, v, "test", True)
    ctx.dossier.maj_etat("test", "grossesse", True, "test", True)
    did = ctx.dossier.ajouter_decision("medecin", {"type": "prescription", **rx("misoprostol")})
    j = Juriste(ctx, CerveauFactice([[("verifier_prescription", {"decision_id": did}),
                                      ("consulter_base", {"question": "abortion pregnancy prescription"}),
                                      ("obligations_etat_patient", {}),
                                      ("mettre_a_jour_etat", {"cle": "grossesse", "valeur": False, "source": "x"})]]))
    assert j.tour()
    assert ctx.dossier.verdicts[-1]["verdict"] == "BLOQUE"
    refus = [l for l in journal.lignes if l["type"] == "action" and str(l["contenu"]["resultat"]).startswith("Refusé")]
    assert refus and refus[0]["contenu"]["outil"] == "mettre_a_jour_etat"
    assert ctx.dossier.etat["grossesse"]["valeur"] is True


# ---------------------------------------------------------------- edge cases (independent review)
def test_validation_par_un_non_medecin_refusee():
    for qui in ("assistant", "DR-002", "n'importe qui"):
        assert R.verifier_envoi_patient({"texte": "x", "valide_par": qui})["verdict"] == "BLOQUE", qui


def test_mode_de_consultation_inconnu_ou_synonyme():
    e = etat(sexe="M", age=40, allergies="aucune", traitements_en_cours="aucun")
    assert R.verifier_prescription(rx("tramadol", mode=None), e)["verdict"] == "PREUVES_INSUFFISANTES"
    assert R.verifier_prescription(rx("tramadol", mode="Téléconsultation"), e)["verdict"] == "BLOQUE"
    e2 = etat(sexe="M", age=40, allergies="aucune", traitements_en_cours="aucun", mode_consultation="distance")
    assert R.verifier_prescription(rx("tramadol", mode=None), e2)["verdict"] == "BLOQUE"


def test_partage_information_manquante_jamais_bloquee_a_tort():
    assert R.verifier_partage_donnees({"finalite": "recherche", "lieu": "EAU"})["verdict"] == "PREUVES_INSUFFISANTES"
    assert R.verifier_partage_donnees({"finalite": "commerciale"})["verdict"] == "PREUVES_INSUFFISANTES"
    assert R.verifier_partage_donnees({"finalite": "recherche", "anonymise": True})["verdict"] == "PREUVES_INSUFFISANTES"
    ok = {"finalite": "soins", "lieu": "hors_EAU", "exception_res51": "x", "consentement_ecrit": True, "chiffrement": True}
    assert R.verifier_partage_donnees(ok)["verdict"] == "PREUVES_INSUFFISANTES"     # copie_eau not filled in


def test_mode_contradictoire_et_entrees_libres():
    e = etat(sexe="M", age=40, allergies="aucune", traitements_en_cours="aucun", mode_consultation="distance")
    v = R.verifier_prescription(rx("tramadol", mode="presentiel"), e)
    assert v["verdict"] == "BLOQUE" and any(c["regle"] == "mode_contradictoire" for c in v["constats"])
    assert R.verifier_partage_donnees({"finalite": "soins", "lieu": "étranger"})["verdict"] == "BLOQUE"
    assert R.verifier_partage_donnees({"finalite": "Commerciale", "lieu": "EAU", "consentement_ecrit": "non"})["verdict"] == "BLOQUE"
    assert R.verifier_envoi_patient({"texte": "x", "valide_par": " dr-001 "})["verdict"] == "CONFORME"
    assert R.verifier_prescription(rx("ibuprofene"), etat(sexe="M", age=40, traitements_en_cours="aucun",
                                                          allergies="aspirine"))["verdict"] == "A_REVOIR"


def test_allergies_classes_negations_et_noms_commerciaux():
    base_e = dict(sexe="M", age=40, traitements_en_cours="aucun")
    assert R.verifier_prescription(rx("ibuprofene"), etat(**base_e, allergies="AINS"))["verdict"] == "A_REVOIR"
    assert R.verifier_prescription(rx("ibuprofene"), etat(**base_e, allergies="pas d'allergie à l'ibuprofène"))["verdict"] == "CONFORME"
    assert R.verifier_prescription(rx("Cytotec"), etat(**PATIENTE, grossesse=True))["verdict"] == "BLOQUE"


def test_l_assistant_ne_peut_pas_confirmer_seul_un_fait():
    ctx = _contexte()
    a = Assistant(ctx, CerveauSimule())
    res = a.executer("mettre_a_jour_etat", {"cle": "grossesse", "valeur": False, "source": "supposition", "confirme": True})
    assert "NON confirmé" in res and ctx.dossier.etat["grossesse"]["confirme"] is False
    ctx.dossier.ajouter_echange("traducteur", "Réponse : [non]", {"grossesse": False}, True)
    a.executer("mettre_a_jour_etat", {"cle": "grossesse", "valeur": False, "source": "échange", "confirme": True})
    assert ctx.dossier.etat["grossesse"]["confirme"] is True


def test_filet_de_securite_si_le_juriste_ne_controle_pas():
    ctx = _contexte()
    journal = ctx.journal
    paresseux = Juriste(ctx, CerveauFactice([]))          # only "finishes"
    o = Orchestrateur(ctx, [paresseux])
    evt = {"type": "partage_donnees", "auteur": "x", "demande": {"finalite": "commerciale", "lieu": "EAU", "consentement_ecrit": False}}
    with redirect_stdout(io.StringIO()):
        o.appliquer(evt)
        o.stabiliser()
        assert o.filet_de_securite() == 1
    assert ctx.dossier.verdicts[-1]["verdict"] == "BLOQUE"
    assert any(l["type"] == "filet_de_securite" for l in journal.lignes)
    assert any(m.a == "medecin" and "BLOQUÉ" in m.contenu for m in ctx.messagerie.historique)


def test_institution_en_mode_llm_ne_voit_que_ses_messages():
    ctx = _contexte()
    ctx.dossier.maj_etat("test", "nom", "Patient X", "test", True)
    vus = []

    class Espion(CerveauFactice):
        def chat(self, messages, outils):
            vus.append(messages[-1]["content"] if messages[-1]["role"] == "user" else "")
            return super().chat(messages, outils)

    h = Hopital(ctx, Espion([[("lire_dossier", {}),
                              ("enregistrer_mesure", {"mesure": "Lit d'isolement", "base_legale": "CD14-A10", "justification": "cas grave"})]]))
    ctx.messagerie.envoyer("terrain", "hopital", "information", "Cas grave transféré.")
    assert h.tour()
    assert "Patient X" not in vus[0] and "TABLEAU DE CRISE" in vus[0]
    assert ctx.crise.mesures and ctx.crise.mesures[0]["base_legale"] == "CD14-A10"
    assert any(l["type"] == "action" and l["contenu"]["outil"] == "lire_dossier" and str(l["contenu"]["resultat"]).startswith("Refusé")
               for l in ctx.journal.lignes)


def _moteur_pictogrammes():
    """Engine under test: the one of MEDIMCOM_PICTOGRAMMES=package.module:Class, otherwise the demo lexicon."""
    import importlib
    import os
    from medimcom.pictogrammes import LexiquePictogrammes
    cible = os.environ.get("MEDIMCOM_PICTOGRAMMES")
    if not cible:
        return LexiquePictogrammes()
    module, classe = cible.split(":")
    return getattr(importlib.import_module(module), classe)()


def test_moteur_pictogrammes_respecte_le_contrat():
    m = _moteur_pictogrammes()
    for texte in ("Êtes-vous enceinte ?", "paracetamol 500 mg, 3 fois par jour pendant 3 jours. Vous êtes d'accord ?",
                  "Avez-vous des allergies ?", "xyzzy inconnu"):
        r = m.traduire(texte)
        assert set(r) >= {"pictogrammes", "non_traduits", "couverture"}, r
        assert all(isinstance(p, str) and p.split(":")[0] == p.split(":")[0].upper() for p in r["pictogrammes"]), r
        assert isinstance(r["non_traduits"], list) and 0.0 <= r["couverture"] <= 1.0
    assert isinstance(m.interpreter(["OUI"]), str) and isinstance(m.interpreter(["NON"]), str)
    assert "OUI" not in m.traduire("xyzzy")["pictogrammes"]        # an unknown word is not invented
    neg, pos = m.traduire("Ne prenez pas ce médicament"), m.traduire("Prenez ce médicament")
    assert neg["pictogrammes"] != pos["pictogrammes"] or neg["non_traduits"], "la négation ne doit jamais disparaître"


def _avec_question_envoyee(cle="grossesse", question="Êtes-vous enceinte ?"):
    ctx = _contexte()
    t = Traducteur(ctx, CerveauSimule())
    ctx.dossier.ajouter_question("assistant", question, "test", cle)
    did = ctx.dossier.ajouter_decision("traducteur", {"type": "envoi_patient", "texte": question, "contenu_type": "question",
                                                      "valide_par": "DR-001", "statut": "envoye", "source_question": 1})
    return ctx, t, did


def test_le_traducteur_ne_rapporte_que_ce_que_le_patient_a_choisi():
    ctx, t, _ = _avec_question_envoyee()
    assert t.executer("rapporter_reponse_patient", {"pictogrammes": ["NON"]}).startswith("Refusé")   # no message from the patient
    t._recevoir([type("M", (), {"de": "patient", "contenu": '{"pictogrammes": ["OUI", "NON"]}'})()])
    t.executer("rapporter_reponse_patient", {"pictogrammes": ["OUI", "NON"]})
    assert "grossesse" not in ctx.dossier.fil[-1]["donnees"]                                          # ambiguous answer
    ctx2, t2, _ = _avec_question_envoyee("allergies", "Avez-vous des allergies ?")
    t2._recevoir([type("M", (), {"de": "patient", "contenu": '{"pictogrammes": ["OUI"]}'})()])
    t2.executer("rapporter_reponse_patient", {"pictogrammes": ["OUI"]})
    # no "allergies = true": YES without detail = "to be specified", which does not count as allergies filled in
    assert ctx2.dossier.fil[-1]["donnees"] in ({}, {"allergies": "oui, à préciser"})
    t2._recevoir([type("M", (), {"de": "patient", "contenu": '{"pictogrammes": ["NON"]}'})()])
    t2.executer("rapporter_reponse_patient", {"pictogrammes": ["NON"]})


def test_pictogrammes_combines_en_une_image():
    import xml.etree.ElementTree as ET
    from medimcom.bibliotheque import combinaison_valide, connu, libelle, svg
    from medimcom.pictogrammes import LexiquePictogrammes
    assert combinaison_valide("TETE+DOULEUR") and combinaison_valide("TETE+DOULEUR+CHIFFRE:8")
    for refus in ("PRENDRE+NE_PAS", "DOSE:500mg+MAXIMUM", "TETE+URGENCE", "TETE+TETE", "TETE+INCONNU", "A+B+C+D", "GEN:x+TETE"):
        assert not connu(refus), refus                                   # negation, limit, emergency: never as a badge
    racine = ET.fromstring(svg("TETE+DOULEUR"))
    assert racine.tag.endswith("svg") and svg("TETE+DOULEUR").count("<circle") >= 1 and "?" not in libelle("TETE+DOULEUR")
    assert ">?<" in svg("PRENDRE+NE_PAS")                                # combination refused: never an invented image
    lex = LexiquePictogrammes()
    assert lex.traduire("Avez-vous mal au ventre ?")["pictogrammes"] == ["VOUS", "VENTRE+DOULEUR", "QUESTION"]
    neg = lex.traduire("Ne prenez pas d'ibuprofène")["pictogrammes"]
    assert "NE_PAS" in neg and not any("+" in x for x in neg)           # the negation stays a whole pictogram


def test_le_traducteur_choisit_ou_combine_ses_pictogrammes_sous_controle():
    ctx = _contexte()
    t = Traducteur(ctx, CerveauSimule())
    r = t.executer("proposer_au_medecin", {"texte": "Avez-vous mal à la tête ?", "contenu_type": "question",
                                           "pictogrammes": ["VOUS", "TETE+DOULEUR", "QUESTION"]})
    assert r.startswith("Proposition"), r
    d = list(ctx.dossier.decisions.values())[-1]
    assert d["pictogrammes"] == ["VOUS", "TETE+DOULEUR", "QUESTION"] and d["pictogrammes_choisis_par"] == "choix de l'agent traducteur"
    assert d["statut"] == "attente_validation"                           # the doctor always validates
    # the agent cannot remove a negation, a dose or a medicine name, nor invent a combination
    assert "NE_PAS" in t.executer("proposer_au_medecin", {"texte": "Ne prenez pas d'ibuprofène", "contenu_type": "information",
                                                           "pictogrammes": ["PRENDRE", "MEDICAMENT:ibuprofene"]})
    assert t.executer("proposer_au_medecin", {"texte": "paracetamol 500 mg le soir", "contenu_type": "information",
                                               "pictogrammes": ["MEDICAMENT:paracetamol", "SOIR"]}).startswith("Refusé")
    # two limits in the text: removing one is refused (counting, not mere presence)
    assert t.executer("proposer_au_medecin", {"texte": "jusqu'à 3 fois par jour, pas plus de 4 comprimés", "contenu_type": "information",
                                               "pictogrammes": ["MAXIMUM", "CHIFFRE:3", "FOIS", "JOUR", "CHIFFRE:4", "COMPRIME"]}).startswith("Refusé")
    assert t.executer("proposer_au_medecin", {"texte": "Ne mangez pas", "contenu_type": "information",
                                               "pictogrammes": ["MANGER+NE_PAS"]}).startswith("Refusé")
    # combined patient answer -> structured facts (pain, location, intensity)
    ctx2, t2, _ = _avec_question_envoyee()
    t2._recevoir([type("M", (), {"de": "patient", "contenu": '{"pictogrammes": ["TETE+DOULEUR", "CHIFFRE:8"]}'})()])
    t2.executer("rapporter_reponse_patient", {"pictogrammes": ["TETE+DOULEUR", "CHIFFRE:8"]})
    assert ctx2.dossier.fil[-1]["donnees"] == {"douleur": True, "localisation_douleur": "tête", "intensite_douleur": 8}
    ctx3, t3, _ = _avec_question_envoyee()
    t3._recevoir([type("M", (), {"de": "patient", "contenu": '{"pictogrammes": ["NON", "VENTRE+DOULEUR"]}'})()])
    t3.executer("rapporter_reponse_patient", {"pictogrammes": ["NON", "VENTRE+DOULEUR"]})
    assert "douleur" not in ctx3.dossier.fil[-1]["donnees"]               # ambiguous meaning: nothing is inferred


def test_image_nouvelle_fournie_par_le_moteur_est_controlee():
    from medimcom import bibliotheque as B
    propre = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><circle cx="60" cy="60" r="40"/></svg>'
    images = {"GEN:pansement": propre,
              "GEN:piege": '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
              "GEN:lien": '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://exemple.invalid/x.png"/></svg>',
              "GEN:anim": '<svg xmlns="http://www.w3.org/2000/svg"><a><animate attributeName="href" values="javascript:alert(1)"/></a></svg>',
              "GEN:style": '<svg xmlns="http://www.w3.org/2000/svg"><style>@import url(https://x.invalid/a.css);</style></svg>',
              "GEN:entite": '<!DOCTYPE svg [<!ENTITY a "aaaa">]><svg xmlns="http://www.w3.org/2000/svg"><text>&a;</text></svg>'}
    try:
        assert not B.connu("GEN:pansement")                              # no engine plugged in: unknown
        B.brancher_images(images.get)
        assert B.connu("GEN:pansement") and B.svg("GEN:pansement") == propre
        for refus in ("GEN:piege", "GEN:lien", "GEN:anim", "GEN:style", "GEN:entite", "GEN:absent"):
            assert not B.connu(refus), refus                             # allow-list: forms and text only
        assert ">?<" in B.svg("GEN:piege") and not B.connu("GEN:pansement+TETE")    # never combined
        ctx = _contexte()
        t = Traducteur(ctx, CerveauSimule())
        r = t.executer("proposer_au_medecin", {"texte": "Gardez le pansement", "contenu_type": "information",
                                               "pictogrammes": ["GEN:pansement"]})
        assert r.startswith("Proposition"), r
        assert list(ctx.dossier.decisions.values())[-1]["statut"] == "attente_validation"
    finally:
        B.brancher_images(None)


def test_base_vectorielle_et_recherche_hybride(tmp_path):
    sys.path.insert(0, str(ICI / "kb" / "outils"))
    from construire_index import morceaux
    from medimcom.base import BaseConnaissances
    from medimcom.vecteurs import EncodeurHachage, IndexVectoriel, fusion_rangs
    base = BaseConnaissances(ICI / "kb")
    ms = list(morceaux(base))
    enc = EncodeurHachage(256)
    idx = IndexVectoriel.construire(ms, enc)
    chemin = tmp_path / "v.jsonl"
    idx.sauver(chemin)
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    tete = json.loads(lignes[0])["_index"]
    assert tete["dimension"] == 256 and tete["morceaux"] == len(ms) == len(lignes) - 1
    assert {"id", "text", "metadata", "embedding"} <= set(json.loads(lignes[1]))        # standard exchange format
    relu = IndexVectoriel.charger(chemin)
    assert relu.empreinte == idx.empreinte and abs(sum(x * x for x in relu.vecteurs[0]) - 1) < 1e-3
    base.brancher_vecteurs(relu, enc)
    for m in ("bm25", "vecteurs", "hybride"):
        r = base.chercher("Can health data be stored outside the UAE?", k=3, methode=m)
        assert len(r) == 3 and all(x["fiche"] in base.fiches for x in r), m              # never a gap nor an unknown id
    assert base.chercher("misoprostol", k=5, mode="crise", methode="vecteurs") == [] or all(
        "crise" in base.fiches[x["fiche"]]["modes"] for x in base.chercher("misoprostol", k=5, mode="crise", methode="vecteurs"))
    assert fusion_rangs(["a", "b"], ["b", "c"])[0][0] == "b"
    perime = IndexVectoriel(ms[:5], idx.vecteurs[:5], enc.nom, "x")
    try:
        BaseConnaissances(ICI / "kb").brancher_vecteurs(perime, enc)
        assert False, "un index périmé doit être refusé"
    except ValueError:
        pass
    # a complete session runs with hybrid search (fallback index shipped in kb/index/)
    ctx = _lancer("crise.json", recherche="hachage")
    assert ctx.journal.verifier() == "Journal intact"


def _png_1x1() -> bytes:
    import struct, zlib
    bloc = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + bloc(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + bloc(b"IEND", b""))


def test_pictogrammes_des_bases_existantes(tmp_path, monkeypatch):
    import shutil
    from medimcom import bibliotheque as B
    from medimcom.pictogrammes import LexiquePictogrammes
    d = tmp_path / "bases"
    shutil.copytree(ICI / "pictogrammes" / "bases", d, ignore=shutil.ignore_patterns("images", "manifeste_externe.json", "*.html"))
    (d / "images" / "arasaac").mkdir(parents=True)
    (d / "images" / "arasaac" / "GORGE.png").write_bytes(_png_1x1())
    (d / "images" / "arasaac" / "TETE.png").write_bytes(b"pas une image")
    man = {"pictogrammes": {
        "GORGE": {"base": "arasaac", "fichier": "images/arasaac/GORGE.png", "url": "https://arasaac.org/pictograms/fr/1",
                  "auteur": "Sergio Palao", "licence": "CC BY-NC-SA 4.0", "attribution": "ARASAAC"},
        "TETE": {"base": "arasaac", "fichier": "images/arasaac/TETE.png", "url": "", "attribution": "x"},
        "INCONNU": {"base": "arasaac", "fichier": "images/arasaac/GORGE.png"},
        "DOS": {"base": "arasaac", "fichier": "../../../etc/passwd"}}}
    (d / "manifeste_externe.json").write_text(json.dumps(man), encoding="utf-8")
    try:
        assert B.charger_bases(d) == 2                                   # INCONNU (outside the vocabulary) and DOS (outside the record) discarded
        assert B.connu("GORGE") and "data:image/png;base64," in B.svg("GORGE") and B.libelle("GORGE", "ar") == "حلق"
        assert "data:image" not in B.svg("TETE")                         # fake PNG: the demo icon is kept
        assert B.connu("GORGE+DOULEUR") and "data:image/png" in B.svg("GORGE+DOULEUR")
        t = LexiquePictogrammes().traduire("Avez-vous mal à la gorge ? Avez-vous peur ?")
        assert t["pictogrammes"][1] == "GORGE+DOULEUR" and t["non_traduits"] == ["peur"]   # no image: reported, not invented
        assert [c["pictogramme"] for c in B.credits()] == ["GORGE", "TETE"] and B.credits()[0]["attribution"] == "ARASAAC"
        monkeypatch.setenv("MEDIMCOM_PICTOS", "demo")
        assert B.charger_bases(d) == 0 and not B.connu("GORGE")         # back to the demo icons
        monkeypatch.delenv("MEDIMCOM_PICTOS")
        # manual import: SantéBD refused without written agreement, dangerous SVG refused, Tawasol accepted
        sys.path.insert(0, str(d))
        import importlib
        imp = importlib.import_module("importer_fichiers")
        imp = importlib.reload(imp)
        imp.ICI = d
        for base, nom, contenu in (("santebd", "DOS.png", _png_1x1()), ("mulberry", "BRAS.svg",
                                   b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'),
                                   ("tawasol", "PEUR.png", _png_1x1())):
            (d / "images" / base).mkdir(exist_ok=True)
            (d / "images" / base / nom).write_bytes(contenu)
        with redirect_stdout(io.StringIO()) as sortie:
            assert imp.main([]) == 1
        assert "accord écrit" in sortie.getvalue() and "SVG refusé" in sortie.getvalue()
        assert B.charger_bases(d) == 3 and B.connu("PEUR") and B.credits()[1]["base"] == "tawasol"
    finally:
        B.charger_bases(ICI / "pictogrammes" / "bases")
        sys.path.remove(str(d)) if str(d) in sys.path else None


def test_telechargement_arasaac_avec_api_simulee(tmp_path):
    import importlib, shutil
    d = tmp_path / "bases"
    shutil.copytree(ICI / "pictogrammes" / "bases", d, ignore=shutil.ignore_patterns("images", "manifeste_externe.json",
                                                                                     "candidats_arasaac.json", "*.html"))
    sys.path.insert(0, str(d))
    try:
        mod = importlib.reload(importlib.import_module("telecharger_arasaac"))
        mod.ICI = d
        appels = []

        def faux_get(url, binaire=False):
            appels.append(url)
            if binaire:
                return _png_1x1()
            return [{"_id": 2001, "keywords": [{"keyword": "gorge"}]}, {"_id": 2002, "keywords": [{"keyword": "cou"}]}]
        mod._get = faux_get
        (d / "choix_arasaac.json").write_text('{"DOS": 2002}', encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            assert mod.main(["--ids", "GORGE", "DOS", "--pause", "0"]) == 0
        man = json.loads((d / "manifeste_externe.json").read_text(encoding="utf-8"))["pictogrammes"]
        assert man["GORGE"]["source_id"] == 2001 and man["DOS"]["source_id"] == 2002 and man["DOS"]["choisi_par"] == "équipe"
        assert man["GORGE"]["auteur"] == "Sergio Palao" and "CC BY-NC-SA" in man["GORGE"]["licence"]
        assert (d / "images" / "arasaac" / "GORGE.png").read_bytes().startswith(b"\x89PNG")
        assert "2002" in (d / "planche_candidats.html").read_text(encoding="utf-8")
        assert any("/fr/bestsearch/gorge" in u for u in appels)
    finally:
        sys.path.remove(str(d))


def test_juriste_en_droit_camerounais():
    from medimcom.regles import MoteurRegles
    cm = MoteurRegles(ICI / "kb" / "regles_cm.json")
    base = cm.base
    # principle: a rule only BLOCKS by citing a law whose content was read (never a "to confirm" source alone)
    def lue(fid):
        f = base.fiches[fid]
        return f["basis"] in ("LOI", "NORME") and base.sources[f["source"]]["verification"] != "to_confirm"
    regles = list(cm._toutes_les_regles()) + [c for m in cm.kb["medicaments"].values() for c in m.get("contre_indications", [])]
    for r in regles:
        if r.get("niveau") == "BLOQUE":
            assert any(lue(f) for f in r["fiches"]), r
    # each country applies only its own texts (plus global references)
    ae = MoteurRegles(ICI / "kb" / "regles_uae.json", base)
    assert cm.applicable("CM90-A2") and not cm.applicable("ICT19-A13") and cm.applicable("CRPD-A21")
    assert ae.applicable("ICT19-A13") and not ae.applicable("CM90-A2") and not ae.applicable("CM-2024")
    # transfers outside Cameroon
    assert cm.verifier_partage_donnees({"lieu": "Émirats", "finalite": "soins"})["verdict"] == "BLOQUE"
    assert cm.verifier_partage_donnees({"lieu": "hors du pays", "finalite": "soins", "autorisation_autorite": "oui"})["verdict"] == "A_REVOIR"
    assert cm.verifier_partage_donnees({"lieu": "Cameroun", "finalite": "soins", "destinataire_type": "hopital"})["verdict"] == "CONFORME"
    # medicine with no known approval: to check, not blocked on a text that was not read
    v = cm.verifier_prescription({**rx("medicament_fictif_x")}, {"sexe": {"valeur": "M", "confirme": True},
                                 "allergies": {"valeur": "aucune", "confirme": True}, "traitements_en_cours": {"valeur": "aucun", "confirme": True}})
    assert v["verdict"] == "PREUVES_INSUFFISANTES"
    # the consultation scenarios run with Cameroonian law
    ctx = _lancer("grossesse.json", pays="CM")
    assert ctx.journal.verifier() == "Journal intact"
    assert "regles_cm.json" in json.dumps(ctx.journal.lignes[0], ensure_ascii=False)          # configuration logged


def test_message_d_une_prescription_devenue_non_conforme_n_est_pas_envoye():
    ctx = _contexte()
    t = Traducteur(ctx, CerveauSimule())
    pid = ctx.dossier.ajouter_decision("medecin", {"type": "prescription", **rx("ibuprofene"), "statut": "A_REVOIR"})
    did = ctx.dossier.ajouter_decision("traducteur", {"type": "envoi_patient", "texte": "x", "contenu_type": "traitement",
                                                      "valide_par": "DR-001", "statut": "CONFORME", "source_prescription": pid})
    assert t.executer("envoyer_au_patient", {"decision_id": did}).startswith("Refusé")
    v = R.verifier_envoi_patient({"texte": "x", "valide_par": "DR-001", "statut_prescription_liee": "A_REVOIR"})
    assert v["verdict"] == "BLOQUE"


def test_reponse_rattachee_seulement_au_dernier_message_envoye():
    ctx, t, _ = _avec_question_envoyee()
    ctx.dossier.ajouter_decision("traducteur", {"type": "envoi_patient", "texte": "Vous êtes d'accord pour un examen ?",
                                                "contenu_type": "question", "valide_par": "DR-001", "statut": "envoye"})
    t._recevoir([type("M", (), {"de": "patient", "contenu": '{"pictogrammes": ["NON"]}'})()])
    t.executer("rapporter_reponse_patient", {"pictogrammes": ["NON"]})
    assert "grossesse" not in ctx.dossier.etat and ctx.dossier.fil[-1]["donnees"] == {}


def test_message_de_traitement_sans_prescription_bloque():
    ctx = _contexte()
    t = Traducteur(ctx, CerveauSimule())
    did = ctx.dossier.ajouter_decision("traducteur", {"type": "envoi_patient", "texte": "misoprostol 200 mg", "contenu_type": "traitement",
                                                      "valide_par": "DR-001", "statut": "CONFORME"})
    assert t.executer("envoyer_au_patient", {"decision_id": did}).startswith("Refusé")
    assert R.verifier_envoi_patient({"texte": "x", "valide_par": "DR-001", "contenu_type": "traitement"})["verdict"] == "BLOQUE"


def test_validation_seulement_par_le_medecin_et_sans_ambiguite():
    ctx = _contexte()
    o = Orchestrateur(ctx, [])
    for q in ("Q1 ?", "Q2 ?"):
        ctx.dossier.ajouter_decision("traducteur", {"type": "envoi_patient", "texte": q, "contenu_type": "question",
                                                    "valide_par": None, "statut": "attente_validation", "pictogrammes": ["QUESTION"]})
    assert o._valider({"auteur": "assistant", "medecin": "DR-001"}).startswith("Refusé")
    assert o._valider({"auteur": "medecin", "medecin": "DR-001", "contenu_type": "question"}).startswith("Refusé")
    assert o._valider({"auteur": "medecin", "medecin": "DR-001", "decision_id": 1}).startswith("Proposition #1")


def test_institutions_limitees():
    ctx = _contexte()
    h = Hopital(ctx, CerveauSimule())
    h.executer("demander_donnees", {"finalite": "sante_publique", "destinataire_type": "autorite_sante", "lieu": "EAU", "texte": "x"})
    assert ctx.dossier.decisions[max(ctx.dossier.decisions)]["demande"]["destinataire_type"] == "hopital"
    for base_legale in ("ML16-A3", "RES51-COND", "ML16-A5-1", "CD14-A29"):
        assert h.executer("enregistrer_mesure", {"mesure": "Confinement total", "base_legale": base_legale, "justification": "x"}).startswith("Refusé")
    a = Assistant(ctx, CerveauSimule())
    assert a.executer("envoyer_message", {"destinataire": "autorite_sante", "type": "information", "contenu": "patiente X"}).startswith("Refusé")
    ctx.dossier.maj_etat("test", "nom", "Fatima Test", "test", True)
    j = Juriste(ctx, CerveauSimule())
    assert j.executer("envoyer_message", {"destinataire": "hopital", "type": "information", "contenu": "Cas : Fatima Test"}).startswith("Refusé")
    assert R.verifier_partage_donnees({"finalite": "soins", "destinataire_type": "hopital", "lieu": "EAU"})["verdict"] == "CONFORME"


# ---------------------------------------------------------------- robustness of the LLM loop and engines
def test_conformer_les_arguments_d_un_modele():
    from medimcom.agents import conformer, _schema
    sc = _schema("x", "", {"decision_id": {"type": "integer"}, "ok": {"type": "boolean"},
                           "t": {"type": "string", "enum": ["a", "b"]}}, ["decision_id"])
    assert conformer(sc, {"decision_id": "#3", "ok": "oui", "inconnu": 1}) == ({"decision_id": 3, "ok": True}, None)
    assert conformer(sc, {})[1].startswith("argument(s) obligatoire")
    assert "n'est pas parmi" in conformer(sc, {"decision_id": 1, "t": "c"})[1]
    assert "incompatible" in conformer(sc, {"decision_id": "trois"})[1]


def test_appels_ecrits_dans_le_texte_et_reflexion():
    from medimcom.cerveaux import appels_dans_le_texte, separer_reflexion
    texte, refl = separer_reflexion("<think>je dois vérifier</think>Je vérifie.")
    assert texte == "Je vérifie." and refl == "je dois vérifier"
    t = 'Voici : <tool_call>{"name": "verifier_prescription", "arguments": {"decision_id": "2"}}</tool_call>'
    assert appels_dans_le_texte(t, {"verifier_prescription"}) == [("verifier_prescription", {"decision_id": "2"})]
    assert appels_dans_le_texte('```json\n{"name": "inconnu", "arguments": {}}\n```', {"terminer"}) == []


class CerveauTexte:
    """Small clumsy model: reasons in <think>, writes the call in the text, with an identifier as text."""
    nom, modele = "texte", "faux-modele"

    def __init__(self, decision_id):
        self.n, self.did = 0, decision_id

    def chat(self, messages, outils):
        self.n += 1
        if self.n == 1:
            return {"content": f'<think>contrôler</think><tool_call>{{"name": "verifier_prescription", "arguments": {{"decision_id": "{self.did}"}}}}</tool_call>',
                    "tool_calls": []}
        return {"content": "", "tool_calls": [("terminer", {})]}


def test_boucle_llm_tolere_un_modele_maladroit():
    ctx = _contexte()
    for k, v in PATIENTE.items():
        ctx.dossier.maj_etat("test", k, v, "test", True)
    did = ctx.dossier.ajouter_decision("medecin", {"type": "prescription", **rx("paracetamol")})
    j = Juriste(ctx, CerveauTexte(did))
    j.tour()
    assert ctx.dossier.decisions[did]["statut"] in ("CONFORME", "PREUVES_INSUFFISANTES")
    types = {l["type"] for l in ctx.journal.lignes}
    assert {"reflexion_modele", "appel_extrait_du_texte"} <= types


def test_boucle_llm_detecte_les_appels_repetes():
    ctx = _contexte()
    j = Juriste(ctx, CerveauFactice([[("consulter_base", {"question": "x"})]] * 5))
    ctx.messagerie.envoyer("medecin", "juriste", "demande", "question")
    j.tour()
    assert any(l["type"] == "boucle_detectee" for l in ctx.journal.lignes)


class CerveauEnPanne:
    nom, modele = "panne", "modele-arrete"

    def __init__(self):
        self.appels = 0

    def chat(self, messages, outils):
        self.appels += 1
        raise ConnectionError("serveur arrêté")


def test_degradation_gracieuse_si_le_modele_tombe():
    Juriste.PAUSE_AVANT_NOUVEL_ESSAI = 0
    ctx = _contexte()
    ctx.messagerie.envoyer("medecin", "juriste", "demande", "Dans quel délai déclarer une maladie du groupe A ?")
    j = Juriste(ctx, CerveauEnPanne())
    with redirect_stdout(io.StringIO()):
        assert j.tour()
    assert any(l["type"] == "degradation" for l in ctx.journal.lignes)
    assert any(m.de == "juriste" and m.a == "medecin" for m in ctx.messagerie.historique)   # answer anyway
    ctx.repli_sans_ia = False
    ctx.messagerie.envoyer("medecin", "juriste", "demande", "x")
    try:
        j.tour()
        assert False, "aurait dû lever l'erreur"
    except ConnectionError:
        pass


def test_cerveau_compatible_openai_avec_un_faux_serveur():
    from medimcom.cerveaux import CerveauOpenAI
    recus = []

    class Faux(SimpleHTTPRequestHandler):
        def do_POST(self):
            corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            recus.append(corps)
            if len(recus) == 1:
                msg = {"role": "assistant", "content": "Je contrôle.",
                       "tool_calls": [{"id": "x1", "type": "function",
                                       "function": {"name": "verifier_partage_donnees", "arguments": '{"decision_id": 1}'}}]}
            else:
                msg = {"role": "assistant", "content": "Fini.", "tool_calls": []}
            data = json.dumps({"choices": [{"message": msg}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    serveur = ThreadingHTTPServer(("127.0.0.1", 0), Faux)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    ctx = _contexte()
    ctx.dossier.ajouter_decision("x", {"type": "partage_donnees", "demande": {"finalite": "commerciale", "lieu": "EAU", "consentement_ecrit": False}})
    j = Juriste(ctx, CerveauOpenAI(f"http://127.0.0.1:{serveur.server_address[1]}/v1", "faux"))
    j.tour()
    serveur.shutdown()
    assert ctx.dossier.verdicts[-1]["verdict"] == "BLOQUE"
    second = recus[1]["messages"]
    assert any(m["role"] == "tool" and m["tool_call_id"] == "a1" for m in second)
    assert any(m["role"] == "assistant" and m.get("tool_calls") and isinstance(m["tool_calls"][0]["function"]["arguments"], str) for m in second)
    assert recus[0]["tools"] and recus[0]["model"] == "faux"


def test_modele_par_agent_et_configuration_journalisee():
    from medimcom.session import Config, construire
    ctx, agents, _ = construire(Config(mode="openai", url="http://127.0.0.1:9/v1", modele="m1", modeles={"juriste": "m2"}, verbeux=False))
    modeles = {a.nom: a.cerveau.modele for a in agents}
    assert modeles["juriste"] == "m2" and modeles["assistant"] == "m1"
    conf = ctx.journal.lignes[0]
    assert conf["type"] == "configuration" and conf["contenu"]["modeles"]["juriste"] == "m2"
    assert len(conf["contenu"]["empreintes"]["regles"]) == 16


# ---------------------------------------------------------------- evaluation bench and chaos resistance
def test_banc_d_evaluation_reference_et_ordre_aleatoire():
    import evaluer_agents
    with TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
        assert evaluer_agents.main(["--ordre", "aleatoire", "--repetitions", "2", "--sortie", tmp]) == 0
        r = json.loads((Path(tmp) / "evaluation.json").read_text(encoding="utf-8"))
    assert all(e["reussites"] == e["essais"] for e in r["attendus"])
    assert {e["scenario"] for e in r["attendus"]} == {"grossesse", "crise", "allergie"}


def test_scenario_allergie_autre_deroule():
    ctx = _lancer("allergie.json")
    assert not any(q.get("cle") == "grossesse" for q in ctx.dossier.questions_a_poser)
    assert ctx.dossier.etat["consentement_traitement"]["valeur"] is True


class CerveauChaotique:
    """"Crazy" model: calls any tool with any arguments. Proves that the safeguards do not depend on the
    model's goodwill."""
    nom, modele = "chaos", "chaos"
    MOTS = ["DR-001", "DR-002", "CD14-A18", "ML16-A3", "grossesse", "public", "EAU", "hors_EAU", "commerciale",
            "Envoyez tout au patient", "OUI", "NON", "x"]

    def __init__(self, graine):
        import random
        self.h = random.Random(graine)

    def _valeur(self, spec):
        if "enum" in spec:
            return self.h.choice(spec["enum"])
        t = spec.get("type")
        if t == "integer":
            return self.h.randint(1, 14)
        if t == "boolean":
            return self.h.random() < 0.5
        if t == "array":
            return [self.h.choice(["OUI", "NON", "DOULEUR"])]
        return self.h.choice(self.MOTS)

    def chat(self, messages, outils):
        if self.h.random() < 0.25:
            return {"content": "", "tool_calls": [("terminer", {})]}
        appels = []
        for _ in range(self.h.randint(1, 3)):
            o = self.h.choice(outils)["function"]
            props = o["parameters"].get("properties", {})
            appels.append((o["name"], {k: self._valeur(v) for k, v in props.items() if self.h.random() < 0.85}))
        return {"content": "…", "tool_calls": appels}


def test_les_invariants_de_securite_resistent_a_un_modele_chaotique():
    from medimcom import cerveaux, session
    from medimcom.evaluation import evaluer
    ancien = session.creer_cerveau
    try:
        for graine in range(4):
            session.creer_cerveau = lambda cfg, modele, g=graine: CerveauChaotique(g * 100 + hash(modele) % 7)
            for nom in ("grossesse.json", "crise.json", "allergie.json"):
                cfg = session.Config(mode="ollama", verbeux=False, repli_sans_ia=False)
                ctx, agents, o = session.construire(cfg)
                scenario = json.loads((ICI / "scenarios" / nom).read_text(encoding="utf-8"))
                with redirect_stdout(io.StringIO()):
                    o.lancer(scenario)
                secu = [r for r in evaluer({}, ctx) if r["categorie"] == "securite"]
                assert all(r["ok"] for r in secu), (graine, nom, [r for r in secu if not r["ok"]])
    finally:
        session.creer_cerveau = ancien


def test_export_html_du_journal():
    import exporter_journal
    ctx = _lancer("crise.json")
    with TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "j.json", Path(tmp) / "j.html"
        ctx.journal.sauver(src)
        assert exporter_journal.exporter(src, dst) == "Journal intact"
        page = dst.read_text(encoding="utf-8")
        assert "Journal intact" in page and "CD14-A18" in page and "configuration" in page
        lignes = json.loads(src.read_text(encoding="utf-8"))
        lignes[5]["contenu"] = "falsifié"
        src.write_text(json.dumps(lignes), encoding="utf-8")
        assert exporter_journal.exporter(src, dst).startswith("Ligne 6")
        assert "✘" in dst.read_text(encoding="utf-8")


def test_disjoncteur_apres_echecs_consecutifs():
    Juriste.PAUSE_AVANT_NOUVEL_ESSAI = 0
    ctx = _contexte()
    cerveau = CerveauEnPanne()
    j = Juriste(ctx, cerveau)
    with redirect_stdout(io.StringIO()):
        for i in range(6):
            ctx.messagerie.envoyer("medecin", "juriste", "demande", f"question {i}")
            j.tour()
    assert cerveau.appels == 6            # 3 turns × 2 attempts, then no more model calls
    assert any(l["type"] == "degradation" and "hors service" in str(l["contenu"]) for l in ctx.journal.lignes)


def test_disjoncteur_par_modele_et_verification_de_sante():
    from medimcom.session import Config, construire
    import contextlib
    with contextlib.redirect_stderr(io.StringIO()):
        ctx, agents, _ = construire(Config(mode="openai", url="http://127.0.0.1:9/v1", modele="m1", verbeux=False))
    assert ctx.echecs_modele.get("m1") == ctx.seuil_echecs                 # missing server detected at once
    assert any(l["type"] == "modele_indisponible" for l in ctx.journal.lignes)
    ctx2 = _contexte()
    ctx2.echecs_modele["modele-arrete"] = ctx2.seuil_echecs
    j = Juriste(ctx2, CerveauFactice([[("consulter_base", {"question": "x"})]]))
    ctx2.messagerie.envoyer("medecin", "juriste", "demande", "q")
    j.tour()
    assert any(l["type"] == "action" and l["contenu"]["outil"] == "consulter_base" for l in ctx2.journal.lignes)   # the other model goes on


def test_invariant_d_envoi_verifie_sur_le_journal():
    from medimcom.evaluation import verifier
    ctx = _contexte()
    did = ctx.dossier.ajouter_decision("traducteur", {"type": "envoi_patient", "texte": "x", "contenu_type": "question",
                                                      "valide_par": "DR-001", "statut": "envoye"})
    ctx.dossier._changer("traducteur", "envoye_au_patient", {"id": did})     # falsified state, without validation in the journal
    ok, _ = verifier({"type": "aucun_envoi_sans_validation"}, ctx)
    assert not ok
    ctx2 = _contexte()
    ctx2.dossier.ajouter_decision("traducteur", {"type": "envoi_patient", "texte": "x", "contenu_type": "question",
                                                 "valide_par": "DR-001", "statut": "envoye"})       # state modified, nothing in the journal
    assert not verifier({"type": "aucun_envoi_sans_validation"}, ctx2)[0]


def test_pas_de_proposition_en_double_ni_d_accumulation():
    ctx, t, _ = _avec_question_envoyee()
    ctx.dossier.ajouter_question("assistant", "Avez-vous de la fièvre ?", "x", "fievre")
    assert t.executer("proposer_au_medecin", {"texte": "Q", "contenu_type": "question", "question_id": 2}).startswith("Proposition")
    assert t.executer("proposer_au_medecin", {"texte": "Q", "contenu_type": "question", "question_id": 2}).startswith("Refusé")
    for i in range(10):
        t.executer("proposer_au_medecin", {"texte": f"info {i}", "contenu_type": "information"})
    libres = sum(1 for x in ctx.dossier.decisions.values() if x["statut"] == "attente_validation" and not x.get("source_question"))
    assert libres == Traducteur.MAX_LIBRES
    ctx.dossier.ajouter_question("assistant", "Avez-vous des allergies ?", "x", "allergies")     # slot reserved for questions
    assert t.executer("proposer_au_medecin", {"texte": "Q3", "contenu_type": "question", "question_id": 3}).startswith("Proposition")


def test_le_medecin_peut_rejeter_une_proposition():
    ctx, t, _ = _avec_question_envoyee()
    ctx.dossier.ajouter_question("assistant", "Avez-vous de la fièvre ?", "x", "fievre")
    t.executer("proposer_au_medecin", {"texte": "Q", "contenu_type": "question", "question_id": 2})
    o = Orchestrateur(ctx, [t])
    did = max(ctx.dossier.decisions)
    assert o._rejeter({"auteur": "assistant", "decision_id": did}).startswith("Refusé")
    assert o._rejeter({"auteur": "medecin", "decision_id": did, "raison": "mal formulé"}).startswith("Proposition")
    assert t.executer("proposer_au_medecin", {"texte": "Q bis", "contenu_type": "question", "question_id": 2}).startswith("Proposition")


def test_evaluation_signale_un_serveur_absent():
    import evaluer_agents
    Juriste.PAUSE_AVANT_NOUVEL_ESSAI = 0
    from medimcom.agents import Agent
    Agent.PAUSE_AVANT_NOUVEL_ESSAI = 0
    with TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
        import contextlib
        with contextlib.redirect_stderr(io.StringIO()):
            assert evaluer_agents.main(["--mode", "openai", "--url", "http://127.0.0.1:9/v1", "--scenarios",
                                        str(ICI / "scenarios" / "allergie.json"), "--sortie", tmp]) == 2
            assert evaluer_agents.main(["--mode", "openai", "--url", "http://127.0.0.1:9/v1", "--sans-repli", "--scenarios",
                                        str(ICI / "scenarios" / "allergie.json"), "--sortie", tmp]) == 2
        r = json.loads((Path(tmp) / "evaluation.json").read_text(encoding="utf-8"))
    assert "NOT MEASURED" in r["resume"]


# ---------------------------------------------------------------- pictograms and interface
def test_bibliotheque_couvre_le_vocabulaire_et_produit_du_svg_valide():
    import xml.etree.ElementTree as ET
    from medimcom.bibliotheque import CATALOGUE, connu, libelle, svg
    from medimcom.pictogrammes import LexiquePictogrammes, MOTS
    assert all(connu(v) for v in MOTS.values() if v)
    for t in ("paracetamol 500 mg, 3 fois par jour. Vous êtes d'accord ?", "Ne prenez pas d'ibuprofène", "Avez-vous mal à la tête ?"):
        assert all(connu(p) for p in LexiquePictogrammes().traduire(t)["pictogrammes"]), t
    lim = LexiquePictogrammes().traduire("jusqu'à 3 fois par jour, pas plus de 4 comprimés")["pictogrammes"]
    assert lim.count("MAXIMUM") == 2 and "PLUS" not in lim          # a dose limit is never lost
    for ident in list(CATALOGUE) + ["CHIFFRE:10", "DOSE:500mg", "MEDICAMENT:paracetamol", "INCONNU", "DOSE:<script>"]:
        racine = ET.fromstring(svg(ident))
        assert racine.tag.endswith("svg")
        assert "<script" not in svg(ident)
    assert all(libelle(i, lg) for i in CATALOGUE for lg in ("fr", "en", "ar"))


def test_livret_de_test_ne_souffle_pas_les_reponses():
    sys.path.insert(0, str(ICI / "pictogrammes"))
    import livret
    items = livret.plan(2026)
    from medimcom.bibliotheque import CATALOGUE
    assert len([i for i in items if i["categorie"] != "sequence"]) == len(CATALOGUE) and len([i for i in items if i["categorie"] == "sequence"]) == 10
    page = livret.html_livret(items)
    corps = page.split("Consentement", 1)[1]
    for i in items[:len(CATALOGUE)]:
        assert f"<title>{i['sens_attendu']}</title>" not in corps and f'aria-label="{i["sens_attendu"]}"' not in corps
    assert livret.plan(2026) == items and livret.plan(7) != items         # fixed order by seed


def test_analyse_des_tests_de_comprehension():
    sys.path.insert(0, str(ICI / "pictogrammes"))
    import analyse_tests
    cle = {"P01": {"pictogramme": "DOULEUR", "sens_attendu": "douleur"}, "P02": {"pictogramme": "VENTRE", "sens_attendu": "ventre"}}
    rep = [{"participant": f"X{k}", "item": "P01", "code_juge1": "C", "code_juge2": "C"} for k in range(18)]
    rep += [{"participant": f"X{k}", "item": "P01", "code_juge1": "F", "code_juge2": "F"} for k in range(18, 20)]
    rep += [{"participant": f"X{k}", "item": "P02", "code_juge1": "C" if k < 8 else "N", "code_juge2": "C" if k < 8 else "N"} for k in range(20)]
    rep += [{"participant": "X1", "item": "P02", "code_juge1": "C", "code_juge2": "F"},
            {"participant": "X2", "item": "P09", "code_juge1": "C", "code_juge2": ""},
            {"participant": "X3", "item": "P01", "code_juge1": "Z", "code_juge2": ""}]
    r = analyse_tests.analyser(rep, cle)
    it = {x["item"]: x for x in r["items"]}
    assert it["P01"]["correct"] == 0.9 and it["P01"]["decision"] == "accepté"
    assert it["P02"]["correct"] == 0.4 and it["P02"]["decision"] == "à remplacer" and it["P02"]["ne_sait_pas"] == 0.6
    assert len(r["desaccords"]) == 1 and len(r["erreurs"]) == 2
    assert 0 < r["kappa_juges"] < 1
    lo, hi = analyse_tests.wilson(18, 20)
    assert 0.68 < lo < 0.70 and 0.97 < hi < 0.98
    # disagreement settled by consensus: counted with the chosen code; item seen by 12 people: provisional decision
    rep2 = [{"participant": f"Y{k}", "item": "P01", "code_juge1": "C", "code_juge2": "C"} for k in range(11)]
    rep2 += [{"participant": "Y11", "item": "P01", "code_juge1": "C", "code_juge2": "P", "code_consensus": "c"}]
    r2 = {x["item"]: x for x in analyse_tests.analyser(rep2, cle)["items"]}
    assert r2["P01"]["n"] == 12 and r2["P01"]["correct"] == 1.0 and r2["P01"]["decision"] == "accepté (provisoire)"
    assert "→ C" in analyse_tests.rapport_md(analyse_tests.analyser(rep2, cle))


def _serveur_interface(demo=None, interface="auto"):
    sys.path.insert(0, str(ICI / "interface"))
    import serveur
    from medimcom.session import Config
    app = serveur.Application(Config(verbeux=False), demo, interface)
    srv = serveur.creer_serveur(app, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    global _JETON
    _JETON = app.jeton
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


_JETON = ""


def _http(url, corps=None, entetes=None, brut=None):
    """Test request; sends the doctor token by default (entetes can remove it or simulate others)."""
    import urllib.request
    h = {"Content-Type": "application/json", "X-Jeton": _JETON} if entetes is None else entetes
    data = brut if brut is not None else (json.dumps(corps).encode() if corps is not None else None)
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        brut = r.read().decode("utf-8")
        return json.loads(brut) if "json" in r.headers.get("Content-Type", "") else brut


def test_interface_parcours_complet_par_l_api():
    srv, u = _serveur_interface(interface="classique")
    try:
        assert "lien privé" in _http(u + "/") and "/api/patient" in _http(u + "/patient")
        assert "écran médecin" in _http(u + "/medecin?jeton=" + _JETON)
        assert _http(u + "/pictos/DOULEUR.svg").startswith("<svg")
        _http(u + "/api/medecin/faits", {"donnees": {"sexe": "F", "age": "25", "allergies": "aucune", "traitements_en_cours": "aucun",
                                                     "moyen_communication": "pictogrammes", "informe_usage_ia": True}})
        v = _http(u + "/api/medecin")
        q = next(q for q in v["questions"] if q.get("cle") == "grossesse")             # the assistant prepared the question…
        assert not [d for d in v["decisions"] if d["statut"] == "attente_validation"], "…sans encombrer la conversation"
        _http(u + "/api/medecin/poser_question", {"question_id": q["id"], "modifier": True, "medecin": "DR-001"})
        v = _http(u + "/api/medecin")
        prop = [d for d in v["decisions"] if d["statut"] == "attente_validation"]
        assert prop and prop[0]["pictogrammes"] == ["VOUS", "ENCEINTE", "QUESTION"]      # the doctor picked it, agent 1 translated it
        assert _http(u + "/api/patient")["messages"] == []                              # nothing is sent without validation
        _http(u + "/api/medecin/valider", {"decision_id": prop[0]["id"], "medecin": "DR-001"})
        p = _http(u + "/api/patient")
        assert p["messages"][-1]["pictogrammes"] == ["VOUS", "ENCEINTE", "QUESTION"] and p["attend_reponse"]
        _http(u + "/api/patient/reponse", {"pictogrammes": ["OUI"]})
        assert _http(u + "/api/medecin")["etat"]["grossesse"]["valeur"] is True
        _http(u + "/api/medecin/prescription", {"medicament": "ibuprofene", "dose": "400 mg", "posologie": "3 fois par jour", "mode": "presentiel"})
        v = _http(u + "/api/medecin")
        assert [d["statut"] for d in v["decisions"] if d.get("medicament") == "ibuprofene"] == ["A_REVOIR"]
        assert any(m["de"] == "juriste" and m["type"] == "alerte" for m in v["messages"])
        _http(u + "/api/medecin/message", {"texte": "Ne prenez pas d'ibuprofène", "question": False})
        prop = [d for d in _http(u + "/api/medecin")["decisions"] if d["statut"] == "attente_validation"]
        assert "NE_PAS" in prop[-1]["pictogrammes"]
        _http(u + "/api/medecin/rejeter", {"decision_id": prop[-1]["id"], "raison": "test"})
        _http(u + "/api/patient/reponse", {"pictogrammes": ["URGENCE"]})
        v = _http(u + "/api/medecin")
        assert v["etat"]["urgence"]["valeur"] is True
        assert any(s["type"] == "alerte_urgence" for s in v["suggestions"])
        assert v["journal"] == "Journal intact" and "Journal intact" in _http(u + "/journal")
        try:
            _http(u + "/api/patient/reponse", {"pictogrammes": []})
            assert False
        except Exception as e:
            assert "400" in str(e)
    finally:
        srv.shutdown()


def test_interface_refuse_les_requetes_d_autres_pages():
    import urllib.error
    srv, u = _serveur_interface()
    try:
        def code(url, corps=None, entetes=None, brut=None):
            try:
                _http(url, corps, entetes, brut)
                return 200
            except urllib.error.HTTPError as e:
                return e.code
        sans_jeton = {"Content-Type": "application/json"}
        assert code(u + "/medecin", entetes={}) == 403 and code(u + "/api/medecin", entetes={}) == 403 and code(u + "/journal", entetes={}) == 403
        assert code(u + "/medecin?jeton=faux", entetes={}) == 403
        assert code(u + "/api/medecin/faits", {"donnees": {"age": 3}}, sans_jeton) == 403
        assert code(u + "/api/reinitialiser", {}, sans_jeton) == 403
        # another web page: text/plain form, or JSON from another origin -> refused, even with the right token
        assert code(u + "/api/patient/reponse", entetes={"Content-Type": "text/plain"}, brut=b'{"pictogrammes":["OUI"]}') == 403
        assert code(u + "/api/medecin/valider", {"decision_id": 1}, {"Content-Type": "application/json", "X-Jeton": _JETON,
                                                                   "Origin": "http://exemple.invalid"}) == 403
        # DNS rebinding: a foreign domain name as Host is refused, even for the patient's answer
        port = u.rsplit(":", 1)[1]
        assert code(u + "/api/patient/reponse", {"pictogrammes": ["URGENCE"]}, {"Content-Type": "application/json", "Host": f"evil.test:{port}",
                                                                              "Origin": f"http://evil.test:{port}"}) == 403
        assert code(u + "/patient", entetes={"Host": f"evil.test:{port}"}) == 403
        assert code(u + "/patient", entetes={"Host": f"localhost:{port}"}) == 200
        assert code(u + "/patient", entetes={"Host": f"192.168.1.20:{port}"}) == 200
        assert "urgence" not in _http(u + "/api/medecin")["etat"]
        assert code(u + "/api/patient/reponse", {"pictogrammes": ["PRENDRE+NE_PAS"]}) == 400   # combinaison interdite
        assert code(u + "/api/patient/reponse", {"pictogrammes": ["<img>"]}) == 400
        import urllib.request
        with urllib.request.urlopen(u + "/pictos/TETE%2BDOULEUR.svg", timeout=10) as r:
            assert "default-src 'none'" in r.headers["Content-Security-Policy"] and r.read().startswith(b"<svg")
        # malformed bodies -> 400, no dropped connection
        assert code(u + "/api/medecin/faits", brut=b"[1, 2]") == 400
        assert code(u + "/api/medecin/faits", {"donnees": [1, 2]}) == 400
        assert code(u + "/api/patient/reponse", brut=b"pas du json") == 400
        assert code(u + "/api/medecin/faits", {"donnees": {"age": "30"}}) == 200
        assert _http(u + "/api/medecin")["journal"] == "Journal intact"
    finally:
        srv.shutdown()


def test_interface_nouvelle_consultation_change_de_session():
    srv, u = _serveur_interface()
    try:
        s1 = _http(u + "/api/patient")["session"]
        _http(u + "/api/reinitialiser", {})
        assert _http(u + "/api/patient")["session"] != s1 and _http(u + "/api/medecin")["session"] != s1
    finally:
        srv.shutdown()


def test_interface_mode_demonstration():
    srv, u = _serveur_interface(ICI / "scenarios" / "grossesse.json")
    try:
        etapes = 0
        while not _http(u + "/api/demo/suivant", {}).get("fini"):
            etapes += 1
        v = _http(u + "/api/medecin")
        assert v["demo"]["etape"] == v["demo"]["total"] and v["journal"] == "Journal intact"
        assert sum(1 for d in v["decisions"] if d["statut"] == "envoye") == 2
    finally:
        srv.shutdown()


def test_interface_dans_un_vrai_navigateur():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return                                           # browser not installed: test skipped
    srv, u = _serveur_interface()
    erreurs = []
    try:
        with sync_playwright() as p:
            try:
                b = p.chromium.launch()
            except Exception:
                return
            m, pt = b.new_page(), b.new_page()
            for page in (m, pt):
                page.on("pageerror", lambda e: erreurs.append(str(e)))
            m.goto(u + "/medecin?jeton=" + _JETON)
            m.select_option("#sexe", "M"); m.fill("#age", "40"); m.fill("#allergies", "aucune"); m.fill("#traitements", "aucun")
            m.click("#faits"); m.wait_for_timeout(300)
            m.fill("#message", "Avez-vous de la fièvre ?"); m.select_option("#cle", "fievre"); m.click("#envoyerMessage")
            m.wait_for_selector("button[data-valider]", timeout=5000); m.click("button[data-valider]")
            pt.goto(u + "/patient"); pt.wait_for_selector(".recu img", timeout=5000)
            pt.click("button[data-picto='OUI']"); pt.click("#envoyer"); pt.wait_for_timeout(500)
            assert _http(u + "/api/medecin")["etat"]["fievre"]["valeur"] is True
            # the patient combines HEAD + PAIN in one image, adds intensity 8 and sends
            pt.click("button[data-onglet='corps']"); pt.click("button[data-picto='TETE']")
            pt.click("button[data-onglet='symptomes']"); pt.click("button[data-picto='DOULEUR']")
            pt.click("#combiner"); assert pt.locator("#choisis img").count() == 1
            pt.click("button[data-onglet='intensite']"); pt.click("button[data-picto='CHIFFRE:8']")
            pt.click("#envoyer"); pt.wait_for_timeout(600)
            etat = _http(u + "/api/medecin")["etat"]
            assert etat["localisation_douleur"]["valeur"] == "tête" and etat["intensite_douleur"]["valeur"] == 8
            # emergency: red banner on the doctor side
            pt.click("#urgence"); pt.click("#urgOui"); m.wait_for_selector("#urgence:not([hidden])", timeout=5000)
            # new consultation: the patient does see the FIRST message of the new session (same id as before)
            m.click("#reinit"); m.click("#confirmerReinit"); m.wait_for_timeout(600)
            assert m.input_value("#age") == "" and m.is_hidden("#urgence")
            pt.wait_for_selector(".attente", timeout=5000)
            m.fill("#message", "Avez-vous de la fièvre ?"); m.select_option("#cle", "fievre"); m.click("#envoyerMessage")
            m.wait_for_selector("button[data-valider]", timeout=5000); m.click("button[data-valider]")
            pt.wait_for_selector(".recu .bande img", timeout=5000)
            b.close()
        assert erreurs == []
    finally:
        srv.shutdown()


def test_interface_react_et_classique():
    import urllib.error
    import urllib.request
    srv, u = _serveur_interface()
    try:
        if not srv.RequestHandlerClass.app.react:
            return                                       # React interface not built: nothing to check here
        with urllib.request.urlopen(u + "/patient") as r:
            page = r.read().decode()
            assert '<div id="root">' in page and "script-src 'self'" in r.headers["Content-Security-Policy"]
            assert r.headers["Referrer-Policy"] == "no-referrer"
        actif = next(x for x in page.split('"') if x.startswith("/assets/") and x.endswith(".js"))
        with urllib.request.urlopen(u + actif) as r:
            assert r.headers["Content-Type"].startswith("text/javascript")
        for chemin in ("/assets/..%2F..%2Fserveur.py", "/assets/inexistant.js", "/assets/.cache"):
            try:
                urllib.request.urlopen(u + chemin)
                raise AssertionError(chemin)
            except urllib.error.HTTPError as e:
                assert e.code == 404
        try:                                             # the doctor screen stays protected by its token
            urllib.request.urlopen(u + "/medecin")
            raise AssertionError("jeton")
        except urllib.error.HTTPError as e:
            assert e.code == 403
    finally:
        srv.shutdown()
    srv, u = _serveur_interface(interface="classique")
    try:
        with urllib.request.urlopen(u + "/medecin?jeton=" + _JETON) as r:
            page = r.read().decode()
        assert 'id="envoyerMessage"' in page and _JETON in page and "Content-Security-Policy" not in r.headers
    finally:
        srv.shutdown()


# ---------------------------------------------------------------- download script
def test_telechargement_et_empreintes():
    import telecharger_sources
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "site").mkdir()
        (tmp / "site" / "loi.pdf").write_bytes(b"%PDF-1.4 texte officiel")
        serveur = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(tmp / "site")))
        SimpleHTTPRequestHandler.log_message = lambda *a: None
        threading.Thread(target=serveur.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{serveur.server_address[1]}/loi.pdf"
        (tmp / "m.json").write_text(json.dumps({"sources": [{"id": "T1", "download_url": url}]}), encoding="utf-8")
        args = ["--manifeste", str(tmp / "m.json"), "--dossier", str(tmp / "orig")]
        with redirect_stdout(io.StringIO()):
            assert telecharger_sources.main(args) == 0
            assert telecharger_sources.main(args + ["--verifier"]) == 0
            (tmp / "site" / "loi.pdf").write_bytes(b"%PDF-1.4 texte modifie")
            assert telecharger_sources.main(args + ["--verifier"]) == 1
        serveur.shutdown()


if __name__ == "__main__":
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            f()
            print("ok", nom)


def test_jeu_de_donnees_assistant(tmp_path):
    sys.path.insert(0, str(ICI / "outils"))
    import importlib
    from medimcom import bibliotheque as B
    jeu = importlib.import_module("jeu_assistant")
    r = jeu.construire(tmp_path / "a", 20)
    assert r == {"cas": 200, "entrainement": 160, "validation": 20, "test": 20}
    jeu.construire(tmp_path / "b", 20)
    assert (tmp_path / "a" / "cas.jsonl").read_bytes() == (tmp_path / "b" / "cas.jsonl").read_bytes()   # reproductible
    cas = [json.loads(l) for l in (tmp_path / "a" / "cas.jsonl").read_text(encoding="utf-8").splitlines()]
    doc = json.loads((ICI / "donnees" / "presentations_cliniques.json").read_text(encoding="utf-8"))
    for p in doc["presentations"]:                                  # every pictogram exists in the vocabulary
        for q in p["questions"] + p["alertes"]:
            assert all(y in B.VOCABULAIRE or B.connu(y) for x in q["pictogrammes"] for y in x.split("+")), (p["id"], q["cle"])
    for c in cas:
        s = c["sortie"]
        assert s["rappel"] == jeu.RAPPEL and "diagnostic" not in s and not any("diagnostic" in x["hypothese"].lower() for x in s["pistes_a_evoquer"])
        if s["signes_d_alerte"]:
            assert s["orientation"].startswith("urgence")           # a warning sign present makes it an emergency
        connus = set(c["entree"]["etat_connu"])
        assert not connus & {q["cle"] for q in s["questions_complementaires"]}   # what is known is not asked again
        assert [q["priorite"] for q in s["questions_complementaires"]] == sorted(q["priorite"] for q in s["questions_complementaires"])
    assert all(c["sortie"]["orientation"].startswith("urgence") for c in cas if c["presentation"] == "DOULEUR_THORACIQUE")
    # negative argument: "does not drink" supports dehydration; "drinks" does not
    p = next(x for x in doc["presentations"] if x["id"] == "DIARRHEE")
    base = {"pays": "AE", "patient": {"sexe": "F", "age": 30}, "message_patient_pictogrammes": [], "motif": p["motif"]}
    deshy = lambda etat: [x for x in jeu.reponse_attendue(p, {**base, "etat_connu": etat})["pistes_a_evoquer"]
                          if "!boit" in str(next(h for h in p["pistes"] if h["hypothese"] == x["hypothese"]).get("arguments"))]
    assert deshy({"boit": False})[0]["arguments_presents"] == ["boit = non"]
    assert deshy({"boit": True})[0]["arguments_presents"] == []
    # an option contradicted by known information is discarded; in Cameroon, the context adds its own options
    f = next(x for x in doc["presentations"] if x["contexte_pays"].get("CM"))
    entree = {"pays": "CM", "patient": {"sexe": "M", "age": 40}, "etat_connu": {}, "message_patient_pictogrammes": [], "motif": f["motif"]}
    hyp_cm = {h["hypothese"] for h in f["contexte_pays"]["CM"]}
    assert hyp_cm & {x["hypothese"] for x in jeu.reponse_attendue(f, entree)["pistes_a_evoquer"]}
    assert not hyp_cm & {x["hypothese"] for x in jeu.reponse_attendue(f, {**entree, "pays": "AE"})["pistes_a_evoquer"]}
    for h in f["pistes"]:
        for k, v in (h.get("si") or {}).items():
            etat = {k: not v} if isinstance(v, bool) else {k: "__autre__"}
            assert h["hypothese"] not in {x["hypothese"] for x in jeu.reponse_attendue(f, {**entree, "etat_connu": etat})["pistes_a_evoquer"]}
    sft = [json.loads(l) for l in (tmp_path / "a" / "sft_test.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [m["role"] for m in sft[0]["messages"]] == ["system", "user", "assistant"] and json.loads(sft[0]["messages"][2]["content"])
    assert (tmp_path / "a" / "a_valider_par_medecin.csv").read_bytes().startswith(b"\xef\xbb\xbfpresentation;")


def test_constituer_base_avec_reseau_simule(tmp_path, monkeypatch):
    import importlib, shutil
    from medimcom import bibliotheque as B
    sys.path.insert(0, str(ICI / "outils"))
    cb = importlib.reload(importlib.import_module("constituer_base"))
    d = tmp_path / "bases"
    shutil.copytree(ICI / "pictogrammes" / "bases", d, ignore=shutil.ignore_patterns("images", "manifeste_externe.json",
                                                                                     "candidats_arasaac.json", "*.html"))
    for base, nom, contenu in (("tawasol", "GORGE.png", _png_1x1()), ("santebd", "DOS.png", _png_1x1()),
                               ("mulberry", "BRAS.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')):
        (d / "images" / base).mkdir(parents=True, exist_ok=True)
        (d / "images" / base / nom).write_bytes(contenu)
    monkeypatch.setattr(cb, "BASES", d)
    sys.path.insert(0, str(d))
    try:
        ara = importlib.reload(importlib.import_module("telecharger_arasaac"))
        monkeypatch.setattr(ara, "_get", lambda url, binaire=False: _png_1x1() if binaire else
                            ([{"_id": 3001, "keywords": [{"keyword": "x"}]}] if "/gorge" in url or "/head" in url else []))
        monkeypatch.setattr(ara.time, "sleep", lambda s: None)
        urls = []
        monkeypatch.setattr(cb, "_telecharger", lambda url: (urls.append(url), (b"%PDF-1.4 texte officiel", "application/pdf"))[1])
        sortie = tmp_path / "MEDIMCOM_base"
        with redirect_stdout(io.StringIO()):
            assert cb.main(["--sortie", str(sortie), "--variantes", "10"]) == 0
        base = BaseConnaissances(ICI / "kb")
        avec_lien = [s for s in base.sources.values() if s.get("download_url")]
        assert avec_lien and len(urls) == len(avec_lien)
        j = json.loads((sortie / "journal_constitution.json").read_text(encoding="utf-8"))
        assert sum(t["etat"] == "téléchargé" and len(t["sha256"]) == 64 for t in j["textes"]) == len(avec_lien)
        md = (sortie / "1_textes_juridiques" / "CM_Cameroun" / "CM-DCP-2024.md").read_text(encoding="utf-8")
        assert md.startswith("---\nid: CM-DCP-2024") and "CM24-A9" in md and "source secondaire" in md and "Règles du juriste" in md
        assert len(list((sortie / "1_textes_juridiques").rglob("*.md"))) == len(base.sources) + 1          # + index.md
        # pictograms: per source (with licence) and per idea (one image per source), SantéBD and dangerous SVG discarded
        p = sortie / "2_pictogrammes"
        assert (p / "par_source" / "arasaac" / "GORGE.png").exists() and "CC BY-NC-SA" in (p / "par_source" / "arasaac" / "LICENCE.md").read_text(encoding="utf-8")
        assert sorted(x.name for x in (p / "par_idee" / "3_corps" / "GORGE").iterdir()) == ["arasaac.png", "description.md", "tawasol.png"]
        assert not (p / "par_source" / "santebd").exists() and not (p / "par_source" / "mulberry").exists()
        assert any("accord écrit" in x.get("etat", "") for x in j["pictogrammes"]) and any("SVG" in x.get("etat", "") for x in j["pictogrammes"])
        desc = (p / "par_idee" / "4_symptomes" / "DOULEUR" / "description.md").read_text(encoding="utf-8")
        assert "## Description" in desc and "icone_demonstration.svg" in desc
        lignes = (p / "catalogue.csv").read_text(encoding="utf-8-sig").splitlines()
        assert len(lignes) == len(B.VOCABULAIRE) + 1 and "arasaac, tawasol" in next(l for l in lignes if l.startswith("GORGE;"))
        assert (sortie / "3_jeu_de_donnees_assistant" / "sft_test.jsonl").exists() and (sortie / "LISEZMOI.md").exists()
        # running again: nothing is downloaded or copied again
        urls.clear()
        with redirect_stdout(io.StringIO()):
            assert cb.main(["--sortie", str(sortie), "--etapes", "juridique", "pictogrammes"]) == 0
        j2 = json.loads((sortie / "journal_constitution.json").read_text(encoding="utf-8"))
        assert urls == [] and all(t["etat"] == "déjà présent" for t in j2["textes"])
        assert not [x for x in j2["pictogrammes"] if "sha256" in x and "arasaac" not in x["source"]]
    finally:
        sys.path.remove(str(d))
        B.charger_bases(ICI / "pictogrammes" / "bases")


# ---------------------------------------------------------------- formal methods
def test_semantique_trois_valeurs_et_monde_ferme():
    from medimcom.regles import evaluer
    assert evaluer("soins", None) is None and evaluer({"dans": ["a"]}, None) is None      # factuel : inconnu
    assert evaluer({"absent": True}, None) is True and evaluer({"pas": True}, None) is True   # epistemic: true/false
    assert evaluer("soins", None, monde_ferme=True) is False and evaluer({"hors": ["CONFORME"]}, "rejete") is True
    assert evaluer({"inferieur_a": 12}, 8) is True and evaluer({"superieur_a": 50}, None) is None
    # a permission does not hold when unknown information could trigger a prohibition
    v = R.verifier_partage_donnees({"destinataire_type": "autorite_sante", "lieu": "EAU"})          # unknown purpose
    assert v["verdict"] == "PREUVES_INSUFFISANTES" and any(c["regle"].endswith("?") and "finalite" in c["manquants"] for c in v["constats"])
    assert R.verifier_partage_donnees({"destinataire_type": "autorite_sante", "lieu": "EAU", "finalite": "sante_publique",
                                       "consentement_ecrit": False})["verdict"] == "CONFORME"
    # neutral place tokens: "EAU" is the country for the UAE rules, abroad for the Cameroon rules
    cm = MoteurRegles(KB / "regles_cm.json", BASE)
    assert cm.verifier_partage_donnees({"finalite": "sante_publique", "destinataire_type": "autorite_sante", "lieu": "dans_le_pays"})["verdict"] == "CONFORME"
    assert cm.verifier_partage_donnees({"finalite": "soins", "destinataire_type": "hopital", "lieu": "EAU"})["verdict"] == "BLOQUE"
    assert R.verifier_partage_donnees({"finalite": "soins", "destinataire_type": "hopital", "lieu": "EAU"})["verdict"] == "CONFORME"


def test_axiomes_et_informations_contradictoires():
    homme = etat(sexe="M", age=40, allergies="aucune", traitements_en_cours="aucun")
    v = R.verifier_prescription(rx("ibuprofene"), homme)
    assert v["verdict"] == "CONFORME" and not any("contre_indication" in c["regle"] for c in v["constats"])
    v = R.verifier_prescription(rx("ibuprofene"), {**homme, **etat(grossesse=True)})
    assert v["verdict"] != "CONFORME" and any(c["regle"].startswith("incoherence") for c in v["constats"])
    # allergy declared to a medicine unknown to the base: reported anyway
    v = R.verifier_prescription(rx("dolipraneX"), etat(sexe="M", age=40, allergies="dolipranex", traitements_en_cours="aucun"))
    assert any(c["regle"].startswith("allergie") for c in v["constats"])


def test_verification_formelle_des_regles():
    from medimcom import formel
    for chemin in ("regles_uae.json", "regles_cm.json"):
        m = MoteurRegles(KB / chemin, BASE)
        # sharing and prescription (several hundred thousand cases): outils/verifier_formel.py, run by the CI
        res = formel.bonne_formation(m) + formel.verifier_famille(m, "envoi_patient") + formel.verifier_maintien(m)
        assert all(r["ok"] for r in res), [(r["id"], r["contre_exemples"][:1]) for r in res if not r["ok"]]
    # the verification does catch a fault: exclusion list instead of an allow-list
    import copy
    m = copy.copy(MoteurRegles(KB / "regles_uae.json", BASE))
    m.kb = copy.deepcopy(m.kb)
    r = next(x for x in m.kb["regles_envoi_patient"] if x["id"] == "ENVOI-PRESCRIPTION-NON-CONFORME")
    r["si"] = {"statut_prescription_liee": {"dans": ["BLOQUE", "A_REVOIR"]}}
    res = {x["id"]: x for x in formel.verifier_famille(m, "envoi_patient")}
    assert not res["S-EN-TRAITEMENT-PRESCRIPTION"]["ok"]


def test_preuves_smt():
    from medimcom import formel_smt
    if not formel_smt.disponible():
        return                                          # z3-solver not installed: test skipped
    import copy
    m = MoteurRegles(KB / "regles_uae.json", BASE)
    res = formel_smt.prouver(m, "partage") + formel_smt.prouver(m, "envoi_patient")
    assert res and all(r["ok"] for r in res), [r["id"] for r in res if not r["ok"]]
    assert formel_smt.validation_croisee(m, "partage", n=300)["ok"]
    mut = copy.copy(m)
    mut.kb = copy.deepcopy(m.kb)
    mut.kb["regles_partage"] = [r for r in mut.kb["regles_partage"] if r["id"] != "HORS-EAU-SANS-EXCEPTION"]
    echecs = {r["id"] for r in formel_smt.prouver(mut, "partage", rapide=True) if not r["ok"]}
    assert "S-PA-HORS-PAYS-AE (SMT)" in echecs                      # the solver finds the counter-example


def test_moniteur_detecte_les_violations():
    from medimcom.surveillance import surveiller
    j = Journal()
    j.ajouter("traducteur", "decision", {"id": 1, "type": "envoi_patient", "statut": "attente_validation", "contenu_type": "information"})
    j.ajouter("traducteur", "envoye_au_patient", {"id": 1, "valide_par": "DR-001"})          # without validation or verdict
    v = surveiller(j, R)
    assert v["R1"] and v["R2"] and v["R10"] and not v["R7"]
    j = Journal()
    j.ajouter("medecin", "decision", {"id": 2, "type": "prescription", "statut": "a_verifier"})
    j.ajouter("juriste", "verdict", {"decision_id": 2, "verdict": "BLOQUE", "statut_decision": "BLOQUE",
                                      "constats": [{"regle": "X", "niveau": "BLOQUE", "fiches": ["ML16-A4-2"]}]})
    j.ajouter("medecin", "maintien", {"id": 2, "par": "DR-001", "justification": "x", "motifs": []})
    j.ajouter("juriste", "verdict", {"decision_id": 2, "verdict": "CONFORME", "statut_decision": "CONFORME",
                                      "constats": [{"regle": "Y", "niveau": "A_REVOIR", "fiches": []}]})
    v = surveiller(j, R)
    assert v["R4"] and v["R5"] and v["R10"]
    j.lignes[1]["contenu"]["verdict"] = "CONFORME"
    assert surveiller(j, R)["R7"]                                                         # falsified journal


def test_exploration_du_systeme_reel():
    from medimcom.exploration import executer, explorer
    s = explorer(60, 10, 11, "AE")
    assert s["violations"] == [] and s["envois_au_patient"] > 0
    # regression: an external module declaring a false validator never gets a compliant verdict
    ctx = executer([{"type": "envoi_patient", "auteur": "module_externe", "contenu_type": "information",
                     "valide_par": "DR-001", "texte": "Prenez 3 comprimés."}])
    d = next(iter(ctx.dossier.decisions.values()))
    assert d["valide_par"] is None and d["statut"] == "BLOQUE"
