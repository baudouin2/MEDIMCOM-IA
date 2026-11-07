"""Étape « entrainement » de constituer_base_v2.py : jeux de données prêts pour améliorer ou entraîner un modèle.

Construits uniquement à partir de ce que les autres étapes ont téléchargé (rien n'est inventé) + phrases synthétiques
explicitement marquées comme telles. Partition train / validation / test stable (empreinte de l'identifiant).

05_jeux_entrainement/
├── FICHE_DE_DONNEES.md                 provenance, licences, usages permis et interdits, limites, effectifs
├── pictogrammes_images.jsonl           image -> libellés fr / en / ar, catégorie, notions (classification, CLIP)
│   (+ 02_pictogrammes/metadata.jsonl   même contenu au format « imagefolder » de Hugging Face)
├── phrases_pictogrammes.jsonl          suite de notions (et leurs images) <-> phrase fr / en  [synthétique]
├── juridique_classification.jsonl      article -> juridiction, exigences du hackathon, thèmes, type de texte
├── juridique_recherche.jsonl           requête -> article pertinent (dispositions du juriste) pour entraîner un moteur de recherche
├── references_qr.jsonl                 question -> réponse tirée des fiches de l'OMS (fr / en / ar)
└── lexique_traduction.jsonl            notion -> fr / en / ar (vocabulaire + Wikidata)
"""
import hashlib
import json
import random
import re

import constituer_base_v2 as cb


def partition(identifiant: str) -> str:
    h = int(hashlib.sha256(identifiant.encode()).hexdigest()[:8], 16) % 100
    return "train" if h < 80 else ("validation" if h < 90 else "test")


def lire_jsonl(chemin):
    if not chemin.exists():
        return []
    return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]


# ----------------------------------------------------------------------------------------- pictogrammes
def jeu_images(sortie, notions) -> int:
    picto = sortie / "02_pictogrammes"
    par_id = {n["id"]: n for n in notions}
    lignes = []
    for c in lire_jsonl(picto / "catalogue.jsonl"):
        ns = [par_id[n] for n in c.get("notions", []) if n in par_id]
        lignes.append({"file_name": c["fichier"], "source": c["source"], "id_source": c["id"], "categorie": c["categorie"],
                       "label_fr": ns[0]["fr"] if ns else (c["mots_fr"] or [""])[0],
                       "label_en": ns[0]["en"] if ns else (c["mots_en"] or [""])[0],
                       "label_ar": ns[0]["ar"] if ns else "", "notions": c.get("notions", []),
                       "mots_fr": c["mots_fr"], "mots_en": c["mots_en"], "licence": c["licence"], "sha256": c.get("sha256", ""),
                       "split": partition(c["fichier"])})
    cb.ecrire_jsonl(picto / "metadata.jsonl", lignes)
    cb.ecrire_jsonl(sortie / "05_jeux_entrainement" / "pictogrammes_images.jsonl",
                    [{**l, "file_name": "../02_pictogrammes/" + l["file_name"]} for l in lignes])
    return len(lignes)


# Articles français des parties du corps et des médicaments (pour des phrases correctes : « au ventre », « à la tête »…)
A_CORPS = {"TETE": "à la", "VISAGE": "au", "OEIL": "à l'", "OREILLE": "à l'", "NEZ": "au", "BOUCHE": "à la", "DENT": "à la",
           "LANGUE": "à la", "GORGE": "à la", "COU": "au", "EPAULE": "à l'", "BRAS": "au", "COUDE": "au", "POIGNET": "au",
           "MAIN": "à la", "DOIGT": "au", "POITRINE": "à la", "SEIN": "au", "VENTRE": "au", "ESTOMAC": "à l'", "DOS": "au",
           "HANCHE": "à la", "JAMBE": "à la", "GENOU": "au", "CHEVILLE": "à la", "PIED": "au", "PEAU": "à la", "FRONT": "au",
           "ARTICULATION": "à l'", "MUSCLE": "au", "COLONNE_VERTEBRALE": "à la", "ORGANES_GENITAUX": "aux", "LEVRES": "aux"}
