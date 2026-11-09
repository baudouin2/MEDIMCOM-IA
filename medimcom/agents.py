"""Agents autonomes de MEDIMCOM IA.

Chaque agent a : un BUT, des OUTILS (avec leurs droits), et une BOUCLE de décision.
- En mode Ollama, le modèle de langage choisit lui-même quels outils appeler.
- En mode simulé, une politique écrite à la main joue ce rôle (pour tester sans IA).

Les garde-fous sont dans les outils : un agent ne peut appeler que SES outils,
et le verdict juridique est toujours calculé par le moteur de règles (déterministe).
"""
import json
import re
import time
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path

from .cerveaux import CerveauSimule, appels_dans_le_texte, separer_reflexion
from .surete import normaliser as _normaliser_texte
from .dossier import Dossier
from .journal import Journal
from .messagerie import Messagerie, TYPES
from .bibliotheque import connu as picto_connu, libelle as picto_libelle
from .pictogrammes import LexiquePictogrammes, combiner_automatiquement, PARTIES_DU_CORPS
from .regles import MoteurRegles


class Interrompu(Exception):
    """Un humain attend (clic du médecin ou du patient) : l'agent remet sa réflexion à plus tard."""


@dataclass
class Contexte:
    dossier: Dossier
    messagerie: Messagerie
    journal: Journal
    regles: MoteurRegles
    verbeux: bool = True
    repli_sans_ia: bool = True          # dégradation gracieuse : si le modèle tombe, politique écrite à la main
    echecs_modele: dict = field(default_factory=dict)   # échecs consécutifs, par modèle
    seuil_echecs: int = 3               # au-delà : ce modèle est déclaré hors service (les autres continuent)
    disjoncteur_depuis: dict = field(default_factory=dict)   # modèle -> heure de la mise hors service
    reessai_s: float = 90.0             # un modèle hors service est réessayé après ce délai (clé corrigée, réseau revenu)
    etat_modele: dict = field(default_factory=dict)          # modèle -> {"disponible": bool, "message": str}
    langue_medecin: str = "fr"          # langue d'expression choisie par le médecin (fr, en, ar)
    # Questions de l'assistant : traduites d'office dans la conversation (scénarios, tests) ou seulement quand le médecin
    # les choisit dans l'onglet Assistant (écran médecin : la conversation reste lisible)
    questions_assistant_auto: bool = True
    pictogrammeur: object = field(default_factory=LexiquePictogrammes)
    corpus: object = None               # textes officiels complets et fiches OMS de base_v2 (medimcom.base_v2.Corpus), si présents
    interrompre: object = None          # fonction : vrai si un humain attend (l'agent en ligne cède alors la place)
    derniere_duree_modele: float | None = None   # durée (s) de la dernière réponse du modèle en ligne
    attente_modele: object = None       # gestionnaire de contexte : rend le verrou de l'interface pendant l'attente du modèle
    crise: "RegistreCrise" = field(default_factory=lambda: RegistreCrise())


class RegistreCrise:
    """Tableau de crise partagé par les institutions (sans données nominatives des patients)."""

    def __init__(self):
        self.mesures: list[dict] = []
        self.incidents: list[dict] = []


def _schema(nom, description, proprietes=None, requis=None):
    return {"type": "function", "function": {
        "name": nom, "description": description,
        "parameters": {"type": "object", "properties": proprietes or {}, "required": requis or []}}}


class ModeleHorsService(RuntimeError):
    """Le modèle a échoué trop de fois de suite."""


def conformer(schema: dict, args: dict) -> tuple[dict, str | None]:
    """Adapte les arguments d'un modèle au schéma de l'outil : types convertis (\"3\" -> 3, \"oui\" -> True),
    arguments inconnus ignorés, arguments obligatoires vérifiés."""
    p = schema["function"]["parameters"]
    props, sortie = p.get("properties", {}), {}
    for k, v in args.items():
        if k not in props:
            continue
        t = props[k].get("type")
        try:
            if t == "integer" and not isinstance(v, bool):
                v = int(str(v).strip().lstrip("#"))
            elif t == "boolean" and isinstance(v, str):
                v = {"true": True, "oui": True, "vrai": True, "yes": True, "false": False, "non": False, "faux": False, "no": False}[v.strip().lower()]
            elif t == "array" and isinstance(v, str):
                v = json.loads(v) if v.strip().startswith("[") else [x.strip() for x in v.split(",") if x.strip()]
            elif t == "string" and not isinstance(v, str):
                v = str(v)
        except (ValueError, KeyError, json.JSONDecodeError):
            return args, f"argument « {k} » : valeur {v!r} incompatible avec le type {t}."
        if "enum" in props[k] and v not in props[k]["enum"]:
            return args, f"argument « {k} » : {v!r} n'est pas parmi {props[k]['enum']}."
        sortie[k] = v
    manquants = [r for r in p.get("required", []) if r not in sortie]
    if manquants:
        return args, f"argument(s) obligatoire(s) manquant(s) : {', '.join(manquants)}."
    return sortie, None


S = {"type": "string"}
B = {"type": "boolean"}
I = {"type": "integer"}


class Agent:
    nom = "agent"
    but = ""
    max_iterations = 6

    def __init__(self, ctx: Contexte, cerveau):
        self.ctx = ctx
        self.cerveau = cerveau
        self.vu = 0  # dernière version du dossier lue
        self._reportes = ([], [])  # messages et changements d'un tour interrompu, repris au tour suivant
        self.outils = {**self._outils_communs(), **self._outils_propres()}

    # ------------------------------------------------------------------ outils
    def _outils_communs(self):
        return {
            "lire_dossier": (lambda: self.ctx.dossier.resume(),
                             _schema("lire_dossier", "Lire le dossier de consultation partagé.")),
            "envoyer_message": (self._envoyer, _schema(
                "envoyer_message", "Envoyer un message direct à un autre agent, au médecin ou à une institution.",
                {"destinataire": {"type": "string", "enum": sorted(set(self.ctx.messagerie.boites) - {self.nom})},
                 "type": {"type": "string", "enum": sorted(TYPES)}, "contenu": S, "repond_a": I},
                ["destinataire", "type", "contenu"])),
            "consulter_base": (self._consulter, _schema(
                "consulter_base", "Chercher dans la base de connaissances (lois, normes, exemples mondiaux) ; "
                "renvoie les fiches avec leur citation exacte.", {"question": S, "nombre": I}, ["question"])),
            "chercher_pictogrammes": (self._chercher_pictos, _schema(
                "chercher_pictogrammes", "Trouver les pictogrammes qui expriment une idée (recherche hybride : mots-clés, "
                "écriture, sens). Utile quand un mot n'a pas de pictogramme : « essoufflement », « tête qui tourne ».",
                {"idee": S, "nombre": I}, ["idee"])),
            "terminer": (lambda raison="": f"Tour terminé : {raison}",
                         _schema("terminer", "Terminer ce tour quand il n'y a plus rien d'utile à faire.", {"raison": S})),
        }

    def _outils_propres(self):
        return {}

    def _chercher_pictos(self, idee, nombre=8):
        chercher = getattr(self.ctx.pictogrammeur, "chercher", None)
        if not chercher:
            return "Refusé : la base de pictogrammes (base_v2) n'est pas branchée."
        return [{"id": r["id"], "libelle": r["fr"], "categorie": r["categorie"], "pourquoi": r["pourquoi"]}
                for r in chercher(str(idee), max(1, min(int(nombre), 20)))]

    def _consulter(self, question, nombre=4):
        fiches = self.ctx.regles.base.chercher(question, k=int(nombre))
        if not self.ctx.corpus:
            return fiches
        # base_v2 branchée : on ajoute les extraits des textes officiels complets et des fiches de l'OMS, avec leur lien
        return {"fiches": fiches, "extraits": self.ctx.corpus.chercher(question, k=int(nombre))}

    IDENTIFIANTS = ("nom", "prenom", "identifiant", "emirates_id", "telephone", "adresse", "date_naissance", "dossier_medical")

    def _envoyer(self, destinataire, type, contenu, repond_a=None):
        if destinataire in INSTITUTIONS:
            if self.nom in ("assistant", "traducteur"):
                return ("Refusé : les agents de la consultation n'écrivent pas aux institutions (données du patient) ; "
                        "seuls le médecin et le juriste le peuvent.")
            for cle in self.IDENTIFIANTS:
                v = self.ctx.dossier.etat.get(cle)
                if v and str(v["valeur"]).strip() and str(v["valeur"]).lower() in str(contenu).lower():
                    return f"Refusé : le message contient un identifiant du patient ({cle}) ; passer par une demande de données contrôlée."
        return self.ctx.messagerie.envoyer(self.nom, destinataire, type, contenu, repond_a)

    def executer(self, outil: str, args: dict):
        if outil not in self.outils:
            res = f"Refusé : l'outil « {outil} » n'appartient pas à l'agent {self.nom}."
        else:
            args, erreur = conformer(self.outils[outil][1], args if isinstance(args, dict) else {})
            if erreur:
                res = f"Refusé : {erreur}"
            else:
                garde = self.garde_fou_outil(outil, args)
                try:
                    res = garde or self.outils[outil][0](**args)
                except (TypeError, ValueError) as e:
                    res = f"Refusé : arguments invalides pour {outil} ({e})."
        self.ctx.journal.ajouter(self.nom, "action", {"outil": outil, "arguments": args, "resultat": res})
        if self.ctx.verbeux and outil not in ("lire_dossier", "terminer"):
            print(f"      ↳ {outil}({_court(args)}) → {_court(res)}")
        return res

    def garde_fou_outil(self, outil: str, args: dict) -> str | None:
        """Contrôle déterministe d'une action avant qu'elle ne s'exécute (surchargé par les agents) : None = permis."""
        return None

    # ------------------------------------------------------------------ boucle
    def tour(self) -> bool:
        """Une activation : l'agent regarde ses messages et ce qui a changé, puis décide."""
        nouveaux = self.ctx.messagerie.lire(self.nom)
        self._recevoir(nouveaux)
        msgs = self._reportes[0] + nouveaux
        changements = self._reportes[1] + [c for c in self.ctx.dossier.changements_depuis(self.vu) if c["auteur"] != self.nom]
        self._reportes = ([], [])
        self.vu = self.ctx.dossier.version
        if not msgs and not changements:
            return False
        debut = self.vu
        try:
            agi = self._decider(msgs, changements)
        except Interrompu:
            self._reportes = (msgs, changements)      # rien n'a été fait : tout est repris au prochain tour
            self.ctx.journal.ajouter(self.nom, "reflexion_reportee", {"raison": "un humain attend : son action passe d'abord"})
            return False
        if self.ctx.attente_modele:
            # Pendant que le modèle répondait, le médecin ou le patient a pu agir : ces changements restent à lire.
            pendant = [c for c in self.ctx.dossier.changements_depuis(debut) if c["auteur"] in ("medecin", "patient")]
            if pendant:
                self._reportes = ([], pendant)
        self.vu = self.ctx.dossier.version
        return agi

    def a_du_travail_en_attente(self) -> bool:
        return bool(self._reportes[0] or self._reportes[1] or self.ctx.messagerie.boites.get(self.nom))

    def _politique(self, msgs, changements) -> bool:
        agi = False
        for raisonnement, outil, args in self.politique_simulee(msgs, changements):
            self._penser(raisonnement)
            self.executer(outil, args)
            agi = True
        return agi

    def _decider(self, msgs, changements) -> bool:
        if isinstance(self.cerveau, CerveauSimule):
            return self._politique(msgs, changements)
        cle = getattr(self.cerveau, "modele", self.cerveau.nom)
        if self.ctx.echecs_modele.get(cle, 0) >= self.ctx.seuil_echecs:      # disjoncteur : on n'insiste pas…
            if not self.ctx.repli_sans_ia:
                raise ModeleHorsService(f"modèle {cle} hors service ({self.ctx.echecs_modele[cle]} échecs)")
            depuis = self.ctx.disjoncteur_depuis.setdefault(cle, time.time())
            if time.time() - depuis < self.ctx.reessai_s:                    # … sauf de temps en temps (demi-ouvert)
                if not getattr(self, "_repli_signale", False):
                    self.ctx.journal.ajouter(self.nom, "degradation", {"erreur": "modèle déclaré hors service",
                                                                      "message": (self.ctx.etat_modele.get(cle) or {}).get("message"),
                                                                      "repli": "politique écrite à la main (veille clinique active)"})
                    self._repli_signale = True     # une seule ligne au journal, pas une par tour
                return self._politique(msgs, changements)
            self.ctx.journal.ajouter(self.nom, "nouvel_essai_modele", {"modele": cle})
            self.ctx.echecs_modele[cle] = self.ctx.seuil_echecs - 1         # un échec de plus le referme aussitôt
        try:
            agi = self._boucle_llm(msgs, changements)
            if self.ctx.echecs_modele.get(cle):
                self.ctx.journal.ajouter(self.nom, "modele_retabli", {"modele": cle})
            self.ctx.echecs_modele[cle] = 0
            self.ctx.disjoncteur_depuis.pop(cle, None)
            self.ctx.etat_modele[cle] = {"disponible": True, "message": "en ligne"}
            self._repli_signale = False
            return agi
        except Interrompu:
            raise
        except Exception as e:  # serveur arrêté, délai dépassé, réponse illisible…
            self.ctx.echecs_modele[cle] = self.ctx.echecs_modele.get(cle, 0) + 1
            if self.ctx.echecs_modele[cle] >= self.ctx.seuil_echecs:
                self.ctx.disjoncteur_depuis[cle] = time.time()
                self.ctx.etat_modele[cle] = {"disponible": False, "message": str(e)[:300]}
            if not self.ctx.repli_sans_ia:
                raise
            self.ctx.journal.ajouter(self.nom, "degradation", {"erreur": repr(e)[:300], "repli": "politique écrite à la main"})
            if self.ctx.verbeux:
                print(f"  ⚠ [{self.nom}] modèle indisponible ({e.__class__.__name__}) : repli sur la politique écrite à la main")
            return self._politique(msgs, changements)

    def _penser(self, texte: str):
        if not texte:
            return
        self.ctx.journal.ajouter(self.nom, "raisonnement", texte)
        if self.ctx.verbeux:
            print(f"  [{self.nom}] {texte}")

    PAUSE_AVANT_NOUVEL_ESSAI = 2.0
    LECTURE_SEULE = {"lire_dossier", "consulter_base", "chercher_pictogrammes", "traduire", "obligations_etat_patient", "lire_tableau_crise", "terminer"}

    def _boucle_llm(self, msgs, changements) -> bool:
        schemas = [o[1] for o in self.outils.values()]
        nouveaux = "\n".join(f"- #{m.id} {m}" for m in msgs) or "(aucun)"
        chg = "\n".join(f"- {c['type']} par {c['auteur']} : {_court(c['contenu'], 200)}" for c in changements) or "(aucun)"
        messages = [
            {"role": "system", "content": self.but + "\n\nRÈGLES D'ACTION : agis uniquement par tes outils ; un appel = une "
                                                     "action ; n'invente aucun identifiant ; quand tu as fini, appelle « terminer ». "
                                                     "SOIS RAPIDE : le dossier actuel t'est déjà donné (inutile de le relire) ; "
                                                     "fais tous tes appels dans UNE SEULE réponse et ajoutes-y « terminer » si "
                                                     "tu n'as pas besoin de lire leurs résultats ; s'il n'y a rien d'utile à "
                                                     "faire, appelle seulement « terminer »."
                                                     + ({"en": "\nLANGUE : le médecin lit en ANGLAIS : écris tous tes messages, "
                                                               "suggestions et questions pour lui en anglais.",
                                                         "ar": "\nLANGUE : le médecin lit en ARABE : écris tous tes messages, "
                                                               "suggestions et questions pour lui en arabe."}.get(self.ctx.langue_medecin, ""))},
            {"role": "user", "content": f"NOUVEAUX MESSAGES POUR TOI :\n{nouveaux}\n\n{self._contexte_llm(chg)}\n\n"
                                        "Décide toi-même quoi faire avec tes outils. Explique brièvement ton raisonnement, "
                                        "puis appelle les outils utiles. Appelle « terminer » quand tu as fini."},
        ]
        agi, vus, n_appel = False, {}, 0
        interrompre = getattr(self.ctx, "interrompre", None)
        for iteration in range(self.max_iterations):
            if interrompre and interrompre():     # un clic attend : il passe avant la suite de la réflexion
                if iteration == 0:
                    raise Interrompu()
                self.ctx.journal.ajouter(self.nom, "reflexion_abregee", {"raison": "un humain attend", "apres_appels": iteration})
                break
            debut = time.time()
            with (self.ctx.attente_modele or nullcontext)():      # les clics sont traités pendant que le modèle répond
                try:
                    rep = self.cerveau.chat(messages, schemas)
                except Exception:            # une seconde chance (délai ponctuel), puis l'erreur remonte
                    time.sleep(self.PAUSE_AVANT_NOUVEL_ESSAI)
                    rep = self.cerveau.chat(messages, schemas)
            duree = round(time.time() - debut, 2)
            self.ctx.derniere_duree_modele = duree
            self.ctx.journal.ajouter(self.nom, "appel_modele", {"duree_s": duree, "iteration": iteration + 1})
            contenu, reflexion = separer_reflexion(rep.get("content") or "")
            reflexion = "\n".join(x for x in (rep.get("reflexion") or "", reflexion) if x)
            appels = list(rep.get("tool_calls") or [])
            if reflexion:
                self.ctx.journal.ajouter(self.nom, "reflexion_modele", reflexion[:4000])
            if not appels and contenu:
                appels = appels_dans_le_texte(contenu, set(self.outils))
                if appels:
                    self.ctx.journal.ajouter(self.nom, "appel_extrait_du_texte", [a[0] for a in appels])
            if contenu:
                self._penser(contenu)
            if not appels:
                break
            ids = []
            for nom, args in appels:
                n_appel += 1
                ids.append(f"a{n_appel}")
            messages.append({"role": "assistant", "content": contenu,
                             "tool_calls": [{"id": i, "function": {"name": n, "arguments": a}} for i, (n, a) in zip(ids, appels)]})
            fin = False
            for i, (nom, args) in zip(ids, appels):
                cle = (nom, json.dumps(args, sort_keys=True, ensure_ascii=False, default=str))
                vus[cle] = vus.get(cle, 0) + 1
                if vus[cle] >= 3:
                    res = "Refusé : cet appel identique a déjà été fait deux fois ; passe à autre chose ou termine."
                    self.ctx.journal.ajouter(self.nom, "boucle_detectee", {"outil": nom, "arguments": args})
                    fin = True
                else:
                    self._par_modele = True       # garde-fous propres aux actions décidées par le modèle en ligne
                    try:
                        res = self.executer(nom, args)
                    finally:
                        self._par_modele = False
                    agi = agi or (nom not in self.LECTURE_SEULE and not str(res).startswith("Refusé"))
                messages.append({"role": "tool", "tool_call_id": i, "name": nom, "content": _court(res, 3000)})
                fin = fin or nom == "terminer"
            if fin:
                break
        return agi

    def _recevoir(self, msgs) -> None:
        """Point d'accroche : un agent peut garder trace de certains messages reçus."""

    def _contexte_llm(self, chg: str) -> str:
        return f"CHANGEMENTS DANS LE DOSSIER :\n{chg}\n\nDOSSIER ACTUEL :\n{self.ctx.dossier.resume()}"

    def politique_simulee(self, msgs, changements):
        return iter(())

    # ------------------------------------------------------------------ utilitaires
    def val(self, cle):
        v = self.ctx.dossier.etat.get(cle)
        return None if v is None else v["valeur"]


