"""Jeu de données de l'assistant (agent 3) : questions complémentaires, signes d'alerte et pistes à évoquer.

    python outils/jeu_assistant.py --sortie donnees/jeu_assistant            # 30 variantes par présentation
    python outils/jeu_assistant.py --sortie /chemin --variantes 100 --graine 7

À partir de donnees/presentations_cliniques.json (médecine générale, À VALIDER PAR UN MÉDECIN), le script fabrique des
cas FICTIFS (âge, sexe, pays, ce qui est déjà connu, signes d'alerte présents ou non) et, pour chacun, la réponse
attendue de l'assistant, calculée par des règles explicites (donc vérifiable et corrigeable) :
- les questions complémentaires à faire poser par le traducteur (avec leurs pictogrammes), par priorité ;
- les signes d'alerte déjà présents et l'orientation (urgence ou consultation) ;
- les pistes à évoquer par le médecin, avec les éléments qui les soutiennent et les examens utiles.
Ce ne sont jamais des diagnostics : le médecin examine et décide.

Fichiers produits :
- sft_entrainement.jsonl, sft_validation.jsonl, sft_test.jsonl : conversations {"messages": [system, user, assistant]},
  au format accepté par la plupart des outils d'ajustement (Ollama Modelfile, Unsloth, Axolotl, TRL, OpenAI) ;
- cas.jsonl : les mêmes cas en données structurées (entrée, sortie attendue) ;
- a_valider_par_medecin.csv : chaque question, alerte et piste, avec des colonnes pour la validation ;
- FICHE_DE_DONNEES.md : provenance, composition, limites et usages autorisés.
"""
import argparse
import csv
import json
import random
import sys
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PRESENTATIONS = RACINE / "donnees" / "presentations_cliniques.json"

SYSTEME = ("Tu es l'assistant médical de MEDIMCOM IA (agent 3). Tu aides un médecin qui consulte un patient sourd "
           "communiquant en pictogrammes. À partir de l'état connu du patient et de son message, réponds UNIQUEMENT en JSON avec : "
           "questions_complementaires (ce qui manque, par priorité, avec les pictogrammes à faire traduire), "
           "signes_d_alerte (présents), orientation, pistes_a_evoquer (hypothèses pour le médecin, avec arguments et examens utiles) "
           "et rappel. Tu ne poses jamais de diagnostic certain, tu ne prescris pas, tu ne parles pas au patient : le médecin décide.")
RAPPEL = "Pistes à évoquer par le médecin, pas un diagnostic. Le médecin examine le patient et décide."
OUI_NON = {"fievre", "vomissements", "diarrhee", "toux", "crachats_sang", "contact_malade", "boit", "mange", "nouveau_produit",
           "frissons", "voyage_contact", "gonflement", "grossesse"}
VALEURS = {"allergies": ["aucune", "pénicilline", "aspirine"], "traitements_en_cours": ["aucun", "metformine", "contraception orale"],
           "debut": ["ce matin", "depuis 2 jours", "depuis 1 semaine"], "terme": ["3 mois", "7 mois"]}


def _applicable(si: dict | None, patient: dict) -> bool:
    if not si:
        return True
    if "sexe" in si and patient["sexe"] != si["sexe"]:
        return False
    return si.get("age_min", 0) <= patient["age"] <= si.get("age_max", 200)


def _vrai(v) -> bool:
    return v is True or (isinstance(v, int) and not isinstance(v, bool) and v >= 7)


def generer_cas(p: dict, pays: str, hasard: random.Random) -> dict:
    pop = p["population"]
    patient = {"sexe": pop.get("sexe") or hasard.choice(["F", "M"]), "age": hasard.randint(pop["age_min"], pop["age_max"])}
    etat = {}
    if pop.get("grossesse"):
        etat["grossesse"] = True
    for q in p["questions"]:
        k = q["cle"]
        if k in etat or not _applicable(q.get("si"), patient) or hasard.random() > 0.45:
            continue
        if k == "intensite_douleur":
            etat[k] = hasard.randint(2, 10)
        elif k == "grossesse":
            etat[k] = hasard.random() < 0.3
        elif k in VALEURS:
            etat[k] = hasard.choice(VALEURS[k])
        else:
            etat[k] = hasard.random() < 0.5
    for a in p["alertes"]:
        if hasard.random() < 0.5:
            etat[a["cle"]] = hasard.random() < 0.3
    message = list(p["message_patient"])
    if "intensite_douleur" in etat and hasard.random() < 0.5:
        message.append(f"CHIFFRE:{etat['intensite_douleur']}")
    entree = {"pays": pays, "patient": patient, "etat_connu": etat, "message_patient_pictogrammes": message, "motif": p["motif"]}
    return {"entree": entree, "sortie": reponse_attendue(p, entree)}


