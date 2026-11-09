"""Étape « references » de constituer_base_v2.py : références médicales construites de zéro, sources ouvertes et officielles.

- Fiches d'information de l'OMS (« principaux faits », symptômes, traitement, prévention) en français, anglais et arabe ;
- MedlinePlus (Bibliothèque nationale de médecine des États-Unis, domaine public) : résumés des sujets de santé, en anglais ;
- Wikidata (CC0) : lexique multilingue fr / en / ar des maladies, symptômes, parties du corps et soins du vocabulaire,
  avec code CIM-10 quand il existe.

Chaque enregistrement garde son adresse, sa date et son empreinte SHA-256.
"""
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET

import constituer_base_v2 as cb

OMS_FICHES = [  # identifiant de fiche OMS -> notion du vocabulaire la plus proche
    ("malaria", "PALUDISME"), ("diabetes", "DIABETE"), ("hypertension", "HYPERTENSION"), ("asthma", "ASTHME"),
    ("tuberculosis", "TUBERCULOSE"), ("hiv-aids", "VIH"), ("hepatitis-b", "HEPATITE"), ("hepatitis-c", "HEPATITE"),
    ("cholera", "CHOLERA"), ("typhoid", "TYPHOIDE"), ("measles", "ROUGEOLE"), ("deafness-and-hearing-loss", "SURDITE"),
    ("blindness-and-visual-impairment", "CECITE"), ("epilepsy", "EPILEPSIE"), ("depression", "DEPRESSION"),
    ("anxiety-disorders", "ANXIETE"), ("cancer", "CANCER"), ("cardiovascular-diseases-(cvds)", "CRISE_CARDIAQUE"),
    ("stroke", "AVC"), ("pneumonia", "PNEUMONIE"), ("diarrhoeal-disease", "DIARRHEE"), ("malnutrition", "MALNUTRITION"),
    ("maternal-mortality", "GROSSESSE"), ("influenza-(seasonal)", "GRIPPE"), ("coronavirus-disease-(covid-19)", "COVID"),
    ("dengue-and-severe-dengue", "DENGUE"), ("yellow-fever", "FIEVRE_JAUNE"), ("meningitis", "MENINGITE"),
    ("disability-and-health", "HANDICAP"), ("oral-health", "CARIE"), ("obesity-and-overweight", "OBESITE"),
    ("mental-disorders", "DEPRESSION"), ("newborn-mortality", "NOUVEAU_NE"), ("sexually-transmitted-infections-(stis)", "PRESERVATIF"),
    ("snakebite-envenoming", "MORSURE_DE_SERPENT"), ("rabies", "MORSURE"), ("mpox", "ERUPTION"), ("anaemia", "ANEMIE"),
    ("chronic-obstructive-pulmonary-disease-(copd)", "ESSOUFFLEMENT"), ("palliative-care", "TRAITEMENT"),
    ("immunization-coverage", "VACCINATION"), ("drinking-water", "EAU_POTABLE"), ("sanitation", "SE_LAVER_LES_MAINS"),
    ("burns", "BRULURE"), ("falls", "TOMBER"), ("road-traffic-injuries", "ACCIDENT"), ("drowning", "NOYADE"),
    ("autism-spectrum-disorders", "AUTISME"), ("adolescent-pregnancy", "ENCEINTE"), ("family-planning-contraception", "CONTRACEPTION"),
    ("antimicrobial-resistance", "ANTIBIOTIQUE"), ("sickle-cell-disease", "DREPANOCYTOSE"),
]
LANGUES = {"fr": "https://www.who.int/fr/news-room/fact-sheets/detail/", "en": "https://www.who.int/news-room/fact-sheets/detail/",
           "ar": "https://www.who.int/ar/news-room/fact-sheets/detail/"}
MEDLINE = "https://wsearch.nlm.nih.gov/ws/query?db=healthTopics&retmax=1&term="
WIKIDATA = "https://www.wikidata.org/w/api.php?format=json&"
CATEGORIES_LEXIQUE = ("09_corps_anatomie", "11_douleur_description", "12_symptomes", "17_chirurgie_operations", "20_alimentation_regime", "13_maladies_antecedents", "15_examens_actes",
                      "16_medicaments_posologie", "18_materiel_medical", "23_grossesse_enfant_sexualite", "24_handicap_aides")
LICENCE_OMS = ("© Organisation mondiale de la Santé. Reproduction non commerciale avec attribution ; vérifier les conditions "
               "d'utilisation du site de l'OMS avant toute diffusion.")
BRUIT = re.compile(r"^(skip to|aller au|partager|share|imprimer|print|related|voir aussi|see also|cookies?)\b", re.I)


