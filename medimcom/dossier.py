"""Shared consultation record, read and written continuously by the agents.

Each change increments `version` and is written in the journal, which lets each agent see "what changed since
its last pass".
"""
from itertools import count


class Dossier:
    def __init__(self, journal):
        self.journal = journal
        self.version = 0
        self.historique: list[dict] = []       # (version, type, summary)
        self.etat: dict[str, dict] = {}        # key -> {valeur, source, confirme}
        self.etat_version = 0                  # version of the last state change
        self.fil: list[dict] = []              # consultation exchanges
        self.questions_a_poser: list[dict] = []
        self.suggestions: dict[int, dict] = {}
        self.decisions: dict[int, dict] = {}   # doctor's decisions (prescriptions...)
        self.verdicts: list[dict] = []
        self.lacunes: list[dict] = []
        self._ids = count(1)

    # ------------------------------------------------------------------ interne
    def _changer(self, auteur: str, type_chg: str, contenu: dict) -> None:
        self.version += 1
        self.historique.append({"version": self.version, "type": type_chg, "auteur": auteur, "contenu": contenu})
        self.journal.ajouter(auteur, type_chg, contenu)

    def changements_depuis(self, version: int) -> list[dict]:
        return [h for h in self.historique if h["version"] > version]

    # ------------------------------------------------------------------ writes
    def ajouter_echange(self, auteur: str, texte: str, donnees: dict | None = None, confirme: bool = True,
                        details: dict | None = None) -> None:
        # "v": version of the record at the time of the exchange (chronological order shared with the decisions)
        e = {"auteur": auteur, "texte": texte, "donnees": donnees or {}, "confirme": confirme, "v": self.version + 1, **(details or {})}
        self.fil.append(e)
        self._changer(auteur, "echange", e)

    def maj_etat(self, auteur: str, cle: str, valeur, source: str, confirme: bool) -> str:
        ancien = self.etat.get(cle)
        self.etat[cle] = {"valeur": valeur, "source": source, "confirme": bool(confirme)}
        self.etat_version = self.version + 1
        self._changer(auteur, "etat", {"cle": cle, "valeur": valeur, "source": source, "confirme": bool(confirme),
                                       "ancienne_valeur": ancien["valeur"] if ancien else None})
        if confirme:
            for q in self.questions_a_poser:
                if q.get("cle") == cle and q["statut"] in ("en_attente", "posee"):
                    q["statut"] = "repondue"
        return f"État mis à jour : {cle} = {valeur!r} ({'confirmé' if confirme else 'non confirmé'})."

    def ajouter_question(self, auteur: str, question: str, raison: str, cle: str | None = None) -> str:
        if any((q["question"].lower() == question.lower() or (cle and q.get("cle") == cle)) and q["statut"] == "en_attente"
               for q in self.questions_a_poser):
            return "Cette question est déjà en attente : rien de plus à faire."
        q = {"id": next(self._ids), "question": question, "raison": raison, "cle": cle,
             "statut": "en_attente", "auteur": auteur}
        self.questions_a_poser.append(q)
        self._changer(auteur, "question", q)
        return f"Question {q['id']} transmise au traducteur (à valider par le médecin) : {question}"

    def statut_question(self, auteur: str, qid: int | None, statut: str, raison: str = "") -> None:
        """en_attente -> posee (message sent) -> repondue; or rejetee / annulee (the doctor does not ask it)."""
        q = next((q for q in self.questions_a_poser if q["id"] == qid), None)
        if q and q["statut"] != statut and q["statut"] != "repondue":
            q["statut"] = statut
            self._changer(auteur, "question_statut", {"id": q["id"], "statut": statut, "raison": raison})

    def ajouter_suggestion(self, auteur: str, type_s: str, texte: str, raison: str, source: str) -> str:
        s = {"id": next(self._ids), "type": type_s, "texte": texte, "raison": raison, "source": source,
             "statut": "proposee_au_medecin", "auteur": auteur}
        self.suggestions[s["id"]] = s
        self._changer(auteur, "suggestion", s)
        return f"Suggestion {s['id']} proposée au médecin."

    def retirer_suggestion(self, auteur: str, id_s: int, raison: str) -> str:
        s = self.suggestions.get(int(id_s))
        if not s:
            return f"Suggestion {id_s} introuvable."
        s["statut"] = "retiree"
        self._changer(auteur, "suggestion_retiree", {"id": s["id"], "raison": raison})
        return f"Suggestion {id_s} retirée."

    def ajouter_decision(self, auteur: str, decision: dict) -> int:
        d = {"id": next(self._ids), "auteur": auteur, "statut": "a_verifier", "verifiee_a_version_etat": None, **decision,
             "v": self.version + 1}
        self.decisions[d["id"]] = d
        self._changer(auteur, "decision", d)
        return d["id"]

    def ajouter_verdict(self, auteur: str, verdict: dict) -> None:
        self.verdicts.append(verdict)
        d = self.decisions.get(verdict.get("decision_id"))
        if d:
            # A named override stays valid as long as the verdict does not worsen AND no new "to review" reason appears:
            # the doctor only justified the reasons they examined.
            motifs = {c["regle"] for c in verdict.get("constats", []) if c["niveau"] == "A_REVOIR"}
            m = d.get("maintien")
            garde = bool(m) and verdict["verdict"] == "A_REVOIR" and motifs <= set(m.get("motifs", motifs))
            d["statut"] = "MAINTENUE" if garde else verdict["verdict"]
            d["verifiee_a_version_etat"] = self.etat_version
            if m and not garde and verdict["verdict"] != "CONFORME":
                d["maintien"] = None                 # verdict worsened or new reason: the override lapses
                self._changer(auteur, "maintien_caduc", {"id": d["id"], "verdict": verdict["verdict"], "motifs": sorted(motifs)})
        self._changer(auteur, "verdict", {**verdict, "statut_decision": d["statut"] if d else None})

    def maintenir_decision(self, auteur: str, decision_id: int, medecin: str, justification: str, regles) -> str:
        """A named human overrides a "to review" decision. Impossible for a blocked decision."""
        d = self.decisions.get(int(decision_id))
        if not d:
            return f"Refusé : décision {decision_id} introuvable."
        ok, raison = regles.autoriser_maintien(d["statut"], medecin, justification)
        if not ok:
            self._changer(auteur, "maintien_refuse", {"id": d["id"], "par": medecin, "raison": raison})
            return f"Refusé : {raison}"
        dernier = next((v for v in reversed(self.verdicts) if v.get("decision_id") == d["id"]), {})
        motifs = sorted({c["regle"] for c in dernier.get("constats", []) if c["niveau"] == "A_REVOIR"})
        d["maintien"] = {"par": medecin, "justification": justification, "motifs": motifs}
        d["statut"] = "MAINTENUE"
        self._changer(auteur, "maintien", {"id": d["id"], "par": medecin, "justification": justification, "motifs": motifs})
        return f"Décision {d['id']} maintenue par {medecin} : {justification}"

    def ajouter_lacune(self, auteur: str, sujet: str, detail: str, lacune_id: str | None = None) -> str:
        if any(x["sujet"] == sujet for x in self.lacunes):
            return f"Lacune déjà enregistrée : {sujet}"
        l = {"id": lacune_id, "sujet": sujet, "detail": detail}
        self.lacunes.append(l)
        self._changer(auteur, "lacune", l)
        return f"Lacune enregistrée : {sujet}"

    # ------------------------------------------------------------------ lecture
    def resume(self) -> str:
        etat = "\n".join(f"  - {k} = {v['valeur']!r} ({'confirmé' if v['confirme'] else 'NON confirmé'} ; source : {v['source']})"
                         for k, v in self.etat.items()) or "  (vide)"
        fil = "\n".join(f"  - [{e['auteur']}] {e['texte']}" for e in self.fil[-8:]) or "  (vide)"
        qs = "\n".join(f"  - #{q['id']} {q['question']} [{q['statut']}]" for q in self.questions_a_poser) or "  (aucune)"
        sg = "\n".join(f"  - #{s['id']} ({s['type']}) {s['texte']} [{s['statut']}]" for s in self.suggestions.values()) or "  (aucune)"
        dc = "\n".join(f"  - #{d['id']} {d.get('type')} {d.get('medicament') or d.get('texte', '')[:50]} "
                       f"par {d.get('prescripteur') or d['auteur']} [{d['statut']}]"
                       for d in self.decisions.values()) or "  (aucune)"
        lc = "\n".join(f"  - {l['id'] or '-'} {l['sujet']}" for l in self.lacunes) or "  (aucune)"
        return (f"ÉTAT DU PATIENT :\n{etat}\nDERNIERS ÉCHANGES :\n{fil}\nQUESTIONS À POSER :\n{qs}\n"
                f"SUGGESTIONS :\n{sg}\nDÉCISIONS ET DEMANDES :\n{dc}\nLACUNES SIGNALÉES :\n{lc}")