A_MED = {"COMPRIME": "le", "GELULE": "la", "SIROP": "le", "ANTIBIOTIQUE": "l'", "ANTIDOULEUR": "l'", "PARACETAMOL": "le",
         "ANTIPALUDIQUE": "l'", "VITAMINE": "la", "MEDICAMENT": "le", "SOLUTION_DE_REHYDRATATION": "la", "FER": "le", "VERMIFUGE": "le"}
# Formes locales : pas de « prendre », pas de moment du repas
A_MED_LOCAL = {"POMMADE": ("Appliquez", "la", "Apply the"), "CREME": ("Appliquez", "la", "Apply the"), "COLLYRE": ("Mettez", "le", "Put in the"),
               "GOUTTES_POUR_LES_OREILLES": ("Mettez", "les", "Put in the"), "INHALATEUR": ("Utilisez", "l'", "Use the")}
SYMPTOMES_NOMS = ["FIEVRE", "TOUX", "DIARRHEE", "NAUSEE", "VERTIGE", "FATIGUE", "FAIBLESSE", "ESSOUFFLEMENT", "FRISSONS",
                  "DEMANGEAISON", "ERUPTION", "SAIGNEMENT", "GONFLEMENT", "CONSTIPATION", "PALPITATIONS", "INSOMNIE",
                  "CONVULSION", "VISION_FLOUE", "ENGOURDISSEMENT", "PERTE_D_APPETIT", "PERTE_DE_POIDS", "DOULEUR_THORACIQUE",
                  "MAL_DE_TETE", "MAL_DE_VENTRE", "MAL_DE_GORGE", "MAL_DE_DOS", "MAL_AUX_DENTS", "BRULURE", "BLESSURE", "RHUME"]
TEMPS = ["HIER", "MATIN", "SOIR", "NUIT", "SEMAINE", "MOIS", "LONGTEMPS"]
TEMPS_FR = {"AUJOURD_HUI": "aujourd'hui", "HIER": "hier", "MATIN": "ce matin", "SOIR": "hier soir", "NUIT": "cette nuit",
            "SEMAINE": "une semaine", "MOIS": "un mois", "LONGTEMPS": "longtemps"}
TEMPS_EN = {"HIER": "since yesterday", "MATIN": "since this morning", "SOIR": "since last night", "NUIT": "since last night",
            "SEMAINE": "for a week", "MOIS": "for a month", "LONGTEMPS": "for a long time"}
INTENSITE = {"UN_PEU": ("un peu", "a little"), "BEAUCOUP": ("très", "a lot"), "LEGER": ("légèrement", "mildly"),
             "SEVERE": ("terriblement", "severely")}
INTENSITE_SYMPTOME = {"UN_PEU": ("un peu", "a little"), "BEAUCOUP": ("beaucoup", "a lot"), "LEGER": ("intensité faible", "mild"),
                      "SEVERE": ("intensité forte", "severe")}
EMOTIONS = ["CONTENT", "TRISTE", "INQUIET", "EN_COLERE", "CALME", "STRESSE", "NERVEUX", "GENE", "SURPRIS", "SEUL", "CONFUS",
            "SOULAGE", "FATIGUE", "BIEN", "MAL", "MIEUX"]
FREQ = {"UNE_FOIS_PAR_JOUR": ("une fois par jour", "once a day"), "DEUX_FOIS_PAR_JOUR": ("deux fois par jour", "twice a day"),
        "TROIS_FOIS_PAR_JOUR": ("trois fois par jour", "three times a day")}
MOMENTS = {"MATIN": ("le matin", "in the morning"), "SOIR": ("le soir", "in the evening"), "APRES": ("après le repas", "after meals"),
           "AVANT": ("avant le repas", "before meals")}


def _cap(t):
    return t[:1].upper() + t[1:]


