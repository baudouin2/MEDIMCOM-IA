"""Coordinator: releases the events one by one and lets the agents react.

It imposes no order on the agents: at each "round", each agent looks at its messages and the record,
and decides whether it has something to do. It stops when no agent acts any more (the system is stable)
or after `max_rounds`.
"""
import json
import random

from .agents import precontrole_a_jour


class Orchestrateur:
    def __init__(self, ctx, agents: list, max_rounds: int = 8, ordre: str = "fixe", graine: int = 0):
        self.ctx = ctx
        self.agents = agents
        self.max_rounds = max_rounds
        self.ordre = ordre                      # "aleatoire": the order of play changes at each round
        self.hasard = random.Random(graine)
        self.apres_tour = None                  # callback after each agent action (the interface refreshes its screen)

    def appliquer(self, evt: dict) -> None:
        d = self.ctx.dossier
        t = evt["type"]
        if t == "echange":
            d.ajouter_echange(evt["auteur"], evt["texte"], evt.get("donnees"), evt.get("confirme", True))
            # What the DOCTOR enters in the record goes into the patient's state at once, without waiting for the
            # assistant's turn: with a slow (or failing) online model, the record stayed empty for tens of seconds and
            # the jurist said "missing information" although everything was filled in (feedback of 9 November). What a
            # DOCUMENT suggests also goes in at once, but only if it contradicts nothing: UNconfirmed.
            for cle, valeur in (evt.get("donnees") or {}).items():
                actuel = d.etat.get(cle)
                if evt["auteur"] == "medecin" and evt.get("confirme", True):
                    if not actuel or actuel["valeur"] != valeur or not actuel["confirme"]:
                        d.maj_etat("medecin", cle, valeur, "fiche saisie par le médecin", True)
                elif evt["auteur"] == "document" and actuel is None:
                    d.maj_etat("document", cle, valeur, f"document : {evt['texte'][:60]}", False)
        elif t == "prescription":
            if evt.get("remplace_medicament"):
                for dec in d.decisions.values():
                    if dec.get("medicament") == evt["remplace_medicament"] and dec["statut"] != "annulee":
                        dec["statut"] = "annulee"
                        d._changer(evt["auteur"], "decision_annulee", {"id": dec["id"], "raison": "remplacée par le médecin"})
            champs = ("medicament", "prescripteur", "dose", "posologie", "mode", "urgence", "issue_de_suggestion")
            d.ajouter_decision(evt["auteur"], {"type": "prescription", "texte": evt.get("texte", ""),
                                               **{k: evt.get(k) for k in champs}})
        elif t == "partage_donnees":
            d.ajouter_decision(evt["auteur"], {"type": "partage_donnees", "demande": evt["demande"], "texte": evt.get("texte", "")})
        elif t == "envoi_patient":
            # A message coming from outside is NEVER considered validated, even if it declares a validator: only a
            # recorded validation (doctor's "validation" event) counts. Defect found by the automatic exploration
            # (medimcom/exploration.py, monitor property R8).
            d.ajouter_decision(evt["auteur"], {"type": "envoi_patient", "texte": evt["texte"],
                                               "contenu_type": evt.get("contenu_type"), "valide_par": None,
                                               "valide_par_declare": evt.get("valide_par")})
        elif t == "maintien":
            cible = evt.get("decision_id") or self._chercher(evt)
            if cible is None:
                print("  ⚑ Refusé : aucune décision correspondante.")
            else:
                print(f"  ⚑ {d.maintenir_decision(evt['auteur'], cible, evt['medecin'], evt.get('justification', ''), self.ctx.regles)}")
        elif t == "reponse_patient":
            contenu = json.dumps({"pictogrammes": evt["pictogrammes"]}, ensure_ascii=False)
            self.ctx.messagerie.envoyer("patient", "traducteur", "information", contenu)
        elif t == "texte_medecin":
            # The doctor writes to the patient: a question goes through the question list (the translator takes it),
            # information is handed directly to the translator.
            if evt.get("contenu_type") == "question":
                d.ajouter_question("medecin", evt["texte"], "question du médecin", evt.get("cle") or None)
            else:
                self.ctx.messagerie.envoyer("medecin", "traducteur", "demande", evt["texte"])
        elif t == "suggestion_ignoree":
            sg = d.suggestions.get(int(evt["suggestion_id"]))
            if sg and sg["statut"] == "proposee_au_medecin":
                sg["statut"] = "ignoree"
                d._changer("medecin", "suggestion_ignoree", {"id": sg["id"]})
        elif t == "validation":
            r = self._valider(evt)
            print(f"  {'✖' if r.startswith('Refusé') else '✔'} {r}")
        elif t == "rejet":
            print(f"  ✖ {self._rejeter(evt)}")
        elif t == "poser_question":
            # The doctor picks, in the Assistant tab, a question proposed by the assistant: it is translated; if they
            # clicked "Send" after seeing the preview, it leaves as soon as the jurist has judged it compliant.
            q = next((q for q in d.questions_a_poser if q["id"] == int(evt["question_id"])), None)
            if not q or q["statut"] != "en_attente":
                print("  ✖ Refusé : question introuvable ou déjà traitée.")
            else:
                q["autorisee"] = True
                if not evt.get("modifier"):
                    q["valider_auto_par"] = evt.get("medecin")
                d._changer("medecin", "question_choisie", {"id": q["id"], "par": evt.get("medecin"),
                                                           "envoi": "après modification" if evt.get("modifier") else "direct"})
                print(f"  ✔ Question #{q['id']} choisie : traduction en cours.")
        elif t == "refus_question":
            q = next((q for q in d.questions_a_poser if q["id"] == int(evt["question_id"])), None)
            if q and q["statut"] == "en_attente":
                d.statut_question("medecin", q["id"], "refusee", evt.get("raison", "refusée par le médecin"))
                print(f"  ✔ Question #{q['id']} refusée.")
        elif t == "retrait_message":
            r = self._retirer(evt)
            print(f"  {'✖' if r.startswith('Refusé') else '✔'} {r}")
        elif t == "masquage_message":
            r = self._masquer(evt)
            print(f"  {'✖' if r.startswith('Refusé') else '✔'} {r}")
        elif t == "modification_pictogrammes":
            r = self._modifier_pictogrammes(evt)
            print(f"  {'✖' if r.startswith('Refusé') else '✔'} {r}")
        elif t == "message":
            res = self.ctx.messagerie.envoyer(evt["auteur"], evt["a"], evt.get("type_message", "information"), evt["texte"])
            if res.startswith("Refusé"):
                raise ValueError(res)
        elif t == "question":
            res = self.ctx.messagerie.envoyer(evt["auteur"], evt["a"], "demande", evt["texte"])
            if res.startswith("Refusé"):
                raise ValueError(res)
        else:
            raise ValueError(f"Type d'événement inconnu : {t}")

    def _chercher(self, evt: dict):
        """Last decision targeted by an override: by medicine, or by type (e.g. partage_donnees)."""
        for dec in reversed(list(self.ctx.dossier.decisions.values())):
            if evt.get("medicament") and dec.get("medicament") == evt["medicament"]:
                return dec["id"]
            if evt.get("objet") and dec.get("type") == evt["objet"] and dec["statut"] == "A_REVOIR":
                return dec["id"]
        return None

    def _valider(self, evt: dict) -> str:
        """The doctor validates ONE translator proposal: the one given, or the only pending one of the given type."""
        d = self.ctx.dossier
        if evt.get("auteur") != "medecin":
            return "Refusé : seul le médecin valide un message destiné au patient."
        if evt.get("decision_id"):
            cible = d.decisions.get(evt["decision_id"])
        else:
            props = [x for x in d.decisions.values() if x.get("type") == "envoi_patient" and x["statut"] == "attente_validation"
                     and (not evt.get("contenu_type") or x.get("contenu_type") == evt["contenu_type"])]
            if len(props) > 1:
                return f"Refusé : {len(props)} propositions en attente ; préciser decision_id."
            cible = props[0] if props else None
        if not cible or cible.get("type") != "envoi_patient" or cible["statut"] != "attente_validation":
            return "Refusé : aucune proposition en attente de validation."
        if not [p for p in cible.get("pictogrammes") or [] if p]:
            d._changer(evt["auteur"], "validation_refusee", {"id": cible["id"], "raison": "aucun pictogramme"})
            return ("Refusé : ce message n'a aucun pictogramme, le patient ne verrait rien. Ajoutez-en (Modifier les "
                    "pictogrammes) ou reformulez.")
        pc = cible.get("precontrole") or {}
        if pc.get("verdict") == "BLOQUE" and pc.get("texte") == cible.get("texte"):
            motif = next((c["detail"] for c in pc.get("constats", []) if c["niveau"] == "BLOQUE"), "contenu interdit")
            d._changer(evt["auteur"], "validation_refusee", {"id": cible["id"], "raison": motif})
            return f"Refusé : le juriste a bloqué ce message, il ne peut pas être envoyé. {motif}"
        if pc.get("texte") == cible.get("texte") and any(c["regle"] == "CONTEXTE-A-CONFIRMER" and c["niveau"] == "A_REVOIR"
                                                         for c in pc.get("constats", [])):
            if not evt.get("confirme_contexte"):
                return ("Refusé : le sens de ce message est à confirmer (ni consigne ni incitation ?). "
                        "Confirmez-le en le validant, ou reformulez.")
            cible["contexte_confirme_par"] = evt["medecin"]
            d._changer(evt["auteur"], "contexte_confirme", {"id": cible["id"], "par": evt["medecin"], "texte": cible.get("texte")})
        cible["valide_par"] = evt["medecin"]
        cible["statut"] = "a_verifier"
        d._changer(evt["auteur"], "validation", {"id": cible["id"], "valide_par": evt["medecin"]})
        return f"Proposition #{cible['id']} validée par {evt['medecin']} : {' '.join(cible.get('pictogrammes', []))}"

    def _modifier_pictogrammes(self, evt: dict) -> str:
        """The doctor corrects the translation of a proposal before validating it (add, remove, order, combine).
        Same safeguards as for the translator agent: known pictograms only, and never removing the negation, the
        limit, the emergency, STOP, a number, a dose or a medicine present in the translation."""
        from .bibliotheque import connu
        d = self.ctx.dossier
        cible = d.decisions.get(int(evt["decision_id"]))
        if not cible or cible.get("type") != "envoi_patient" or cible["statut"] != "attente_validation":
            return "Refusé : seule une proposition en attente de validation peut être modifiée."
        choix = [str(x) for x in evt.get("pictogrammes", [])][:12]
        if not choix:
            return "Refusé : aucun pictogramme."
        inconnus = [x for x in choix if not connu(x)]
        if inconnus:
            return f"Refusé : pictogramme ou combinaison inconnu(e) ou interdit(e) : {', '.join(inconnus)}."
        traducteur = next((a for a in self.agents if a.nom == "traducteur"), None)
        if traducteur is not None:
            motif = traducteur._verifier_choix(cible.get("pictogrammes") or [], choix)
            if motif:
                return f"Refusé : {motif}."
        avant = cible.get("pictogrammes")
        cible["pictogrammes"], cible["pictogrammes_choisis_par"] = choix, f"médecin ({evt.get('medecin', 'médecin')})"
        d._changer(evt.get("auteur", "medecin"), "pictogrammes_modifies", {"id": cible["id"], "avant": avant, "apres": choix})
        return f"Proposition #{cible['id']} modifiée : {' '.join(choix)} (à valider)"

    def _rejeter(self, evt: dict) -> str:
        """The doctor rejects a translator proposal (they may receive a new one)."""
        d = self.ctx.dossier
        if evt.get("auteur") != "medecin":
            return "Refusé : seul le médecin rejette une proposition."
        cible = d.decisions.get(evt.get("decision_id") or -1)
        if not cible:
            props = [x for x in d.decisions.values() if x.get("type") == "envoi_patient" and x["statut"] == "attente_validation"
                     and (not evt.get("contenu_type") or x.get("contenu_type") == evt["contenu_type"])]
            if len(props) != 1:
                return f"Refusé : {len(props)} proposition(s) correspondante(s) ; préciser decision_id."
            cible = props[0]
        if cible.get("type") != "envoi_patient" or cible["statut"] != "attente_validation":
            return "Refusé : aucune proposition en attente à rejeter."
        cible["statut"] = "rejete"
        d._changer(evt["auteur"], "rejet", {"id": cible["id"], "raison": evt.get("raison", "")})
        if cible.get("source_question"):        # the translator does not propose it again: the doctor rephrases if they wish
            d.statut_question(evt["auteur"], cible["source_question"], "rejetee", evt.get("raison", ""))
        return f"Proposition #{cible['id']} annulée : {evt.get('raison', '') or 'elle ne partira pas'}"

    def _retirer(self, evt: dict) -> str:
        """The doctor removes from the patient screen a message already sent (mistake, message now wrong). The journal keeps
        the message and its removal: nothing is erased from the trace."""
        d = self.ctx.dossier
        cible = d.decisions.get(int(evt.get("decision_id") or -1))
        if evt.get("auteur") != "medecin" or not cible or cible.get("type") != "envoi_patient" or cible["statut"] != "envoye":
            return "Refusé : seul un message déjà envoyé au patient peut être retiré de son écran."
        cible["statut"] = "retire"
        d._changer("medecin", "message_retire", {"id": cible["id"], "par": evt.get("medecin"), "raison": evt.get("raison", "")})
        return f"Message #{cible['id']} retiré de l'écran du patient (le journal le garde)."

    def _masquer(self, evt: dict) -> str:
        """Hide from the doctor's conversation a message that was not sent (cancelled, blocked) or removed."""
        d = self.ctx.dossier
        cible = d.decisions.get(int(evt.get("decision_id") or -1))
        if not cible or cible.get("type") != "envoi_patient" or cible["statut"] in ("attente_validation", "a_verifier", "CONFORME", "envoye"):
            return "Refusé : annulez ou retirez d'abord ce message."
        cible["masque"] = True
        d._changer("medecin", "message_masque", {"id": cible["id"]})
        return f"Message #{cible['id']} masqué de la conversation (le journal le garde)."

    def stabiliser(self, exclure=frozenset()) -> int:
        """`exclure`: agents that do not play now (the interface first runs the fast agents, then the agent that
        queries the online model, so that a click never waits for the model)."""
        for r in range(1, self.max_rounds + 1):
            ordre = [a for a in self.agents if a.nom not in exclure]
            if self.ordre == "aleatoire":
                self.hasard.shuffle(ordre)
            actifs = []
            for a in ordre:
                if a.tour():
                    actifs.append(a.nom)
                    if self.apres_tour:
                        self.apres_tour()
            if not actifs:
                return r - 1
        self.ctx.journal.ajouter("coordinateur", "arret_max_rounds", {"rounds": self.max_rounds})
        print("  (arrêt : nombre maximal de rounds atteint)")
        return self.max_rounds

    def filet_de_securite(self) -> int:
        """Model-independent guarantee: every unchecked decision (or checked before the last change of the
        patient's state) is checked by the jurist's tool. Logged as such."""
        juriste = next((a for a in self.agents if a.nom == "juriste"), None)
        if juriste is None:
            return 0
        d, n = self.ctx.dossier, 0
        # Content of every proposal to the patient checked BEFORE validation, even if the jurist (model) forgot it
        for dec in list(d.decisions.values()):
            if dec.get("type") == "envoi_patient" and dec["statut"] == "attente_validation" and not precontrole_a_jour(dec, d):
                self.ctx.journal.ajouter("coordinateur", "filet_de_securite",
                                         {"decision": dec["id"], "raison": "contenu non contrôlé avant validation"})
                juriste.executer("precontroler_envoi_patient", {"decision_id": dec["id"]})
                for raisonnement, outil, args in juriste._alerter_precontrole(dec):
                    juriste._penser(raisonnement)
                    juriste.executer(outil, args)
                n += 1
        outils = {"prescription": "verifier_prescription", "envoi_patient": "verifier_envoi_patient",
                  "partage_donnees": "verifier_partage_donnees"}
        for dec in list(d.decisions.values()):
            if dec["statut"] == "annulee" or dec.get("type") not in outils:
                continue
            perime = dec.get("type") == "prescription" and dec["verifiee_a_version_etat"] != d.etat_version
            if dec["statut"] == "a_verifier" or perime:
                self.ctx.journal.ajouter("coordinateur", "filet_de_securite",
                                         {"decision": dec["id"], "raison": "non contrôlée par le juriste après stabilisation"})
                print(f"  ⛑ filet de sécurité : contrôle forcé de la décision #{dec['id']}")
                juriste.executer(outils[dec["type"]], {"decision_id": dec["id"]})
                # The jurist's usual reaction (alerts, requests, gaps) is sent too.
                for raisonnement, outil, args in juriste._reagir(juriste.dernier_verdict, dec):
                    juriste._penser(raisonnement)
                    juriste.executer(outil, args)
                n += 1
        # Questions the doctor picked in the Assistant tab with "Send": validated on their behalf as soon as the jurist
        # has judged the content compliant (they saw the pictogram preview before clicking); otherwise they stay in the
        # conversation, to validate by hand.
        for dec in list(d.decisions.values()):
            q = next((q for q in d.questions_a_poser if q["id"] == dec.get("source_question")), None)
            if dec.get("type") == "envoi_patient" and dec["statut"] == "attente_validation" and q and q.get("valider_auto_par") \
                    and precontrole_a_jour(dec, d):
                medecin = q.pop("valider_auto_par")
                if (dec.get("precontrole") or {}).get("verdict") == "CONFORME" and dec.get("pictogrammes"):
                    r = self._valider({"auteur": "medecin", "medecin": medecin, "decision_id": dec["id"]})
                    print(f"  {'✖' if r.startswith('Refusé') else '✔'} {r} (depuis l'onglet Assistant)")
                    n += 1
        # Assistant's clinical watch (deterministic, instant): a risky prescription is reported to the doctor with its
        # sourced alternative, without waiting for the online model.
        assistant = next((a for a in self.agents if a.nom == "assistant"), None)
        if assistant is not None and hasattr(assistant, "veille_clinique"):
            for raisonnement, outil, args in list(assistant.veille_clinique()):
                assistant._penser(raisonnement)
                assistant.executer(outil, args)
                n += 1
        return n

    def boites_humaines(self) -> None:
        agents = {a.nom for a in self.agents}
        for humain in [b for b in self.ctx.messagerie.boites if b not in agents]:
            for m in self.ctx.messagerie.lire(humain):
                print(f"  ✉  pour {humain.upper()} — {m}")

    def lancer(self, scenario: dict) -> None:
        print(f"\n=== Scénario : {scenario['titre']} ===")
        for i, evt in enumerate(scenario["evenements"], 1):
            print(f"\n--- Événement {i} · {evt['description']} ---")
            self.ctx.journal.ajouter("coordinateur", "evenement_libere", evt)
            self.appliquer(evt)
            n = self.stabiliser()
            if self.filet_de_securite():
                n += self.stabiliser()
            self.boites_humaines()
            print(f"  (stabilisé après {n} round(s))")