UNITES_TEMPS = {"heure": ("heure", "heures"), "heures": ("heure", "heures"), "jour": ("jour", "jours"), "jours": ("jour", "jours"),
                "semaine": ("semaine", "semaines"), "semaines": ("semaine", "semaines"), "mois": ("mois", "mois"),
                "an": ("an", "ans"), "ans": ("an", "ans"), "annee": ("an", "ans"), "annees": ("an", "ans"), "an (annee)": ("an", "ans")}


def _norm_libelle(t: str) -> str:
    return normaliser_simple(t or "")


CHAMPS_LISIBLES = {"allergies": "allergies", "traitements_en_cours": "traitements en cours", "grossesse": "grossesse",
                   "age": "âge", "sexe": "sexe", "poids": "poids", "consentement_traitement": "accord du patient",
                   "mode_consultation": "mode de consultation", "antecedents": "antécédents"}
QUESTIONS_CHAMPS = {"allergies": "Êtes-vous allergique à un médicament ?", "traitements_en_cours": "Prenez-vous des médicaments en ce moment ?",
                    "grossesse": "Êtes-vous enceinte ?"}


def normaliser_simple(t: str) -> str:
    return _normaliser_texte(t).strip()


def analyser_medicaments(texte: str, medicaments: dict) -> list[str]:
    from .surete import analyser_message
    return analyser_message(texte, medicaments).get("medicaments") or []


def _court(x, n=110):
    s = str(x).replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