def phrases(notions) -> list[dict]:
    n = {x["id"]: x for x in notions}
    ok = lambda *ids: all(i in n for i in ids)  # noqa: E731
    sorties = []

    def add(seq, fr, en, intention, locuteur):
        if ok(*[s for s in seq if not s.startswith("_")]):
            seq = [s for s in seq if not s.startswith("_")]
            sorties.append({"notions": seq, "fr": fr, "en": en, "intention": intention, "locuteur": locuteur})

    for c, art in A_CORPS.items():
        if c not in n:
            continue
        cfr, cen = n[c]["fr"], n[c]["en"]
        sep = "" if art.endswith("'") else " "
        add(["MOI", "AVOIR_MAL", c], f"J'ai mal {art}{sep}{cfr}.", f"My {cen} hurts.", "douleur", "patient")
        for t in TEMPS:
            add(["MOI", "AVOIR_MAL", c, "DEPUIS", t], f"J'ai mal {art}{sep}{cfr} depuis {TEMPS_FR[t]}.",
                f"My {cen} has been hurting {TEMPS_EN[t]}.", "douleur_duree", "patient")
        for i, (ifr, ien) in INTENSITE.items():
            add(["MOI", "AVOIR_MAL", c, i], f"J'ai {ifr} mal {art}{sep}{cfr}.", f"My {cen} hurts {ien}.", "douleur_intensite", "patient")
            for t in TEMPS:
                add(["MOI", "AVOIR_MAL", c, i, "DEPUIS", t], f"J'ai {ifr} mal {art}{sep}{cfr} depuis {TEMPS_FR[t]}.",
                    f"My {cen} has been hurting {ien} {TEMPS_EN[t]}.", "douleur_intensite_duree", "patient")
        add(["MEDECIN", "QUESTION", "AVOIR_MAL", c, "QUAND"], f"Depuis quand avez-vous mal {art}{sep}{cfr} ?",
            f"Since when has your {cen} been hurting?", "question_duree", "medecin")
        add(["MEDECIN", "MONTRER", c], f"Montrez-moi {('votre ' + cfr) if not art.startswith('aux') else ('vos ' + cfr)}.",
            f"Show me your {cen}.", "consigne", "medecin")
    for s in SYMPTOMES_NOMS:
        if s not in n:
            continue
        sfr, sen = n[s]["fr"], n[s]["en"]
        for t in TEMPS:
            add([s, "DEPUIS", t], f"{_cap(sfr)} depuis {TEMPS_FR[t]}.", f"{_cap(sen)} {TEMPS_EN[t]}.", "symptome_duree", "patient")
        add(["QUESTION", s], f"Avez-vous ce symptôme : {sfr} ?", f"Do you have this symptom: {sen}?", "question_symptome", "medecin")
        add(["OUI", s], f"Oui, j'ai ce symptôme : {sfr}.", f"Yes, I have {sen}.", "reponse", "patient")
        add(["NON", s], f"Non, pas de {sfr}.", f"No, no {sen}.", "reponse", "patient")
        for i, (ifr, ien) in INTENSITE_SYMPTOME.items():
            add([s, i], f"{_cap(sfr)} : {ifr}.", f"{_cap(sen)}: {ien}.", "symptome_intensite", "patient")
    for e in EMOTIONS:
        if e in n:
            add(["MOI", e], f"Je me sens {n[e]['fr']}.", f"I feel {n[e]['en']}.", "ressenti", "patient")
            add(["MEDECIN", "QUESTION", e], f"Vous sentez-vous {n[e]['fr']} ?", f"Do you feel {n[e]['en']}?", "question_ressenti", "medecin")
    for m, art in A_MED.items():
        if m not in n:
            continue
        mfr, men = n[m]["fr"], n[m]["en"]
        sep = "" if art.endswith("'") else " "
        for f, (ffr, fen) in FREQ.items():
            add(["PRENDRE_UN_MEDICAMENT", m, f], f"Prenez {art}{sep}{mfr} {ffr}.", f"Take the {men} {fen}.", "prescription", "medecin")
            for mo, (mofr, moen) in MOMENTS.items():
                add(["PRENDRE_UN_MEDICAMENT", m, f, mo], f"Prenez {art}{sep}{mfr} {ffr}, {mofr}.", f"Take the {men} {fen}, {moen}.",
                    "prescription", "medecin")
        add(["MOI", "PRENDRE_UN_MEDICAMENT", m, "QUESTION"], f"Est-ce que je dois prendre {art}{sep}{mfr} ?",
            f"Should I take the {men}?", "question_traitement", "patient")
    for m, (verbe, art, verbe_en) in A_MED_LOCAL.items():
        if m not in n:
            continue
        sep = "" if art.endswith("'") else " "
        for f, (ffr, fen) in FREQ.items():
            add(["MEDECIN", m, f], f"{verbe} {art}{sep}{n[m]['fr']} {ffr}.", f"{verbe_en} {n[m]['en']} {fen}.", "prescription", "medecin")
    for x in ("PRISE_DE_SANG", "RADIOGRAPHIE", "ECHOGRAPHIE", "VACCIN", "PIQURE", "TEST_DE_PALUDISME", "TENSION_ARTERIELLE", "GLYCEMIE"):
        if x in n:
            add(["MEDECIN", x, "EXPLIQUER"], f"Je vais vous expliquer l'examen : {n[x]['fr']}.", f"I will explain the procedure: {n[x]['en']}.",
                "information", "medecin")
            add(["CONSENTEMENT", x, "QUESTION"], f"Acceptez-vous cet examen : {n[x]['fr']} ?", f"Do you agree to this procedure: {n[x]['en']}?",
                "consentement", "medecin")
            add(["OUI", "ACCEPTER", x], f"Oui, j'accepte : {n[x]['fr']}.", f"Yes, I agree: {n[x]['en']}.", "consentement", "patient")
            add(["NON", "REFUSER", x], f"Non, je refuse : {n[x]['fr']}.", f"No, I refuse: {n[x]['en']}.", "consentement", "patient")
    for x in ("INTERPRETE", "LANGUE_DES_SIGNES", "REPETER", "ECRIRE", "ATTENDRE", "AIDE"):
        if x in n:
            add(["MOI", "DEMANDER", x], f"J'ai besoin de : {n[x]['fr']}.", f"I need: {n[x]['en']}.", "communication", "patient")
    for x in ("ENCEINTE", "ALLERGIE", "DIABETE", "HYPERTENSION", "ASTHME", "EPILEPSIE", "DREPANOCYTOSE", "VIH"):
        if x in n:
            add(["MOI", x], f"Je signale : {n[x]['fr']}.", f"I report: {n[x]['en']}.", "antecedent", "patient")
    sorties += phrases_fonctions(n)
    return sorties


