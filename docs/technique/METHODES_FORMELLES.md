# Méthodes formelles de MEDIMCOM IA

Ce document explique comment la solidité de MEDIMCOM IA est **démontrée**, et pas seulement testée sur quelques exemples. Les résultats chiffrés de la dernière vérification sont dans [`RAPPORT_VERIFICATION_FORMELLE.md`](RAPPORT_VERIFICATION_FORMELLE.md). Pour tout relancer : `python outils/verifier_formel.py` (option `--mutations` pour l'analyse de mutation).

## 1. Le principe : le modèle de langage propose, des règles formelles décident

Un modèle de langage n'est ni déterministe ni vérifiable. MEDIMCOM ne lui confie donc aucune décision qui engage le patient ou la loi. Trois garde-fous formels l'encadrent, tous **en dehors du modèle** :

| Garde-fou | Rôle | Fichiers |
|---|---|---|
| **Moteur de règles du juriste** | Rend les verdicts (conforme, information manquante, à revoir, bloqué). C'est un programme déterministe qui suit une sémantique écrite (section 2). Le modèle peut l'interroger, mais il ne peut pas changer un verdict. | `medimcom/regles.py`, `kb/regles_uae.json`, `kb/regles_cm.json` |
| **Spécification formelle** | Fixe ce que les règles doivent garantir pour **toutes** les entrées possibles : ce qui doit être empêché (sûreté) et ce qui doit rester possible (utilité). | `kb/specification_formelle.json` |
| **Moniteur du journal** | Relit le journal infalsifiable et contrôle que le déroulement réel des agents respecte des invariants : par exemple, aucun message n'atteint le patient sans validation humaine. | `medimcom/surveillance.py` |

Cette architecture neuro-symbolique suit la littérature récente sur la sûreté des agents à base de modèles de langage : contraintes appliquées à l'exécution, en dehors du modèle (AgentSpec, Wang et al., 2025), et vérification de politiques de sûreté par des règles explicites (ShieldAgent, Chen et al., ICML 2025). Elle répond aussi à deux exigences du règlement européen sur l'IA : l'enregistrement des événements (art. 12) et le contrôle humain (art. 14).

## 2. Le langage des règles et sa sémantique

Chaque règle est une donnée, comme dans les approches « rules as code » (Catala, Merigoux et al., ICFP 2021 ; LegalRuleML, standard OASIS 2021) :

```json
{"id": "HORS-EAU-SANS-EXCEPTION", "si": {"lieu": "hors_du_pays", "exception_res51": {"absent": true}},
 "niveau": "BLOQUE", "base": "LOI", "fiches": ["ICT19-A13"]}
```

**Signature typée.** Chaque fichier de règles déclare ses variables par famille (partage, envoi au patient, prescription, contre-indications…), avec leur type (booléen, énumération, texte, nombre) et leur **monde** :
- en **monde ouvert**, une valeur absente est *inconnue* ;
- en **monde fermé** (hypothèse du monde clos de Reiter, 1978), une valeur absente veut dire « aucun ». C'est le cas, par exemple, d'une prescription liée à un message.

Une variable utilisée par une règle mais non déclarée est une erreur : c'est la propriété WF1, qui détecte aussi les fautes de frappe.

**Deux familles d'opérateurs.**

| Opérateurs | Portent sur | Valeur sur une information inconnue |
|---|---|---|
| `absent`, `present`, `pas` (« il n'est pas établi que ») | ce que l'on **sait** (épistémiques) | toujours vrai ou faux |
| égalité, `dans`, `hors`, `contient`, `inferieur_a`, `superieur_a` | le **monde** (factuels) | *inconnu* (logique à trois valeurs de Kleene, 1952) |

**Règle d'une conjonction.** Elle est fausse si l'une de ses conditions est fausse. Sinon, elle est inconnue si l'une est inconnue. Sinon, elle est vraie.

**Principe de prudence.** Une règle restrictive (à revoir, bloqué) qui *pourrait* s'appliquer, faute de savoir, donne « information manquante » et cite ce qui manque. Une inconnue n'est donc jamais supposée sans danger.

**Treillis des verdicts.** Les verdicts sont ordonnés : CONFORME < PREUVES_INSUFFISANTES < A_REVOIR < BLOQUE.
- Le verdict est le **plus strict** des constats ; les conflits entre règles se résolvent ainsi, comme une table de décision DMN dont la politique est « collecter le maximum ».
- **Refus par défaut :** un partage de données que rien n'autorise explicitement n'est pas conforme.
- **Hiérarchie des normes :** seule une loi ou une norme lue sur un texte officiel peut bloquer. Une recommandation peut au plus demander une révision.

**Connaissances de fond (axiomes).** Elles complètent une inconnue quand elle découle de faits connus. Par exemple, un homme n'est pas enceint : pas de fausse alerte de contre-indication. Ces connaissances révèlent aussi les **contradictions** (un homme noté enceint), qui sont signalées et jamais tranchées en silence. C'est l'apport de « Semantic DMN » (Calvanese et al., TPLP 2018) : raisonner sur une table de décision *avec* les connaissances du domaine.

**Maintien nominatif.** Un médecin autorisé peut maintenir une décision « à revoir » en la justifiant par écrit. Ce maintien ne couvre que les motifs qu'il a examinés. Un verdict aggravé ou un nouveau motif le rend caduc.

## 3. La spécification : sûreté et utilité

`kb/specification_formelle.json` est écrit indépendamment des règles, comme une exigence l'est de son implémentation. Chaque exigence cite ses textes juridiques. Elle prend l'une de ces formes :
- « au moins » un verdict, pour la **sûreté** : par exemple, un transfert hors du pays sans exception est bloqué ;
- « jamais » un verdict ;
- « au plus » un verdict, pour l'**utilité** : par exemple, partager pour les soins avec l'hôpital du pays doit rester possible.

Les exigences d'utilité sont indispensables. Sans elles, un système qui refuse tout passerait pour parfaitement sûr. C'est l'analyse de mutation (sections 4 et 7) qui l'a montré : avant leur ajout, supprimer la règle qui autorise le partage pour les soins passait inaperçu. La spécification compte 30 exigences, dont trois de limitation des finalités et de localisation.

## 4. Les méthodes de vérification

| Méthode | Ce qui est vérifié | Outil | Références |
|---|---|---|---|
| **Analyse statique (typage)** | Variables déclarées, opérateurs connus, constantes dans leur domaine, identifiants uniques, blocage seulement sur une loi lue du bon pays (WF1 à WF4) | `medimcom/formel.py` | signatures typées de Catala et DMN |
| **Énumération exhaustive (vérification de modèle explicite)** | Toutes les propriétés, sur le **moteur réel**. Une règle ne compare une variable qu'à des constantes écrites : les valeurs non citées se comportent toutes pareil. Énumérer les constantes, une valeur « autre » et « inconnue » couvre donc **toutes** les entrées possibles (partition en classes d'équivalence). Les noms de lieux bruts (« EAU », « Cameroun »…) sont inclus. | `medimcom/formel.py` | vérification de modèle explicite |
| **Preuve par solveur SMT** | Les mêmes propriétés, sur un encodage logique écrit **directement depuis le JSON** et indépendant du code du moteur, pour toutes les chaînes de caractères (domaine non borné). « Insatisfiable » vaut preuve ; sinon, le solveur fournit un contre-exemple. | `medimcom/formel_smt.py` (Z3) | Backes et al., FMCAD 2018 (Zelkova, AWS) ; de Moura & Bjørner, TACAS 2008 |
| **Validation croisée** | L'encodage logique et le moteur réel rendent le même verdict, contrôlé sur 2 000 entrées par famille. Deux mises en œuvre indépendantes qui s'accordent. | `formel_smt.validation_croisee` | programmation N-version |
| **Relations métamorphiques** | Ajouter une garantie (consentement, chiffrement, anonymisation…) n'aggrave jamais le verdict ; confirmer une information non plus. | `formel.py` (P3, PR7) | Chen et al., ACM CSUR 2018 |
| **Analyse de mutation** | Des fautes sont introduites volontairement dans les règles (règle supprimée, niveau affaibli, condition retirée) ; la spécification doit les détecter. Les mutants survivants désignent des règles redondantes ou des comportements non spécifiés. | `formel_smt.analyse_mutations` | DeMillo et al., 1978 ; Jia & Harman, IEEE TSE 2011 |
| **Vérification à l'exécution** | Dix invariants de sûreté (R1 à R10), écrits en logique temporelle du passé et contrôlés sur le journal. R10 vérifie que chaque décision suit la machine à états de son cycle de vie (section 5). | `medimcom/surveillance.py` | Leucker & Schallhart, JLAP 2009 |
| **Exploration du système réel** | Des centaines de suites d'événements aléatoires (graine fixe, reproductibles), guidées par l'état et incluant des **attaques** : faux validateur, assistant qui prescrit, maintien sans justification… Une violation est réduite automatiquement à une suite minimale. | `medimcom/exploration.py` | QuickCheck (Claessen & Hughes, ICFP 2000) ; delta debugging (Zeller & Hildebrandt, IEEE TSE 2002) ; méthodes formelles chez AWS (Newcombe et al., CACM 2015) |
| **Intégration continue** | Tests, vérification de la base, vérification formelle et banc d'évaluation à chaque modification ; échec si une propriété est violée. | `.github/workflows/ci.yml` | IEC 62304 (activités de vérification du logiciel) |

**Résultats de la dernière vérification complète** (`python outils/verifier_formel.py --mutations`, environ 11 minutes) :
- **Émirats :** 85 propriétés sur 85 vérifiées, 17,9 millions de cas examinés.
- **Cameroun :** 71 propriétés sur 71 vérifiées, 2,5 millions de cas examinés.
- **Exploration :** 1 200 suites d'événements sur les vrais agents, sans aucune violation des dix invariants.

Le détail est dans [`RAPPORT_VERIFICATION_FORMELLE.md`](RAPPORT_VERIFICATION_FORMELLE.md).

## 5. Machine à états d'une décision

```
                 validation par le médecin               contrôle du juriste
 attente_validation ─────────────────────► a_verifier ───────────────────► CONFORME ──► envoye (message)
        │                                                                  PREUVES_INSUFFISANTES
        └──► rejete                                                        A_REVOIR ──► MAINTENUE (maintien signé)
                                                                           BLOQUE (aucune sortie vers MAINTENUE)
 tout statut non terminal ──► annulee (remplacée)        nouveau contrôle après un changement de l'état du patient
```

Toute transition observée dans le journal qui n'est pas dans cette machine est une violation (R10). Les états `envoye`, `rejete` et `annulee` sont terminaux.

## 6. Défauts trouvés par la vérification, puis corrigés

| # | Trouvé par | Défaut | Correction |
|---|---|---|---|
| D1 | Prudence P2 (plus de 7 000 contre-exemples dans l’ancienne sémantique) | Une permission s'appliquait malgré une information inconnue qui aurait pu tout bloquer. Exemple : transmission à un assureur avec un destinataire inconnu (s'il s'agissait du public, elle serait bloquée). | Logique à trois valeurs de Kleene et principe de prudence (section 2) |
| D2 | Exigence S-EN-TRAITEMENT-PRESCRIPTION | Liste d'**exclusion** des statuts de prescription : un statut imprévu laissait partir un message de traitement | Liste d'**autorisation** (`hors : [CONFORME, MAINTENUE]`) |
| D3 | Règle morte P5 (Cameroun) | Le jeton « EAU » voulait dire « dans le pays », mais pour le Cameroun « EAU » désigne les Émirats, donc l'étranger. Une déclaration à l'autorité de santé camerounaise était traitée comme un transfert à l'étranger. | Jetons neutres `dans_le_pays` / `hors_du_pays` ; noms de pays traduits par chaque fichier |
| D4 | Exigence S-PA-COMMERCIAL-JAMAIS-CONFORME (Cameroun) | Un usage commercial consenti, adressé à une autorité de santé, était jugé conforme | Règle COMMERCIAL-AVEC-ACCORD (à revoir) pour le Cameroun |
| D5 | Propriété PR6 | L'allergie n'était pas contrôlée pour un médicament sans autorisation de mise sur le marché, ni pour un nom inconnu de la base | Contrôle d'allergie pour tout médicament prescrit |
| D6 | Propriété PR8 | Un homme noté enceint déclenchait une contre-indication sans que la contradiction soit signalée | Axiomes et détection des informations contradictoires |
| D7 | Exploration + R8 (suite réduite à **un seul** événement) | Un module externe qui *déclarait* un validateur obtenait un verdict « conforme » du juriste (l'envoi restait bloqué plus loin, mais le verdict était faux) | Un message venu de l'extérieur n'est jamais tenu pour validé ; seule une validation enregistrée fait foi |
| D8 | Exploration + R3/R9 | Un maintien restait valable même quand un **nouveau** motif « à revoir » apparaissait | Le maintien ne couvre que les motifs examinés ; il devient caduc sinon |

Chaque correction est protégée par un test de non-régression (`tests/test_noyau.py`).

## 7. Ce que montre l'analyse de mutation

Première analyse, avec une spécification de sûreté seulement : 21 % des mutants détectés (Émirats). Supprimer la règle qui autorise le partage pour les soins passait inaperçu, puisqu'un système plus restrictif reste « sûr ». Après l'ajout des exigences d'**utilité** (« au plus ») et de la **limitation des finalités**, le score est de 69 % (Émirats) et 78 % (Cameroun) pour le partage de données, et de 78 % pour l'envoi au patient ; détail dans le rapport de vérification.

Chaque mutant survivant a été examiné. Aucun ne change un verdict de façon dangereuse :
- **Règles « …-INCONNU » et LIEU-INCONNU (supprimées ou rendues permissives).** Mutants équivalents : la logique de Kleene et le refus par défaut donnent déjà « information manquante ». Ces règles sont gardées parce qu'elles expliquent au médecin, avec leur texte de loi, *quelle* information manque.
- **Condition « anonymise » retirée d'une permission** (recherche, publication). Mutants équivalents : les cas non anonymisés sont déjà bloqués ou à revoir par des règles plus strictes, qui l'emportent dans le treillis.
- **AUTORITE-SANTE supprimée (Émirats).** Redondance : SANTE-PUBLIQUE autorise déjà ce cas.
- **ENVOI-VALIDE sans sa condition.** Mutant équivalent : ENVOI-NON-VALIDE bloque tout message non validé.
- **ENVOI-DIAGNOSTIC supprimée.** C'est une *obligation* (information du patient), pas un verdict : les obligations ne sont pas encore couvertes par la spécification (limite, section 9).

## 8. Traçabilité

| Exigence ou principe | Propriétés | Textes | Tests |
|---|---|---|---|
| Contrôle humain de toute communication au patient | S-EN-VALIDATION-HUMAINE, R1, R2, R8 | DHA AI Policy 2021 §4.4 ; Cameroun loi 90/036 art. 2 | `test_moniteur_detecte_les_violations`, `test_exploration_du_systeme_reel` |
| Localisation des données de santé | S-PA-HORS-PAYS-*, U-PA-* | Loi fédérale 2/2019 art. 13 ; Cameroun loi 2024/017 | `test_semantique_trois_valeurs_et_monde_ferme`, `test_preuves_smt` |
| Usage commercial ou recherche | S-PA-COMMERCIAL*, S-PA-RECHERCHE-* | Loi fédérale 2/2019 art. 16 ; Cameroun loi 2024/017 art. 9 | vérification formelle |
| Consigner l'état du patient avant de traiter | PR3, PR5, PR9 | Décret-loi 4/2016 art. 4(2) ; code de déontologie (Cameroun) | `test_axiomes_et_informations_contradictoires` |
| Maintien nominatif, jamais sur un blocage | MA1, MA2, R4, R9 | hiérarchie des normes ; AI Act art. 14 | `test_moniteur_detecte_les_violations` |
| Journal infalsifiable | R7 | AI Act art. 12 | `test_moniteur_detecte_les_violations` |

## 9. Limites, dites franchement

- **Ce qui est démontré :** les règles respectent la spécification. Que la spécification traduise fidèlement la loi reste une lecture humaine, à faire valider par des juristes (Émirats, Cameroun).
- **Hypothèse du solveur :** les entrées sont normalisées (minuscules, sans accents), comme le fait le moteur. La validation croisée contrôle l'accord entre l'encodage et le moteur.
- **Prescription :** l'énumération porte sur les variables qui comptent pour la sûreté (prescripteur, médicament, sexe, âge aux bornes, grossesse, allergies, mode, ordonnance écrite). Les autres sont fixées.
- **Modèles de langage :** leurs réponses ne sont pas vérifiées formellement. Elles sont **encadrées** : aucune ne peut produire un verdict, et le moniteur contrôle leurs effets.
- **Exploration :** les invariants R1 à R10 sont contrôlés sur des centaines de suites. C'est un test exhaustif *borné*, pas une preuve pour toutes les suites possibles. Une spécification TLA+ de l'orchestration est la prochaine étape naturelle (Newcombe et al., 2015).
- **Obligations :** la spécification porte sur les verdicts ; les obligations rappelées au médecin (informer le patient, déclarer une maladie) sont testées par scénarios, pas encore spécifiées formellement.
- **Certification :** ce n'est pas une certification de dispositif médical (IEC 62304, ISO 14971), mais les activités de vérification décrites ici en sont la base.

## Références

- Merigoux, Chataing, Protzenko. *Catala: A Programming Language for the Law*. ICFP 2021. https://arxiv.org/abs/2103.03198
- OASIS. *LegalRuleML Core Specification Version 1.0*. 2021. https://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/legalruleml-core-spec-v1.0.html
- Governatori. *Practical normative reasoning with defeasible deontic logic*. 2018. https://research-repository.griffith.edu.au/items/828fff8a-5f0d-45fe-a004-63e02711ab18
- Calvanese, Dumas, Maggi, Montali. *Semantic DMN: Formalizing and Reasoning About Decisions in the Presence of Background Knowledge*. TPLP 2019. https://arxiv.org/abs/1807.11615
- Backes et al. *Semantic-based Automated Reasoning for AWS Access Policies using SMT*. FMCAD 2018. https://www.amazon.science/publications/semantic-based-automated-reasoning-for-aws-access-policies-using-smt
- Newcombe et al. *How Amazon Web Services Uses Formal Methods*. Communications of the ACM, 2015. https://www.amazon.science/publications/how-amazon-web-services-uses-formal-methods
- de Moura, Bjørner. *Z3: An Efficient SMT Solver*. TACAS 2008. https://doi.org/10.1007/978-3-540-78800-3_24
- Kleene. *Introduction to Metamathematics*. 1952 (logique à trois valeurs).
- Reiter. *On Closed World Data Bases*. Logic and Data Bases, 1978 (hypothèse du monde clos).
- Leucker, Schallhart. *A Brief Account of Runtime Verification*. JLAP 78(5), 2009. https://doi.org/10.1016/j.jlap.2008.08.004
- Claessen, Hughes. *QuickCheck: A Lightweight Tool for Random Testing of Haskell Programs*. ICFP 2000. https://doi.org/10.1145/351240.351266
- Zeller, Hildebrandt. *Simplifying and Isolating Failure-Inducing Input*. IEEE TSE 28(2), 2002. https://doi.org/10.1109/32.988498
- Chen et al. *Metamorphic Testing: A Review of Challenges and Opportunities*. ACM CSUR 51(1), 2018. https://doi.org/10.1145/3143561
- Jia, Harman. *An Analysis and Survey of the Development of Mutation Testing*. IEEE TSE 37(5), 2011. https://doi.org/10.1109/TSE.2010.62
- Wang, Poskitt, Sun. *AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents*. 2025. https://arxiv.org/abs/2503.18666
- Chen, Kang, Li. *ShieldAgent: Shielding Agents via Verifiable Safety Policy Reasoning*. ICML 2025. https://arxiv.org/abs/2503.22738
- Règlement (UE) 2024/1689 sur l'intelligence artificielle, art. 12 et 14. https://eur-lex.europa.eu/eli/reg/2024/1689/oj