def reponse_attendue(p: dict, entree: dict) -> dict:
    patient, etat, pays = entree["patient"], entree["etat_connu"], entree["pays"]
    alertes = [{"signe": a["cle"], "raison": a["raison"]} for a in p["alertes"] if etat.get(a["cle"]) is True]
    if _vrai(etat.get("intensite_douleur")) and "intensite_douleur" in [q["cle"] for q in p["questions"]]:
        alertes.append({"signe": "douleur_intense", "raison": "Douleur cotée 7/10 ou plus : signe de gravité."})
    questions = [{"cle": a["cle"], "question": a["question"], "pictogrammes": a["pictogrammes"], "priorite": 0,
                  "raison": a["raison"]} for a in p["alertes"] if a["cle"] not in etat]
    questions += [{"cle": q["cle"], "question": q["question"], "pictogrammes": q["pictogrammes"], "priorite": q["priorite"],
                   "raison": q["raison"]} for q in p["questions"] if q["cle"] not in etat and _applicable(q.get("si"), patient)]
    questions.sort(key=lambda q: q["priorite"])
    pistes = []
    for h in p["pistes"] + p.get("contexte_pays", {}).get(pays, []):
        cond, a_confirmer = h.get("si") or {}, []
        if any(k in etat and etat[k] != v for k, v in cond.items()):
            continue
        if any(k == "grossesse" and (patient["sexe"] != "F" or not 12 <= patient["age"] <= 50) for k in cond):
            continue
        a_confirmer = [k for k in cond if k not in etat]
        presents = []
        for k in h.get("arguments", []):
            if k.startswith("!"):                      # argument négatif : présent quand la réponse est NON
                if etat.get(k[1:]) is False:
                    presents.append(f"{k[1:]} = non")
            elif _vrai(etat.get(k)) or (isinstance(etat.get(k), str) and etat[k] not in ("aucune", "aucun")):
                presents.append(k)
        piste = {"hypothese": h["hypothese"], "arguments_presents": presents, "a_confirmer": a_confirmer,
                 "examens_utiles": h.get("examens", []), "a_eliminer_en_urgence": bool(h.get("urgence"))}
        pistes.append(piste)
    pistes.sort(key=lambda x: (not (x["a_eliminer_en_urgence"] and not x["a_confirmer"]), -len(x["arguments_presents"])))
    urgent = bool(alertes) or p.get("toujours_urgent", False) or any(x["a_eliminer_en_urgence"] and not x["a_confirmer"] for x in pistes)
    return {"questions_complementaires": questions, "signes_d_alerte": alertes,
            "orientation": "urgence : prévenir le médecin immédiatement" if urgent else "consultation : le médecin examine le patient",
            "pistes_a_evoquer": pistes, "rappel": RAPPEL}