QUALITES = ["BRULURE", "DOULEUR_EN_PIQURE", "COUP_DE_COUTEAU", "SERREMENT", "PRESSION", "LOURDEUR", "BATTEMENT", "ELANCEMENT",
            "CRAMPE", "DECHARGE_ELECTRIQUE", "FOURMILLEMENTS", "TIRAILLEMENT"]
DECLENCHEURS_COMMUNS = ["LA_NUIT", "LE_MATIN_AU_REVEIL", "QUAND_ON_APPUIE", "AU_REPOS"]
# Déclencheurs plausibles selon la région du corps (évite « mal à la dent quand je marche »)
DECLENCHEURS_PAR_REGION = {
    ("DENT", "BOUCHE", "LANGUE", "GORGE", "LEVRES"): ["QUAND_JE_MANGE", "APRES_AVOIR_MANGE"],
    ("POITRINE", "DOS", "COLONNE_VERTEBRALE", "EPAULE"): ["QUAND_JE_RESPIRE", "QUAND_JE_TOUSSE", "A_L_EFFORT", "QUAND_JE_BOUGE"],
    ("VENTRE", "ESTOMAC"): ["QUAND_JE_MANGE", "APRES_AVOIR_MANGE", "QUAND_JE_TOUSSE", "QUAND_JE_BOUGE"],
    ("ORGANES_GENITAUX",): ["QUAND_J_URINE"],
    ("HANCHE", "JAMBE", "GENOU", "CHEVILLE", "PIED"): ["QUAND_JE_MARCHE", "A_L_EFFORT", "QUAND_JE_BOUGE"],
    ("BRAS", "COUDE", "POIGNET", "MAIN", "DOIGT", "COU", "ARTICULATION", "MUSCLE"): ["A_L_EFFORT", "QUAND_JE_BOUGE"],
    ("TETE", "FRONT", "VISAGE", "OEIL", "OREILLE", "NEZ"): ["A_L_EFFORT", "QUAND_JE_TOUSSE"],
}
DECLENCHEURS = ["QUAND_JE_MANGE", "APRES_AVOIR_MANGE", "QUAND_JE_MARCHE", "A_L_EFFORT", "AU_REPOS", "QUAND_JE_RESPIRE", "QUAND_JE_TOUSSE",
                "QUAND_J_URINE", "QUAND_JE_BOUGE", "QUAND_ON_APPUIE", "LA_NUIT", "LE_MATIN_AU_REVEIL"]