# ====================================================================== AGENT 3
class Assistant(Agent):
    nom = "assistant"
    but = """Tu es l'AGENT 3, l'assistant du médecin, dans MEDIMCOM IA (consultation en pictogrammes pour patients sourds).
TON BUT : que le médecin dispose d'un état du patient fiable et complet, et de suggestions utiles.
TU DÉCIDES SEUL : quels faits ajouter à l'état du patient, ce qui manque (grossesse, allergies, traitements en cours,
âge, maladies des reins ou du foie), quand alerter (signes d'urgence en priorité), quoi suggérer au médecin, et quand
retirer une suggestion devenue inutile ou dangereuse.
TU COLLABORES : tu fais poser des questions au patient (outil demander_question_patient, transmis au traducteur et
validé par le médecin) ; tu peux consulter la base (consulter_base) et le juriste avant de suggérer un traitement ;
tu réponds à ses demandes.
TES LIMITES : tu ne parles jamais au patient ; tu ne poses pas de diagnostic certain (tu parles d'hypothèses) ;
pas de suggestion de traitement sans source (identifiant de fiche) ni si l'état du patient est incomplet ;
le médecin valide ou ignore.
TU SURVEILLES EN TEMPS RÉEL chaque prescription au regard de la fiche du patient (âge, sexe, grossesse, poids,
allergies, maladies, traitements en cours, dose et rythme) : si elle est risquée, dis-le au médecin et propose une
alternative SOURCÉE (outil suggerer_au_medecin, type traitement_alternatif). Une veille automatique le fait déjà
pour les verdicts du juriste : complète-la (interactions, cause du symptôme, examen à faire), ne la répète pas.
TES MESSAGES AU MÉDECIN sont lus pendant la consultation : CLAIRS ET COURTS. Première phrase = ce qu'il doit
savoir ou faire (moins de 20 mots) ; au plus deux phrases ensuite pour le pourquoi. Pas de répétition d'une alerte
déjà envoyée. Le juriste bloque lui-même, avant toute validation, les messages dangereux (incitation à se faire du
mal, injures) et les consignes de médicament sans ordonnance : ne répète pas son blocage ; ajoute seulement ce qui
est utile cliniquement. Numéro d'urgence : 998 (ambulance) aux Émirats ; dans un autre pays, n'en cite aucun.
NE REDEMANDE JAMAIS une information CONFIRMÉE dans l'état du patient (marquée confirmé) et ne la remplace pas. Ne parle
pas de grossesse à un homme, ni à une patiente dont la non-grossesse est confirmée.
PROPOSE DES TRAITEMENTS : à partir des symptômes, de la fiche et des documents du patient, propose au médecin une piste
de traitement SOURCÉE (outil suggerer_au_medecin, type traitement), en indiquant médicament, dose et rythme ; le juriste la
contrôle pour ce patient et le médecin décide."""

    def _outils_propres(self):
        d = self.ctx.dossier
        return {
            "mettre_a_jour_etat": (self._maj_etat,
                                   _schema("mettre_a_jour_etat", "Ajouter ou modifier un fait de l'état du patient. "
                                           "« confirme » n'est accepté que si le fait figure dans un échange confirmé (patient, traducteur, médecin).",
                                           {"cle": S, "valeur": {"type": ["string", "number", "boolean"]}, "source": S, "confirme": B},
                                           ["cle", "valeur", "source"])),
            "demander_question_patient": (lambda question, raison, cle=None: d.ajouter_question(self.nom, question, raison, cle),
                                          _schema("demander_question_patient",
                                                  "Faire poser une question au patient (traduite en pictogrammes, validée par le médecin).",
                                                  {"question": S, "raison": S, "cle": S}, ["question", "raison"])),
            "suggerer_au_medecin": (self._suggerer,
                                    _schema("suggerer_au_medecin", "Proposer une suggestion au médecin (il valide ou ignore). Pour un "
                                            "traitement, joindre « prescription » (médicament, dose, rythme) : le médecin peut "
                                            "préremplir l'ordonnance, que le juriste contrôle.",
                                            {"type": {"type": "string", "enum": ["alerte_urgence", "question_manquante", "reponse", "traitement", "traitement_alternatif"]},
                                             "texte": S, "raison": S, "source": S,
                                             "prescription": {"type": "object", "properties": {"medicament": S, "dose": S, "posologie": S}}},
                                            ["type", "texte", "raison", "source"])),
            "retirer_suggestion": (lambda id, raison: d.retirer_suggestion(self.nom, id, raison),
                                   _schema("retirer_suggestion", "Retirer une de tes suggestions devenue inutile ou dangereuse.",
                                           {"id": I, "raison": S}, ["id", "raison"])),
        }

    def _suggerer(self, type, texte, raison, source, prescription=None):
        res = self.ctx.dossier.ajouter_suggestion(self.nom, type, texte, raison, source)
        if isinstance(prescription, dict) and prescription.get("medicament"):
            s = self.ctx.dossier.suggestions[max(self.ctx.dossier.suggestions)]
            s["prescription"] = {k: str(prescription.get(k) or "")[:120] for k in ("medicament", "dose", "posologie")}
        return res

    # Piste de traitement symptomatique, en premier choix puis en alternative ; chacune est contrôlée par le moteur du
    # juriste pour CE patient (âge, grossesse, allergies, maladies) avant d'être proposée. Doses de l'adulte seulement.
    PISTES_SYMPTOMES = [
        ("paracetamol", "500 mg", "toutes les 6 heures si besoin, 4 fois par jour au maximum"),
        ("ibuprofene", "400 mg", "toutes les 8 heures au cours d'un repas, 3 fois par jour au maximum"),
    ]

    def _piste_traitement(self):
        """Douleur ou fièvre et aucune prescription : piste de traitement sourcée, contrôlée par le juriste."""
        d = self.ctx.dossier
        if not (self.val("douleur") is True or self.val("fievre") is True):
            return
        if any(x.get("type") == "prescription" and x["statut"] != "annulee" for x in d.decisions.values()):
            return
        cle = ("piste", d.etat_version)
        if cle in self._veilles or any(s["type"] == "traitement" and s["statut"] == "proposee_au_medecin" and s["auteur"] == self.nom
                                       for s in d.suggestions.values()):
            return
        self._veilles.add(cle)
        age = self.val("age")
        ecartes = []
        for nom, dose, rythme in self.PISTES_SYMPTOMES:
            r = self.ctx.regles.risques_medicament(nom, d.etat)
            motifs = [c for c in r["constats"] if c["niveau"] in ("BLOQUE", "A_REVOIR")]
            if motifs:
                ecartes.append(f"{nom} écarté : " + motifs[0]["detail"].split(". ")[0].rstrip("."))
                continue
            fiches = r.get("fiches_dose_max") or []
            source = " ; ".join(self.ctx.regles.base.citer_court(f) for f in fiches) or "-"
            enfant = isinstance(age, (int, float)) and age < 12
            symptome = "douleur" if self.val("douleur") is True else "fièvre"
            texte = (f"Piste de traitement pour la {symptome} : {nom}"
                     + (f" {dose}, {rythme}" if not enfant else " (enfant : dose selon le poids, à fixer par vous)")
                     + (f" ; sans dépasser {r['dose_max_mg']} mg par jour chez l'adulte" if r.get("dose_max_mg") and not enfant else "")
                     + ".\nContrôlé par le moteur du juriste pour ce patient : aucune contre-indication connue."
                     + ("\n" + " ; ".join(ecartes) + "." if ecartes else "")
                     + "\nVous décidez : « Préremplir l'ordonnance » pour l'ajuster et la prescrire.")
            yield (f"Le patient signale une {symptome} et rien n'est prescrit : je propose une piste sourcée, contrôlée pour lui.",
                   "suggerer_au_medecin", {"type": "traitement", "texte": texte, "raison": self._raison_fiche(), "source": source,
                                           "prescription": {"medicament": nom, "dose": "" if enfant else dose, "posologie": "" if enfant else rythme}})
            return
        if ecartes:
            yield ("Aucun antalgique simple n'est sans risque pour ce patient : je le dis au médecin.", "suggerer_au_medecin",
                   {"type": "traitement", "texte": "Aucun antalgique simple sans contre-indication pour ce patient.\n• " + "\n• ".join(ecartes)
                    + ".\nAvis médical ; traitement non médicamenteux à envisager.", "raison": self._raison_fiche(), "source": "-"})

    def veille_clinique(self):
        """Veille DÉTERMINISTE (sans modèle, instantanée), indépendante de Grok : l'assistant suit TOUT ce qui passe et
        prévient le médecin, en clair, avec une alternative sourcée et contrôlée par le moteur du juriste :
          1. une prescription jugée risquée par le juriste ;
          2. un message au patient qui conseille un médicament risqué pour CE patient, ou en quantité imprécise ;
          3. un médicament que le patient déclare prendre (réponse en pictogrammes) et qui est risqué pour lui ;
          4. un traitement en cours décrit sans nom de médicament (« contre le diabète ») : impossible de vérifier
             les interactions.
        Le modèle (s'il est branché) peut compléter, jamais retarder."""
        if not hasattr(self, "_veilles"):
            self._veilles = set()
        d = self.ctx.dossier
        derniers = {}
        for v in d.verdicts:
            if v.get("objet") == "prescription" and v.get("decision_id") is not None:
                derniers[v["decision_id"]] = v
        for did, v in derniers.items():
            dec = d.decisions.get(did) or {}
            cle = (did, v["verdict"], d.etat_version)
            if dec.get("statut") not in ("A_REVOIR", "BLOQUE", "PREUVES_INSUFFISANTES") or cle in self._veilles:
                continue
            self._veilles.add(cle)
            med = dec.get("medicament", "?")
            if v["verdict"] == "PREUVES_INSUFFISANTES":
                manquants = v.get("informations_manquantes") or []
                manque = ", ".join(CHAMPS_LISIBLES.get(m, m.replace("_", " ")) for m in manquants) or "des informations"
                a_demander = [m for m in manquants if m in QUESTIONS_CHAMPS]
                texte = (f"Avant de prescrire {med}, il manque : {manque}.\n"
                         + ("J'ai préparé la question pour le patient (onglet Assistant, « Questions à poser ») ; vous pouvez aussi remplir la fiche."
                            if a_demander else "Complétez la fiche ; je revérifie aussitôt."))
                raison = f"Le juriste ne peut pas conclure sans ces informations (prescription #{did})."
                for m in a_demander:          # l'assistant obtient l'information lui-même, auprès du patient
                    yield (f"Information manquante ({CHAMPS_LISIBLES.get(m, m)}) : je fais poser la question au patient.",
                           "demander_question_patient", {"question": QUESTIONS_CHAMPS[m], "raison": f"Nécessaire avant de prescrire {med}.", "cle": m})
            else:
                motifs = [c for c in v.get("constats", []) if c["niveau"] in ("BLOQUE", "A_REVOIR")]
                tete = f"Ne pas prescrire {med} en l'état" if v["verdict"] == "BLOQUE" else f"{med} : à revoir avant toute prescription"
                texte = self._conseil(tete, motifs, (v.get("alternatives") or [None])[0], dec.get("prescripteur"), dec.get("mode"), did)
                raison = self._raison_fiche()
            sources = " ; ".join(dict.fromkeys(c["reference_courte"] for c in v.get("constats", [])
                                               if c["niveau"] in ("BLOQUE", "A_REVOIR", "PREUVES_INSUFFISANTES") and c["reference_courte"] != "-")) or "analyse du juriste"
            if any(s["statut"] == "proposee_au_medecin" and s["texte"] == texte for s in d.suggestions.values()):
                continue                       # même conseil déjà affiché : pas de doublon
            yield (f"Prescription #{did} ({med}) jugée « {v['verdict']} » : je préviens le médecin tout de suite et je propose une alternative sourcée.",
                   "suggerer_au_medecin", {"type": "traitement_alternatif" if v["verdict"] != "PREUVES_INSUFFISANTES" else "question_manquante",
                                           "texte": texte, "raison": raison, "source": sources})
        # 2. Messages au patient qui conseillent un médicament (bloqués par le juriste : l'assistant dit QUOI faire à la place)
        for dec in list(d.decisions.values()):
            pc = dec.get("precontrole") or {}
            if dec.get("type") != "envoi_patient" or not pc.get("constats"):
                continue
            cliniques = [c for c in pc["constats"] if str(c.get("regle", "")).startswith(("contre_indication", "allergie", "SURETE-DOSE"))]
            cle = ("message", dec["id"], pc.get("etat_version"))
            if not cliniques or cle in self._veilles:
                continue
            self._veilles.add(cle)
            meds = (pc.get("analyse") or {}).get("medicaments") or ["ce médicament"]
            tete = (f"Message #{dec['id']} : ne pas conseiller {', '.join(meds)} à ce patient"
                    if any(c["regle"].startswith(("contre_indication", "allergie")) for c in cliniques)
                    else f"Message #{dec['id']} : préciser la dose de {', '.join(meds)}")
            texte = self._conseil(tete, cliniques, (pc.get("alternatives") or [None])[0], None, None, dec["id"])
            texte += "\nPour traiter : onglet Ordonnance (médicament, dose en mg, rythme) ; le juriste et moi la vérifions avant le patient."
            yield (f"Le message #{dec['id']} conseille {', '.join(meds)} : risqué pour ce patient. Je dis au médecin pourquoi et quoi faire.",
                   "suggerer_au_medecin", {"type": "traitement_alternatif", "texte": texte, "raison": self._raison_fiche(),
                                           "source": " ; ".join(dict.fromkeys(c["reference_courte"] for c in cliniques if c.get("reference_courte"))) or "analyse du juriste"})
        # 2 bis. Message contraire à l'éthique : le juriste le bloque ; je dis au médecin la pratique attendue
        for dec in list(d.decisions.values()):
            pc = dec.get("precontrole") or {}
            eth = [c for c in pc.get("constats", []) if str(c.get("regle", "")).startswith("ETHIQUE-")]
            if dec.get("type") != "envoi_patient" or not eth or ("ethique", dec["id"], pc.get("texte")) in self._veilles:
                continue
            self._veilles.add(("ethique", dec["id"], pc.get("texte")))
            texte = (f"Message #{dec['id']} : je ne peux pas vous suivre sur ce point.\nPourquoi :\n• "
                     + "\n• ".join(dict.fromkeys(c["detail"].replace("Message contraire à l'éthique médicale : ", "").split(". Il ne")[0] for c in eth))
                     + ".\nCe qui est possible :\n• " + "\n• ".join(dict.fromkeys(c["piste"] for c in eth if c.get("piste"))))
            yield (f"Le message #{dec['id']} est contraire à l'éthique médicale : je le dis au médecin, avec la pratique attendue.",
                   "suggerer_au_medecin", {"type": "alerte_urgence", "texte": texte,
                                           "raison": "Lecture du message par le juriste et l'assistant.",
                                           "source": " ; ".join(dict.fromkeys(c["reference_courte"] for c in eth))})
        # 3. Médicaments que le patient déclare prendre
        declares = str(self.val("medicaments_declares") or "")
        for brut in [m.strip() for m in declares.split(",") if m.strip()]:
            r = self.ctx.regles.risques_medicament(brut, d.etat)
            motifs = [c for c in r["constats"] if c["niveau"] in ("BLOQUE", "A_REVOIR")]
            cle = ("declare", r["medicament"], d.etat_version)
            if not motifs or cle in self._veilles:
                continue
            self._veilles.add(cle)
            texte = self._conseil(f"Le patient dit prendre {brut} : risqué pour lui", motifs, (r["alternatives"] or [None])[0], None, None, None)
            texte += "\nÀ vérifier avec lui : dose, depuis quand, qui l'a prescrit."
            yield (f"Le patient déclare prendre {brut}, risqué au vu de sa fiche : j'alerte le médecin.", "suggerer_au_medecin",
                   {"type": "alerte_urgence" if any(c["niveau"] == "BLOQUE" for c in motifs) else "traitement_alternatif",
                    "texte": texte, "raison": self._raison_fiche(),
                    "source": " ; ".join(dict.fromkeys(c["reference_courte"] for c in motifs if c.get("reference_courte"))) or "-"})
        # 0. Conseils périmés : urgence prise en charge, prescription corrigée, fiche complétée -> je retire mes suggestions
        if self.val("urgence") is False:
            for sg in list(d.suggestions.values()):
                if sg["auteur"] == self.nom and sg["statut"] == "proposee_au_medecin" and sg["type"] == "alerte_urgence" \
                        and sg["raison"].startswith("urgence = vrai"):
                    yield ("L'urgence est prise en charge par le médecin : je retire mon alerte.", "retirer_suggestion",
                           {"id": sg["id"], "raison": "urgence prise en charge"})
        for sg in list(d.suggestions.values()):
            m = re.search(r"\(prescription #(\d+)\)", sg.get("raison", ""))
            if sg["auteur"] == self.nom and sg["statut"] == "proposee_au_medecin" and m:
                dec = d.decisions.get(int(m.group(1))) or {}
                if dec.get("statut") not in ("PREUVES_INSUFFISANTES",):
                    yield (f"La prescription #{dec.get('id')} n'attend plus d'information : je retire ma suggestion.",
                           "retirer_suggestion", {"id": sg["id"], "raison": "information obtenue ou prescription modifiée"})
        # 7. Le patient ne comprend pas un message : je conseille le médecin
        for i, e in enumerate(d.fil):
            if e.get("incompris") and ("incompris", i) not in self._veilles:
                self._veilles.add(("incompris", i))
                sujet = f"« {e.get('en_reponse_a')} »" if e.get("en_reponse_a") else "votre dernier message"
                yield ("Le patient signale qu'il ne comprend pas : je propose au médecin des façons de reformuler.",
                       "suggerer_au_medecin", {"type": "question_manquante",
                                               "texte": f"Le patient ne comprend pas {sujet}.\nReformulez : une seule idée par message, des mots "
                                                        "simples et concrets (« ventre », « mal », « oui / non ») ; montrez du doigt ; "
                                                        "si cela ne suffit pas, faites appel à un interprète en langue des signes.",
                                               "raison": "Réponse du patient : « je ne comprends pas ».",
                                               "source": f"DHATH-12.4 — {self.ctx.regles.base.citer_court('DHATH-12.4')}" if self.ctx.regles.pays == "AE" else "-"})
        # 8. Le patient refuse l'aide de l'IA : son choix est respecté
        if self.val("informe_usage_ia") is False and ("refus_ia",) not in self._veilles:
            self._veilles.add(("refus_ia",))
            yield ("Le patient refuse que l'IA aide à la consultation : je le dis au médecin.", "suggerer_au_medecin",
                   {"type": "alerte_urgence",
                    "texte": "Le patient a répondu NON à l'aide de l'IA.\nRespectez son choix : poursuivez avec un interprète en langue des "
                             "signes ou un autre moyen qu'il accepte. Ce refus est enregistré au journal.",
                    "raison": "Réponse du patient au message d'accueil.",
                    "source": f"DHA21-4.4 — {self.ctx.regles.base.citer_court('DHA21-4.4')}" if self.ctx.regles.pays == "AE" else "-"})
        # 9. Le patient dit OUI (allergies, traitements) sans dire lesquels : le médecin précise
        for cle, nom in (("allergies", "des allergies"), ("traitements_en_cours", "des traitements en cours")):
            if "préciser" in str(self.val(cle) or "") and ("preciser", cle) not in self._veilles:
                self._veilles.add(("preciser", cle))
                yield (f"Le patient a {nom} sans dire lesquels : le médecin doit préciser.", "suggerer_au_medecin",
                       {"type": "question_manquante",
                        "texte": f"Le patient dit avoir {nom}. Demandez lesquels (montrez-lui les pictogrammes de médicaments, ou "
                                 "son ordonnance, sa boîte) et écrivez-les dans la fiche.",
                        "raison": "Réponse OUI à la question, sans détail.", "source": "-"})
        # 5. Le patient exprime une idée de mort POUR LUI-MÊME (pas un récit sur un tiers) : alerte immédiate
        from .lecture import risque_suicidaire
        for i, e in enumerate(d.fil):
            texte_patient = e.get("interpretation") if e.get("pictogrammes") else None
            r = risque_suicidaire(texte_patient) if texte_patient else None
            if r and r["niveau"] == "alerte" and ("suicide", i) not in self._veilles:
                self._veilles.add(("suicide", i))
                urgence = "998 (ambulance)" if self.ctx.regles.pays == "AE" else "les secours"
                yield ("Le patient semble exprimer une idée de mort pour lui-même : j'alerte le médecin en priorité.",
                       "suggerer_au_medecin", {"type": "alerte_urgence",
                                               "texte": f"Le patient semble parler de mourir (« {texte_patient} »). Évaluez le risque suicidaire maintenant.\n"
                                                        f"Restez avec lui, demandez-lui directement s'il pense à se faire du mal ; si le danger est immédiat : {urgence}.",
                                               "raison": "Lecture de la réponse du patient : " + ", ".join(r["indices"]) + ".",
                                               "source": "Lecture du contexte par MEDIMCOM IA"})
        # 6. Un message évoque (récit) un médicament pris par le patient lui-même, risqué pour lui : à vérifier
        for dec in list(d.decisions.values()):
            a = ((dec.get("precontrole") or {}).get("analyse") or {}) if dec.get("type") == "envoi_patient" else {}
            ctx_lu = a.get("contexte") or {}
            if not a.get("evocation") or ctx_lu.get("intention") != "recit" or "il s'agit d'une autre personne" in ctx_lu.get("indices", []):
                continue
            for brut in a.get("medicaments") or []:
                r = self.ctx.regles.risques_medicament(brut, d.etat)
                motifs = [c for c in r["constats"] if c["niveau"] in ("BLOQUE", "A_REVOIR")]
                cle = ("recit", dec["id"], r["medicament"], d.etat_version)
                if motifs and cle not in self._veilles:
                    self._veilles.add(cle)
                    texte = self._conseil(f"Votre message #{dec['id']} évoque une prise de {r['medicament']} par le patient : à vérifier",
                                          motifs, (r["alternatives"] or [None])[0], None, None, dec["id"])
                    yield (f"Le message #{dec['id']} est un récit (pas une consigne), mais il dit que le patient a pris {r['medicament']}, "
                           "risqué pour lui : je le signale.", "suggerer_au_medecin",
                           {"type": "traitement_alternatif", "texte": texte, "raison": self._raison_fiche(),
                            "source": " ; ".join(dict.fromkeys(c["reference_courte"] for c in motifs)) or "-"})
        # 10. Douleur ou fièvre sans traitement : piste de traitement sourcée et contrôlée
        yield from self._piste_traitement()
        # 4. Traitement en cours sans nom de médicament : impossible de vérifier les interactions
        tt = self.val("traitements_en_cours")
        if isinstance(tt, str) and tt.strip() and normaliser_simple(tt) not in ("aucun", "non", "rien", "neant", "none"):
            connus = analyser_medicaments(tt, self.ctx.regles.kb.get("medicaments", {}))
            cle = ("traitement_vague", tt)
            if not connus and cle not in self._veilles:
                self._veilles.add(cle)
                yield (f"Traitement en cours « {tt} » : aucun médicament nommé. Je demande au médecin de préciser.",
                       "suggerer_au_medecin", {"type": "question_manquante",
                                               "texte": f"Préciser le traitement en cours (« {tt} ») : nom du médicament et dose.\n"
                                                        "Sans le nom, je ne peux pas vérifier les interactions ni les contre-indications.",
                                               "raison": "Traitement en cours renseigné sans nom de médicament.",
                                               "source": f"ML16-A4-2 — {self.ctx.regles.base.citer_court('ML16-A4-2')}" if self.ctx.regles.pays == "AE" else "-"})

    def _raison_fiche(self) -> str:
        d = self.ctx.dossier
        noms = {"age": "âge", "sexe": "sexe", "grossesse": "enceinte", "poids": "poids (kg)", "allergies": "allergies",
                "antecedents": "antécédents", "medicaments_declares": "médicaments déclarés"}
        lisible = lambda v: "oui" if v is True else "non" if v is False else v  # noqa: E731
        return "Fiche du patient prise en compte : " + ", ".join(
            f"{noms[k]} : {lisible(x['valeur'])}" for k, x in d.etat.items() if k in noms) + "."

    def _conseil(self, tete, motifs, alt, prescripteur, mode, ref) -> str:
        """Message clair : quoi (1re ligne), pourquoi (puces), alternative contrôlée par le moteur du juriste."""
        d = self.ctx.dossier
        pourquoi = list(dict.fromkeys(c["detail"].replace("Pour ce patient : ", "").split(". ")[0].rstrip(".") for c in motifs))
        texte = f"{tete}.\nPourquoi :\n• " + "\n• ".join(pourquoi) + "."
        if alt:
            # L'alternative est d'abord soumise au moteur de règles du juriste, pour CE patient (contre-indications,
            # allergies) : on ne propose jamais une alternative qui serait elle-même à revoir sans le dire.
            avis = self.ctx.regles.verifier_prescription(
                {"medicament": alt["medicament"], "prescripteur": prescripteur, "auteur": "medecin", "mode": mode}, d.etat)
            risques = [c for c in avis["constats"] if c["niveau"] in ("BLOQUE", "A_REVOIR")
                       and c["regle"].startswith(("contre_indication", "allergie"))]
            self.ctx.journal.ajouter(self.nom, "avis_juriste_alternative",
                                     {"pour": ref, "alternative": alt["medicament"],
                                      "risques": [c["regle"] for c in risques] or "aucune contre-indication connue"})
            if risques:
                texte += (f"\nL'alternative {alt['medicament']} est elle aussi à vérifier : "
                          + " ; ".join(c["detail"].split(". ")[0] for c in risques) + ".")
            else:
                maxi = self.ctx.regles.risques_medicament(alt["medicament"], d.etat).get("dose_max_mg")
                texte += (f"\nAlternative à discuter : {alt['medicament']} (source : {alt['source']}) ; contrôlée par le "
                          "moteur du juriste : aucune contre-indication connue pour ce patient. Dose à adapter à l'âge et au poids"
                          + (f" (maximum {maxi} mg par jour chez l'adulte)." if maxi else "."))
        return texte

    GROSSESSE = re.compile(r"grossesse|enceinte|pregnan|test de grossesse|β-?hcg|beta-?hcg|حمل", re.I)

    def garde_fou_outil(self, outil, args):
        """Le modèle en ligne ne doit pas insister sur une question réglée : parler de grossesse à un homme, ou à une
        patiente dont la non-grossesse est confirmée, est inutile et blessant (retour d'usage du 7 novembre)."""
        if not getattr(self, "_par_modele", False) or outil not in ("suggerer_au_medecin", "demander_question_patient", "envoyer_message"):
            return None
        texte = " ".join(str(args.get(k, "")) for k in ("texte", "question", "contenu"))
        if not self.GROSSESSE.search(texte):
            return None
        sexe, g = self.ctx.dossier.etat.get("sexe"), self.ctx.dossier.etat.get("grossesse")
        if sexe and sexe["valeur"] == "M":
            return "Refusé : le patient est un homme ; ne pas parler de grossesse."
        if g and g["confirme"] and g["valeur"] is False:
            return "Refusé : la patiente n'est pas enceinte (information confirmée) ; ne pas insister sur la grossesse."
        return None

    def _maj_etat(self, cle, valeur, source, confirme=False):
        """Garde-fou : l'assistant ne peut pas « confirmer » lui-même un fait que personne n'a rapporté, ni remplacer
        par une valeur NON confirmée un fait que le médecin ou le patient a confirmé."""
        d = self.ctx.dossier
        actuel = d.etat.get(cle)
        if actuel and actuel["confirme"] and not confirme and str(actuel["valeur"]).lower() != str(valeur).lower():
            return (f"Refusé : « {cle} » est déjà confirmé ({actuel['valeur']!r}, source : {actuel.get('source', '?')}). "
                    "Une valeur non confirmée ne le remplace pas ; signalez la contradiction au médecin si besoin.")
        rapporte = any(e["confirme"] and str(e["donnees"].get(cle)).lower() == str(valeur).lower()
                       for e in d.fil if cle in e["donnees"])
        res = d.maj_etat(self.nom, cle, valeur, source, bool(confirme) and rapporte)
        if confirme and not rapporte:
            res += " Fait enregistré comme NON confirmé : aucun échange confirmé ne le rapporte."
        return res

    def politique_simulee(self, msgs, changements):
        d, base = self.ctx.dossier, self.ctx.regles.base
        # 1. Intégrer les faits nouveaux rapportés par le traducteur ou le médecin
        for c in changements:
            if c["type"] == "echange":
                for cle, valeur in c["contenu"]["donnees"].items():
                    if self.val(cle) != valeur:
                        yield (f"Nouveau fait rapporté par {c['auteur']} : {cle} = {valeur!r}. Je l'ajoute à l'état du patient.",
                               "mettre_a_jour_etat",
                               {"cle": cle, "valeur": valeur, "source": f"échange : {c['contenu']['texte'][:60]}",
                                "confirme": c["contenu"]["confirme"]})
        # 2. Urgence d'abord
        if self.val("urgence") is True and not any(s["type"] == "alerte_urgence" for s in d.suggestions.values()):
            yield ("Signe d'urgence dans l'état du patient : j'alerte le médecin en priorité.", "suggerer_au_medecin",
                   {"type": "alerte_urgence", "texte": "Urgence : utiliser le jeu de pictogrammes d'urgence et orienter sans délai.",
                    "raison": "urgence = vrai dans l'état du patient", "source": "DHATH-12.4"})
        # 3. Repérer de moi-même une information indispensable manquante
        sexe, age = self.val("sexe"), self.val("age")
        if sexe == "F" and age is not None and 12 <= age <= 50 and "grossesse" not in d.etat:
            if not any(q.get("cle") == "grossesse" for q in d.questions_a_poser):
                yield ("Femme en âge de procréer et grossesse non renseignée : indispensable avant tout traitement. "
                       "Je fais poser la question, sans attendre qu'on me le demande.",
                       "demander_question_patient",
                       {"question": "Êtes-vous enceinte ?", "raison": "Information obligatoire avant toute prescription.", "cle": "grossesse"})
                yield ("Je préviens aussi le médecin.", "suggerer_au_medecin",
                       {"type": "question_manquante", "texte": "Vérifier une éventuelle grossesse avant tout traitement.",
                        "raison": f"Patiente de {age} ans ; grossesse non renseignée.", "source": f"ML16-A4-2 — {base.citer_court('ML16-A4-2')}"})
        # 4. Répondre aux autres agents
        for m in msgs:
            if m.de == "juriste" and m.type == "demande":
                en_attente = [q for q in d.questions_a_poser if q["statut"] == "en_attente"]
                if en_attente:
                    yield ("Le juriste réclame une information ; la question est déjà partie vers le patient. Je le lui dis.",
                           "envoyer_message", {"destinataire": "juriste", "type": "information", "repond_a": m.id,
                                               "contenu": f"Question déjà transmise au patient : « {en_attente[0]['question']} ». Je vous préviens dès la réponse."})
            if m.de == "juriste" and m.type == "alerte" and "grossesse" in m.contenu.lower():
                yield ("Le juriste signale un problème lié à la grossesse. Je cherche dans la base une piste citée, "
                       "puis je la propose au médecin sans choisir à sa place.", "consulter_base",
                       {"question": "pain treatment during pregnancy alternative to NSAID", "nombre": 2})
                yield ("La fiche FDA20-NSAID cite le paracétamol comme alternative pour la douleur pendant la grossesse.",
                       "suggerer_au_medecin",
                       {"type": "traitement_alternatif", "texte": "Envisager un antalgique compatible avec la grossesse (la source cite le paracétamol), selon votre jugement.",
                        "raison": m.contenu[:140], "source": f"FDA20-NSAID — {base.citer_court('FDA20-NSAID')}"})
        # 5. Retirer de moi-même ce qui est devenu inutile
        if self.val("grossesse") is not None:
            for s in list(d.suggestions.values()):
                if s["auteur"] == self.nom and s["statut"] == "proposee_au_medecin" and s["type"] == "question_manquante" and "grossesse" in s["texte"]:
                    yield ("La grossesse est maintenant renseignée : ma suggestion n'a plus lieu d'être, je la retire.",
                           "retirer_suggestion", {"id": s["id"], "raison": "Information obtenue."})


