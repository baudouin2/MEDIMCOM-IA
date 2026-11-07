"""Rapport de responsabilités tiré du journal chaîné (demande du hackathon : traçabilité, défaillances de l'IA et des
textes juridiques, y compris en crise, et aide à établir les responsabilités).

Pour chaque message au patient et chaque prescription : QUI l'a proposé (agent), CE QUE le juriste a jugé et sur
QUELLE base (loi, norme, recommandation, garde-fou du système), QUI a décidé (médecin nommé, avec sa justification),
ce qui est parti. Puis les défaillances de l'IA (modèle indisponible, contrôle oublié rattrapé par le filet de
sécurité, action refusée par un garde-fou, traduction corrigée par le médecin…) et les lacunes du droit (situations
qu'aucun texte lu ne règle, mesures de crise refusées faute de base légale). Tout vient du journal : rien n'est inventé.
"""
from __future__ import annotations

from collections import Counter

DEFAILLANCES = {
    "modele_indisponible": "Modèle en ligne indisponible au démarrage",
    "degradation": "Modèle en échec : repli sur les règles écrites",
    "nouvel_essai_modele": "Nouvel essai du modèle",
    "modele_retabli": "Modèle rétabli",
    "modele_remplace": "Modèle demandé absent : remplacé",
    "filet_de_securite": "Contrôle oublié par un agent, rattrapé par le filet de sécurité",
    "boucle_detectee": "Le modèle répétait la même action : arrêté",
    "validation_refusee": "Validation refusée (contenu bloqué ou message vide)",
    "pictogrammes_modifies": "Traduction de l'IA corrigée par le médecin",
    "suggestion_ignoree": "Suggestion de l'assistant écartée par le médecin",
    "message_agent_masque": "Message d'un agent écarté par le médecin",
    "rejet": "Proposition de l'IA annulée par le médecin",
    "erreur_evenement": "Erreur technique pendant un événement",
    "erreur_reflexion": "Erreur technique pendant la réflexion du modèle",
}
HUMAINS = {"validation": "a validé l'envoi", "maintien": "a maintenu la décision malgré l'avis « à revoir »",
           "contexte_confirme": "a confirmé le sens d'un message ambigu", "message_retire": "a retiré un message de l'écran du patient",
           "question_choisie": "a choisi une question de l'assistant", "langue": "a changé la langue"}


def rapport(lignes: list[dict]) -> dict:
    decisions: dict[int, dict] = {}
    defaillances, refus, lacunes, crise, humains = [], Counter(), [], [], []
    exemples_refus: dict[str, str] = {}
    for l in lignes:
        t, c, n, qui = l["type"], l["contenu"], l["n"], l["agent"]
        if not isinstance(c, dict):
            continue
        if t == "decision":
            decisions[c["id"]] = {"id": c["id"], "type": c.get("type"), "auteur": c.get("auteur"), "texte": c.get("texte") or c.get("medicament"),
                                  "medicament": c.get("medicament"), "ligne": n, "verdicts": [], "humains": [], "fin": None,
                                  "prescripteur": c.get("prescripteur") if c.get("type") == "prescription" and c.get("auteur") == "medecin" else None}
        elif t == "verdict" and c.get("decision_id") in decisions:
            bases = sorted({k.get("base", "?") for k in c.get("constats", []) if k.get("niveau") != "CONFORME"})
            refs = sorted({k.get("reference_courte", "") for k in c.get("constats", []) if k.get("reference_courte") not in (None, "", "-")})
            decisions[c["decision_id"]]["verdicts"].append({"ligne": n, "verdict": c.get("verdict"), "bases": bases, "references": refs[:4],
                                                            "precontrole": bool(c.get("precontrole"))})
        elif t in HUMAINS:
            ident = c.get("id")
            entree = {"ligne": n, "heure": l.get("heure"), "par": c.get("valide_par") or c.get("par") or qui, "action": HUMAINS[t],
                      "justification": c.get("justification") or c.get("raison")}
            humains.append(entree)
            if ident in decisions:
                decisions[ident]["humains"].append(entree)
        elif t in ("envoye_au_patient", "decision_annulee", "rejet") and c.get("id") in decisions:
            decisions[c["id"]]["fin"] = {"envoye_au_patient": "envoyé au patient", "decision_annulee": "annulé", "rejet": "annulé par le médecin"}[t]
        if t == "document_lu" and c.get("statut") != "lu":
            defaillances.append({"ligne": n, "agent": qui, "quoi": "Document du patient non lu automatiquement",
                                 "detail": str(c.get("erreur_modele") or c.get("statut"))[:200]})
        if t in DEFAILLANCES:
            defaillances.append({"ligne": n, "agent": qui, "quoi": DEFAILLANCES[t],
                                 "detail": str(c.get("erreur") or c.get("message") or c.get("raison") or c.get("modele") or "")[:200]})
        if t == "action" and str(c.get("resultat", "")).startswith("Refusé") and qui not in ("medecin", "patient"):
            refus[qui] += 1
            exemples_refus.setdefault(qui, f"{c.get('outil')} : {str(c.get('resultat'))[:180]}")
        if t == "lacune":
            lacunes.append({"ligne": n, "id": c.get("id") or c.get("lacune_id"), "sujet": c.get("sujet"), "detail": str(c.get("detail", ""))[:300]})
        if t in ("mesure", "incident") or (t == "action" and qui in ("autorite_sante", "hopital", "cellule_crise")):
            crise.append({"ligne": n, "agent": qui, "type": t, "detail": str(c.get("mesure") or c.get("description") or c.get("resultat") or "")[:240]})
    chaines = []
    for d in decisions.values():
        dernier = d["verdicts"][-1] if d["verdicts"] else None
        decideur = next((h["par"] for h in reversed(d["humains"]) if h["action"] in (HUMAINS["validation"], HUMAINS["maintien"])), None) \
            or d.get("prescripteur")                      # une prescription est elle-même la décision du médecin
        chaines.append({**d, "dernier_verdict": dernier, "decideur": decideur,
                        "responsabilite": ("décision humaine : " + decideur) if decideur else
                                          ("bloqué par le juriste avant toute décision humaine" if dernier and dernier["verdict"] == "BLOQUE" else
                                           "en attente d'une décision humaine")})
    return {"chaines": chaines, "humains": humains, "defaillances": defaillances, "refus_par_agent": dict(refus),
            "exemples_refus": exemples_refus, "lacunes": lacunes, "crise": crise,
            "bilan": {"decisions": len(chaines), "envoyes": sum(1 for d in chaines if d["fin"] == "envoyé au patient"),
                      "bloques_par_le_juriste": sum(1 for d in chaines if d["dernier_verdict"] and d["dernier_verdict"]["verdict"] == "BLOQUE"),
                      "decisions_humaines": len(humains), "defaillances": len(defaillances), "actions_refusees": sum(refus.values()),
                      "lacunes": len(lacunes), "evenements_de_crise": len(crise)}}