# Conseils d'hygiène de vie généraux et consensuels, associés seulement aux maladies pour lesquelles ils sont pertinents
# (à faire valider par un médecin avant tout entraînement ; aucune posologie).
CONSEILS_PAR_MALADIE = {
    "DIABETE": ["SANS_SUCRE", "PETITES_PORTIONS", "REPAS_A_HEURES_FIXES", "MARCHER_CHAQUE_JOUR", "CONTROLER_LA_GLYCEMIE", "PESER_CHAQUE_SEMAINE"],
    "HYPERTENSION": ["SANS_SEL", "MARCHER_CHAQUE_JOUR", "ARRETER_DE_FUMER", "PAS_D_ALCOOL", "PRENDRE_LA_TENSION"],
    "OBESITE": ["PETITES_PORTIONS", "MOINS_DE_GRAS", "MARCHER_CHAQUE_JOUR", "PESER_CHAQUE_SEMAINE"],
    "INSUFFISANCE_CARDIAQUE": ["SANS_SEL", "PESER_CHAQUE_SEMAINE", "REVENIR_EN_URGENCE_SI"],
    "ULCERE": ["PAS_D_ALCOOL", "ARRETER_DE_FUMER", "REPAS_A_HEURES_FIXES"],
    "ASTHME": ["ARRETER_DE_FUMER", "REVENIR_EN_URGENCE_SI"],
    "DREPANOCYTOSE": ["BOIRE_BEAUCOUP_D_EAU", "SE_REPOSER", "REVENIR_EN_URGENCE_SI"],
    "GOUTTE": ["PAS_D_ALCOOL", "BOIRE_BEAUCOUP_D_EAU"],
    "GASTRO_ENTERITE": ["BOIRE_SOUVENT", "SOLUTION_DE_REHYDRATATION", "SE_LAVER_LES_MAINS"],
    "PALUDISME": ["UTILISER_UNE_MOUSTIQUAIRE", "REVENIR_SI_CA_NE_VA_PAS_MIEUX"],
    "TUBERCULOSE": ["NE_PAS_ARRETER_SEUL", "TOUSSER_DANS_LE_COUDE"],
    "VIH": ["NE_PAS_ARRETER_SEUL", "RELATIONS_PROTEGEES", "RENDEZ_VOUS_DE_CONTROLE"],
}


def _deplier(n, ids, profondeur=0):
    """Remplace chaque notion composée par ses composants : la suite ne contient que des pictogrammes de base."""
    sortie = []
    for i in ids:
        x = n.get(i)
        if x and x.get("composition") and profondeur < 3:
            sortie += _deplier(n, x["composition"], profondeur + 1)
        else:
            sortie.append(i)
    return sortie


