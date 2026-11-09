"""Documents du patient joints par le médecin : photo d'ordonnance manuscrite, facture de pharmacie, boîte de
médicament, compte rendu, radiographie, analyse… Les agents en tirent ce qui sert à la sécurité du patient.

  - Texte (.txt) et PDF à texte : lus directement (pypdf s'il est installé).
  - Photos et PDF scannés : lus par le modèle en ligne s'il est branché et accepte les images (Grok le fait) ;
    sinon le document est joint au dossier et le médecin le lit lui-même (dit clairement, jamais en silence).
  - Ce qui est extrait (médicaments, maladies, allergies) entre dans le dossier comme fait NON CONFIRMÉ, avec la
    source « document » : l'assistant vérifie les risques pour ce patient, le médecin confirme ou corrige.
Seule l'empreinte (SHA-256) du document est inscrite au journal, jamais son contenu.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from datetime import datetime, timezone

TYPES = {"ordonnance": "ordonnance", "facture": "facture de pharmacie", "traitement": "boîte ou notice de médicament",
         "radio": "radiographie ou imagerie", "analyse": "résultat d'analyse", "compte_rendu": "compte rendu médical", "autre": "autre"}
TAILLE_MAX = 8 * 1024 * 1024

CONSIGNE = (
    "Tu lis un document médical d'un patient (photo d'ordonnance manuscrite, facture de pharmacie, boîte de médicament, "
    "compte rendu, analyse, radiographie). Réponds UNIQUEMENT par un objet JSON : "
    '{"type_document": "", "medicaments": [{"nom": "", "dose": "", "posologie": ""}], "maladies": [], "allergies": [], '
    '"examens": [{"nom": "", "resultat": ""}], "date": "", "resume": "une phrase en français", '
    '"lisibilite": "bonne|moyenne|mauvaise"}. '
    "N'invente rien : laisse vide ce qui est illisible ou absent. Pour une radiographie, décris seulement ce qui est écrit "
    "sur le document (compte rendu, légende) : tu ne poses aucun diagnostic.")


def nouveau(nom: str, type_doc: str, mime: str, contenu_b64: str, numero: int) -> tuple[dict, bytes]:
    octets = base64.b64decode(contenu_b64.split(",", 1)[-1], validate=False)
    if len(octets) > TAILLE_MAX:
        raise ValueError(f"document trop lourd ({len(octets) // 1024} Ko ; maximum {TAILLE_MAX // 1024 // 1024} Mo)")
    if not (mime.startswith("image/") or mime in ("application/pdf", "text/plain")):
        raise ValueError("format accepté : image (photo), PDF ou texte")
    doc = {"id": numero, "nom": re.sub(r"[^\w .,()-]", "_", nom)[:80] or f"document_{numero}", "type": type_doc if type_doc in TYPES else "autre",
           "mime": mime, "taille": len(octets), "sha256": hashlib.sha256(octets).hexdigest(),
           "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "extraction": {"statut": "en_cours", "par": None, "resume": "", "medicaments": [], "maladies": [], "allergies": [],
                          "examens": [], "texte": ""}}
    return doc, octets


def texte_pdf(octets: bytes) -> str:
    for module in ("pypdf", "PyPDF2"):
        try:
            m = __import__(module)
            lecteur = m.PdfReader(io.BytesIO(octets))
            return "\n".join((p.extract_text() or "") for p in lecteur.pages[:20]).strip()
        except ImportError:
            continue
        except Exception:  # noqa: BLE001 — PDF illisible : on le dit
            return ""
    return ""


def _json(texte: str) -> dict:
    m = re.search(r"\{.*\}", texte or "", flags=re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except ValueError:
        return {}


def lire(doc: dict, octets: bytes, cerveau, medicaments: dict) -> dict:
    """Extraction : texte direct (txt, PDF à texte), puis modèle en ligne pour les images ; enfin lecture déterministe
    (médicaments, maladies) du texte obtenu, pour ne jamais dépendre du seul modèle."""
    from .faits import extraire_faits
    from .lecture import trouver_medicaments
    ex = dict(doc["extraction"])
    texte = ""
    if doc["mime"] == "text/plain":
        texte, ex["par"] = octets.decode("utf-8", "replace")[:20000], "lecture directe"
    elif doc["mime"] == "application/pdf":
        texte = texte_pdf(octets)
        ex["par"] = "lecture directe du PDF" if texte else None
    lu = {}
    if hasattr(cerveau, "lire_document") and (doc["mime"].startswith("image/") or (texte and len(texte) > 40)):
        try:
            lu = _json(cerveau.lire_document(octets if doc["mime"].startswith("image/") else None, doc["mime"], CONSIGNE, texte))
            ex["par"] = f"modèle en ligne ({getattr(cerveau, 'modele', '?')})" + (" + lecture directe" if texte else "")
        except Exception as e:  # noqa: BLE001 — modèle indisponible ou sans vision : on le dit
            ex["erreur_modele"] = str(e)[:200]
    if not texte and not lu:
        ex.update(statut="non_lu", resume=("Photo jointe au dossier : lecture automatique impossible sans modèle en ligne "
                                          "acceptant les images. Lisez-la et reportez les informations utiles dans la fiche."))
        return ex
    # Lecture déterministe en plus du modèle : les médicaments connus sont toujours repérés, même si le modèle les oublie
    meds = {m["nom"]: m for m in trouver_medicaments(texte + " " + json.dumps(lu, ensure_ascii=False), medicaments)}
    for m in lu.get("medicaments") or []:
        if isinstance(m, dict) and m.get("nom"):
            nom = (trouver_medicaments(str(m["nom"]), medicaments) or [{"nom": str(m["nom"]).lower()}])[0]["nom"]
            meds[nom] = {"nom": nom, "dose": m.get("dose", ""), "posologie": m.get("posologie", "")}
    faits = extraire_faits(texte + " " + " ".join(map(str, lu.get("maladies") or [])))
    ex.update(statut="lu", texte=texte[:3000], resume=str(lu.get("resume") or (texte[:200] + ("…" if len(texte) > 200 else ""))),
              medicaments=[{"nom": n, "dose": m.get("dose", ""), "posologie": m.get("posologie", "")} for n, m in meds.items()],
              maladies=list(dict.fromkeys([str(x) for x in (lu.get("maladies") or [])] + faits.get("maladies_connues", []))),
              allergies=[str(x) for x in (lu.get("allergies") or [])], examens=lu.get("examens") or [],
              lisibilite=lu.get("lisibilite"), faits={k: v for k, v in faits.items() if k != "maladies_connues"})
    return ex


def faits_du_document(doc: dict) -> dict:
    """Faits à proposer au dossier (NON confirmés) : le médecin les confirme ou les corrige."""
    ex = doc["extraction"]
    donnees = dict(ex.get("faits") or {})
    if ex.get("medicaments"):
        donnees["medicaments_declares"] = ", ".join(m["nom"] for m in ex["medicaments"])
    if ex.get("maladies"):
        donnees["maladies_connues"] = ex["maladies"]
    if ex.get("allergies"):
        donnees["allergies"] = ", ".join(ex["allergies"])
    return donnees
