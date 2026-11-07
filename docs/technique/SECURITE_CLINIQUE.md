# Sécurité clinique des prescriptions

Ce que le juriste et l'assistant vérifient sur chaque prescription, avec quelles sources, et ce qui n'est pas couvert.

## Principe

1. **Le juriste** applique des règles écrites, chacune rattachée à une citation exacte d'une notice officielle
   (`kb/fiches.jsonl`, sources dans `kb/sources.json`, rôle `clinical_reference`).
2. **Il rapproche la prescription de la fiche du patient** : âge, sexe, grossesse, poids, allergies, traitements en cours,
   antécédents (texte libre, lu par `medimcom/faits.py` : maladie des reins, du foie, ulcère, anticoagulant, maladie du cœur).
3. **Il lit la dose et le rythme** (`medimcom/regles.py`, `lire_dose`) : « 50 mg » × « 3 fois par jour » = 150 mg/j ; il lit
   aussi « 7fois parjours », « 3x/j », « toutes les 6 h », « matin et soir ».
4. **L'assistant** (veille déterministe, sans modèle) explique au médecin pourquoi ne pas prescrire en l'état et propose une
   alternative sourcée, **après l'avoir fait contrôler par le moteur du juriste pour ce patient**.
5. Rien n'est expliqué au patient tant que la prescription n'est pas conforme (ou maintenue par le médecin, nominativement).

## Niveaux

| Situation | Verdict | Qui peut passer outre |
|---|---|---|
| Contre-indication d'une notice (référence étrangère, non contraignante aux Émirats) | À REVOIR | le médecin, en le justifiant (nom enregistré) |
| Au-delà de la dose maximale par jour | À REVOIR | le médecin, en le justifiant |
| Plus du double de la dose maximale, ou unité impossible (« 1 kg ») | BLOQUÉ (garde-fou de sûreté) | personne |
| Dose ou rythme illisible, fiche incomplète (grossesse, allergies, traitements) | Information manquante | — compléter |
| Antécédents non renseignés | Information (rappel) | — |

Les antécédents sont en **monde fermé** : une maladie qui n'est pas écrite dans la fiche est supposée absente. C'est pourquoi le
juriste rappelle de remplir « Maladies connues, antécédents » (même « aucun ») avant un médicament concerné. La grossesse,
elle, reste en monde ouvert : non renseignée chez une femme de 12 à 50 ans, elle doit être demandée.

## Médicaments couverts