def phrases_fonctions(n) -> list[dict]:
    """Phrases pour les intentions de communication : notions composées, douleur détaillée, consignes, conseils, réassurance, opération."""
    sorties = []

    def add(seq, fr, en, intention, locuteur):
        seq = _deplier(n, seq)
        if all(i in n for i in seq):
            sorties.append({"notions": seq, "fr": fr, "en": en, "intention": intention, "locuteur": locuteur})

    fin = lambda t: t if t.endswith(("?", ".", "!")) else t + ("" if t.endswith(" ") else ".")  # noqa: E731
    question = lambda t: t if t.endswith("?") else t + " ?"  # noqa: E731
    for x in n.values():
        if x.get("composition"):
            cat = x["categorie"]
            locuteur = "patient" if cat in ("11_douleur_description", "12_symptomes", "14_emotions_ressenti") else "medecin"
            if cat == "03_questions":
                add([x["id"]], _cap(question(x["fr"])), _cap(x["en"]) + "?", "question", "medecin")
            else:
                add([x["id"]], _cap(fin(x["fr"])), _cap(fin(x["en"])), "notion_composee:" + cat, locuteur)
    for x in n.values():
        if x["categorie"] in ("06_consignes_examen", "07_conseils_recommandations", "05_reassurance_soutien") and not x.get("composition"):
            intention = {"06_consignes_examen": "consigne", "07_conseils_recommandations": "conseil", "05_reassurance_soutien": "reassurance"}[x["categorie"]]
            add(["MEDECIN", x["id"]], _cap(fin(x["fr"])), _cap(fin(x["en"])), intention, "medecin")
    corps = [c for c in A_CORPS if c in n]
    region = {c: d for cs, d in DECLENCHEURS_PAR_REGION.items() for c in cs}
    combis = [(c, q, d) for c in corps for q in QUALITES for d in DECLENCHEURS_COMMUNS + region.get(c, []) if q in n and d in n]
    random.Random(7).shuffle(combis)
    for c, q, d in combis[:1500]:
        art = A_CORPS[c]
        sep = "" if art.endswith("'") else " "
        add(["MOI", "AVOIR_MAL", c, q, d], f"J'ai mal {art}{sep}{n[c]['fr']} : {n[q]['fr']}, {n[d]['fr']}.",
            f"My {n[c]['en']} hurts: {n[q]['en']}, {n[d]['en']}.", "douleur_detaillee", "patient")
    for mal, conseils in CONSEILS_PAR_MALADIE.items():
        if mal not in n:
            continue
        for k in conseils:
            if k in n:
                add([mal, k], f"Pour votre {n[mal]['fr']} : {n[k]['fr']}.", f"For your {n[mal]['en']}: {n[k]['en']}.", "conseil_hygiene_de_vie", "medecin")
    for t, tfr, ten in (("DEMAIN", "demain", "tomorrow"), ("APRES_DEMAIN", "après-demain", "the day after tomorrow"), ("SEMAINE", "dans une semaine", "in a week")):
        add(["OPERATION", t], f"L'opération est prévue {tfr}.", f"The surgery is planned {ten}.", "annonce_operation", "medecin")
        add(["A_JEUN_AVANT_L_OPERATION", t], f"Ne mangez rien avant l'opération de {tfr}.".replace("de dans", "prévue dans"),
            f"Do not eat before the surgery {ten}.", "consigne_operation", "medecin")
    return sorties


def jeu_phrases(sortie, notions) -> int:
    par_notion = {}
    for c in lire_jsonl(sortie / "02_pictogrammes" / "catalogue.jsonl"):
        for nid in c.get("notions", []):
            par_notion.setdefault(nid, []).append("../02_pictogrammes/" + c["fichier"])
    lignes = []
    for k, p in enumerate(phrases(notions)):
        ident = "phr-" + hashlib.sha256((" ".join(p["notions"]) + p["fr"]).encode()).hexdigest()[:12]
        lignes.append({"id": ident, **p, "images": [par_notion.get(x, [None])[0] for x in p["notions"]],
                       "synthetique": True, "a_valider": "phrase générée par gabarit : relecture par un locuteur et un médecin",
                       "split": partition(ident)})
    random.Random(2026).shuffle(lignes)
    cb.ecrire_jsonl(sortie / "05_jeux_entrainement" / "phrases_pictogrammes.jsonl", lignes)
    return len(lignes)


# ----------------------------------------------------------------------------------------- juridique
def _articles(sortie):
    for f in sorted((sortie / "01_base_juridique").rglob("articles.jsonl")):
        for a in lire_jsonl(f):
            yield a


def jeu_juridique(sortie) -> tuple[int, int]:
    cat = {s["id"]: s for s in json.loads((cb.CORPUS / "catalogue_sources.json").read_text(encoding="utf-8"))["sources"]}
    classif, par_source = [], {}
    for a in _articles(sortie):
        s = cat.get(a["source"])
        if not s or len(a["texte"]) < 60:
            continue
        par_source.setdefault(a["source"], {})[a["article"]] = a
        classif.append({"id": a["id"], "texte": a["texte"][:6000], "source": a["source"], "article": a["article"],
                        "juridiction": s["dossier"].split("/")[0], "sous_dossier": s["dossier"], "axes": s["axes"],
                        "themes": s["themes"], "type": s["type"], "langue": s["langue"], "date": s["date"],
                        "etiquetage": "faible : étiquettes du document appliquées à chacun de ses articles", "split": partition(a["id"])})
    cb.ecrire_jsonl(sortie / "05_jeux_entrainement" / "juridique_classification.jsonl", classif)
    recherche = []
    fiches = lire_jsonl(cb.RACINE / "kb" / "fiches.jsonl")
    for f in fiches:
        arts = par_source.get(f.get("source"), {})
        m = re.search(r"(\d+)", str(f.get("ref", "")))
        if not arts or not m:
            continue
        a = arts.get(m.group(1))
        if not a:
            continue
        for requete, type_req in ((f.get("title", ""), "titre_disposition"), (f.get("text", ""), "resume_disposition")):
            if requete:
                ident = f"rech-{f['id']}-{type_req}"
                recherche.append({"id": ident, "requete": requete, "positif": a["texte"][:4000], "positif_id": a["id"],
                                  "source": a["source"], "type_requete": type_req, "origine": "dispositions du juriste MEDIMCOM (kb/fiches.jsonl)",
                                  "split": partition(f["id"])})
    cb.ecrire_jsonl(sortie / "05_jeux_entrainement" / "juridique_recherche.jsonl", recherche)
    return len(classif), len(recherche)


