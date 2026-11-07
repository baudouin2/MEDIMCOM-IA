# Vidéo de démonstration (7 minutes maximum) — script et plan de tournage

La vidéo est demandée si l'équipe est présélectionnée. Elle suit l'ordre des critères du jury : base de connaissances, agents dans des scénarios d'erreur, lacunes, traçabilité, alignement UIT. **Narration en anglais** (jury international), sous-titres anglais incrustés ; si possible, un médaillon d'interprète en langue des signes (cohérent avec le projet). Durée cible : 6 min 45 s.

## Préparation

- Deux fenêtres côte à côte, en 1920 × 1080 : écran médecin (navigateur, zoom 110 %) et écran patient (fenêtre étroite ou tablette filmée, ou l'outil d'émulation mobile du navigateur).
- Consultation : `python interface/serveur.py --demo scenarios/grossesse.json` ; crise : `python interface/serveur.py --demo scenarios/crise.json --port 8001`. Ouvrir l'écran médecin avec le **lien privé** affiché dans le terminal (`/medecin?jeton=…`) ; ne pas filmer la barre d'adresse (ou la flouter).
- Enregistrement d'écran : OBS Studio (gratuit). Narration enregistrée à part, au calme, puis montée (DaVinci Resolve ou Shotcut, gratuits).
- **Données fictives uniquement** à l'écran ; pas de nom réel ; bandeau « prototype, not a medical device » visible.
- Répéter deux fois à blanc : le mode démonstration rejoue toujours la même chose.

## Plan minuté

| Temps | À l'écran | Narration (anglais) |
|---|---|---|
| 0:00–0:25 | Photo libre de droits ou dessin : patient sourd face à un médecin, sans interprète | *In many clinics, a deaf patient who reads little cannot tell the doctor where it hurts — and cannot understand the treatment. Interpreters are rare, especially in an emergency.* |
| 0:25–1:05 | Schéma du rapport (agents autour du dossier partagé) | *MEDIMCOM AI gives them a shared language: pictograms. Three autonomous AI agents work around one consultation record. A translator turns the doctor's words into pictograms. An assistant keeps the patient's state complete and suggests. A jurist checks every prescription, every message and every data request against UAE law. The doctor always decides.* |
| 1:05–1:35 | Écran médecin : « Étape suivante » (fiche patiente) ; l'assistant pose de lui-même la question ; la proposition de pictogrammes apparaît | *A 25-year-old woman reports abdominal pain. Nobody told the assistant what to do: it notices that pregnancy is unknown and asks. The translator proposes pictograms — nothing leaves without the doctor.* |
| 1:35–2:00 | Clic « Valider et envoyer » ; écran patient : VOUS · ENCEINTE · QUESTION ; elle touche OUI | *The doctor validates. The patient answers with one tap. Her answer becomes a confirmed fact in the record.* |
| 2:00–2:40 | Ordonnance ibuprofène → alerte REVIEW du juriste avec la source ; suggestion de l'assistant ; paracétamol → COMPLIANT | *The doctor prescribes ibuprofen. The jurist re-checks on its own: REVIEW, with the exact source. The assistant proposes a sourced alternative. The doctor chooses paracetamol: compliant, with the legal obligations attached — consent, explanation, accessible information.* |
| 2:40–3:10 | Étape « module externe » → BLOQUÉ ; étape « IA hors des Émirats » → BLOQUÉ, amende citée, piste conforme | *Errors are injected on purpose. A module tries to message the patient without validation: blocked. Someone proposes sending the consultation to a foreign cloud AI: blocked — UAE law keeps health data in the country — and the jurist proposes the lawful path: a local model.* |
| 3:10–4:30 | Démo crise (port 8001), étapes accélérées : tramadol à distance BLOQUÉ, maintien refusé ; maladie du groupe A → rappel des 24 h ; autorité : enquête, question au juriste, zone infectée ; presse → publication nominative BLOQUÉE → chiffres anonymes ; panne d'IA → incident | *Now a crisis, released in fragments. Each institution only sees its own messages and never the patient record. A controlled drug by teleconsultation: blocked, and no override is possible. A suspected outbreak: the jurist reminds the 24-hour notification. The health authority opens an investigation, asks the jurist for its powers, then declares an infected area — every measure must cite a binding legal basis from its mandate. The press asks for names: blocked; the authority follows the jurist's path and publishes anonymised figures.* |
| 4:30–5:15 | `kb/sources.json` ouvert, puis tableau des lacunes du rapport | *All of this rests on a verified knowledge base: 40 instruments, 124 provisions, each with its official link and verification level, tested on 60 questions. When no text settles a situation, the jurist records a gap — for example, no rule says whether consent given in pictograms is valid — with global examples such as the UN Convention and the NHS Accessible Information Standard.* |
| 5:15–6:00 | Page « Journal lisible » ; terminal : `verifier_journal.py --falsifier 10` → « Ligne 10 modifiée » ; tableau de `evaluer_agents.py` | *Everything is auditable: every thought, action, message and verdict is chained by SHA-256 hashes — change one line and it shows. An evaluation bench checks six safety invariants on every run; even a chaotic model calling random tools cannot break them. It all runs offline, on a laptop, with small open models.* |
| 6:00–6:35 | Planche de pictogrammes ; livret de test ; (si faits) résultats des tests | *The pictograms come from existing pictogram databases, labelled in Arabic, English and French. We are testing them with deaf people, following a protocol inspired by ISO 9186-1, and we only claim what the tests show.* |
| 6:35–6:50 | Logo / équipe | *MEDIMCOM AI — team ShifaMiko, University of Yaoundé I. AI that supports, a doctor who decides, and a law that protects.* |

Environ 520 mots de narration : laisse de l'air pour les clics à l'écran. Si les tests utilisateurs ont eu lieu, remplacer la phrase de 6:00 par les chiffres réels (voir `docs/pictogrammes/PROTOCOLE_TESTS.md`, section 7).

## Contrôle avant envoi

- [ ] Durée ≤ 7:00 ; sous-titres lisibles ; son sans souffle.
- [ ] Aucune donnée réelle ; bandeau « prototype » visible au moins une fois.
- [ ] Les chiffres dits correspondent au rapport (sources, dispositions, tests).
- [ ] Rien n'est affirmé qui n'est pas montré (vrai modèle d'IA, tests utilisateurs : seulement s'ils ont été faits).