def _sections(texte: str) -> tuple[str, list[dict]]:
    titre = next((l[2:].strip() for l in texte.splitlines() if l.startswith("# ")), "")
    sections, courant = [], {"section": "introduction", "lignes": []}
    for ligne in texte.splitlines():
        if ligne.startswith("## "):
            if courant["lignes"]:
                sections.append(courant)
            courant = {"section": ligne[3:].strip(), "lignes": []}
        elif ligne.strip() and not ligne.startswith("# ") and not BRUIT.match(ligne.strip()):
            courant["lignes"].append(ligne.strip())
    if courant["lignes"]:
        sections.append(courant)
    sortie = []
    for s in sections:
        t = "\n".join(s["lignes"]).strip()
        if len(t) > 80 and s["section"]:
            sortie.append({"section": s["section"], "texte": t})
    return titre, sortie


def fiches_oms(dossier, reseau, journal) -> dict:
    lignes, ok, echecs = [], 0, []
    for slug_oms, notion in OMS_FICHES:
        for langue, base in LANGUES.items():
            url = base + slug_oms
            cle = f"oms:{langue}:{slug_oms}"
            cache = dossier / "oms_fiches" / langue / f"{slug_oms}.html"
            try:
                if cache.exists() and journal.d["documents"].get(cle, {}).get("sha256") == cb.sha256(cache.read_bytes()):
                    donnees = cache.read_bytes()
                else:
                    donnees, _, url = reseau.get(url)
                    cb.ecrire(cache, donnees, binaire=True)
            except RuntimeError as e:
                echecs.append(f"{langue} {slug_oms} : {e}")
                continue
            empreinte = cb.sha256(donnees)
            journal.d["documents"][cle] = {"etat": "obtenu", "url": url, "sha256": empreinte, "date": cb.maintenant()}
            titre, sections = _sections(cb.texte_html(donnees))
            if not sections:
                echecs.append(f"{langue} {slug_oms} : page sans contenu exploitable")
                continue
            ok += 1
            meta = {"source": "OMS — fiche d'information", "fiche": slug_oms, "langue": langue, "titre": titre, "notion": notion,
                    "url": url, "sha256": empreinte, "date": cb.maintenant()[:10], "licence": LICENCE_OMS}
            md = ["---"] + [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in meta.items()] + ["---", "", f"# {titre}", ""]
            for k, s in enumerate(sections):
                md += [f"## {s['section']}", "", s["texte"], ""]
                lignes.append({"id": f"oms-{langue}-{slug_oms}-{k}", **meta, "section": s["section"], "texte": s["texte"]})
            cb.ecrire(dossier / "oms_fiches" / langue / f"{slug_oms}.md", "\n".join(md))
    cb.ecrire_jsonl(dossier / "oms_fiches.jsonl", lignes)
    return {"pages": ok, "sections": len(lignes), "echecs": echecs}


def medlineplus(dossier, reseau, notions) -> dict:
    lignes, echecs = [], []
    cibles = [n for n in notions if n["categorie"] in ("12_symptomes", "13_maladies_antecedents", "23_grossesse_enfant_sexualite", "24_handicap_aides")]
    for n in cibles:
        url = MEDLINE + urllib.parse.quote(n["en"])
        try:
            donnees, _, _ = reseau.get(url)
            racine = ET.fromstring(donnees)
        except (RuntimeError, ET.ParseError) as e:
            echecs.append(f"{n['en']} : {e}")
            if "injoignable" in str(e):
                break
            continue
        doc = racine.find(".//document")
        if doc is None:
            continue
        champs = {}
        for c in doc.findall("content"):
            texte = cb.texte_html(("<p>" + "".join(c.itertext()) + "</p>").encode())
            champs.setdefault(c.get("name"), []).append(texte)
        lignes.append({"id": f"medlineplus-{n['id']}", "notion": n["id"], "terme": n["en"], "url": doc.get("url"),
                       "titre": (champs.get("title") or [""])[0], "autres_titres": champs.get("altTitle", []),
                       "resume": (champs.get("FullSummary") or [""])[0], "mesh": champs.get("mesh", []),
                       "groupes": champs.get("groupName", []), "langue": "en", "date": cb.maintenant()[:10],
                       "licence": "MedlinePlus.gov (NLM) — domaine public sauf mention contraire ; citer MedlinePlus.gov"})
    cb.ecrire_jsonl(dossier / "medlineplus.jsonl", lignes)
    return {"sujets": len(lignes), "echecs": echecs[:20]}