# ----------------------------------------------------------------------------------------- références
QUESTIONS = [
    (("symptôme", "symptom", "signes", "الأعراض", "أعراض"), {"fr": "Quels sont les symptômes : {m} ?", "en": "What are the symptoms of {m}?", "ar": "ما هي أعراض {m}؟"}),
    (("traitement", "treatment", "prise en charge", "العلاج"), {"fr": "Comment traite-t-on : {m} ?", "en": "How is {m} treated?", "ar": "كيف يتم علاج {m}؟"}),
    (("prévention", "prevention", "الوقاية"), {"fr": "Comment prévenir : {m} ?", "en": "How can {m} be prevented?", "ar": "كيف يمكن الوقاية من {m}؟"}),
    (("principaux faits", "key facts", "حقائق رئيسية"), {"fr": "Quels sont les principaux faits : {m} ?", "en": "What are the key facts about {m}?", "ar": "ما هي الحقائق الرئيسية عن {m}؟"}),
    (("cause", "transmission", "facteurs de risque", "risk factors", "الأسباب", "عوامل الخطر"), {"fr": "Quelles sont les causes et facteurs de risque : {m} ?", "en": "What causes {m} and what are the risk factors?", "ar": "ما هي أسباب {m} وعوامل الخطر؟"}),
    (("diagnostic", "diagnosis", "التشخيص"), {"fr": "Comment pose-t-on le diagnostic : {m} ?", "en": "How is {m} diagnosed?", "ar": "كيف يتم تشخيص {m}؟"}),
]


def jeu_references(sortie) -> int:
    lignes = []
    for s in lire_jsonl(sortie / "03_references_medicales" / "oms_fiches.jsonl"):
        titre = s["section"].lower()
        for motifs, q in QUESTIONS:
            if any(m in titre for m in motifs):
                ident = f"qr-{s['id']}"
                lignes.append({"id": ident, "langue": s["langue"], "question": q[s["langue"]].format(m=s["titre"] or s["fiche"]),
                               "reponse": s["texte"][:4000], "maladie": s["fiche"], "notion": s["notion"], "section": s["section"],
                               "source_url": s["url"], "sha256_source": s["sha256"], "licence": s["licence"],
                               "avertissement": "information générale de l'OMS, pas un diagnostic ; le médecin décide",
                               "split": partition(s["fiche"])})
                break
    cb.ecrire_jsonl(sortie / "05_jeux_entrainement" / "references_qr.jsonl", lignes)
    return len(lignes)


def jeu_lexique(sortie, notions) -> int:
    wd = {x["notion"]: x for x in lire_jsonl(sortie / "03_references_medicales" / "lexique_multilingue_wikidata.jsonl")}
    lignes = []
    for n in notions:
        w = wd.get(n["id"], {})
        lignes.append({"notion": n["id"], "categorie": n["categorie"], "fr": n["fr"], "en": n["en"], "ar": n["ar"] or w.get("label_ar", ""),
                       "ar_origine": "vocabulaire MEDIMCOM" if n["ar"] else ("Wikidata" if w.get("label_ar") else ""),
                       "synonymes_fr": w.get("alias_fr", []), "synonymes_en": w.get("alias_en", []), "cim10": w.get("cim10", []),
                       "wikidata": w.get("wikidata", "")})
    cb.ecrire_jsonl(sortie / "05_jeux_entrainement" / "lexique_traduction.jsonl", lignes)
    return len(lignes)