| Médicament | Règles | Sources (citation exacte dans `kb/fiches.jsonl`) |
|---|---|---|
| Tramadol | grossesse ; moins de 12 ans ; mineur ; 400 mg/j | Notice FDA (DailyMed, 3/2021) |
| Paracétamol | maladie du foie ; anticoagulant (surveiller l'INR) ; 4 000 mg/j | Étiquette OTC FDA (copie NDC List) |
| Ibuprofène | grossesse (20 semaines, 3 derniers mois) ; ulcère ; anticoagulant ; reins ; cœur ; après 60 ans ; 3 200 mg/j | FDA 2020, étiquettes OTC et Rx |
| Aspirine | moins de 18 ans (syndrome de Reye) ; grossesse ; ulcère ; anticoagulant ; 3 900 mg/j | Étiquette OTC FDA (copie NDC List) |
| Amoxicilline | allergie aux pénicillines / bêta-lactamines ; insuffisance rénale sévère (pas de 875 mg) | Notice FDA (DailyMed, 01/2024) |
| Metformine | maladie des reins (DFG) ; foie ; 2 550 mg/j adulte, 2 000 mg/j enfant | Notice FDA (DailyMed, 6/2026) |
| Misoprostol | grossesse | Notice Cytotec (FDA) |

Les notices DailyMed sont aussi téléchargées dans `base_v2` (dossier `B_international/09_securite_medicaments`) pour que les
agents puissent en citer les passages : `python outils/constituer_base_v2.py --sortie base_v2 --etapes juridique`
(les documents déjà présents ne sont pas retéléchargés).

## Messages au patient qui citent un médicament (7 novembre)

Un message n'est pas une ordonnance, mais il peut en tenir lieu (« et du tramadol », « je vais vous prescrire
beaucoup de paracétamol »). Le juriste le lit comme une consigne de traitement dès qu'un médicament est cité sans
négation ni question : verbe de prise, dose, annonce de prescription, quantité, ou message réduit au médicament.
Il le confronte alors à la fiche du patient, comme une prescription :
- consigne sans ordonnance → BLOQUÉ (ENVOI-TRAITEMENT-SANS-PRESCRIPTION, ENVOI-PRODUIT-CONTROLE) ;
- contre-indication pour ce patient (grossesse, âge, allergie, maladies) → citée dans le blocage (« Pour ce patient : … ») ;
- quantité imprécise (« beaucoup », « à volonté ») → SURETE-DOSE-IMPRECISE, avec la dose maximale sourcée.
Le contrôle est refait si la fiche change après la proposition (pré-contrôle lié à la version de l'état).
« Prenez-vous du tramadol ? » (question) et « Ne prenez pas d'ibuprofène » (mise en garde) restent permis.

Propos dangereux : en plus des incitations explicites, « et vous pendre », « vous tuer » et un message réduit à un
mot de mort (« pendre ») sont bloqués. Une question de dépistage du risque suicidaire (« Avez-vous des idées de
vous tuer ? ») reste permise.

## L'assistant, même sans modèle en ligne

La veille de l'assistant est déterministe (aucun appel réseau) ; elle tourne après chaque événement :
1. prescription jugée risquée → pourquoi + alternative contrôlée par le moteur du juriste ;
2. message au patient qui conseille un médicament risqué ou en quantité imprécise → quoi faire à la place ;
3. médicament montré par le patient (MEDICAMENT:… dans sa réponse) → fait « médicaments déclarés » et alerte s'il est
   risqué pour lui ;
4. traitement en cours décrit sans nom de médicament → demande de préciser (sinon, pas de contrôle d'interactions).
Si le modèle (Grok) ne répond pas, la raison exacte est affichée (clé refusée, modèle inconnu…), l'assistant passe
en « mode règles » et le modèle est réessayé toutes les 90 s.

## Traduction prudente

Mieux vaut « sans pictogramme » qu'une image fausse. La traduction automatique n'utilise, du catalogue complet, que
le libellé principal des images ARASAAC, avec l'accent exact ; jamais les mots-clés secondaires, Mulberry ou OpenMoji
(libellés déduits de l'anglais). Les mots de violence ne sont jamais illustrés d'office ; les mots-outils (« vais »,
« comme ») sont ignorés ; le rapprochement automatique se limite aux formes conjuguées connues et aux fautes de
frappe évidentes sur des mots d'au moins 6 lettres. La recherche manuelle du médecin trouve toujours tout.

## Lecture du contexte et fautes de frappe (medimcom/lecture.py)

Un mot ne suffit pas à juger un message. Le juriste lit QUI parle de QUOI et POUR FAIRE QUOI (personne, temps,
question, négation, propos rapportés) et rend une intention avec ses indices :

| Message | Lecture | Effet |
|---|---|---|
| « Prenez du tramadol », « et du tramadol », « je vais vous prescrire… » | consigne | bloqué sans ordonnance ; risques de CE patient cités |
| « Allez vous pendre », « et vous pendre », « je vais vous tuer » | incitation, menace | bloqué |
| « Avez-vous des idées de vous tuer ? », « Prenez-vous du tramadol ? » | question | permis |
| « Ne prenez pas d'ibuprofène » | mise en garde | permis |
| « Il s'est pendu l'an dernier », « Vous m'avez dit avoir pris du tramadol hier » | récit | permis ; l'assistant vérifie si le patient lui-même est concerné |
| « Le paracétamol peut donner des nausées » | information | permis |
| « pendre » seul, « Il m'a dit : va te pendre », « tramadol pour votre dos » | ambigu | part seulement si le médecin confirme le sens (signé au journal), sinon il reformule |

Les agents se disent ce qu'ils ont compris : le juriste écrit sa lecture à l'assistant, qui ne prend pas un récit pour
une prescription ; une idée de mort exprimée par le patient pour lui-même déclenche une alerte de l'assistant.

Fautes de frappe et de dictée, corrigées seulement quand c'est sûr, et toujours montrées (« lu comme ») :
« tramadole », « paracetamole », « ibuprophène », « doliprane » (nom commercial), « para c'est tamol » et « trama dol »
(dictée) ; « pandre », « suisider » (même prononciation, jamais « prendre » ni « vendre ») ; « sentew » (clavier QWERTY) ;
« diabhete », « insufisance renale », « enseinte » dans la fiche. Valable aussi dans l'onglet Ordonnance.

La sécurité vaut pour tous les profils, pas seulement la grossesse : âge (aspirine chez l'enfant), allergie
(amoxicilline), ulcère (AINS, aspirine), maladie rénale ou hépatique (metformine), anticoagulants, cœur.

## Inspection fonctionnelle (7 novembre) : ce qui a été corrigé

| Lacune | Risque | Correction |
|---|---|---|
| Un OUI à « Vous êtes d'accord ? » valait consentement même si « d'accord » n'avait pas d'image (le patient voyait « vous ? ») | Consentement non éclairé | Le traducteur ajoute l'image « d'accord » / « accepter » ; sans elle, le OUI n'est PAS enregistré et le médecin est prévenu |
| Aucun moyen d'informer le patient de l'usage de l'IA (obligation DHA IA-INFORMER) | Éthique, transparence | « Message d'accueil » : un ordinateur aide, le médecin décide, le patient peut refuser ; sa réponse est enregistrée ; un refus est signalé et respecté |
| « Où avez-vous mal ? » perdait « où » | Question changée | « où » reconnu ; s'il n'a pas d'image, il est signalé au médecin, jamais perdu |
| Prescription bloquée sur « information manquante » sans moyen direct de la compléter | Perte de temps, abandon | L'assistant fait poser la question au patient ; boutons « Aucune / Demander au patient » ; OUI sans détail = « à préciser » (pas encore renseigné) |
| Questions devenues inutiles restées « à valider » ; conseils périmés et en double | Bruit, confusion | Retrait automatique (journalisé) ; pas de doublon |
| Urgence : le patient ne savait pas s'il était entendu ; le médecin ne pouvait pas clore | Angoisse, alerte permanente | Écran patient : « Le médecin est prévenu », puis « s'occupe de vous » ; bouton « Pris en charge » |
| Le patient ne pouvait pas dire simplement « je ne comprends pas » | Malentendu, faux consentement | Bouton sous chaque message ; l'assistant conseille de reformuler ou de faire appel à un interprète en langue des signes |
| Écran patient sur téléphone : barre du bas coupée | Bouton d'urgence inaccessible | Barre sur deux lignes, images adaptées |
| Filtres du journal bloqués par la politique de sécurité | Traçabilité difficile à lire | Script autorisé par son empreinte (et lui seul) |
| Libellés techniques (« traitements_en_cours », « MEDICAMENT:… ») | Lisibilité | Libellés en clair |

## Garde-fous éthiques (medimcom/ethique.py)

Un message conforme à la forme peut être contraire à l'éthique. Le juriste le bloque et l'assistant rappelle la
pratique attendue, sauf si le contexte en fait une question, une mise en garde ou un récit :

| Exemple | Catégorie | Base |
|---|---|---|
| « une femme enceinte doit se droguer », « vous pouvez fumer » | conseil nuisible (drogue, alcool, tabac) | garde-fou éthique |
| « je vais vous aider à vendre votre bébé » | trafic d'enfant ou d'organe | garde-fou éthique |
| « vous me plaisez », « je veux vous enceinter » | propos sexuels envers le patient | garde-fou éthique |
| « vous pouvez avorter » | avortement par message | loi (Émirats : loi 4/2016, art. 16) |
| « imbecil », « vote cul » | injure, même mal écrite | loi (art. 3) et garde-fou |

Un message sans aucun pictogramme ne part jamais (le patient ne verrait rien).

## Côté patient

- Guide « Décrire ma douleur » : où, comment, intensité, **durée** (nombre + heure, jour, semaine, mois, an), **autres
  symptômes** (vomir, diarrhée, vertige, sang…), **médicaments déjà pris** (enregistrés et vérifiés par l'assistant).
- « Mon ordonnance » : les prescriptions conformes dont l'explication a été validée et envoyée ; affichage en
  pictogrammes et **PDF téléchargeable** (empreinte du journal pour l'authenticité).
- Le texte français accompagnant les pictogrammes n'est montré que si le patient a choisi le français.

## Côté médecin

- Chaque référence citée par le juriste est cliquable : titre, résumé, **extrait exact** et lien vers le texte officiel.
- Langue d'expression (FR, EN, عربي) : interface principale, légendes des pictogrammes, textes des règles du juriste
  (anglais pour EN et AR), consignes données à Grok, traduction en pictogrammes d'un message écrit en anglais.
  Limite : les messages déjà écrits et une partie des libellés secondaires restent en français.
- Traduction : mots collés (« enpharmacie »), fautes sur les mots longs (« erghotherapeute »), « ou » de choix
  distingué de « où » de lieu.

## Limites (à dire au jury)

- **Références étrangères** : ce sont des notices américaines. Un déploiement aux Émirats doit les remplacer par les notices
  de l'Emirates Drug Establishment et le formulaire national ; au Cameroun, par la liste nationale des médicaments essentiels.
- **Couverture** : sept médicaments. Les autres n'ont que les contrôles généraux (dose lisible, fiche complète, allergie
  déclarée au nom du produit). Il n'y a pas de base d'interactions médicamenteuses complète.
- **Pas de calcul au poids** pour l'enfant (mg/kg), sauf la dose maximale de la metformine chez l'enfant.
- **Trois étiquettes** (paracétamol, ibuprofène, aspirine) viennent d'une copie fidèle du texte FDA (NDC List, MedLibrary),
  marquées `secondary_source` : à vérifier sur DailyMed.
- Règles cliniques d'exemple : **à valider par un médecin et un pharmacien** avant tout usage réel.