def precontrole_a_jour(dec: dict, dossier) -> bool:
    """Le contrôle du contenu d'une proposition vaut pour un texte ET un état du patient : si le médecin saisit
    « enceinte » après coup, « et du tramadol » doit être recontrôlé."""
    pc = dec.get("precontrole") or {}
    return pc.get("texte") == dec.get("texte") and pc.get("etat_version") == dossier.etat_version


# ====================================================================== AGENT 2
class Juriste(Agent):
    nom = "juriste"
    but = """Tu es l'AGENT 2, le juriste de MEDIMCOM IA (pays hôte : Émirats arabes unis).
TON BUT : qu'aucune action illégale ou dangereuse n'atteigne le patient, et conseiller le médecin et les autorités
en cas de crise (lois applicables, responsabilités des institutions, pouvoirs d'urgence, engagements internationaux,
lacunes, exemples mondiaux).
TU DÉCIDES SEUL : tu surveilles le dossier en continu ; tu contrôles chaque prescription, chaque message destiné au
patient et chaque demande de partage de données, et tu les recontrôles quand l'état du patient change ; tu rappelles
les obligations qui naissent de l'état du patient (par exemple une déclaration de maladie).
TU COLLABORES : tu expliques tes verdicts au médecin ; tu réclames l'information manquante à l'assistant ; tu proposes
une piste conforme quand tu refuses ; tu réponds aux questions avec consulter_base ; tu signales les lacunes.
TES LIMITES : le verdict est TOUJOURS celui rendu par tes outils verifier_* (moteur de règles) ; tu ne peux pas le
changer ; tu cites toujours la fiche et le texte ; sans texte applicable, tu le dis et tu signales une lacune."""

    def __init__(self, ctx, cerveau):
        super().__init__(ctx, cerveau)
        self.dernier_verdict = None
        self.lacunes_signalees: set[str] = set()
        self.obligations_signalees: set[str] = set()
        self.verdict_precedent: dict[int, str] = {}

    def _outils_propres(self):
        return {
            "verifier_prescription": (self._verifier_prescription, _schema(
                "verifier_prescription", "Contrôler une prescription du médecin avec le moteur de règles (verdict déterministe).",
                {"decision_id": I}, ["decision_id"])),
            "verifier_envoi_patient": (self._verifier_envoi, _schema(
                "verifier_envoi_patient", "Contrôler un message destiné au patient avant son envoi (verdict déterministe).",
                {"decision_id": I}, ["decision_id"])),
            "precontroler_envoi_patient": (self._precontroler_envoi, _schema(
                "precontroler_envoi_patient", "Contrôler le CONTENU d'une proposition destinée au patient dès qu'elle est "
                "proposée, avant la validation du médecin (propos dangereux, consigne de médicament sans prescription).",
                {"decision_id": I}, ["decision_id"])),
            "verifier_partage_donnees": (self._verifier_partage, _schema(
                "verifier_partage_donnees", "Contrôler une demande de partage de données (verdict déterministe).",
                {"decision_id": I}, ["decision_id"])),
            "obligations_etat_patient": (lambda: self.ctx.regles.obligations_etat(self.ctx.dossier.etat), _schema(
                "obligations_etat_patient", "Lister les obligations légales qui découlent de l'état actuel du patient.")),
            "signaler_lacune": (self._signaler_lacune, _schema(
                "signaler_lacune", "Enregistrer une lacune du droit. Donner l'identifiant du catalogue (L01…L09) s'il existe.",
                {"sujet": S, "detail": S, "lacune_id": S}, ["sujet", "detail"])),
        }

    # ------------------------------------------------------------------ outils
    def _decision(self, decision_id, type_attendu):
        d = self.ctx.dossier.decisions.get(int(decision_id))
        if not d or d.get("type") != type_attendu:
            return None
        return d

    def _enregistrer(self, d, v):
        v["decision_id"] = d["id"]
        self.ctx.dossier.ajouter_verdict(self.nom, v)
        self.dernier_verdict = v
        return v

    def _verifier_prescription(self, decision_id):
        d = self._decision(decision_id, "prescription")
        if not d:
            return f"Décision {decision_id} introuvable ou pas une prescription."
        champs = ("medicament", "prescripteur", "auteur", "dose", "posologie", "mode", "urgence", "issue_de_suggestion")
        return self._enregistrer(d, self.ctx.regles.verifier_prescription({k: d.get(k) for k in champs}, self.ctx.dossier.etat))

    def _precontroler_envoi(self, decision_id):
        """Contrôle du contenu AVANT la validation : un message dangereux ne doit même pas pouvoir être validé."""
        d = self._decision(decision_id, "envoi_patient")
        if not d:
            return f"Décision {decision_id} introuvable ou pas un message au patient."
        if d["statut"] != "attente_validation":
            return f"Refusé : le message #{d['id']} n'est plus une proposition (statut « {d['statut']} »)."
        p = self.ctx.dossier.decisions.get(d.get("source_prescription") or -1)
        v = self.ctx.regles.verifier_envoi_patient({**d, "statut_prescription_liee": p["statut"] if p else None}, suppose_valide=True,
                                                   etat=self.ctx.dossier.etat)
        motifs = [c for c in v["constats"] if c["niveau"] != "CONFORME"]
        garder = ("regle", "niveau", "base", "detail", "piste", "reference_courte")
        d["precontrole"] = {"verdict": v["verdict"], "texte": d.get("texte"), "analyse": v.get("analyse_contenu", {}),
                            "etat_version": self.ctx.dossier.etat_version, "alternatives": v.get("alternatives", []),
                            "constats": [{k: c.get(k) for k in garder} for c in motifs],
                            # ce que le juriste a compris du message (récit, question…) et les fautes corrigées
                            "lecture": [{k: c.get(k) for k in garder} for c in v.get("informations", [])
                                        if str(c.get("regle", "")).startswith(("LECTURE", "CONTEXTE"))]}
        self.ctx.dossier._changer(self.nom, "precontrole", {"id": d["id"], "verdict": v["verdict"], "motifs": [c["regle"] for c in motifs]})
        if v["verdict"] == "BLOQUE":
            # Verdict enregistré (journal, onglet Droit) : la proposition passe au statut BLOQUE et ne peut plus être validée.
            self._enregistrer(d, {**v, "precontrole": True})
            self.verdict_precedent[d["id"]] = "BLOQUE"
        return {"decision_id": d["id"], "verdict": v["verdict"], "motifs": [c["detail"] for c in motifs]}

    def _verifier_envoi(self, decision_id):
        d = self._decision(decision_id, "envoi_patient")
        if not d:
            return f"Décision {decision_id} introuvable ou pas un message au patient."
        if d["statut"] == "attente_validation":
            # Contrôler maintenant bloquerait définitivement la proposition (« non validé ») avant même que le médecin
            # l'ait vue : défaut observé avec un vrai modèle. Le contrôle se fait après la validation du médecin.
            return (f"Refusé : la proposition #{d['id']} attend encore la validation du médecin ; "
                    "je la contrôlerai quand il l'aura validée (aucun verdict enregistré).")
        if d["statut"] not in ("a_verifier", "CONFORME", "BLOQUE"):
            return f"Refusé : le message #{d['id']} est au statut « {d['statut']} » : rien à contrôler."
        p = self.ctx.dossier.decisions.get(d.get("source_prescription") or -1)
        message = {**d, "statut_prescription_liee": p["statut"] if p else None}
        return self._enregistrer(d, self.ctx.regles.verifier_envoi_patient(message, etat=self.ctx.dossier.etat))

    def _verifier_partage(self, decision_id):
        d = self._decision(decision_id, "partage_donnees")
        if not d:
            return f"Décision {decision_id} introuvable ou pas un partage de données."
        return self._enregistrer(d, self.ctx.regles.verifier_partage_donnees(d["demande"]))

    def _signaler_lacune(self, sujet, detail, lacune_id=None):
        lac = self.ctx.regles.base.lacunes.get(lacune_id) if lacune_id else None
        if lac:
            exemples = " ; ".join(self.ctx.regles.base.citer_court(x["fiche"]) for x in lac["global_examples"])
            detail = f"{detail} | Manque : {lac['missing']} | Exemples mondiaux : {exemples}"
        self.lacunes_signalees.add(lacune_id or sujet)
        return self.ctx.dossier.ajouter_lacune(self.nom, sujet, detail, lacune_id)

    # ------------------------------------------------------------------ politique sans IA
    def politique_simulee(self, msgs, changements):
        d = self.ctx.dossier
        for dec in list(d.decisions.values()):
            t, statut = dec.get("type"), dec["statut"]
            if statut == "annulee":
                continue
            if t == "prescription":
                nouvelle = statut == "a_verifier"
                if not nouvelle and dec["verifiee_a_version_etat"] == d.etat_version:
                    continue
                yield ((f"Nouvelle prescription #{dec['id']} ({dec['medicament']}) : je la contrôle avant tout envoi au patient."
                        if nouvelle else f"L'état du patient a changé depuis mon contrôle de #{dec['id']} : je revérifie."),
                       "verifier_prescription", {"decision_id": dec["id"]})
                yield from self._reagir(self.dernier_verdict, dec)
            elif t == "envoi_patient" and statut == "attente_validation" and not precontrole_a_jour(dec, d):
                yield ((f"Nouvelle proposition #{dec['id']} pour le patient : je contrôle son contenu avant que le médecin la valide."
                        if not dec.get("precontrole") else
                        f"La fiche du patient a changé : je recontrôle la proposition #{dec['id']} avant que le médecin la valide."),
                       "precontroler_envoi_patient", {"decision_id": dec["id"]})
                yield from self._alerter_precontrole(dec)
            elif t in ("envoi_patient", "partage_donnees") and statut == "a_verifier":
                outil = "verifier_envoi_patient" if t == "envoi_patient" else "verifier_partage_donnees"
                quoi = "Message destiné au patient" if t == "envoi_patient" else "Demande de partage de données"
                yield (f"{quoi} #{dec['id']} : je le contrôle.", outil, {"decision_id": dec["id"]})
                yield from self._reagir(self.dernier_verdict, dec)
        # Obligations nées de l'état du patient (ex. déclaration d'une maladie transmissible)
        nouvelles = [o for o in self.ctx.regles.obligations_etat(d.etat) if o["regle"] not in self.obligations_signalees]
        if nouvelles:
            yield ("L'état du patient fait naître des obligations légales : je les rappelle au médecin avec leurs sources.",
                   "obligations_etat_patient", {})
            for o in nouvelles:
                self.obligations_signalees.add(o["regle"])
                yield ("", "envoyer_message", {"destinataire": "medecin", "type": "alerte" if o["niveau"] == "OBLIGATION" else "information",
                                               "contenu": f"{o['niveau']} : {o['detail']} [{o['reference_courte']}]"})
                yield from self._lacunes([o["lacune"]] if o.get("lacune") else [])
        # Questions (mode conseiller)
        for m in msgs:
            if m.type == "demande" and (m.de == "medecin" or m.de in INSTITUTIONS):
                yield (f"Question de {m.de} : je cherche les textes applicables dans la base avant de répondre.",
                       "consulter_base", {"question": m.contenu, "nombre": 5})
                res = [r for r in self.ctx.regles.base.chercher(m.contenu, k=12)
                       if self.ctx.regles.applicable(r["fiche"])][:5]          # textes du pays choisi + références mondiales
                lac = self.ctx.regles.base.lacunes_liees([r["fiche"] for r in res[:3]], minimum=2)
                reponse = " | ".join(f"{r['fiche']} ({r['base']}) {r['titre']} — {self.ctx.regles.base.citer_court(r['fiche'])}" for r in res)
                note = f" Lacunes liées : {', '.join(lac)}." if lac else ""
                if self.ctx.corpus:
                    extraits = self.ctx.corpus.chercher(m.contenu, k=3, type_="texte_officiel")
                    if extraits:
                        note += " Extraits des textes complets : " + " | ".join(f"{x['citation']} <{x['lien']}>" for x in extraits) + "."
                yield ("Je réponds en citant les textes ; je ne tranche que ce que les textes tranchent.", "envoyer_message",
                       {"destinataire": m.de, "type": "information", "repond_a": m.id,
                        "contenu": f"Textes applicables : {reponse or 'aucun texte trouvé'}.{note} Décision finale : humaine."})
                yield from self._lacunes(lac[:1])

    def _alerter_precontrole(self, dec):
        pc = dec.get("precontrole") or {}
        if not hasattr(self, "_alertes_pc"):
            self._alertes_pc = set()
        cle = (dec["id"], pc.get("verdict"), pc.get("texte"))
        if cle in self._alertes_pc:
            return
        self._alertes_pc.add(cle)
        analyse = pc.get("analyse") or {}
        if analyse.get("evocation") or analyse.get("a_confirmer"):
            # Les agents se disent ce qu'ils ont compris : l'assistant sait que ce n'est pas une consigne
            lu = analyse.get("evocation") or analyse.get("a_confirmer")
            yield (f"Message #{dec['id']} : {lu}. Je dis à l'assistant ce que j'ai compris : il suit la consultation.",
                   "envoyer_message", {"destinataire": "assistant", "type": "information",
                                       "contenu": f"Lecture du message #{dec['id']} « {dec.get('texte', '')} » : {lu}. "
                                                  f"Indices : {', '.join((analyse.get('contexte') or {}).get('indices') or []) or 'aucun'}."})
        if pc.get("verdict") == "A_REVOIR" and any(c["regle"] == "CONTEXTE-A-CONFIRMER" for c in pc.get("constats", [])):
            yield ("Je ne peux pas trancher le sens de ce message : le médecin confirme ce qu'il veut dire, ou reformule.",
                   "envoyer_message", {"destinataire": "medecin", "type": "information",
                                       "contenu": f"Message au patient #{dec['id']} « {dec.get('texte', '')} » : sens à confirmer. "
                                                  f"{analyse.get('a_confirmer', '')}. Il ne partira que si vous confirmez, en le validant, "
                                                  "que ce n'est ni une consigne ni une incitation (votre nom est enregistré), ou reformulez."})
        if pc.get("verdict") != "BLOQUE":
            return
        bloquants = [c for c in pc["constats"] if c["niveau"] == "BLOQUE"]
        patient = [c for c in pc["constats"] if c["niveau"] == "A_REVOIR" and str(c.get("detail", "")).startswith("Pour ce patient")]
        detail = " ".join(dict.fromkeys(c["detail"] for c in bloquants + patient))
        refs = " ; ".join(dict.fromkeys(r for c in bloquants + patient for r in str(c["reference_courte"]).split(" ; ")))
        pistes = " ".join(dict.fromkeys(c["piste"] for c in bloquants if c.get("piste")))
        yield ("Ce contenu est interdit par une règle contraignante : je le bloque avant toute validation et je dis au médecin quoi faire.",
               "envoyer_message", {"destinataire": "medecin", "type": "alerte",
                                   "contenu": f"Message au patient #{dec['id']} « {dec.get('texte', '')} » BLOQUÉ, il ne partira pas : {detail} [{refs}]"
                                              + (f" Piste conforme : {pistes}" if pistes else "")})

    def _lacunes(self, ids):
        base = self.ctx.regles.base
        for lid in ids:
            if lid in self.lacunes_signalees or lid not in base.lacunes:
                continue
            lac = base.lacunes[lid]
            titre = lac["title"] if self.ctx.regles.langue == "en" else lac.get("title_fr", lac["title"])
            yield (f"Les textes ne règlent pas entièrement cette situation : je signale la lacune {lid}.", "signaler_lacune",
                   {"sujet": titre, "detail": lac["situation"], "lacune_id": lid})

    def _reagir(self, v, dec):
        if v is None:
            return
        avant = self.verdict_precedent.get(dec["id"])
        self.verdict_precedent[dec["id"]] = v["verdict"]
        if avant == v["verdict"]:
            self._penser(f"Verdict inchangé pour #{dec['id']} ({v['verdict']}) : rien de plus à dire.")
            return
        c = v["constats"]
        motifs = " ; ".join(f"{x['detail']} [{x['reference_courte']}]" for x in c) or "aucun constat"
        pistes = " ; ".join(dict.fromkeys(x["piste"] for x in c if x.get("piste")))
        motifs += f" Piste conforme : {pistes}" if pistes else ""
        oblig = " ; ".join(f"{x['detail']} [{x['reference_courte']}]" for x in v.get("obligations", []))
        objet = dec.get("medicament") or dec.get("type")
        lib = {"prescription": f"Prescription #{dec['id']} ({objet})", "envoi_patient": f"Message au patient #{dec['id']}",
               "partage_donnees": f"Demande de partage #{dec['id']}"}.get(dec.get("type"), f"#{dec['id']}")
        demandeur = dec["auteur"] if dec.get("type") == "partage_donnees" and dec["auteur"] in self.ctx.messagerie.boites \
            and dec["auteur"] not in (self.nom, "medecin") else None
        if v["verdict"] == "PREUVES_INSUFFISANTES":
            if dec.get("type") == "prescription":
                yield ("Je ne peux pas juger sans ces informations. Je les réclame à l'assistant et j'informe le médecin.",
                       "envoyer_message", {"destinataire": "assistant", "type": "demande",
                                           "contenu": f"{lib} : informations manquantes : {', '.join(v.get('informations_manquantes', [])) or 'voir constats'}. Pouvez-vous les obtenir ?"})
            yield ("Information manquante : je ne peux pas juger, je le dis au demandeur.", "envoyer_message",
                   {"destinataire": demandeur or "medecin", "type": "information",
                    "contenu": f"{lib} en attente : preuves insuffisantes. {motifs}"})
        elif v["verdict"] == "A_REVOIR":
            yield ("Problème détecté, mais la décision relève du jugement d'un humain : il peut maintenir en le justifiant.",
                   "envoyer_message", {"destinataire": "medecin", "type": "alerte",
                                       "contenu": f"{lib} À REVOIR : {motifs}. Vous pouvez maintenir en le justifiant (votre nom sera enregistré), ou choisir une alternative."})
            if dec.get("type") == "prescription":
                yield ("", "envoyer_message", {"destinataire": "assistant", "type": "alerte", "contenu": f"#{dec['id']} : {c[-1]['detail']}"})
            if demandeur:
                yield ("", "envoyer_message", {"destinataire": demandeur, "type": "information",
                                                "contenu": f"{lib} : décision humaine nominative requise. {motifs}"})
        elif v["verdict"] == "BLOQUE":
            yield ("Une règle contraignante interdit cette action : blocage sans dérogation possible. J'alerte et je propose une piste conforme si elle existe.",
                   "envoyer_message", {"destinataire": demandeur or "medecin", "type": "alerte",
                                       "contenu": f"{lib} BLOQUÉ, il ne partira pas (aucune dérogation possible) : {motifs}"})
            if dec.get("type") == "envoi_patient":
                yield ("", "envoyer_message", {"destinataire": "traducteur", "type": "alerte",
                                                "contenu": f"#{dec['id']} : ne pas envoyer ce message au patient tant qu'un médecin autorisé ne l'a pas validé."})
        else:
            dest = "traducteur" if dec.get("type") in ("prescription", "envoi_patient") else (demandeur or "medecin")
            yield ("Conforme : la décision peut avancer ; je joins les obligations à remplir.", "envoyer_message",
                   {"destinataire": dest, "type": "information",
                    "contenu": f"Décision #{dec['id']} ({objet}) conforme." + (f" Obligations : {oblig}" if oblig else "")})
        yield from self._lacunes(v.get("lacunes_liees", []))


