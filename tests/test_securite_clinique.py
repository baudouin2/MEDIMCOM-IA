"""Clinical safety of prescriptions: official labels (FDA / DailyMed) turned into jurist rules, matched against the
patient record (pregnancy, age, kidney, liver, ulcer, anticoagulant, allergy) and the daily dose."""
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from medimcom.faits import extraire_faits  # noqa: E402
from medimcom.regles import MoteurRegles  # noqa: E402

MOTEURS = {p: MoteurRegles(RACINE / "kb" / f) for p, f in (("AE", "regles_uae.json"), ("CM", "regles_cm.json"))}
BASE = dict(sexe="M", age=45, allergies="aucune", traitements_en_cours="aucun", mode_consultation="presentiel", antecedents="aucun")


def juger(med, dose, posologie, pays="AE", **patient):
    etat = {k: {"valeur": v, "confirme": True} for k, v in {**BASE, **patient}.items()}
    return MOTEURS[pays].verifier_prescription({"medicament": med, "prescripteur": "DR-001", "auteur": "medecin", "dose": dose,
                                                "posologie": posologie, "mode": "presentiel"}, etat)


def regles(r):
    return {c["regle"] for c in r["constats"]}


@pytest.mark.parametrize("pays", ["AE", "CM"])
@pytest.mark.parametrize("med,dose,pos,patient,attendu,regle", [
    ("ibuprofene", "400 mg", "3 fois par jour", {"anticoagulant": True}, "A_REVOIR", "contre_indication:ibuprofene:anticoagulant"),
    ("ibuprofene", "400 mg", "3 fois par jour", {"ulcere_digestif": True}, "A_REVOIR", "contre_indication:ibuprofene:ulcere_digestif"),
    ("ibuprofene", "400 mg", "3 fois par jour", {"maladie_renale": True}, "A_REVOIR", "contre_indication:ibuprofene:maladie_renale"),
    ("ibuprofene", "800 mg", "5 fois par jour", {}, "A_REVOIR", "dose_max:ibuprofene"),
    ("aspirine", "500 mg", "3 fois par jour", {"age": 14}, "A_REVOIR", "contre_indication:aspirine:age"),
    ("aspirine", "500 mg", "3 fois par jour", {"sexe": "F", "age": 30, "grossesse": True}, "A_REVOIR", "contre_indication:aspirine:grossesse"),
    ("metformine", "850 mg", "2 fois par jour", {"maladie_renale": True}, "A_REVOIR", "contre_indication:metformine:maladie_renale"),
    ("metformine", "850 mg", "2 fois par jour", {"maladie_hepatique": True}, "A_REVOIR", "contre_indication:metformine:maladie_hepatique"),
    ("metformine", "1000 mg", "3 fois par jour", {}, "A_REVOIR", "dose_max:metformine"),
    ("metformine", "1000 mg", "2 fois par jour", {"age": 14}, "CONFORME", None),          # 2000 mg/day: maximum for children
    ("metformine", "850 mg", "3 fois par jour", {"age": 14}, "A_REVOIR", "dose_max:metformine"),  # 2550 > 2000 chez l'enfant
    ("amoxicilline", "500 mg", "3 fois par jour", {"allergies": "pénicilline"}, "A_REVOIR", "allergie:amoxicilline"),
    ("paracetamol", "1 g", "6 fois par jour", {}, "A_REVOIR", "dose_max:paracetamol"),
    ("paracetamol", "1 g", "3 fois par jour", {"maladie_hepatique": True}, "A_REVOIR", "contre_indication:paracetamol:maladie_hepatique"),
    ("paracetamol", "1 g", "3 fois par jour", {}, "CONFORME", None),
    ("amoxicilline", "500 mg", "3 fois par jour", {}, "CONFORME", None),
])
def test_regles_cliniques(pays, med, dose, pos, patient, attendu, regle):
    r = juger(med, dose, pos, pays, **patient)
    assert r["verdict"] == attendu, (r["verdict"], regles(r))
    if regle:
        assert regle in regles(r)
        fiche = next(c for c in r["constats"] if c["regle"] == regle)["fiches"]
        assert fiche and all(f in MOTEURS[pays].base.fiches for f in fiche), "règle sans source"


def test_alternative_proposee_et_sourcee():
    r = juger("ibuprofene", "400 mg", "3 fois par jour", sexe="F", age=28, grossesse=True)
    assert r["alternatives"] and r["alternatives"][0]["medicament"] == "paracetamol"
    assert "FDA" in r["alternatives"][0]["source"]


def test_antecedents_lus_dans_le_texte_libre():
    f = extraire_faits("diabète, sous warfarine, ancien ulcère gastrique, insuffisance rénale chronique")
    assert f["anticoagulant"] and f["ulcere_digestif"] and f["maladie_renale"]


def test_antecedents_non_renseignes_signales():
    etat = {k: {"valeur": v, "confirme": True} for k, v in
            {"sexe": "M", "age": 45, "allergies": "aucune", "traitements_en_cours": "aucun", "mode_consultation": "presentiel"}.items()}
    r = MOTEURS["AE"].verifier_prescription({"medicament": "ibuprofene", "prescripteur": "DR-001", "auteur": "medecin",
                                             "dose": "400 mg", "posologie": "3 fois par jour", "mode": "presentiel"}, etat)
    infos = [c for c in r["informations"] if c["regle"].startswith("antecedents_non_renseignes")]
    assert infos and "maladie des reins" in infos[0]["detail"]