def construire(sortie: Path, variantes: int = 30, graine: int = 2026, presentations: Path = PRESENTATIONS) -> dict:
    doc = json.loads(Path(presentations).read_text(encoding="utf-8"))
    hasard = random.Random(graine)
    sortie.mkdir(parents=True, exist_ok=True)
    cas, parts = [], {"entrainement": [], "validation": [], "test": []}
    for p in doc["presentations"]:
        for i in range(variantes):
            pays = ("AE", "CM")[i % 2]
            c = generer_cas(p, pays, hasard)
            c["id"] = f"{p['id']}-{i + 1:03d}"
            c["presentation"] = p["id"]
            part = "test" if i % 10 == 9 else "validation" if i % 10 == 8 else "entrainement"
            c["partie"] = part
            cas.append(c)
            parts[part].append({"id": c["id"], "messages": [
                {"role": "system", "content": SYSTEME},
                {"role": "user", "content": json.dumps(c["entree"], ensure_ascii=False)},
                {"role": "assistant", "content": json.dumps(c["sortie"], ensure_ascii=False)}]})
    (sortie / "cas.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cas), encoding="utf-8")
    for nom, lignes in parts.items():
        (sortie / f"sft_{nom}.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lignes), encoding="utf-8")
    with open(sortie / "a_valider_par_medecin.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["presentation", "type", "contenu", "raison_ou_arguments", "examens_utiles", "pays", "valide (oui/non)", "correction", "medecin", "date"])
        for p in doc["presentations"]:
            for q in p["questions"]:
                w.writerow([p["id"], "question", q["question"], q["raison"], "", "", "", "", "", ""])
            for a in p["alertes"]:
                w.writerow([p["id"], "signe d'alerte", a["question"], a["raison"], "", "", "", "", "", ""])
            for pays, hs in [("tous", p["pistes"])] + list(p.get("contexte_pays", {}).items()):
                for h in hs:
                    w.writerow([p["id"], "piste à évoquer", h["hypothese"], ", ".join(h.get("arguments", [])), "; ".join(h.get("examens", [])), pays, "", "", "", ""])
    stats = {k: len(v) for k, v in parts.items()}
    (sortie / "FICHE_DE_DONNEES.md").write_text(f"""# Fiche de données — assistant MEDIMCOM IA (agent 3)

Générée le {date.today().isoformat()} par `outils/jeu_assistant.py` (graine {graine}, {variantes} variantes par présentation).

## Ce que contient le jeu
- {len(cas)} cas **fictifs** issus de {len(doc['presentations'])} présentations cliniques (`donnees/presentations_cliniques.json`) : {', '.join(p['motif'] for p in doc['presentations'])}.
- Répartition : entraînement {stats['entrainement']}, validation {stats['validation']}, test {stats['test']} (par variante : les mêmes présentations dans chaque partie).
- Pays alternés : Émirats (AE) et Cameroun (CM). Le contexte du pays ajoute des pistes (paludisme au Cameroun, par exemple).
- Entrée : âge, sexe, ce qui est déjà connu, message du patient en pictogrammes. Sortie attendue : questions complémentaires (avec pictogrammes), signes d'alerte présents, orientation, pistes à évoquer, rappel.

## Comment les réponses sont calculées
Par des règles explicites (`outils/jeu_assistant.py`, fonction `reponse_attendue`) :
- on demande ce qui manque, en commençant par les signes d'alerte ;
- un signe d'alerte présent ou une douleur à 7/10 ou plus donne l'orientation « urgence » ;
- une piste est écartée si une information connue la contredit ; elle est « à confirmer » si l'information manque.
Corriger une règle ou une présentation, puis relancer le script : tout le jeu est régénéré.

## Limites, à dire franchement
- Contenu de médecine générale rédigé pour le prototype : **à valider par un médecin** avant tout entraînement (`a_valider_par_medecin.csv`).
- Cas générés par règles : peu de variété de formulation ; à compléter par des cas rédigés par des médecins (toujours fictifs).
- Aucune donnée de patient réel. Ne jamais y ajouter de données réelles sans cadre légal et éthique.
- Le modèle entraîné propose des pistes au médecin ; il ne pose pas de diagnostic et ne s'adresse jamais au patient.

## Usage
- Évaluer un modèle tel quel (sans entraînement) sur `sft_test.jsonl` : comparer ses questions et ses alertes à la sortie attendue.
- Ajuster un petit modèle local (par exemple qwen3:8b) sur `sft_entrainement.jsonl`, en gardant `sft_validation.jsonl` pour régler l'entraînement.
""", encoding="utf-8")
    return {"cas": len(cas), **stats}


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--sortie", default=str(RACINE / "donnees" / "jeu_assistant"))
    a.add_argument("--variantes", type=int, default=30)
    a.add_argument("--graine", type=int, default=2026)
    x = a.parse_args()
    r = construire(Path(x.sortie), x.variantes, x.graine)
    print(f"{r['cas']} cas fictifs · entraînement {r['entrainement']} · validation {r['validation']} · test {r['test']} -> {x.sortie}")
    sys.exit(0)