# ====================================================================== AGENT 1
class Traducteur(Agent):
    nom = "traducteur"
    but = """Tu es l'AGENT 1, le traducteur de MEDIMCOM IA (patient sourd, peu habitué à l'écrit).
TON BUT : que le médecin et le patient se comprennent, en pictogrammes.
TU DÉCIDES SEUL : quand traduire une question de l'assistant ou une décision conforme du médecin, comment la
simplifier, et quand prévenir le médecin qu'un mot n'a pas de pictogramme. Tu peux choisir toi-même les
pictogrammes (argument « pictogrammes » de proposer_au_medecin) et COMBINER plusieurs pictogrammes en UNE image
quand c'est plus clair : « TETE+DOULEUR » (le premier en grand, les autres en médaillon, 3 au plus). La négation
(NE_PAS), la limite (MAXIMUM), l'urgence et STOP restent toujours des pictogrammes entiers ; tu ne supprimes jamais
une négation, une limite, une dose, un chiffre ni un nom de médicament de la traduction.
Quand un mot n'a pas de pictogramme (« essoufflement », « serre »), cherche par le sens avec l'outil
chercher_pictogrammes, puis propose ton choix au médecin (argument « pictogrammes ») : il voit et valide.
Si aucun pictogramme ni aucune combinaison ne convient et que le moteur de pictogrammes sait créer des images,
tu peux proposer une image nouvelle « GEN:… » ; le médecin la voit et la valide comme le reste.
TU COLLABORES : chaque message est d'abord proposé au médecin (outil proposer_au_medecin) ; le médecin valide ;
le juriste contrôle ; tu envoies ensuite (outil envoyer_au_patient).
TES LIMITES : tu n'envoies JAMAIS rien au patient sans validation du médecin et verdict CONFORME du juriste ;
tu n'ajoutes aucune information médicale qui n'est pas dans le texte du médecin ou de l'assistant."""

    def __init__(self, ctx, cerveau):
        super().__init__(ctx, cerveau)
        self.derniere = None
        self.reponses_patient: list[list[str]] = []
        self.repondus: set[int] = set()

    def _outils_propres(self):
        return {
            "traduire": (lambda texte: self.ctx.pictogrammeur.traduire(texte), _schema(
                "traduire", "Traduire un texte en pictogrammes (aucun envoi).", {"texte": S}, ["texte"])),
            "proposer_au_medecin": (self._proposer, _schema(
                "proposer_au_medecin", "Proposer au médecin un message en pictogrammes, qu'il devra valider avant tout envoi.",
                {"texte": S, "contenu_type": {"type": "string", "enum": ["question", "information", "diagnostic", "traitement"]},
                 "question_id": I, "prescription_id": I,
                 "pictogrammes": {"type": "array", "items": S, "description": "facultatif : ton propre choix de pictogrammes, "
                                  "y compris des images combinées comme TETE+DOULEUR ; sinon la traduction automatique est utilisée"}},
                ["texte", "contenu_type"])),
            "rapporter_reponse_patient": (self._rapporter, _schema(
                "rapporter_reponse_patient", "Rapporter dans le dossier la réponse que le patient vient d'envoyer "
                "(exactement les pictogrammes qu'il a choisis). Un OUI ou NON seul à une question fermée devient un fait.",
                {"pictogrammes": {"type": "array", "items": S}}, ["pictogrammes"])),
            "retirer_proposition": (self._retirer_proposition, _schema(
                "retirer_proposition", "Retirer une de tes propositions encore en attente de validation, devenue inutile "
                "(l'information est déjà obtenue).", {"decision_id": I, "raison": S}, ["decision_id", "raison"])),
            "envoyer_au_patient": (self._envoyer_patient, _schema(
                "envoyer_au_patient", "Envoyer au patient un message validé par le médecin et jugé CONFORME par le juriste.",
                {"decision_id": I}, ["decision_id"])),
        }

    MAX_LIBRES = 3      # messages sans question ni prescription liée, en attente de validation

    # éléments que l'agent ne peut jamais retirer d'une traduction : ce qui change le sens ou la sécurité
    INDISPENSABLES = ("NE_PAS", "MAXIMUM", "URGENCE", "STOP")
    PREFIXES_INDISPENSABLES = ("DOSE:", "CHIFFRE:", "MEDICAMENT:")

    def _elements(self, pictos):
        return [x for p in pictos for x in p.split("+")]

    def _verifier_choix(self, auto, choix):
        """Contrôle le choix de pictogrammes fait par l'agent ; renvoie un motif de refus, ou None."""
        if not isinstance(choix, list) or not 1 <= len(choix) <= 12:
            return "il faut entre 1 et 12 pictogrammes"
        choix = [str(x) for x in choix]
        inconnus = [x for x in choix if not picto_connu(x)]
        if inconnus:
            return f"pictogramme ou combinaison inconnu(e) ou interdit(e) : {', '.join(inconnus)}"
        from collections import Counter
        garder = Counter(x for x in self._elements(auto) if x in self.INDISPENSABLES or x.startswith(self.PREFIXES_INDISPENSABLES))
        dispo = Counter(self._elements(choix))
        manquants = [x for x, n in garder.items() if dispo[x] < n]     # compté : deux limites restent deux limites
        if manquants:
            return f"élément indispensable retiré de la traduction : {', '.join(manquants)}"
        return None

    def _proposer(self, texte, contenu_type, question_id=None, prescription_id=None, pictogrammes=None):
        envois = [x for x in self.ctx.dossier.decisions.values() if x.get("type") == "envoi_patient" and x["auteur"] == self.nom]
        for x in envois:
            if x["statut"] in ("BLOQUE", "rejete"):
                continue
            if (question_id and x.get("source_question") == question_id) or (prescription_id and x.get("source_prescription") == prescription_id):
                return f"Refusé : la proposition #{x['id']} existe déjà pour ce sujet (statut : {x['statut']})."
        q = next((q for q in self.ctx.dossier.questions_a_poser if q["id"] == question_id), None) if question_id else None
        if q and q["statut"] in ("rejetee", "annulee"):
            return f"Refusé : le médecin a annulé la question #{question_id} ; il la reformulera s'il le souhaite."
        libres = [x for x in envois if x["statut"] == "attente_validation" and not (x.get("source_question") or x.get("source_prescription"))]
        if not (question_id or prescription_id) and len(libres) >= self.MAX_LIBRES:
            return (f"Refusé : déjà {self.MAX_LIBRES} messages libres attendent la validation du médecin "
                    "(les questions et explications de traitement restent possibles).")
        t = dict(self.ctx.pictogrammeur.traduire(texte))
        choisi_par = "traduction automatique"
        q = next((q for q in self.ctx.dossier.questions_a_poser if q["id"] == question_id), None) if question_id else None
        demande_accord = (contenu_type == "traitement" and prescription_id) or (q and q.get("cle") in ("consentement_traitement", "informe_usage_ia"))
        if demande_accord and not any(x in self.ACCORD for p in t["pictogrammes"] for x in p.split("+")):
            accord = next((a for a in self.ACCORD if picto_connu(a)), None)
            if accord:          # la question d'accord doit être VUE par le patient, sinon son OUI ne vaut pas accord
                pos = t["pictogrammes"].index("QUESTION") if "QUESTION" in t["pictogrammes"] else len(t["pictogrammes"])
                t["pictogrammes"] = t["pictogrammes"][:pos] + [accord] + t["pictogrammes"][pos:]
                t["non_traduits"] = [m for m in t["non_traduits"] if "accord" not in m.lower()]
        if pictogrammes:
            motif = self._verifier_choix(t["pictogrammes"], pictogrammes)
            if motif:
                return f"Refusé : {motif}. Traduction automatique proposée : {' '.join(t['pictogrammes'])}."
            t["pictogrammes"], choisi_par = [str(x) for x in pictogrammes], "choix de l'agent traducteur"
        rapproches = t.get("rapproches") or {}      # mots inconnus rapprochés en arrière-plan (faute, conjugaison, sens)
        for mot, corrige in (t.get("corrections") or {}).items():   # fautes de frappe ou de dictée corrigées
            rapproches.setdefault(mot, f"lu comme « {corrige} »")
        did = self.ctx.dossier.ajouter_decision(self.nom, {
            "type": "envoi_patient", "texte": texte, "contenu_type": contenu_type, "valide_par": None,
            "statut": "attente_validation", "pictogrammes": t["pictogrammes"], "non_traduits": t["non_traduits"],
            "pictogrammes_choisis_par": choisi_par, "rapproches": rapproches,
            "source_question": question_id, "source_prescription": prescription_id})
        self.derniere = (did, t)
        manque = f" Mots sans pictogramme : {', '.join(t['non_traduits'])}." if t["non_traduits"] else ""
        if rapproches:
            manque += " Rapprochés automatiquement : " + " ; ".join(f"{m} → {i}" for m, i in rapproches.items()) + "."
        return f"Proposition #{did} soumise au médecin : {' '.join(t['pictogrammes'])}.{manque}"

    FAITS_OUI_NON = {"grossesse", "urgence", "consentement_traitement", "informe_usage_ia", "nausees", "fievre", "douleur"}
    # Questions à réponse OUI / NON qui portent sur une LISTE : NON = « aucune » ; OUI = à préciser (le juriste et
    # l'assistant ne considèrent pas le champ comme renseigné tant que le médecin n'a pas écrit lesquelles)
    FAITS_LISTE = {"allergies": "aucune", "traitements_en_cours": "aucun"}
    # Un accord n'est un consentement que si la question d'accord a vraiment été MONTRÉE en pictogrammes
    ACCORD = ("D_ACCORD", "ACCEPTER", "ACCORD", "CONSENTEMENT")

    def _recevoir(self, msgs):
        for m in msgs:
            if m.de == "patient":
                try:
                    self.reponses_patient.append([str(p).upper() for p in json.loads(m.contenu)["pictogrammes"]])
                except (ValueError, KeyError, TypeError):
                    pass

    def _question_ouverte(self):
        """La question visée est le DERNIER message envoyé au patient, s'il attend encore une réponse.
        Renvoie (decision, cle, libelle) ou (None, None, None)."""
        d = self.ctx.dossier
        envoyes = [x for x in d.decisions.values() if x.get("type") == "envoi_patient" and x["statut"] == "envoye"]
        if not envoyes or envoyes[-1]["id"] in self.repondus:
            return None, None, None
        dernier = envoyes[-1]
        if dernier.get("source_question"):
            q = next((q for q in d.questions_a_poser if q["id"] == dernier["source_question"]), None)
            if q and q["statut"] in ("en_attente", "posee"):
                return dernier, q.get("cle"), q["question"]
        if dernier.get("contenu_type") == "traitement" and dernier.get("source_prescription"):
            return dernier, "consentement_traitement", dernier["texte"]
        return None, None, None

    def _rapporter(self, pictogrammes):
        pictos = [str(p).upper() for p in pictogrammes]
        if sorted(pictos) not in [sorted(r) for r in self.reponses_patient]:
            return "Refusé : aucune réponse du patient ne correspond à ces pictogrammes (on ne rapporte que ce que le patient a choisi)."
        self.reponses_patient = [r for r in self.reponses_patient if sorted(r) != sorted(pictos)]
        texte = self.ctx.pictogrammeur.interpreter(pictos)
        dec, cle, libelle = self._question_ouverte()
        donnees, details = {}, {}
        oui_non = len(pictos) == 1 and pictos[0] in ("OUI", "NON", "D_ACCORD", "PAS_D_ACCORD")
        oui = pictos[0] in ("OUI", "D_ACCORD") if oui_non else None
        if cle in ("consentement_traitement", "informe_usage_ia") and oui_non and dec is not None \
                and not any(x in self.ACCORD for p in dec.get("pictogrammes") or [] for x in p.split("+")):
            # Garde-fou éthique : « vous ? » n'est pas « êtes-vous d'accord ? ». Sans pictogramme d'accord montré, le OUI
            # n'est pas enregistré comme consentement ; le médecin est prévenu.
            details["accord_non_valable"] = True
            self.ctx.messagerie.envoyer(self.nom, "medecin", "alerte",
                                        f"Réponse « {pictos[0].lower()} » au message #{dec['id']} NON enregistrée comme accord : la question "
                                        "d'accord n'a pas été montrée en pictogramme (aucune image « d'accord » ou « accepter »). "
                                        "Ajoutez-la (Modifier les pictogrammes) et reposez la question.")
        elif cle in self.FAITS_OUI_NON and oui_non:
            donnees[cle] = oui
        elif cle in self.FAITS_LISTE and oui_non:
            donnees[cle] = self.FAITS_LISTE[cle] if not oui else "oui, à préciser"
        elements_reponse = {x for p in pictos for x in p.split("+")}
        if "COMPRENDRE" in elements_reponse and elements_reponse & {"NE_PAS", "NON"}:
            details["incompris"] = True            # « je ne comprends pas » : l'assistant conseille le médecin
        if "URGENCE" in pictos:          # le bouton d'urgence du patient prime sur tout le reste
            donnees["urgence"] = True
        donnees.update(self._faits_douleur(pictos))
        # Médicament montré par le patient (« qu'avez-vous pris ? » -> MEDICAMENT:TRAMADOL) : un fait que l'assistant et
        # le juriste confrontent à sa fiche (grossesse, âge, allergies…). Rien n'est déduit d'une réponse niée.
        elements = [x for p in pictos for x in p.split("+")]
        meds = [x.split(":", 1)[1].lower() for x in elements if x.startswith("MEDICAMENT:")]
        if meds and not {"NON", "NE_PAS"} & set(elements):
            donnees["medicaments_declares"] = ", ".join(dict.fromkeys(meds))
        if dec:
            self.repondus.add(dec["id"])
            if dec.get("source_question"):
                self.ctx.dossier.statut_question(self.nom, dec["source_question"], "repondue")
        sujet = f" à « {libelle} »" if libelle else ""
        self.ctx.dossier.ajouter_echange(self.nom, f"Réponse du patient{sujet} en pictogrammes : [{' '.join(pictos)}] → « {texte} »",
                                         donnees, confirme=True,
                                         details={"pictogrammes": pictos, "interpretation": texte, "en_reponse_a": libelle,
                                                  "message_id": dec["id"] if dec else None, **details})
        faits = " ; ".join(f"{k} = {v}" for k, v in donnees.items())
        return f"Réponse rapportée : « {texte} »" + (f" ; {faits}" if faits else " (texte seulement, aucun fait structuré)")

    @staticmethod
    def _faits_douleur(pictos):
        """Lecture structurée d'une douleur ou de symptômes signalés par le patient : TETE+DOULEUR (ou TETE puis DOULEUR),
        un chiffre de 0 à 10 (intensité) et une DURÉE (« 3 » suivi de « semaine » = depuis 3 semaines) -> douleur,
        localisation, intensité, durée. Rien n'est déduit si la réponse contient NON ou NE_PAS (sens ambigu : le médecin
        lit alors la réponse telle quelle)."""
        elements = [x for p in pictos for x in p.split("+")]
        if {"NON", "NE_PAS"} & set(elements):
            return {}
        duree, intensites = None, []
        for k, x in enumerate(elements):
            if x.startswith("CHIFFRE:") and x.split(":", 1)[1].isdigit():
                unite = UNITES_TEMPS.get(_norm_libelle(picto_libelle(elements[k + 1]))) if k + 1 < len(elements) else None
                if unite:
                    n = int(x.split(":", 1)[1])
                    duree = f"{n} {unite[1] if n > 1 else unite[0]}"
                else:
                    intensites.append(int(x.split(":", 1)[1]))
        faits = {"duree_symptomes": duree} if duree else {}
        if "DOULEUR" not in elements:
            return faits
        faits["douleur"] = True
        lieux = [x for p in combiner_automatiquement(pictos) if "+" in p and "DOULEUR" in p.split("+")
                 for x in p.split("+") if x in PARTIES_DU_CORPS]
        if len(lieux) == 1 and sum(x in PARTIES_DU_CORPS for x in elements) == 1:   # plusieurs parties du corps : ambigu
            faits["localisation_douleur"] = picto_libelle(lieux[0])
        if len(intensites) == 1 and 0 <= intensites[0] <= 10:
            faits["intensite_douleur"] = intensites[0]
        return faits

    def _retirer_proposition(self, decision_id, raison):
        d = self.ctx.dossier.decisions.get(int(decision_id))
        if not d or d.get("type") != "envoi_patient" or d["auteur"] != self.nom or d["statut"] != "attente_validation":
            return "Refusé : seule une de mes propositions en attente de validation peut être retirée."
        d["statut"] = "annulee"
        self.ctx.dossier._changer(self.nom, "decision_annulee", {"id": d["id"], "raison": raison})
        return f"Proposition #{d['id']} retirée : {raison}."

    def _envoyer_patient(self, decision_id):
        d = self.ctx.dossier.decisions.get(int(decision_id))
        if not d or d.get("type") != "envoi_patient":
            return f"Refusé : {decision_id} n'est pas un message au patient."
        if d["statut"] != "CONFORME" or not d.get("valide_par"):
            return f"Refusé : le message #{decision_id} n'a pas été validé par le médecin et jugé conforme (statut : {d['statut']})."
        p = self.ctx.dossier.decisions.get(d.get("source_prescription") or -1)
        if d.get("contenu_type") == "traitement" and not p:
            return "Refusé : un message de traitement doit expliquer une prescription du médecin jugée conforme."
        if p and p["statut"] not in ("CONFORME", "MAINTENUE"):
            return (f"Refusé : la prescription #{p['id']} expliquée par ce message n'est plus conforme (statut : {p['statut']}). "
                    "Message à refaire.")
        d["statut"] = "envoye"
        self.ctx.dossier._changer(self.nom, "envoye_au_patient", {"id": d["id"], "pictogrammes": d.get("pictogrammes"), "valide_par": d["valide_par"]})
        if d.get("source_question"):
            self.ctx.dossier.statut_question(self.nom, d["source_question"], "posee")
        return f"Message #{d['id']} envoyé au patient."

    def politique_simulee(self, msgs, changements):
        d = self.ctx.dossier
        envois = [x for x in d.decisions.values() if x.get("type") == "envoi_patient"]
        # 0. Réponses du patient (il choisit des pictogrammes ; je les rapporte sans les interpréter au-delà)
        for r in list(self.reponses_patient):
            yield (f"Le patient a répondu par pictogrammes {r} : je rapporte sa réponse dans le dossier.",
                   "rapporter_reponse_patient", {"pictogrammes": r})
        # 0 bis. Informations que le médecin veut transmettre au patient
        for m in msgs:
            if m.de == "medecin" and m.type == "demande":
                yield ("Le médecin veut informer le patient : je traduis son texte et le lui soumets pour validation.",
                       "proposer_au_medecin", {"texte": m.contenu, "contenu_type": "information"})
                yield from self._signaler_manques()
        # 1. Questions de l'assistant ou du médecin à faire traduire
        for q in d.questions_a_poser:
            if q.get("auteur") != "medecin" and not self.ctx.questions_assistant_auto and not q.get("autorisee"):
                continue                       # le médecin la choisira (ou la refusera) dans l'onglet Assistant
            if q["statut"] == "en_attente" and not any(x.get("source_question") == q["id"] and x["statut"] not in ("rejete",) for x in envois):
                yield (f"L'assistant veut poser « {q['question']} » : je la traduis et la soumets au médecin.",
                       "proposer_au_medecin", {"texte": q["question"], "contenu_type": "question", "question_id": q["id"]})
                yield from self._signaler_manques()
        # 2. Décisions du médecin jugées conformes : expliquer le traitement
        for p in list(d.decisions.values()):
            if p.get("type") == "prescription" and p["statut"] in ("CONFORME", "MAINTENUE") \
                    and not any(x.get("source_prescription") == p["id"] for x in envois):
                texte = f"{p['medicament']} {p.get('dose') or ''}, {p.get('posologie') or ''}. Vous êtes d'accord ?"
                yield (f"La prescription #{p['id']} est conforme : je prépare l'explication en pictogrammes, avec la "
                       "question d'accord (consentement), pour validation par le médecin.",
                       "proposer_au_medecin", {"texte": texte, "contenu_type": "traitement", "prescription_id": p["id"]})
                yield from self._signaler_manques()
        # 2 bis. Question devenue inutile (le médecin a rempli la fiche entre-temps) : je retire ma proposition
        for x in envois:
            q = next((q for q in d.questions_a_poser if q["id"] == x.get("source_question")), None)
            if x["auteur"] == self.nom and x["statut"] == "attente_validation" and q and q.get("cle") and q["statut"] == "repondue":
                yield (f"La réponse à « {q['question']} » est déjà dans la fiche : je retire la proposition #{x['id']}, devenue inutile.",
                       "retirer_proposition", {"decision_id": x["id"], "raison": "information déjà obtenue"})
        # 3. Messages validés et jugés conformes : envoyer
        for x in envois:
            if x["auteur"] == self.nom and x["statut"] == "CONFORME" and x.get("valide_par"):
                yield (f"Le message #{x['id']} est validé par {x['valide_par']} et conforme : je l'envoie au patient.",
                       "envoyer_au_patient", {"decision_id": x["id"]})

    def _signaler_manques(self):
        if self.derniere and self.derniere[1]["non_traduits"]:
            did, t = self.derniere
            d = self.ctx.dossier.decisions.get(did) or {}
            from .surete import analyser_message
            a = analyser_message(d.get("texte", ""), self.ctx.regles.kb.get("medicaments", {}))
            if a["incitation_au_mal"] or (a["consigne_medicament"] and not d.get("source_prescription")):
                self.derniere = None       # le juriste va bloquer ce message : inutile de parler de pictogrammes
                return
            yield ("Certains mots n'ont pas de pictogramme : je préviens le médecin plutôt que d'inventer.", "envoyer_message",
                   {"destinataire": "medecin", "type": "information",
                    "contenu": f"Proposition #{did} : mots sans pictogramme ({', '.join(t['non_traduits'])}). Reformuler ou valider tel quel."})
        self.derniere = None


