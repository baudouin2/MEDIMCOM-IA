"""Prescription given to the patient: on screen (pictograms) and as a downloadable PDF.

Only the prescriptions judged compliant (or overridden by the doctor) AND whose pictogram explanation was
validated and sent to the patient are given to them: the patient receives what the doctor decided and explained,
nothing else. The PDF is written in pure Python (nothing to install); each prescription carries the fingerprint
of its journal line, which allows checking that it was not modified.
"""
from __future__ import annotations

from datetime import datetime, timezone


def ordonnances(ctx) -> list[dict]:
    d = ctx.dossier
    from .bibliotheque import libelle
    lignes = {l["contenu"].get("id"): l for l in ctx.journal.lignes if l["type"] == "decision" and isinstance(l["contenu"], dict)}
    prescripteurs = ctx.regles.kb.get("prescripteurs", {})
    sortie = []
    for p in d.decisions.values():
        if p.get("type") != "prescription" or p["statut"] not in ("CONFORME", "MAINTENUE"):
            continue
        explication = next((x for x in d.decisions.values() if x.get("type") == "envoi_patient"
                            and x.get("source_prescription") == p["id"] and x["statut"] == "envoye"), None)
        if not explication:
            continue
        ligne = lignes.get(p["id"]) or {}
        sortie.append({
            "id": p["id"], "medicament": p.get("medicament"), "dose": p.get("dose") or "", "posologie": p.get("posologie") or "",
            "prescripteur": (prescripteurs.get(p.get("prescripteur")) or {}).get("nom", p.get("prescripteur") or ""),
            "valide_par": (prescripteurs.get(explication.get("valide_par")) or {}).get("nom", explication.get("valide_par") or ""),
            "date": (ligne.get("heure") or datetime.now(timezone.utc).isoformat(timespec="seconds"))[:10],
            "statut": p["statut"], "maintien": (p.get("maintien") or {}).get("justification"),
            "pictogrammes": explication.get("pictogrammes") or [],
            "en_images": " · ".join(" + ".join(libelle(e) or e for e in x.split("+")) for x in explication.get("pictogrammes") or []),
            "empreinte": (ligne.get("empreinte") or "")[:16],
        })
    return sortie


# ------------------------------------------------------------------ PDF minimal (texte, Helvetica, WinAnsi)
def _echapper(t: str) -> str:
    return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _couper(t: str, n: int = 92) -> list[str]:
    mots, lignes, cour = t.split(), [], ""
    for m in mots:
        if len(cour) + len(m) + 1 > n:
            lignes.append(cour)
            cour = m
        else:
            cour = f"{cour} {m}".strip()
    return lignes + ([cour] if cour else [])


def pdf(ords: list[dict], patient: dict, session: str, pays: str = "AE") -> bytes:
    """A prescription readable by everyone (text), with the word translation of the pictograms shown to the patient."""
    lignes: list[tuple[int, str]] = [(18, "ORDONNANCE"), (10, f"MEDIMCOM IA - consultation {session} - données fictives (démonstration)"),
                                     (10, "")]
    infos = ", ".join(f"{k} : {v}" for k, v in patient.items() if v not in (None, ""))
    lignes += [(11, "Patient : " + (infos or "non renseigné")), (10, "")]
    for o in ords:
        lignes.append((13, f"{o['medicament']} {o['dose']}".strip()))
        for l in _couper(f"Mode d'emploi : {o['posologie'] or 'voir avec le médecin'}"):
            lignes.append((11, l))
        for l in _couper(f"En images (montré au patient) : {o['en_images']}"):
            lignes.append((10, l))
        lignes.append((9, f"Prescrit par {o['prescripteur']} le {o['date']} ; explication validée par {o['valide_par']}."))
        lignes.append((9, f"Vérifiée par le juriste de MEDIMCOM IA : {'conforme' if o['statut'] == 'CONFORME' else 'maintenue par le médecin'}."
                          f" Empreinte du journal : {o['empreinte']}"))
        if o.get("maintien"):
            for l in _couper(f"Justification du médecin : {o['maintien']}"):
                lignes.append((9, l))
        lignes.append((10, ""))
    lignes += [(9, "Ne dépassez pas la dose prescrite. En cas de doute ou d'effet inattendu, montrez cette ordonnance à un médecin"),
               (9, "ou à un pharmacien." + (" Urgence aux Émirats : 998." if pays == "AE" else "")),
               (9, "Document produit par un prototype de recherche (ITU AI for Good) : il ne remplace pas une ordonnance officielle.")]
    pages, cour, y = [], [], 800
    for taille, texte in lignes:
        pas = taille + 6
        if y - pas < 40:
            pages.append(cour)
            cour, y = [], 800
        y -= pas
        cour.append((taille, y, texte))
    pages.append(cour)
    objets = ["<< /Type /Catalog /Pages 2 0 R >>", None,
              "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    kids = []
    for page in pages:
        flux = "BT\n" + "".join(f"/F1 {t} Tf 1 0 0 1 50 {y} Tm ({_echapper(x)}) Tj\n" for t, y, x in page) + "ET"
        donnees = flux.encode("cp1252", "replace")
        objets.append(f"<< /Length {len(donnees)} >>\nstream\n".encode("latin-1") + donnees + b"\nendstream")
        objets.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> "
                      f"/Contents {len(objets)} 0 R >>")
        kids.append(len(objets))
    objets[1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"
    sortie, positions = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
    for i, o in enumerate(objets, 1):
        positions.append(len(sortie))
        corps = o if isinstance(o, bytes) else o.encode("latin-1")
        sortie += f"{i} 0 obj\n".encode() + corps + b"\nendobj\n"
    xref = len(sortie)
    sortie += f"xref\n0 {len(objets) + 1}\n0000000000 65535 f \n".encode()
    sortie += "".join(f"{p:010d} 00000 n \n" for p in positions).encode()
    sortie += f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(sortie)
