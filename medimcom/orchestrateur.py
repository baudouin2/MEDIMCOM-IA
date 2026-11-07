"""Coordinateur : libère les événements un par un et laisse les agents réagir.

Il n'impose aucun ordre aux agents : à chaque « round », chaque agent regarde ses
messages et le dossier, et décide s'il a quelque chose à faire. On s'arrête quand
plus aucun agent n'agit (le système est stable) ou après `max_rounds`.
"""
import json
import random

from .agents import precontrole_a_jour


class Orchestrateur:
    def __init__(self, ctx, agents: list, max_rounds: int = 8, ordre: str = "fixe", graine: int = 0):
        self.ctx = ctx
        self.agents = agents
        self.max_rounds = max_rounds
        self.ordre = ordre                      # « aleatoire » : l'ordre de passage change à chaque round
        self.hasard = random.Random(graine)
        self.apres_tour = None                  # rappel après chaque action d'agent (l'interface rafraîchit son écran)

    def appliquer(self, evt: dict) -> None:
        d = self.ctx.dossier
        t = evt["type"]
        if t == "echange":
            d.ajouter_echange(evt["auteur"], evt["texte"], evt.get("donnees"), evt.get("confirme", True))
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
            # Un message venu de l'extérieur n'est JAMAIS considéré comme validé, même s'il déclare un validateur :
            # seule une validation enregistrée (événement « validation » du médecin) fait foi. Défaut trouvé par
            # l'exploration automatique (medimcom/exploration.py, propriété R8 du moniteur).
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
            # Le médecin écrit au patient : une question passe par la liste des questions (le traducteur la prend),
            # une information est confiée directement au traducteur.
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
        """Dernière décision visée par un maintien : par médicament, ou par type (ex. partage_donnees)."""
        for dec in reversed(list(self.ctx.dossier.decisions.values())):
            if evt.get("medicament") and dec.get("medicament") == evt["medicament"]:
                return dec["id"]
            if evt.get("objet") and dec.get("type") == evt["objet"] and dec["statut"] == "A_REVOIR":
                return dec["id"]
        return None

    def _valider(self, evt: dict) -> str:
        """Le médecin valide UNE proposition du traducteur : celle indiquée, ou la seule en attente du type donné."""
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
        """Le médecin corrige la traduction d'une proposition avant de la valider (ajout, retrait, ordre, combinaison).
        Mêmes garde-fous que pour l'agent traducteur : pictogrammes connus seulement, et jamais de retrait de la négation,
        de la limite, de l'urgence, de STOP, d'un chiffre, d'une dose ou d'un médicament présents dans la traduction."""
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
        """Le médecin rejette une proposition du traducteur (il pourra en recevoir une nouvelle)."""
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
        if cible.get("source_question"):        # le traducteur ne la repropose pas : le médecin reformule s'il le souhaite
            d.statut_question(evt["auteur"], cible["source_question"], "rejetee", evt.get("raison", ""))
        return f"Proposition #{cible['id']} annulée : {evt.get('raison', '') or 'elle ne partira pas'}"

    def _retirer(self, evt: dict) -> str:
        """Le médecin retire de l'écran du patient un message déjà envoyé (erreur, message devenu faux). Le journal garde
        le message et son retrait : rien n'est effacé de la trace."""
        d = self.ctx.dossier
        cible = d.decisions.get(int(evt.get("decision_id") or -1))
        if evt.get("auteur") != "medecin" or not cible or cible.get("type") != "envoi_patient" or cible["statut"] != "envoye":
            return "Refusé : seul un message déjà envoyé au patient peut être retiré de son écran."
        cible["statut"] = "retire"
        d._changer("medecin", "message_retire", {"id": cible["id"], "par": evt.get("medecin"), "raison": evt.get("raison", "")})
        return f"Message #{cible['id']} retiré de l'écran du patient (le journal le garde)."

    def _masquer(self, evt: dict) -> str:
        """Masquer de la conversation du médecin un message qui n'est pas parti (annulé, bloqué) ou retiré."""
        d = self.ctx.dossier
        cible = d.decisions.get(int(evt.get("decision_id") or -1))
        if not cible or cible.get("type") != "envoi_patient" or cible["statut"] in ("attente_validation", "a_verifier", "CONFORME", "envoye"):
            return "Refusé : annulez ou retirez d'abord ce message."
        cible["masque"] = True
        d._changer("medecin", "message_masque", {"id": cible["id"]})
        return f"Message #{cible['id']} masqué de la conversation (le journal le garde)."

    def stabiliser(self, exclure=frozenset()) -> int:
        """`exclure` : agents qui ne jouent pas maintenant (l'interface fait d'abord passer les agents rapides,
        puis l'agent qui interroge le modèle en ligne, pour qu'un clic n'attende jamais le modèle)."""
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
        """Garantie indépendante du modèle : toute décision non contrôlée (ou contrôlée avant le dernier
        changement de l'état du patient) est contrôlée par l'outil du juriste. Journalisé comme tel."""
        juriste = next((a for a in self.agents if a.nom == "juriste"), None)
        if juriste is None:
            return 0
        d, n = self.ctx.dossier, 0
        # Contenu de chaque proposition au patient contrôlé AVANT la validation, même si le juriste (modèle) l'a oublié
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
                # La réaction habituelle du juriste (alertes, demandes, lacunes) est envoyée elle aussi.
                for raisonnement, outil, args in juriste._reagir(juriste.dernier_verdict, dec):
                    juriste._penser(raisonnement)
                    juriste.executer(outil, args)
                n += 1
        # Veille clinique de l'assistant (déterministe, instantanée) : une prescription risquée est signalée au
        # médecin avec son alternative sourcée, sans attendre le modèle en ligne.
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