def lexique_wikidata(dossier, reseau, notions) -> dict:
    cibles = [n for n in notions if n["categorie"] in CATEGORIES_LEXIQUE]
    qids, echecs = {}, []
    for n in cibles:
        url = WIKIDATA + "action=wbsearchentities&type=item&limit=1&language=en&search=" + urllib.parse.quote(n["en"])
        try:
            r = reseau.json(url)
        except (RuntimeError, ValueError) as e:
            echecs.append(f"{n['en']} : {e}")
            if "injoignable" in str(e):
                break
            continue
        if r.get("search"):
            qids[n["id"]] = r["search"][0]["id"]
    entites = {}
    liste = sorted(set(qids.values()))
    for i in range(0, len(liste), 50):
        url = WIKIDATA + "action=wbgetentities&props=labels|descriptions|aliases|claims&languages=fr|en|ar&ids=" + "|".join(liste[i:i + 50])
        try:
            entites.update(reseau.json(url).get("entities", {}))
        except (RuntimeError, ValueError) as e:
            echecs.append(f"lot {i} : {e}")
    lignes = []
    par_id = {n["id"]: n for n in cibles}
    for nid, q in qids.items():
        e = entites.get(q, {})
        lab = {l: e.get("labels", {}).get(l, {}).get("value", "") for l in ("fr", "en", "ar")}
        cim = [c["mainsnak"].get("datavalue", {}).get("value") for c in e.get("claims", {}).get("P494", []) if c.get("mainsnak")]
        lignes.append({"notion": nid, "categorie": par_id[nid]["categorie"], "terme_vocabulaire_fr": par_id[nid]["fr"],
                       "wikidata": q, "url": f"https://www.wikidata.org/wiki/{q}", **{f"label_{l}": v for l, v in lab.items()},
                       **{f"description_{l}": e.get("descriptions", {}).get(l, {}).get("value", "") for l in ("fr", "en")},
                       **{f"alias_{l}": [a["value"] for a in e.get("aliases", {}).get(l, [])][:8] for l in ("fr", "en", "ar")},
                       "cim10": [c for c in cim if c], "licence": "Wikidata — CC0",
                       "a_verifier": "rapprochement automatique par libellé anglais : vérifier que l'élément correspond au sens médical"})
    cb.ecrire_jsonl(dossier / "lexique_multilingue_wikidata.jsonl", lignes)
    cb.ecrire_csv(dossier / "lexique_multilingue_wikidata.csv", ["notion", "categorie", "fr_vocabulaire", "fr", "en", "ar", "cim10", "wikidata"],
                  [[x["notion"], x["categorie"], x["terme_vocabulaire_fr"], x["label_fr"], x["label_en"], x["label_ar"], " ".join(x["cim10"]),
                    x["wikidata"]] for x in lignes])
    return {"termes": len(lignes), "echecs": echecs[:20]}


def etape_references(sortie, reseau, journal) -> dict:
    dossier = sortie / "03_references_medicales"
    notions, _ = cb.charger_vocabulaire()
    print("  Fiches OMS (fr, en, ar)…")
    r = {"oms": fiches_oms(dossier, reseau, journal)}
    journal.sauver()
    print(f"    {r['oms']['pages']} pages, {r['oms']['sections']} sections")
    print("  MedlinePlus…")
    r["medlineplus"] = medlineplus(dossier, reseau, notions)
    print(f"    {r['medlineplus']['sujets']} sujets")
    print("  Lexique Wikidata fr / en / ar…")
    r["wikidata"] = lexique_wikidata(dossier, reseau, notions)
    print(f"    {r['wikidata']['termes']} termes")
    cb.ecrire(dossier / "LISEZMOI.md", f"""# Références médicales

| Fichier | Contenu | Licence |
|---|---|---|
| `oms_fiches/<fr|en|ar>/*.md`, `oms_fiches.jsonl` | {r['oms']['pages']} fiches d'information de l'OMS découpées en {r['oms']['sections']} sections (principaux faits, symptômes, traitement, prévention…) | {LICENCE_OMS} |
| `medlineplus.jsonl` | {r['medlineplus']['sujets']} résumés MedlinePlus (anglais) rattachés aux notions du vocabulaire | domaine public (NLM) ; citer MedlinePlus.gov |
| `lexique_multilingue_wikidata.jsonl/.csv` | {r['wikidata']['termes']} termes fr / en / ar avec alias et code CIM-10 | CC0 |

Ces textes sont des **références** pour l'assistant médical : ils n'établissent pas de diagnostic ; le médecin décide.
Les échecs éventuels sont listés dans `journal.json` (étape références).
""")
    return {k: {kk: vv for kk, vv in v.items() if kk != "echecs"} | {"echecs": len(v["echecs"])} for k, v in r.items()}
