# Rapport de vérification formelle — MEDIMCOM IA

Généré par `outils/verifier_formel.py` le 2026-11-07 en 175 s. Méthodes, sémantique et références : [`METHODES_FORMELLES.md`](METHODES_FORMELLES.md).

**Résultat : toutes les propriétés sont vérifiées.**

## Émirats arabes unis (kb/regles_uae.json)

89 propriétés sur 89 vérifiées ; 18 432 299 cas examinés par énumération  plus les preuves SMT sur un domaine non borné.

| | Propriété | Énoncé | Méthode | Cas | Référence |
|---|---|---|---|---|---|
| ✅ | `WF1` | Typage : variables déclarées, opérateurs connus, constantes dans leur domaine | analyse statique | 48 | signature typée (DMN, Catala) |
| ✅ | `WF2` | Identifiants de règles uniques | analyse statique | 48 |  |
| ✅ | `WF3` | Seule une loi ou une norme lue peut bloquer | analyse statique | 81 | principe de la hiérarchie des normes |
| ✅ | `WF4` | Chaque règle ne cite que des textes applicables dans son pays | analyse statique | 81 |  |
| ✅ | `partage.P1` | Refus par défaut : rien n'est conforme sans une permission explicite | énumération exhaustive | 577 368 | politiques « deny by default » (Backes et al., 2018) |
| ✅ | `partage.P2` | Prudence : si une information inconnue pouvait rendre la demande non conforme, le verdict n'est pas « conforme » | énumération exhaustive | 577 368 | logique à trois valeurs de Kleene ; hypothèse du monde ouvert |
| ✅ | `partage.P3` | Monotonie : ajouter une garantie (anonymise, chiffrement, consentement_ecrit, copie_eau) n'aggrave jamais le verdict | énumération exhaustive (relation métamorphique) | 2 309 472 | test métamorphique (Chen et al., 2018) |
| ✅ | `S-PA-HORS-PAYS-AE` | Des données de santé envoyées hors des Émirats sans exception réglementaire sont bloquées. (au moins BLOQUE) | énumération exhaustive | 577 368 | fiches ICT19-A13 |
| ✅ | `S-PA-HORS-PAYS-JAMAIS-CONFORME` | Un transfert hors du pays n'est jamais conforme d'office : au mieux, il est à revoir par un humain. (jamais CONFORME) | énumération exhaustive | 577 368 | fiches ICT19-A13, CM24-TRANSFERT |
| ✅ | `S-PA-COMMERCIAL` | Un usage commercial ou publicitaire sans consentement écrit est bloqué. (au moins BLOQUE) | énumération exhaustive | 577 368 | fiches ICT19-A16, CM24-A9 |
| ✅ | `S-PA-COMMERCIAL-JAMAIS-CONFORME` | Un usage commercial ou publicitaire n'est jamais conforme d'office. (jamais CONFORME) | énumération exhaustive | 577 368 | fiches ICT19-A16, CM24-A9 |
| ✅ | `S-PA-PUBLICATION-NOMINATIVE` | Publier des données non anonymisées est bloqué. (au moins BLOQUE) | énumération exhaustive | 577 368 | fiches ICT19-A16, CM24-SENSIBLES |
| ✅ | `S-PA-RECHERCHE-IDENTIFIANTE` | Une recherche sur des données identifiantes sans consentement est bloquée. (au moins BLOQUE) | énumération exhaustive | 577 368 | fiches ICT19-A16, CM24-A9 |
| ✅ | `S-PA-LIEU-INCONNU` | Sans savoir où vont les données, rien n'est conforme. (jamais CONFORME) | énumération exhaustive | 577 368 | fiches ICT19-A13, CM24-TRANSFERT |
| ✅ | `U-PA-SOINS` | Partager pour les soins avec un hôpital ou le médecin traitant du pays reste possible : conforme quand tout est connu. (au plus CONFORME) | énumération exhaustive | 577 368 | fiches ICT19-A4, ICT19-A16, CM24-SENSIBLES, CM90-A4 |
| ✅ | `U-PA-RECHERCHE-ANONYME` | La recherche sur données anonymisées dans le pays reste possible. (au plus CONFORME) | énumération exhaustive | 577 368 | fiches ICT19-A16 |
| ✅ | `U-PA-AUTORITE-SANTE` | Transmettre à l'autorité de santé du pays pour la santé publique reste possible (déclaration obligatoire). (au plus CONFORME) | énumération exhaustive | 577 368 | fiches ICT19-A16, CM24-SENSIBLES |
| ✅ | `U-PA-PUBLICATION-ANONYME` | Publier des données anonymisées (information du public) reste possible. (au plus CONFORME) | énumération exhaustive | 577 368 | fiches ICT19-A16, CD14-A29 |
| ✅ | `U-PA-ASSURANCE-AE` | Aux Émirats, la transmission à l'assureur santé dans le pays reste possible. (au plus CONFORME) | énumération exhaustive | 577 368 | fiches ICT19-A16 |
| ✅ | `U-PA-JUSTICE-AE` | Aux Émirats, la transmission à une autorité judiciaire du pays reste possible. (au plus CONFORME) | énumération exhaustive | 577 368 | fiches ICT19-A16 |
| ✅ | `U-PA-SANTE-PUBLIQUE-AE` | Aux Émirats, l'usage pour la santé publique dans le pays reste possible. (au plus CONFORME) | énumération exhaustive | 577 368 | fiches ICT19-A16, CD14-A10, CD14-A29 |
| ✅ | `S-PA-HORS-PAYS-GARANTIES-AE` | Hors des Émirats avec exception, consentement, chiffrement et copie locale : ni conforme d'office, ni bloqué ; un humain décide (à revoir). (au moins A_REVOIR et au plus A_REVOIR) | énumération exhaustive | 577 368 | fiches RES51-EXC, RES51-COND, ICT19-A13 |
| ✅ | `S-PA-HORS-PAYS-SANS-GARANTIE-AE` | Hors des Émirats, l'absence de consentement, de chiffrement ou de copie locale bloque, même avec une exception. (au moins BLOQUE) | énumération exhaustive | 577 368 | fiches ICT19-A13, RES51-COND |
| ✅ | `S-PA-HORS-PAYS-CHIFFREMENT-AE` | Hors des Émirats sans chiffrement : bloqué. (au moins BLOQUE) | énumération exhaustive | 577 368 | fiches ICT19-A13, RES51-COND |
| ✅ | `S-PA-HORS-PAYS-COPIE-AE` | Hors des Émirats sans copie conservée aux Émirats : bloqué. (au moins BLOQUE) | énumération exhaustive | 577 368 | fiches ICT19-A13, RES51-COND |
| ✅ | `S-PA-ENTRAINEMENT-IA` | Entraîner une IA sur des données dont l'anonymisation n'est pas établie demande toujours une décision humaine (au moins à revoir). (au moins A_REVOIR) | énumération exhaustive | 577 368 | fiches ICT19-A16, AIA-A57-59, CM24-A9, CM24-SENSIBLES |
| ✅ | `S-PA-RECHERCHE-IDENTIFIANTE-ACCORD-AE` | Recherche sur données identifiantes avec consentement : décision humaine (à revoir). (au moins A_REVOIR) | énumération exhaustive | 577 368 | fiches ICT19-A16 |
| ✅ | `S-PA-PERMISSION-DANS-LE-PAYS` | Rien n'est conforme d'office si les données ne restent pas dans le pays (lieu établi : dans le pays). (jamais CONFORME) | énumération exhaustive | 577 368 | fiches ICT19-A13, CM24-TRANSFERT |
| ✅ | `S-PA-FINALITE-NON-PREVUE` | Limitation des finalités : une finalité que les textes ne prévoient pas n'est jamais conforme d'office (sauf transmission à une autorité ou publication anonyme, régies par leurs propres règles). (jamais CONFORME) | énumération exhaustive | 577 368 | fiches ICT19-A16, CM24-A9 |
| ✅ | `S-PA-SOINS-DESTINATAIRE` | Pour les soins, seuls les soignants (médecin traitant, établissement de santé, hôpital) ou les autorités reçoivent les données d'office. (jamais CONFORME) | énumération exhaustive | 577 368 | fiches ICT19-A16, CM24-SENSIBLES |
| ✅ | `partage.P5` | Aucune règle morte : chaque règle s'applique dans au moins un cas | énumération exhaustive | 26 | analyse de couverture des tables de décision (DMN) |
| ✅ | `envoi_patient.P1` | Refus par défaut : rien n'est conforme sans une permission explicite | énumération exhaustive | 648 | politiques « deny by default » (Backes et al., 2018) |
| ✅ | `envoi_patient.P2` | Prudence : si une information inconnue pouvait rendre la demande non conforme, le verdict n'est pas « conforme » | énumération exhaustive | 648 | logique à trois valeurs de Kleene ; hypothèse du monde ouvert |
| ✅ | `S-EN-VALIDATION-HUMAINE` | Aucun message n'est conforme sans la validation d'un médecin autorisé et actif. (au moins BLOQUE) | énumération exhaustive | 648 | fiches DHA21-4.4, CM90-A2 |
| ✅ | `S-EN-TRAITEMENT-PRESCRIPTION` | Un message de traitement n'est conforme que s'il explique une prescription conforme ou maintenue par le médecin. (au moins BLOQUE) | énumération exhaustive | 648 | fiches ML16-A4-2, CM90-A2 |
| ✅ | `S-EN-TRAITEMENT-SANS-PRESCRIPTION` | Un message de traitement sans prescription liée est bloqué. (au moins BLOQUE) | énumération exhaustive | 648 | fiches ML16-A4-2, CM90-A2 |
| ✅ | `S-EN-PROPOS-DANGEREUX` | Un message qui incite le patient à se faire du mal (ou l'injurie) est bloqué, même validé par le médecin. (au moins BLOQUE) | énumération exhaustive | 648 | fiches ML16-A3, DHA21-4.4 |
| ✅ | `S-EN-PRODUIT-CONTROLE` | Une consigne de prise d'un produit contrôlé sans prescription liée est bloquée. (au moins BLOQUE) | énumération exhaustive | 648 | fiches MP24-A55 |
| ✅ | `U-EN-MESSAGE-VALIDE` | Un message validé par un médecin autorisé, sans traitement en jeu et sans propos dangereux, peut partir au patient. (au plus CONFORME) | énumération exhaustive | 648 | fiches DHA21-4.4, CM90-A2 |
| ✅ | `U-EN-TRAITEMENT-CONFORME` | L'explication validée d'une prescription conforme ou maintenue peut partir au patient. (au plus CONFORME) | énumération exhaustive | 648 | fiches DHA21-4.4, CM90-A2 |
| ✅ | `envoi_patient.P5` | Aucune règle morte : chaque règle s'applique dans au moins un cas | énumération exhaustive | 7 | analyse de couverture des tables de décision (DMN) |
| ✅ | `prescription.PR1` | Une prescription conforme vient d'un médecin humain, autorisé et actif | énumération exhaustive | 186 624 | contrôle humain (AI Act, art. 14) |
| ✅ | `prescription.PR2` | Une prescription conforme porte sur un médicament connu et autorisé (AMM) | énumération exhaustive | 186 624 |  |
| ✅ | `prescription.PR3` | Une prescription conforme suppose les informations obligatoires connues et confirmées | énumération exhaustive | 186 624 | fiches des champs obligatoires |
| ✅ | `prescription.PR4` | Grossesse confirmée et contre-indication : verdict au moins celui de la contre-indication | énumération exhaustive | 186 624 |  |
| ✅ | `prescription.PR5` | Grossesse inconnue chez une femme qui peut être enceinte : jamais conforme avec un médicament contre-indiqué | énumération exhaustive | 186 624 | logique de Kleene |
| ✅ | `prescription.PR6` | Allergie au médicament prescrit : verdict au moins celui de la règle d'allergie | énumération exhaustive | 186 624 |  |
| ✅ | `prescription.PR7` | Confirmer une information n'aggrave jamais le verdict | énumération exhaustive (relation métamorphique) | 186 624 | test métamorphique (Chen et al., 2018) |
| ✅ | `prescription.PR8` | Pas de fausse alerte : grossesse non renseignée chez un homme, aucune contre-indication liée à la grossesse | énumération exhaustive | 186 624 | connaissances de fond (axiomes), Semantic DMN (Calvanese et al.) |
| ✅ | `prescription.PR9` | Informations contradictoires (homme noté enceint) : signalées, jamais conformes | énumération exhaustive | 186 624 | cohérence des faits avec les axiomes |
| ✅ | `maintien.MA1` | Une décision bloquée ne peut jamais être maintenue | énumération exhaustive | 120 | hiérarchie des normes |
| ✅ | `maintien.MA2` | Un maintien exige une décision « à revoir », un médecin autorisé et actif, et une justification écrite | énumération exhaustive | 120 | contrôle humain (AI Act, art. 14) |
| ✅ | `partage.P1` | Refus par défaut (preuve) | preuve SMT (Z3), domaine non borné | ∞ | Backes et al., FMCAD 2018 |
| ✅ | `partage.P2` | Prudence face à l'inconnu (preuve) | preuve SMT (Z3), domaine non borné | ∞ | logique de Kleene |
| ✅ | `partage.P3` | Monotonie des garanties (preuve) | preuve SMT (Z3), domaine non borné | ∞ | Chen et al., 2018 |
| ✅ | `S-PA-HORS-PAYS-AE (SMT)` | Des données de santé envoyées hors des Émirats sans exception réglementaire sont bloquées. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A13 |
| ✅ | `S-PA-HORS-PAYS-JAMAIS-CONFORME (SMT)` | Un transfert hors du pays n'est jamais conforme d'office : au mieux, il est à revoir par un humain. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A13, CM24-TRANSFERT |
| ✅ | `S-PA-COMMERCIAL (SMT)` | Un usage commercial ou publicitaire sans consentement écrit est bloqué. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CM24-A9 |
| ✅ | `S-PA-COMMERCIAL-JAMAIS-CONFORME (SMT)` | Un usage commercial ou publicitaire n'est jamais conforme d'office. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CM24-A9 |
| ✅ | `S-PA-PUBLICATION-NOMINATIVE (SMT)` | Publier des données non anonymisées est bloqué. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CM24-SENSIBLES |
| ✅ | `S-PA-RECHERCHE-IDENTIFIANTE (SMT)` | Une recherche sur des données identifiantes sans consentement est bloquée. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CM24-A9 |
| ✅ | `S-PA-LIEU-INCONNU (SMT)` | Sans savoir où vont les données, rien n'est conforme. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A13, CM24-TRANSFERT |
| ✅ | `U-PA-SOINS (SMT)` | Partager pour les soins avec un hôpital ou le médecin traitant du pays reste possible : conforme quand tout est connu. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A4, ICT19-A16, CM24-SENSIBLES, CM90-A4 |
| ✅ | `U-PA-RECHERCHE-ANONYME (SMT)` | La recherche sur données anonymisées dans le pays reste possible. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16 |
| ✅ | `U-PA-AUTORITE-SANTE (SMT)` | Transmettre à l'autorité de santé du pays pour la santé publique reste possible (déclaration obligatoire). | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CM24-SENSIBLES |
| ✅ | `U-PA-PUBLICATION-ANONYME (SMT)` | Publier des données anonymisées (information du public) reste possible. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CD14-A29 |
| ✅ | `U-PA-ASSURANCE-AE (SMT)` | Aux Émirats, la transmission à l'assureur santé dans le pays reste possible. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16 |
| ✅ | `U-PA-JUSTICE-AE (SMT)` | Aux Émirats, la transmission à une autorité judiciaire du pays reste possible. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16 |
| ✅ | `U-PA-SANTE-PUBLIQUE-AE (SMT)` | Aux Émirats, l'usage pour la santé publique dans le pays reste possible. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CD14-A10, CD14-A29 |
| ✅ | `S-PA-HORS-PAYS-GARANTIES-AE (SMT)` | Hors des Émirats avec exception, consentement, chiffrement et copie locale : ni conforme d'office, ni bloqué ; un humain décide (à revoir). | preuve SMT (Z3), domaine non borné | ∞ | fiches RES51-EXC, RES51-COND, ICT19-A13 |
| ✅ | `S-PA-HORS-PAYS-SANS-GARANTIE-AE (SMT)` | Hors des Émirats, l'absence de consentement, de chiffrement ou de copie locale bloque, même avec une exception. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A13, RES51-COND |
| ✅ | `S-PA-HORS-PAYS-CHIFFREMENT-AE (SMT)` | Hors des Émirats sans chiffrement : bloqué. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A13, RES51-COND |
| ✅ | `S-PA-HORS-PAYS-COPIE-AE (SMT)` | Hors des Émirats sans copie conservée aux Émirats : bloqué. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A13, RES51-COND |
| ✅ | `S-PA-ENTRAINEMENT-IA (SMT)` | Entraîner une IA sur des données dont l'anonymisation n'est pas établie demande toujours une décision humaine (au moins à revoir). | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, AIA-A57-59, CM24-A9, CM24-SENSIBLES |
| ✅ | `S-PA-RECHERCHE-IDENTIFIANTE-ACCORD-AE (SMT)` | Recherche sur données identifiantes avec consentement : décision humaine (à revoir). | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16 |
| ✅ | `S-PA-PERMISSION-DANS-LE-PAYS (SMT)` | Rien n'est conforme d'office si les données ne restent pas dans le pays (lieu établi : dans le pays). | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A13, CM24-TRANSFERT |
| ✅ | `S-PA-FINALITE-NON-PREVUE (SMT)` | Limitation des finalités : une finalité que les textes ne prévoient pas n'est jamais conforme d'office (sauf transmission à une autorité ou publication anonyme, régies par leurs propres règles). | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CM24-A9 |
| ✅ | `S-PA-SOINS-DESTINATAIRE (SMT)` | Pour les soins, seuls les soignants (médecin traitant, établissement de santé, hôpital) ou les autorités reçoivent les données d'office. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CM24-SENSIBLES |
| ✅ | `partage.X` | Validation croisée : l'encodage logique et le moteur réel rendent le même verdict | comparaison sur 2000 entrées | 2 000 | N-version / double implémentation |
| ✅ | `envoi_patient.P1` | Refus par défaut (preuve) | preuve SMT (Z3), domaine non borné | ∞ | Backes et al., FMCAD 2018 |
| ✅ | `envoi_patient.P2` | Prudence face à l'inconnu (preuve) | preuve SMT (Z3), domaine non borné | ∞ | logique de Kleene |
| ✅ | `S-EN-VALIDATION-HUMAINE (SMT)` | Aucun message n'est conforme sans la validation d'un médecin autorisé et actif. | preuve SMT (Z3), domaine non borné | ∞ | fiches DHA21-4.4, CM90-A2 |
| ✅ | `S-EN-TRAITEMENT-PRESCRIPTION (SMT)` | Un message de traitement n'est conforme que s'il explique une prescription conforme ou maintenue par le médecin. | preuve SMT (Z3), domaine non borné | ∞ | fiches ML16-A4-2, CM90-A2 |
| ✅ | `S-EN-TRAITEMENT-SANS-PRESCRIPTION (SMT)` | Un message de traitement sans prescription liée est bloqué. | preuve SMT (Z3), domaine non borné | ∞ | fiches ML16-A4-2, CM90-A2 |
| ✅ | `S-EN-PROPOS-DANGEREUX (SMT)` | Un message qui incite le patient à se faire du mal (ou l'injurie) est bloqué, même validé par le médecin. | preuve SMT (Z3), domaine non borné | ∞ | fiches ML16-A3, DHA21-4.4 |
| ✅ | `S-EN-PRODUIT-CONTROLE (SMT)` | Une consigne de prise d'un produit contrôlé sans prescription liée est bloquée. | preuve SMT (Z3), domaine non borné | ∞ | fiches MP24-A55 |
| ✅ | `U-EN-MESSAGE-VALIDE (SMT)` | Un message validé par un médecin autorisé, sans traitement en jeu et sans propos dangereux, peut partir au patient. | preuve SMT (Z3), domaine non borné | ∞ | fiches DHA21-4.4, CM90-A2 |
| ✅ | `U-EN-TRAITEMENT-CONFORME (SMT)` | L'explication validée d'une prescription conforme ou maintenue peut partir au patient. | preuve SMT (Z3), domaine non borné | ∞ | fiches DHA21-4.4, CM90-A2 |
| ✅ | `envoi_patient.X` | Validation croisée : l'encodage logique et le moteur réel rendent le même verdict | comparaison sur 648 entrées | 648 | N-version / double implémentation |

**Exploration du système réel** : 600 suites, 6006 événements (dont des tentatives d'abus), 61347 lignes de journal, 181 messages envoyés au patient, 23 maintiens acceptés et 252 refusés ; verdicts : A_REVOIR 372, BLOQUE 1720, CONFORME 446, PREUVES_INSUFFISANTES 225. Aucune violation des propriétés du moniteur.

## Cameroun (kb/regles_cm.json)

71 propriétés sur 71 vérifiées ; 3 104 762 cas examinés par énumération  plus les preuves SMT sur un domaine non borné.

| | Propriété | Énoncé | Méthode | Cas | Référence |
|---|---|---|---|---|---|
| ✅ | `WF1` | Typage : variables déclarées, opérateurs connus, constantes dans leur domaine | analyse statique | 34 | signature typée (DMN, Catala) |
| ✅ | `WF2` | Identifiants de règles uniques | analyse statique | 34 |  |
| ✅ | `WF3` | Seule une loi ou une norme lue peut bloquer | analyse statique | 67 | principe de la hiérarchie des normes |
| ✅ | `WF4` | Chaque règle ne cite que des textes applicables dans son pays | analyse statique | 67 |  |
| ✅ | `partage.P1` | Refus par défaut : rien n'est conforme sans une permission explicite | énumération exhaustive | 67 500 | politiques « deny by default » (Backes et al., 2018) |
| ✅ | `partage.P2` | Prudence : si une information inconnue pouvait rendre la demande non conforme, le verdict n'est pas « conforme » | énumération exhaustive | 67 500 | logique à trois valeurs de Kleene ; hypothèse du monde ouvert |
| ✅ | `partage.P3` | Monotonie : ajouter une garantie (anonymise, autorisation_autorite, consentement_ecrit) n'aggrave jamais le verdict | énumération exhaustive (relation métamorphique) | 202 500 | test métamorphique (Chen et al., 2018) |
| ✅ | `S-PA-HORS-PAYS-CM` | Des données de santé envoyées hors du Cameroun sans autorisation établie de l'autorité de protection des données sont bloquées. (au moins BLOQUE) | énumération exhaustive | 67 500 | fiches CM24-TRANSFERT |
| ✅ | `S-PA-HORS-PAYS-JAMAIS-CONFORME` | Un transfert hors du pays n'est jamais conforme d'office : au mieux, il est à revoir par un humain. (jamais CONFORME) | énumération exhaustive | 67 500 | fiches ICT19-A13, CM24-TRANSFERT |
| ✅ | `S-PA-COMMERCIAL` | Un usage commercial ou publicitaire sans consentement écrit est bloqué. (au moins BLOQUE) | énumération exhaustive | 67 500 | fiches ICT19-A16, CM24-A9 |
| ✅ | `S-PA-COMMERCIAL-JAMAIS-CONFORME` | Un usage commercial ou publicitaire n'est jamais conforme d'office. (jamais CONFORME) | énumération exhaustive | 67 500 | fiches ICT19-A16, CM24-A9 |
| ✅ | `S-PA-PUBLICATION-NOMINATIVE` | Publier des données non anonymisées est bloqué. (au moins BLOQUE) | énumération exhaustive | 67 500 | fiches ICT19-A16, CM24-SENSIBLES |
| ✅ | `S-PA-RECHERCHE-IDENTIFIANTE` | Une recherche sur des données identifiantes sans consentement est bloquée. (au moins BLOQUE) | énumération exhaustive | 67 500 | fiches ICT19-A16, CM24-A9 |
| ✅ | `S-PA-LIEU-INCONNU` | Sans savoir où vont les données, rien n'est conforme. (jamais CONFORME) | énumération exhaustive | 67 500 | fiches ICT19-A13, CM24-TRANSFERT |
| ✅ | `U-PA-SOINS` | Partager pour les soins avec un hôpital ou le médecin traitant du pays reste possible : conforme quand tout est connu. (au plus CONFORME) | énumération exhaustive | 67 500 | fiches ICT19-A4, ICT19-A16, CM24-SENSIBLES, CM90-A4 |
| ✅ | `U-PA-RECHERCHE-ANONYME` | La recherche sur données anonymisées dans le pays reste possible. (au plus CONFORME) | énumération exhaustive | 67 500 | fiches ICT19-A16 |
| ✅ | `U-PA-AUTORITE-SANTE` | Transmettre à l'autorité de santé du pays pour la santé publique reste possible (déclaration obligatoire). (au plus CONFORME) | énumération exhaustive | 67 500 | fiches ICT19-A16, CM24-SENSIBLES |
| ✅ | `U-PA-PUBLICATION-ANONYME` | Publier des données anonymisées (information du public) reste possible. (au plus CONFORME) | énumération exhaustive | 67 500 | fiches ICT19-A16, CD14-A29 |
| ✅ | `S-PA-HORS-PAYS-AUTORISE-CM` | Hors du Cameroun avec l'autorisation de l'autorité : ni conforme d'office, ni bloqué ; un humain décide (à revoir). (au moins A_REVOIR et au plus A_REVOIR) | énumération exhaustive | 67 500 | fiches CM24-TRANSFERT, CM24-A9 |
| ✅ | `S-PA-ENTRAINEMENT-IA` | Entraîner une IA sur des données dont l'anonymisation n'est pas établie demande toujours une décision humaine (au moins à revoir). (au moins A_REVOIR) | énumération exhaustive | 67 500 | fiches ICT19-A16, AIA-A57-59, CM24-A9, CM24-SENSIBLES |
| ✅ | `S-PA-PERMISSION-DANS-LE-PAYS` | Rien n'est conforme d'office si les données ne restent pas dans le pays (lieu établi : dans le pays). (jamais CONFORME) | énumération exhaustive | 67 500 | fiches ICT19-A13, CM24-TRANSFERT |
| ✅ | `S-PA-FINALITE-NON-PREVUE` | Limitation des finalités : une finalité que les textes ne prévoient pas n'est jamais conforme d'office (sauf transmission à une autorité ou publication anonyme, régies par leurs propres règles). (jamais CONFORME) | énumération exhaustive | 67 500 | fiches ICT19-A16, CM24-A9 |
| ✅ | `S-PA-SOINS-DESTINATAIRE` | Pour les soins, seuls les soignants (médecin traitant, établissement de santé, hôpital) ou les autorités reçoivent les données d'office. (jamais CONFORME) | énumération exhaustive | 67 500 | fiches ICT19-A16, CM24-SENSIBLES |
| ✅ | `partage.P5` | Aucune règle morte : chaque règle s'applique dans au moins un cas | énumération exhaustive | 15 | analyse de couverture des tables de décision (DMN) |
| ✅ | `envoi_patient.P1` | Refus par défaut : rien n'est conforme sans une permission explicite | énumération exhaustive | 648 | politiques « deny by default » (Backes et al., 2018) |
| ✅ | `envoi_patient.P2` | Prudence : si une information inconnue pouvait rendre la demande non conforme, le verdict n'est pas « conforme » | énumération exhaustive | 648 | logique à trois valeurs de Kleene ; hypothèse du monde ouvert |
| ✅ | `S-EN-VALIDATION-HUMAINE` | Aucun message n'est conforme sans la validation d'un médecin autorisé et actif. (au moins BLOQUE) | énumération exhaustive | 648 | fiches DHA21-4.4, CM90-A2 |
| ✅ | `S-EN-TRAITEMENT-PRESCRIPTION` | Un message de traitement n'est conforme que s'il explique une prescription conforme ou maintenue par le médecin. (au moins BLOQUE) | énumération exhaustive | 648 | fiches ML16-A4-2, CM90-A2 |
| ✅ | `S-EN-TRAITEMENT-SANS-PRESCRIPTION` | Un message de traitement sans prescription liée est bloqué. (au moins BLOQUE) | énumération exhaustive | 648 | fiches ML16-A4-2, CM90-A2 |
| ✅ | `U-EN-MESSAGE-VALIDE` | Un message validé par un médecin autorisé, sans traitement en jeu et sans propos dangereux, peut partir au patient. (au plus CONFORME) | énumération exhaustive | 648 | fiches DHA21-4.4, CM90-A2 |
| ✅ | `U-EN-TRAITEMENT-CONFORME` | L'explication validée d'une prescription conforme ou maintenue peut partir au patient. (au plus CONFORME) | énumération exhaustive | 648 | fiches DHA21-4.4, CM90-A2 |
| ✅ | `envoi_patient.P5` | Aucune règle morte : chaque règle s'applique dans au moins un cas | énumération exhaustive | 5 | analyse de couverture des tables de décision (DMN) |
| ✅ | `prescription.PR1` | Une prescription conforme vient d'un médecin humain, autorisé et actif | énumération exhaustive | 186 624 | contrôle humain (AI Act, art. 14) |
| ✅ | `prescription.PR2` | Une prescription conforme porte sur un médicament connu et autorisé (AMM) | énumération exhaustive | 186 624 |  |
| ✅ | `prescription.PR3` | Une prescription conforme suppose les informations obligatoires connues et confirmées | énumération exhaustive | 186 624 | fiches des champs obligatoires |
| ✅ | `prescription.PR4` | Grossesse confirmée et contre-indication : verdict au moins celui de la contre-indication | énumération exhaustive | 186 624 |  |
| ✅ | `prescription.PR5` | Grossesse inconnue chez une femme qui peut être enceinte : jamais conforme avec un médicament contre-indiqué | énumération exhaustive | 186 624 | logique de Kleene |
| ✅ | `prescription.PR6` | Allergie au médicament prescrit : verdict au moins celui de la règle d'allergie | énumération exhaustive | 186 624 |  |
| ✅ | `prescription.PR7` | Confirmer une information n'aggrave jamais le verdict | énumération exhaustive (relation métamorphique) | 186 624 | test métamorphique (Chen et al., 2018) |
| ✅ | `prescription.PR8` | Pas de fausse alerte : grossesse non renseignée chez un homme, aucune contre-indication liée à la grossesse | énumération exhaustive | 186 624 | connaissances de fond (axiomes), Semantic DMN (Calvanese et al.) |
| ✅ | `prescription.PR9` | Informations contradictoires (homme noté enceint) : signalées, jamais conformes | énumération exhaustive | 186 624 | cohérence des faits avec les axiomes |
| ✅ | `maintien.MA1` | Une décision bloquée ne peut jamais être maintenue | énumération exhaustive | 120 | hiérarchie des normes |
| ✅ | `maintien.MA2` | Un maintien exige une décision « à revoir », un médecin autorisé et actif, et une justification écrite | énumération exhaustive | 120 | contrôle humain (AI Act, art. 14) |
| ✅ | `partage.P1` | Refus par défaut (preuve) | preuve SMT (Z3), domaine non borné | ∞ | Backes et al., FMCAD 2018 |
| ✅ | `partage.P2` | Prudence face à l'inconnu (preuve) | preuve SMT (Z3), domaine non borné | ∞ | logique de Kleene |
| ✅ | `partage.P3` | Monotonie des garanties (preuve) | preuve SMT (Z3), domaine non borné | ∞ | Chen et al., 2018 |
| ✅ | `S-PA-HORS-PAYS-CM (SMT)` | Des données de santé envoyées hors du Cameroun sans autorisation établie de l'autorité de protection des données sont bloquées. | preuve SMT (Z3), domaine non borné | ∞ | fiches CM24-TRANSFERT |
| ✅ | `S-PA-HORS-PAYS-JAMAIS-CONFORME (SMT)` | Un transfert hors du pays n'est jamais conforme d'office : au mieux, il est à revoir par un humain. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A13, CM24-TRANSFERT |
| ✅ | `S-PA-COMMERCIAL (SMT)` | Un usage commercial ou publicitaire sans consentement écrit est bloqué. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CM24-A9 |
| ✅ | `S-PA-COMMERCIAL-JAMAIS-CONFORME (SMT)` | Un usage commercial ou publicitaire n'est jamais conforme d'office. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CM24-A9 |
| ✅ | `S-PA-PUBLICATION-NOMINATIVE (SMT)` | Publier des données non anonymisées est bloqué. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CM24-SENSIBLES |
| ✅ | `S-PA-RECHERCHE-IDENTIFIANTE (SMT)` | Une recherche sur des données identifiantes sans consentement est bloquée. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CM24-A9 |
| ✅ | `S-PA-LIEU-INCONNU (SMT)` | Sans savoir où vont les données, rien n'est conforme. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A13, CM24-TRANSFERT |
| ✅ | `U-PA-SOINS (SMT)` | Partager pour les soins avec un hôpital ou le médecin traitant du pays reste possible : conforme quand tout est connu. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A4, ICT19-A16, CM24-SENSIBLES, CM90-A4 |
| ✅ | `U-PA-RECHERCHE-ANONYME (SMT)` | La recherche sur données anonymisées dans le pays reste possible. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16 |
| ✅ | `U-PA-AUTORITE-SANTE (SMT)` | Transmettre à l'autorité de santé du pays pour la santé publique reste possible (déclaration obligatoire). | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CM24-SENSIBLES |
| ✅ | `U-PA-PUBLICATION-ANONYME (SMT)` | Publier des données anonymisées (information du public) reste possible. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CD14-A29 |
| ✅ | `S-PA-HORS-PAYS-AUTORISE-CM (SMT)` | Hors du Cameroun avec l'autorisation de l'autorité : ni conforme d'office, ni bloqué ; un humain décide (à revoir). | preuve SMT (Z3), domaine non borné | ∞ | fiches CM24-TRANSFERT, CM24-A9 |
| ✅ | `S-PA-ENTRAINEMENT-IA (SMT)` | Entraîner une IA sur des données dont l'anonymisation n'est pas établie demande toujours une décision humaine (au moins à revoir). | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, AIA-A57-59, CM24-A9, CM24-SENSIBLES |
| ✅ | `S-PA-PERMISSION-DANS-LE-PAYS (SMT)` | Rien n'est conforme d'office si les données ne restent pas dans le pays (lieu établi : dans le pays). | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A13, CM24-TRANSFERT |
| ✅ | `S-PA-FINALITE-NON-PREVUE (SMT)` | Limitation des finalités : une finalité que les textes ne prévoient pas n'est jamais conforme d'office (sauf transmission à une autorité ou publication anonyme, régies par leurs propres règles). | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CM24-A9 |
| ✅ | `S-PA-SOINS-DESTINATAIRE (SMT)` | Pour les soins, seuls les soignants (médecin traitant, établissement de santé, hôpital) ou les autorités reçoivent les données d'office. | preuve SMT (Z3), domaine non borné | ∞ | fiches ICT19-A16, CM24-SENSIBLES |
| ✅ | `partage.X` | Validation croisée : l'encodage logique et le moteur réel rendent le même verdict | comparaison sur 2000 entrées | 2 000 | N-version / double implémentation |
| ✅ | `envoi_patient.P1` | Refus par défaut (preuve) | preuve SMT (Z3), domaine non borné | ∞ | Backes et al., FMCAD 2018 |
| ✅ | `envoi_patient.P2` | Prudence face à l'inconnu (preuve) | preuve SMT (Z3), domaine non borné | ∞ | logique de Kleene |
| ✅ | `S-EN-VALIDATION-HUMAINE (SMT)` | Aucun message n'est conforme sans la validation d'un médecin autorisé et actif. | preuve SMT (Z3), domaine non borné | ∞ | fiches DHA21-4.4, CM90-A2 |
| ✅ | `S-EN-TRAITEMENT-PRESCRIPTION (SMT)` | Un message de traitement n'est conforme que s'il explique une prescription conforme ou maintenue par le médecin. | preuve SMT (Z3), domaine non borné | ∞ | fiches ML16-A4-2, CM90-A2 |
| ✅ | `S-EN-TRAITEMENT-SANS-PRESCRIPTION (SMT)` | Un message de traitement sans prescription liée est bloqué. | preuve SMT (Z3), domaine non borné | ∞ | fiches ML16-A4-2, CM90-A2 |
| ✅ | `U-EN-MESSAGE-VALIDE (SMT)` | Un message validé par un médecin autorisé, sans traitement en jeu et sans propos dangereux, peut partir au patient. | preuve SMT (Z3), domaine non borné | ∞ | fiches DHA21-4.4, CM90-A2 |
| ✅ | `U-EN-TRAITEMENT-CONFORME (SMT)` | L'explication validée d'une prescription conforme ou maintenue peut partir au patient. | preuve SMT (Z3), domaine non borné | ∞ | fiches DHA21-4.4, CM90-A2 |
| ✅ | `envoi_patient.X` | Validation croisée : l'encodage logique et le moteur réel rendent le même verdict | comparaison sur 648 entrées | 648 | N-version / double implémentation |

**Exploration du système réel** : 600 suites, 5861 événements (dont des tentatives d'abus), 59922 lignes de journal, 166 messages envoyés au patient, 33 maintiens acceptés et 214 refusés ; verdicts : A_REVOIR 476, BLOQUE 1527, CONFORME 350, PREUVES_INSUFFISANTES 253. Aucune violation des propriétés du moniteur.

## Propriétés du moniteur (journal)

| | Énoncé |
|---|---|
| `R1` | Aucun message n'atteint le patient sans avoir été validé avant par un médecin humain, autorisé et actif. |
| `R2` | Aucun message n'atteint le patient sans un verdict « conforme » du juriste, rendu après la validation. |
| `R3` | Un message de traitement n'atteint le patient que si la prescription expliquée est conforme ou maintenue. |
| `R4` | Seule une décision « à revoir » peut être maintenue, par un médecin autorisé et actif, avec une justification écrite. |
| `R5` | Chaque verdict enregistré est le plus strict de ses constats, et chaque constat restrictif cite au moins une fiche. |
| `R6` | Toute décision soumise (prescription, partage, message validé) a reçu au moins un verdict du juriste. |
| `R7` | Le journal est intact (chaîne d'empreintes SHA-256). |
| `R9` | Un maintien ne couvre que les motifs « à revoir » examinés par le médecin : un nouveau motif exige un nouveau maintien. |
| `R10` | Le cycle de vie de chaque décision suit la machine à états spécifiée (aucune transition interdite). |
| `R8` | Le juriste ne juge « conforme » un message au patient que si une validation par un médecin autorisé a été enregistrée avant. |