# ====================================================================== INSTITUTIONS (crise)
INSTITUTIONS = {"autorite_sante", "hopital", "cellule_crise"}
MANDATS = json.loads((Path(__file__).parent / "mandats.json").read_text(encoding="utf-8"))
BASES_CONTRAIGNANTES = {"LOI", "NORME"}
# Thèmes des fiches qui fondent un pouvoir d'agir (et pas seulement un droit ou un secret).
THEMES_POUVOIRS = {"emergency powers", "outbreak response", "isolation", "institutional cooperation", "crisis governance", "emergency use"}


def refus_base_de_mesure(institution: str, base_legale: str, base) -> str | None:
    """Raison du refus d'une base légale pour une mesure, ou None si elle est acceptable."""
    f = base.fiches.get(base_legale)
    if not f:
        return f"« {base_legale} » n'est pas une fiche de la base. Demandez la base légale au juriste."
    mandat = MANDATS["institutions"].get(institution, {}).get("bases_legales", [])
    if base_legale not in mandat:
        return (f"{base_legale} ne fait pas partie de votre mandat ({', '.join(mandat) or 'aucune base vérifiée'}). "
                "Adressez-vous à l'institution compétente ou au juriste.")
    if f["basis"] not in BASES_CONTRAIGNANTES:
        return f"{base_legale} ({f['basis']}) n'est pas une base contraignante pour une mesure. Demandez au juriste."
    if "crise" not in f["modes"]:
        return f"{base_legale} ne concerne pas les situations de crise. Demandez au juriste."
    if not set(f["themes"]) & THEMES_POUVOIRS:
        return f"{base_legale} ({f['title']}) ne donne pas de pouvoir d'agir. Demandez au juriste quel texte fonde cette mesure."
    if base.sources[f["source"]]["verification"] != "official_text":
        return f"{base_legale} n'est connu que par une source secondaire ; une mesure exige le texte officiel."
    return None