def etape_entrainement(sortie) -> dict:
    notions, _ = cb.charger_vocabulaire()
    r = {"pictogrammes_images": jeu_images(sortie, notions), "phrases_pictogrammes": jeu_phrases(sortie, notions)}
    r["juridique_classification"], r["juridique_recherche"] = jeu_juridique(sortie)
    r["references_qr"] = jeu_references(sortie)
    r["lexique_traduction"] = jeu_lexique(sortie, notions)
    assistant = sortie / "04_jeu_de_donnees_assistant"
    r["cas_assistant"] = sum(1 for _ in (assistant / "cas.jsonl").open(encoding="utf-8")) if (assistant / "cas.jsonl").exists() else 0
    cb.ecrire(sortie / "05_jeux_entrainement" / "FICHE_DE_DONNEES.md", fiche_de_donnees(r))
    return r


def fiche_de_donnees(r) -> str:
    return f"""# Fiche de données — jeux d'entraînement MEDIMCOM IA

Générée le {cb.maintenant()[:10]} par `outils/constituer_base_v2.py`. Partition stable 80 / 10 / 10 (champ `split`),
calculée sur l'empreinte de l'identifiant : relancer le script ne fait pas passer un exemple d'une partition à l'autre.

| Jeu | Exemples | Origine | Réel ou synthétique | Usage visé | Licence |
|---|---|---|---|---|---|
| `pictogrammes_images.jsonl` (+ `../02_pictogrammes/metadata.jsonl`) | {r['pictogrammes_images']} | ARASAAC, Mulberry, OpenMoji | réel (images officielles des bases) | classification d'images, modèle image-texte (CLIP), recherche de pictogramme | par image (`licence`) ; ARASAAC et donc le jeu : **non commercial**, partage à l'identique |
| `phrases_pictogrammes.jsonl` | {r['phrases_pictogrammes']} | gabarits sur le vocabulaire de consultation | **synthétique**, à relire | traduction pictogrammes ⇄ texte (agent traducteur) | celle des images citées |
| `juridique_classification.jsonl` | {r['juridique_classification']} | articles des textes officiels téléchargés | réel ; étiquettes **faibles** (niveau document) | classer un article par juridiction, exigence, thème | textes officiels (domaine public ou conditions de l'éditeur) |
| `juridique_recherche.jsonl` | {r['juridique_recherche']} | dispositions du juriste (`kb/fiches.jsonl`) rapprochées des articles | réel (paires vérifiées par numéro d'article) | entraîner / évaluer le moteur de recherche du juriste | idem |
| `references_qr.jsonl` | {r['references_qr']} | fiches d'information de l'OMS (fr, en, ar) | réel (réponse = texte OMS) ; question par gabarit | assistant médical : réponses de référence, évaluation RAG | © OMS, non commercial |
| `lexique_traduction.jsonl` | {r['lexique_traduction']} | vocabulaire MEDIMCOM + Wikidata | réel ; rapprochement Wikidata automatique | traduction fr / en / ar, synonymes, codes CIM-10 | CC0 (Wikidata) |
| `../04_jeu_de_donnees_assistant/` | {r['cas_assistant']} cas | présentations cliniques du projet | **synthétique** | conversations d'entraînement de l'assistant | à faire valider par un médecin |

## Usages interdits
- Diagnostiquer ou prescrire sans médecin : MEDIMCOM aide à communiquer, **le médecin décide**.
- Usage commercial des jeux qui contiennent des images ARASAAC ou des textes de l'OMS.
- Présenter les phrases synthétiques comme des propos réels de patients.

## Limites connues
- Les étiquettes juridiques sont faibles : un article hérite des exigences de tout son document.
- Les phrases synthétiques couvrent des formulations simples ; pas de dialectes, peu de négations complexes.
- L'arabe n'est disponible que pour une partie des notions (vocabulaire historique + Wikidata).
- Aucune donnée de patient réel : tout cas clinique est fictif.

## Traçabilité
Chaque document et image a son adresse d'origine, sa date et son empreinte SHA-256 dans `../journal.json`.
"""
