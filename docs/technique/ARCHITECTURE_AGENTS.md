# Agents et collaboration — guide technique (partie de Franck)

Ce guide couvre les agents, le dossier partagé, la messagerie, le journal et les institutions. Tout ce qui est décrit ici est **codé et testé** (`python -m pytest -q`). Ce qui n'a pas pu être fait ici est listé à la fin : faire tourner un vrai modèle.

## 1. Vue d'ensemble

```
             événements du scénario (un par un, chaque fragment à son seul destinataire)
                                   │
                            ┌──────▼──────┐   ordre de passage fixe ou aléatoire, arrêt quand plus
                            │ coordinateur│   personne n'agit ; filet de sécurité après chaque événement
                            └──────┬──────┘
   ┌───────────────┬───────────────┼───────────────┬───────────────┬──────────────┐
 traducteur     assistant        juriste      autorité de santé    hôpital    cellule de crise
   │               │               │               │                 │              │
   └──── dossier de consultation partagé ────┘     └──── tableau de crise (sans données de patients) ────┘
                messagerie directe typée : demande · information · alerte · proposition · désaccord
                journal chaîné SHA-256 : chaque pensée, action, message, verdict, mesure
```

| Fichier | Rôle |
|---|---|
| `medimcom/agents.py` | classe `Agent` (boucle observer → réfléchir → agir), les 6 agents, `conformer()` |
| `medimcom/dossier.py` | dossier partagé, versionné : chaque agent voit ce qui a changé depuis son dernier passage |
| `medimcom/messagerie.py` | messages directs typés ; destinataire et type contrôlés |
| `medimcom/journal.py` | journal infalsifiable (chaque ligne contient l'empreinte de la précédente) |
| `medimcom/orchestrateur.py` | libère les événements, fait tourner les agents jusqu'à stabilité, filet de sécurité |
| `medimcom/cerveaux.py` | ce qui choisit les outils : politique écrite, Ollama, serveur compatible OpenAI |
| `medimcom/session.py` | assemble une session à partir d'une `Config` (utilisé partout : main, évaluation, tests) |
| `medimcom/evaluation.py` | vérifie les « attendus » d'un scénario + 6 invariants de sécurité |
| `medimcom/mandats.json` | fiches mandat des institutions (bases légales, ce qu'elles peuvent et ne peuvent pas faire) |
| `evaluer_agents.py` | banc d'évaluation : tableau de score, répétitions, ordre aléatoire |
| `exporter_journal.py` | journal → page HTML lisible avec filtres (audit, jury, vidéo) |

## 2. Anatomie d'un agent

Un agent = **un but** (texte `but`, devient la consigne système du modèle) + **des outils** (fonctions Python avec un schéma JSON) + **des garde-fous dans les outils**. Il n'y a pas de procédure : à chaque tour, l'agent lit ses messages et les changements du dossier, puis **choisit** ses outils (ou ne fait rien).

| Agent | Outils propres (en plus de `envoyer_message`, `consulter_base`, `terminer`) | Garde-fous clés |
|---|---|---|
| traducteur | `traduire`, `proposer_au_medecin`, `rapporter_reponse_patient`, `envoyer_au_patient` (+ `lire_dossier`) | n'envoie rien sans validation d'un médecin actif ET verdict CONFORME ; une seule proposition par question ou prescription (sauf après rejet), 3 messages libres au plus en attente, les questions et explications gardent toujours leur place ; ne rapporte que les pictogrammes réellement choisis ; un OUI/NON ne devient un fait que s'il répond seul au dernier message |
| assistant | `mettre_a_jour_etat`, `demander_question_patient`, `suggerer_au_medecin`, `retirer_suggestion` (+ `lire_dossier`) | ne peut pas « confirmer » un fait que personne n'a rapporté ; n'écrit pas aux institutions |
| juriste | `verifier_prescription`, `verifier_envoi_patient`, `verifier_partage_donnees`, `obligations_etat_patient`, `signaler_lacune` (+ `lire_dossier`) | le verdict vient du moteur de règles, jamais du modèle |
| institutions (×3) | `lire_tableau_crise`, `enregistrer_mesure`, `demander_donnees`, `enregistrer_incident` — **pas** `lire_dossier` | mesure seulement sur une fiche de **son mandat**, contraignante, officielle, qui donne un pouvoir d'agir ; demande de données toujours à son propre nom et contrôlée par le juriste |

Les verdicts du juriste suivent une sémantique formelle vérifiée (énumération exhaustive et preuves SMT), et un moniteur contrôle dix invariants sur le journal : voir [`METHODES_FORMELLES.md`](METHODES_FORMELLES.md). Toute modification d'un garde-fou doit garder `python outils/verifier_formel.py` au vert.

Garde-fous communs : un outil qui n'appartient pas à l'agent est refusé et journalisé ; les arguments sont **conformés** au schéma (`"3"` → 3, `"oui"` → vrai, arguments inconnus ignorés, obligatoires vérifiés) ; un message vers une institution est refusé s'il contient un identifiant du patient enregistré dans le dossier (nom, identifiant, téléphone…) ; c'est un filet, pas une anonymisation complète.

## 3. Ajouter un agent (exemple : un pharmacien)

```python
class Pharmacien(Agent):
    nom = "pharmacien"
    but = """Tu es le pharmacien... TON BUT : ... TU DÉCIDES SEUL : ... TES LIMITES : ..."""

    def _outils_propres(self):
        return {"signaler_interaction": (self._interaction, _schema(
            "signaler_interaction", "Signaler une interaction médicamenteuse au médecin.",
            {"decision_id": I, "detail": S}, ["decision_id", "detail"]))}

    def _interaction(self, decision_id, detail):
        ...                                   # le garde-fou va ICI, pas dans la consigne
        return "Interaction signalée."

    def politique_simulee(self, msgs, changements):   # version sans IA, pour les tests
        yield ("raisonnement", "signaler_interaction", {"decision_id": 3, "detail": "..."})
```

Puis : ajouter `"pharmacien"` à `BOITES` et la classe à `CLASSES` dans `session.py`, écrire un test, et des attendus dans un scénario.

## 4. Événements de scénario

| `type` | Champs | Effet |
|---|---|---|
| `echange` | `auteur`, `texte`, `donnees`, `confirme` | ajoute un échange (faits rapportés) au dossier |
| `prescription` | `prescripteur`, `medicament`, `dose`, `posologie`, `mode`, `urgence`, `remplace_medicament`, `issue_de_suggestion` | nouvelle décision du médecin |
| `validation` | `auteur: "medecin"`, `medecin`, `decision_id` ou `contenu_type` | le médecin valide UNE proposition du traducteur (refus si ambigu) |
| `rejet` | `auteur: "medecin"`, `decision_id` ou `contenu_type`, `raison` | le médecin rejette une proposition ; le traducteur peut en refaire une |
| `reponse_patient` | `pictogrammes` | le patient répond ; seul le traducteur la reçoit |
| `maintien` | `medecin`, `justification`, `decision_id` ou `medicament` ou `objet` | le médecin maintient une décision « à revoir » (impossible si bloquée) |
| `partage_donnees` | `auteur`, `demande` | demande de données contrôlée par le juriste |
| `envoi_patient` | `auteur`, `contenu_type`, `valide_par`, `texte` | injection d'erreur : un module tente d'envoyer au patient |
| `message` | `auteur`, `a`, `type_message`, `texte` | **fragment d'information** remis à un seul destinataire (ex. `terrain` → `hopital`) |
| `question` | `auteur`, `a`, `texte` | question à un agent (mode conseiller du juriste) |

Un scénario peut contenir des `attendus` (section 6).

## 5. Les cerveaux

```bash
python main.py                                                   # politiques écrites (référence)
python main.py --mode ollama --modele qwen3:8b                   # Ollama
python main.py --mode openai --url http://localhost:8080/v1 --modele qwen2.5-7b-instruct
python main.py --mode ollama --modeles juriste=qwen3:8b,traducteur=llama3.1:8b   # un modèle par agent
python main.py --ordre aleatoire --graine 3                      # ordre de passage différent à chaque round
```

Le mode `openai` fonctionne avec tout serveur compatible : `llama-server` de llama.cpp, LM Studio, vLLM, ou un bac à sable qui expose cette API (clé : `--cle` ou variable `MEDIMCOM_CLE`).

La boucle tolère les maladresses des petits modèles : appels d'outil écrits dans le texte (`<tool_call>…</tool_call>`, bloc JSON), balises `<think>` (journalisées à part en « réflexion du modèle »), arguments mal typés, appel identique répété trois fois (coupé et journalisé). Chaque appel au modèle a droit à un second essai. **Dégradation gracieuse** : si le serveur tombe, l'agent se replie sur sa politique écrite et le journal le note ; après 3 échecs consécutifs, un **disjoncteur** déclare ce modèle hors service (les agents servis par un autre modèle continuent). Au démarrage, une **vérification de santé** interroge le serveur (Ollama : modèle téléchargé ? serveur compatible OpenAI : `/models`) : un serveur absent est signalé en quelques secondes. `--sans-repli` pour mesurer le modèle seul. Après chaque événement, le **filet de sécurité** du coordinateur fait contrôler par le juriste toute décision restée sans contrôle.

## 6. Évaluer

```bash
python evaluer_agents.py                                         # référence : 100 % attendu
python evaluer_agents.py --mode ollama --modele qwen3:8b --repetitions 3 --sans-repli
python evaluer_agents.py --ordre aleatoire --repetitions 5
```

Sortie : une ligne de progression par run, un tableau, `sortie/evaluation.md`, `sortie/evaluation.json`. Codes de retour : **0** tout va bien ; **1** un invariant de sécurité a échoué ; **2** mesure non valable (le modèle n'a pas répondu : replis sur les politiques écrites — la capacité est alors affichée « NON MESURÉE » — ou runs interrompus, qui ne sont pas comptés). Deux catégories :
- **sécurité** : 6 invariants ajoutés à tout scénario (journal intact ; rien n'atteint le patient sans validation puis feu vert — vérifié sur le journal chaîné, pas sur l'état modifiable ; aucune explication d'une prescription non conforme ; la consultation n'écrit pas aux institutions ; toute mesure a une base valable de son mandat ; pas de doublon ni d'accumulation de messages libres) + les blocages propres au scénario. **Doit rester à 100 %** quel que soit le modèle.
- **capacité** : ce que les agents devraient faire d'eux-mêmes (poser la question de la grossesse, revérifier, proposer une alternative, déclarer une zone infectée…). C'est ce qu'on mesure avec un vrai modèle.

Preuves déjà obtenues : en mode simulé, 100 % / 100 % sur les 3 scénarios, y compris avec un ordre de passage aléatoire ; un test fait jouer un **modèle « chaotique »** (outils et arguments au hasard) sur les 3 scénarios : les invariants de sécurité tiennent toujours.

Types d'attendus : `decision`, `verdicts_dans_l_ordre`, `fait`, `question_posee`, `message`, `mesure`, `suggestion`, `lacunes`, `envois`, plus les invariants (voir `medimcom/evaluation.py`).

## 7. Le journal

Chaque ligne : numéro, heure, agent, type, contenu figé, empreinte précédente, empreinte. Types : `configuration` (modèles, température, ordre, empreintes des règles et de la base : reproductibilité), `evenement_libere`, `raisonnement`, `reflexion_modele`, `action`, `message`, `verdict`, `lacune`, `mesure`, `incident`, `degradation`, `filet_de_securite`, `boucle_detectee`, `appel_extrait_du_texte`, et les changements du dossier.

```bash
python verifier_journal.py sortie/journal.json --falsifier 10   # démonstration de détection
python exporter_journal.py sortie/journal.json                  # page HTML : frise, filtres, vue résumée
```

Limite assumée du prototype : le journal prouve qu'aucune ligne n'a été modifiée après coup, pas l'identité de celui qui l'a écrite (pas de signature par acteur) ; en production, chaque acteur signerait ses lignes.

## 8. Ce que Franck doit faire chez lui (ce qui n'a pas pu être fait ici)

Ce poste de travail n'a pas d'accès réseau aux modèles : **aucun vrai modèle n'a tourné**. À faire, dans l'ordre :

1. Installer Ollama, puis `ollama pull qwen3:8b` et `ollama pull llama3.1:8b` ; `pip install -r requirements.txt` (client `ollama` 0.5.1 ou plus). Vérifier avec `ollama list`.
2. Commencer petit : `python evaluer_agents.py --mode ollama --modele qwen3:8b --scenarios scenarios/allergie.json --sans-repli`. Si tout se passe bien : `--repetitions 3` sur tous les scénarios, puis la même chose avec `llama3.1:8b`. Code de retour 2 = le modèle n'a pas répondu (voir le message).
3. Lire `sortie/evaluation.md` : la **sécurité doit être à 100 %**. Pour chaque attendu de capacité raté, ouvrir le journal (`exporter_journal.py`) et regarder ce que l'agent a pensé.
4. Ajuster seulement : le texte `but` de l'agent concerné, `max_iterations`, la température, ou le modèle de cet agent (`--modeles`). Ne jamais déplacer un garde-fou de l'outil vers la consigne.
5. Garder le meilleur réglage, refaire tourner `python -m pytest -q`, puis mettre le tableau de score dans le rapport (section 5).

Repère de durée : un run de scénario demande de l'ordre de 100 à 150 appels au modèle (chaque agent, à chaque tour où quelque chose a changé). Sur un PC portable sans carte graphique (16 Go de RAM, modèle 8B quantifié), un appel peut prendre de quelques secondes à plus d'une demi-minute : **compter de 15 minutes à plus d'une heure par scénario** ; avec une carte graphique, beaucoup moins. La réflexion longue de qwen3 est désactivée par défaut (option `think`) pour gagner du temps. Lancer les longues évaluations la nuit.

## 9. Limites connues

- Politiques écrites à la main pour la référence ; le comportement d'un vrai modèle reste à mesurer (section 8).
- Les institutions sont fictives ; le mandat légal de la cellule de crise n'est pas vérifié (elle n'enregistre donc aucune mesure).
- L'outil vérifie qu'une base légale est dans le mandat et donne un pouvoir d'agir, pas qu'elle convient à la mesure précise : ce jugement reste au juriste et à l'humain.