class Institution(Agent):
    """Participant institutionnel : ne voit que SES messages (information fragmentée), jamais le dossier du patient."""
    mandat = ""

    def __init__(self, ctx, cerveau):
        fiche = MANDATS["institutions"].get(self.nom, {})
        self.mandat = fiche.get("mandat", self.mandat)
        bases = "; ".join(f"{f} ({ctx.regles.base.citer_court(f)})" for f in fiche.get("bases_legales", [])) or "aucune vérifiée"
        self.but = (f"Tu es {self.nom.upper()} — {fiche.get('intitule', '')}, participant institutionnel de la simulation de crise MEDIMCOM IA.\n"
                    f"TON MANDAT : {self.mandat}\n"
                    f"TES BASES LÉGALES : {bases}.\n"
                    f"TU PEUX : {', '.join(fiche.get('peut', []))}. TU NE PEUX PAS : {', '.join(fiche.get('ne_peut_pas', []))}.\n"
                    + (f"À CONFIRMER : {fiche['a_confirmer']}\n" if fiche.get("a_confirmer") else "") +
                    "TU DÉCIDES SEUL des mesures à prendre et des institutions à informer, à partir des seuls messages que tu reçois.\n"
                    "TES LIMITES : tu n'as pas accès au dossier des patients ; une mesure n'est enregistrée qu'avec une base légale "
                    "contraignante (identifiant de fiche) ; toute demande de données passe par le juriste ; en cas de doute, "
                    "demande au juriste (envoyer_message, type demande).")
        super().__init__(ctx, cerveau)
        self.attente: dict[int, str] = {}

    def _outils_communs(self):
        o = super()._outils_communs()
        o.pop("lire_dossier")
        o["lire_tableau_crise"] = (self._tableau, _schema("lire_tableau_crise", "Lire les mesures et incidents de la crise (sans données de patients)."))
        return o

    def _outils_propres(self):
        return {
            "enregistrer_mesure": (self._mesure, _schema(
                "enregistrer_mesure", "Enregistrer une mesure institutionnelle avec sa base légale (identifiant de fiche, ex. CD14-A18).",
                {"mesure": S, "base_legale": S, "justification": S}, ["mesure", "base_legale", "justification"])),
            "demander_donnees": (self._demande, _schema(
                "demander_donnees", "Demander des données ; la demande est contrôlée par le juriste avant toute transmission.",
                {"finalite": S, "destinataire_type": S, "lieu": S, "anonymise": B, "consentement_ecrit": B, "texte": S},
                ["finalite", "destinataire_type", "lieu", "texte"])),
            "enregistrer_incident": (self._incident, _schema(
                "enregistrer_incident", "Enregistrer un incident (par exemple une défaillance d'IA).",
                {"description": S, "gravite": {"type": "string", "enum": ["faible", "moyenne", "grave"]}}, ["description", "gravite"])),
        }

    def _tableau(self):
        c = self.ctx.crise
        return {"mesures": c.mesures, "incidents": c.incidents}

    def _mesure(self, mesure, base_legale, justification):
        refus = refus_base_de_mesure(self.nom, base_legale, self.ctx.regles.base)
        if refus:
            return f"Refusé : {refus}"
        m = {"par": self.nom, "mesure": mesure, "base_legale": base_legale,
             "citation": self.ctx.regles.base.citer_court(base_legale), "justification": justification}
        self.ctx.crise.mesures.append(m)
        self.ctx.journal.ajouter(self.nom, "mesure", m)
        return f"Mesure enregistrée : {mesure} [{m['citation']}]"

    def _demande(self, finalite, destinataire_type, lieu, texte, anonymise=None, consentement_ecrit=None):
        # Une institution demande pour elle-même (ou pour publier) : elle ne peut pas se faire passer pour une autre.
        destinataire_type = "public" if destinataire_type == "public" else self.nom
        demande = {"finalite": finalite, "destinataire_type": destinataire_type, "lieu": lieu}
        if anonymise is not None:
            demande["anonymise"] = anonymise
        if consentement_ecrit is not None:
            demande["consentement_ecrit"] = consentement_ecrit
        did = self.ctx.dossier.ajouter_decision(self.nom, {"type": "partage_donnees", "demande": demande, "texte": texte})
        return f"Demande #{did} transmise au juriste pour contrôle."

    def _incident(self, description, gravite):
        i = {"par": self.nom, "description": description, "gravite": gravite}
        self.ctx.crise.incidents.append(i)
        self.ctx.journal.ajouter(self.nom, "incident", i)
        return f"Incident enregistré ({gravite})."

    def _contexte_llm(self, chg: str) -> str:
        c = self.ctx.crise
        return f"TABLEAU DE CRISE (aucune donnée de patient) :\nMesures : {c.mesures or 'aucune'}\nIncidents : {c.incidents or 'aucun'}"

    def tour(self) -> bool:
        msgs = self._reportes[0] + self.ctx.messagerie.lire(self.nom)
        self._reportes = ([], [])
        if not msgs:
            return False
        try:
            return self._decider(msgs, [])
        except Interrompu:
            self._reportes = (msgs, [])
            return False

    def _demander_au_juriste(self, question, cle):
        yield ("Je ne tranche pas seul une question de droit : je la pose au juriste.", "envoyer_message",
               {"destinataire": "juriste", "type": "demande", "contenu": question})
        self.attente[self.ctx.messagerie.historique[-1].id] = cle

    def _reponse(self, m):
        return self.attente.pop(m.repond_a, None) if m.de == "juriste" and m.repond_a else None


class AutoriteSante(Institution):
    nom = "autorite_sante"
    mandat = ("autorité de santé de l'émirat : surveiller l'épidémie, ordonner les mesures prévues par la loi, "
              "informer la population sans exposer les malades.")

    def politique_simulee(self, msgs, changements):
        for m in msgs:
            c = m.contenu.lower()
            cle = self._reponse(m)
            if m.de == "medecin" and "groupe a" in c:
                yield ("Déclaration d'un cas suspect du groupe A : j'ouvre l'enquête autour du cas, comme la loi le prévoit.",
                       "enregistrer_mesure", {"mesure": "Enquête épidémiologique, dépistage et isolement des contacts du cas déclaré",
                                              "base_legale": "CD14-A10", "justification": "Déclaration du médecin reçue"})
                yield ("Pour la surveillance, je demande les cas suspects ; le juriste contrôlera la demande.", "demander_donnees",
                       {"finalite": "sante_publique", "destinataire_type": "autorite_sante", "lieu": "dans_le_pays",
                        "texte": "Cas suspects pour la surveillance de l'épidémie."})
                yield ("J'informe la cellule de crise, sans aucune donnée nominative.", "envoyer_message",
                       {"destinataire": "cellule_crise", "type": "information", "contenu": "Un cas suspect de maladie du groupe A a été déclaré dans le quartier. Enquête ouverte."})
                yield from self._demander_au_juriste("Quels pouvoirs la loi nous donne-t-elle pendant une épidémie : déclarer une zone infectée, restreindre les rassemblements ?", "pouvoirs")
            elif cle == "pouvoirs":
                if "CD14-A18" in m.contenu:
                    yield ("Le juriste cite l'article sur les pouvoirs en cas d'épidémie : j'enregistre la mesure sur cette base.",
                           "enregistrer_mesure", {"mesure": "Déclaration du quartier comme zone infectée ; rassemblements restreints",
                                                  "base_legale": "CD14-A18", "justification": "Foyer confirmé ; avis du juriste"})
                else:
                    self._penser("La réponse du juriste ne cite pas de pouvoir applicable : je ne prends pas de mesure coercitive.")
            elif m.de == "cellule_crise" and "liste" in c and ("presse" in c or "public" in c):
                yield ("La presse réclame la liste des personnes infectées. Je prépare une publication ; le juriste la contrôlera.",
                       "demander_donnees", {"finalite": "information_publique", "destinataire_type": "public", "lieu": "dans_le_pays",
                                            "anonymise": False, "texte": "Publier la liste nominative des personnes infectées."})
            elif m.de == "juriste" and m.type == "alerte" and "BLOQUÉ" in m.contenu and "Piste conforme" in m.contenu:
                yield ("Le juriste bloque la publication nominative et propose une piste conforme : je la suis.", "demander_donnees",
                       {"finalite": "information_publique", "destinataire_type": "public", "lieu": "dans_le_pays", "anonymise": True,
                        "texte": "Publier le nombre de cas par quartier, sans aucune identité."})


class Hopital(Institution):
    nom = "hopital"
    mandat = "hôpital de référence : accueillir les cas graves, isoler, coopérer avec l'autorité de santé."

    def politique_simulee(self, msgs, changements):
        for m in msgs:
            c = m.contenu.lower()
            if any(x in c for x in ("détresse", "urgence", "transféré")):
                yield ("Un cas grave arrive : je réserve un lit d'isolement, comme la loi impose aux établissements de coopérer.",
                       "enregistrer_mesure", {"mesure": "Lit d'isolement réservé ; équipe prévenue",
                                              "base_legale": "CD14-A10", "justification": "Transfert d'un cas suspect grave"})
                yield ("Le patient est sourd : je demande au médecin les pictogrammes d'urgence pour l'accueil.", "envoyer_message",
                       {"destinataire": "medecin", "type": "demande",
                        "contenu": "Lit d'isolement prêt. Patient sourd : merci de transmettre le jeu de pictogrammes d'urgence pour l'accueil."})
                yield ("J'informe l'autorité de santé.", "envoyer_message",
                       {"destinataire": "autorite_sante", "type": "information", "contenu": "Un cas grave suspect est hospitalisé en isolement."})


class CelluleCrise(Institution):
    nom = "cellule_crise"
    mandat = "cellule de crise : coordonner les institutions, suivre les incidents (y compris d'IA), informer le public."

    def politique_simulee(self, msgs, changements):
        for m in msgs:
            c = m.contenu.lower()
            cle = self._reponse(m)
            if m.de == "terrain" and ("panne" in c or "pictogramme" in c):
                yield ("Défaillance d'un système d'IA dans plusieurs établissements : je l'enregistre comme incident.",
                       "enregistrer_incident", {"description": m.contenu, "gravite": "grave"})
                yield from self._demander_au_juriste(f"Incident d'IA : {m.contenu} À qui et dans quel délai le signaler ?", "incident")
            elif cle == "incident":
                yield ("Je transmets à l'autorité de santé l'avis du juriste sur le signalement de l'incident.", "envoyer_message",
                       {"destinataire": "autorite_sante", "type": "information", "contenu": f"Incident d'IA enregistré. Avis du juriste : {m.contenu[:400]}"})
            elif m.de == "terrain" and "liste" in c:
                yield ("Demande de la presse : la décision revient à l'autorité de santé, je la lui transmets.", "envoyer_message",
                       {"destinataire": "autorite_sante", "type": "information", "contenu": f"La presse réclame la liste des personnes infectées. ({m.contenu})"})
