import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  AlertTriangle, BookOpen, Bot, Building2, Check, ChevronDown, ClipboardList, FileText, Gavel, Hand, Info,
  Languages, Lock, MessageSquareText, MonitorSmartphone, Network, Pill, Play, RotateCcw, Scale, ScrollText,
  Send, Share2, ShieldAlert, ShieldCheck, Siren, Sparkles, Stethoscope, UserRound, X,
  Loader2, ArrowLeft, ArrowRight, EyeOff, PencilLine, Split, Undo2, WifiOff,
} from "lucide-react";
import {
  combinable, envoyer, ErreurApi, jetonMedecin, lire, urlPicto,
  type Decision, type DocumentPatient, type Echange, type MessageAgent, type Verdict, type VueMedecin,
} from "./api";
import { Bouton, Case, Champ, champ, ContexteLangue, cx, Dialogue, Panneau, Pastille, Picto, Statut, useLibelle, useRechercheSens, useNotifier, useSondage, Vide } from "./ui";
import { Marque } from "./Marque";


// Doctor's language: interface, captions, jurist and agents (see /api/medecin/langue)
let LANGUE_UI: "fr" | "en" | "ar" = "fr";
const TRAD: Record<string, [string, string]> = {
  'Écran patient': ['Patient screen', 'شاشة المريض'],
  'Journal': ['Log', 'السجل'],
  'Crédits': ['Credits', 'الاعتمادات'],
  'Nouvelle consultation': ['New consultation', 'استشارة جديدة'],
  'Données fictives': ['Fictitious data', 'بيانات وهمية'],
  'Conversation': ['Conversation', 'المحادثة'],
  'Vos messages sont traduits en pictogrammes. Rien ne part sans votre validation.': ['Your messages are translated into pictograms. Nothing is sent without your approval.', 'تُترجم رسائلك إلى رموز مصورة. لا يُرسل شيء دون موافقتك.'],
  "Informer le patient de l'IA": ['Tell the patient about the AI', 'إبلاغ المريض بالذكاء الاصطناعي'],
  'Traduction en pictogrammes': ['Pictogram translation', 'الترجمة إلى رموز'],
  'Annuler': ['Cancel', 'إلغاء'],
  'Reformuler': ['Rephrase', 'إعادة الصياغة'],
  'Modifier les pictogrammes': ['Edit pictograms', 'تعديل الرموز'],
  'Valider et envoyer': ['Approve and send', 'اعتماد وإرسال'],
  "Retirer de l'écran du patient": ['Remove from patient screen', 'إزالة من شاشة المريض'],
  'Masquer': ['Hide', 'إخفاء'],
  "C'est une question": ['It is a question', 'إنه سؤال'],
  'Faire traduire': ['Translate', 'ترجمة'],
  'Agents': ['Agents', 'الوكلاء'],
  'Assistant': ['Assistant', 'المساعد'],
  'Ordonnance': ['Prescription', 'الوصفة'],
  'Droit': ['Law', 'القانون'],
  'Crise': ['Crisis', 'أزمة'],
  'Suggestions': ['Suggestions', 'اقتراحات'],
  'Questions à poser': ['Questions to ask', 'أسئلة للطرح'],
  'Ignorer': ['Dismiss', 'تجاهل'],
  'Médicament': ['Medicine', 'الدواء'],
  'Dose': ['Dose', 'الجرعة'],
  "Mode d'emploi": ['Directions', 'طريقة الاستعمال'],
  'Consultation': ['Consultation', 'الاستشارة'],
  'Remplace': ['Replaces', 'يستبدل'],
  'Prescrire': ['Prescribe', 'وصف'],
  'Décisions': ['Decisions', 'القرارات'],
  'Patient': ['Patient', 'المريض'],
  'Informations cliniques': ['Clinical information', 'معلومات سريرية'],
  'Fiche patient': ['Patient record', 'ملف المريض'],
  'Enregistrer la fiche': ['Save record', 'حفظ الملف'],
  'Demander au juriste': ['Ask the legal agent', 'اسأل الوكيل القانوني'],
  'Envoyer la question': ['Send question', 'إرسال السؤال'],
  'Votre message': ['Your message', 'رسالتك'],
  'Pris en charge': ['Taken care of', 'تمت المعالجة'],
  "Message d'accueil (IA, droit de refuser)": ['Welcome message (AI, right to refuse)', 'رسالة ترحيب (الذكاء الاصطناعي، حق الرفض)'],
  'Demander au patient': ['Ask the patient', 'اسأل المريض'],
  'Ordonnance du patient (PDF)': ['Patient prescription (PDF)', 'وصفة المريض (PDF)'],
  'Texte cité par le juriste': ['Text cited by the legal agent', 'النص الذي استشهد به الوكيل القانوني'],
  'Ouvrir la source officielle': ['Open the official source', 'فتح المصدر الرسمي'],
  'Extrait exact': ['Exact quote', 'الاقتباس الحرفي'],
  'Résumé': ['Summary', 'ملخص'],
  'Langue': ['Language', 'اللغة'],
};
const tr = (fr: string) => (LANGUE_UI === "fr" ? fr : (TRAD[fr]?.[LANGUE_UI === "en" ? 0 : 1] ?? fr));

// ------------------------------------------------------------------ displayed vocabulary
const FAITS: Record<string, string> = {
  sexe: "Sexe", age: "Âge", symptome: "Motif", douleur: "Douleur", localisation_douleur: "Siège de la douleur",
  intensite_douleur: "Intensité de la douleur", nausees: "Nausées", fievre: "Fièvre", grossesse: "Grossesse",
  allergies: "Allergies", traitements_en_cours: "Traitements en cours", moyen_communication: "Communication",
  informe_usage_ia: "Informé de l'usage de l'IA", consentement_traitement: "Accord pour le traitement", urgence: "Urgence signalée",
  antecedents: "Antécédents (texte libre)", maladies_connues: "Maladies repérées", autres_informations: "Autres informations",
  poids: "Poids", maladie_renale: "Maladie rénale", maladie_hepatique: "Maladie du foie", ulcere_digestif: "Ulcère digestif",
  anticoagulant: "Sous anticoagulant", maladie_cardiaque: "Maladie cardiaque", allaitement: "Allaitement",
  medicaments_declares: "Médicaments déclarés par le patient", duree_symptomes: "Depuis",
};
const ORDRE_FAITS = Object.keys(FAITS);
// Missing information before a prescription: direct answer of the doctor, or question to the patient (translated, validated)
const REMPLIR: Record<string, { valeurs: [string, unknown][]; question?: string }> = {
  allergies: { valeurs: [["Aucune", "aucune"]], question: "Êtes-vous allergique à un médicament ?" },
  traitements_en_cours: { valeurs: [["Aucun", "aucun"]], question: "Prenez-vous des médicaments en ce moment ?" },
  grossesse: { valeurs: [["Pas enceinte", false], ["Enceinte", true]], question: "Êtes-vous enceinte ?" },
};
const CLES_REPONSE: Record<string, string> = {
  grossesse: "Grossesse", fievre: "Fièvre", douleur: "Douleur", nausees: "Nausées", consentement_traitement: "Accord pour le traitement",
  allergies: "Allergies (oui / non)", traitements_en_cours: "Traitements en cours (oui / non)", informe_usage_ia: "Accord pour l'aide de l'IA",
};
const AGENTS: Record<string, { nom: string; icone: ReactNode }> = {
  traducteur: { nom: "Traducteur", icone: <Languages size={15} /> },
  assistant: { nom: "Assistant médical", icone: <Stethoscope size={15} /> },
  juriste: { nom: "Juriste", icone: <Scale size={15} /> },
  coordinateur: { nom: "Coordinateur", icone: <Network size={15} /> },
  medecin: { nom: "Médecin", icone: <UserRound size={15} /> },
  autorite_sante: { nom: "Autorité de santé", icone: <Building2 size={15} /> },
  hopital: { nom: "Hôpital", icone: <Building2 size={15} /> },
  cellule_crise: { nom: "Cellule de crise", icone: <Building2 size={15} /> },
  document: { nom: "Document du patient", icone: <FileText size={15} /> },
};
const agent = (cle: string) => AGENTS[cle] ?? { nom: cle.charAt(0).toUpperCase() + cle.slice(1).replace(/_/g, " "), icone: <Bot size={15} /> };

function valeur(cle: string, v: unknown): string {
  if (v === true) return "Oui";
  if (v === false) return "Non";
  if (cle === "sexe") return v === "F" ? "Femme" : v === "M" ? "Homme" : String(v);
  if (cle === "age") return `${v} ans`;
  if (cle === "poids") return `${v} kg`;
  if (Array.isArray(v)) return v.join(", ");
  if (cle === "intensite_douleur") return `${v} sur 10`;
  if (cle === "moyen_communication" && v === "pictogrammes") return "Pictogrammes";
  const t = String(v ?? "");
  return t.charAt(0).toUpperCase() + t.slice(1);
}
/** Agent message → header ("#10 BLOCKED …"), text, references in brackets and suggested next step. */
function analyserMessage(t: string) {
  const refs = [...t.matchAll(/\[([^\]]+)\]/g)].map((m) => m[1]);
  let texte = t.replace(/\s*\[[^\]]+\]/g, "").trim();
  let piste: string | null = null;
  const i = texte.search(/\s*Piste conforme\s*:/);
  if (i >= 0) { piste = texte.slice(i).replace(/^\s*Piste conforme\s*:\s*/, ""); texte = texte.slice(0, i); }
  let entete: string | null = null;
  const m = texte.match(/^((?:Prescription|Message au patient|Demande de partage)?\s*#\d+[^:]*?)\s*:\s*/);
  if (m) { entete = m[1]; texte = texte.slice(m[0].length); }
  return { entete, texte: texte.charAt(0).toUpperCase() + texte.slice(1), refs, piste };
}
const nomMedicament = (m?: string | null) => (m ? m.charAt(0).toUpperCase() + m.slice(1).replace(/_/g, " ") : "");

// ================================================================== screen
export default function EcranMedecin() {
  const jeton = useMemo(jetonMedecin, []);
  const notifier = useNotifier();
  const { donnees: vue, erreur, rafraichir } = useSondage(() => lire<VueMedecin>("/api/medecin", jeton));
  const [occupe, setOccupe] = useState(false);
  const [medecin, setMedecin] = useState("DR-001");
  const [dialogue, setDialogue] = useState<null | { type: "retirer" | "maintenir" | "reinit"; id?: number }>(null);
  const [edition, setEdition] = useState<null | { id: number; pictos: string[] }>(null);
  const [brouillon, setBrouillon] = useState<null | { texte: string; n: number }>(null);

  const poster = useCallback(async (url: string, corps: object = {}, silencieux = false) => {
    if (!silencieux) setOccupe(true);
    try {
      const j = await envoyer<{ retour?: string; description?: string }>(url, corps, jeton);
      const msg = j.retour?.replace(/^[✔✖⚑]\s*/, "") || (j.description ? `Étape : ${j.description}` : "");
      if (msg && !silencieux) notifier(msg, /^✖/.test(j.retour ?? ""));
      await rafraichir();
      return j;
    } catch (e) {
      notifier(e instanceof ErreurApi ? e.message : "Le serveur ne répond pas. Vérifiez qu'il tourne toujours.", true);
      return null;
    } finally {
      if (!silencieux) setOccupe(false);
    }
  }, [jeton, notifier, rafraichir]);

  const [loi, setLoi] = useState<string | null>(null);
  if (erreur instanceof ErreurApi && erreur.statut === 403) return <AccesRefuse />;
  if (!vue) return <Chargement erreur={!!erreur} />;
  LANGUE_UI = (vue.langue as "fr" | "en" | "ar") || "fr";

  const urgence = vue.etat.urgence?.valeur === true;
  return (
    <ContexteLangue.Provider value={LANGUE_UI}>
    <ContexteLoi.Provider value={setLoi}>
    <div className="flex min-h-dvh flex-col xl:h-dvh" dir={LANGUE_UI === "ar" ? "rtl" : undefined}>
      <BarreHaute vue={vue} jeton={jeton} medecin={medecin} setMedecin={setMedecin} onReinit={() => setDialogue({ type: "reinit" })}
        onLangue={(l) => poster("/api/medecin/langue", { langue: l })} />
      {urgence && (
        <div id="urgence" role="alert" className="flex items-center gap-3 bg-danger px-4 py-2.5 text-white sm:px-6">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white/15"><Siren size={18} /></span>
          <p className="flex-1 text-sm"><b className="font-semibold">Urgence signalée par le patient.</b> Il a appuyé sur le bouton d'urgence : prenez-le en charge en priorité.
            Son écran lui indique que vous êtes prévenu.</p>
          <Bouton id="urgencePriseEnCharge" taille="sm" variante="secondary" disabled={occupe} icone={<Check size={14} />}
            onClick={() => poster("/api/medecin/urgence_prise_en_charge", { medecin })}>{tr('Pris en charge')}</Bouton>
        </div>
      )}
      {vue.demo.actif && <BarreDemo vue={vue} occupe={occupe} onSuivant={() => poster("/api/demo/suivant")} />}

      <main key={vue.session} className="grid flex-1 grid-cols-[minmax(0,1fr)] gap-4 p-4 sm:p-5 lg:grid-cols-[300px_minmax(0,1fr)] xl:min-h-0 xl:grid-cols-[300px_minmax(0,1fr)_420px] 2xl:grid-cols-[340px_minmax(0,1fr)_460px]">
        <div className="flex flex-col gap-4 xl:min-h-0 xl:overflow-y-auto barre-fine">
          <DossierPatient vue={vue} occupe={occupe} poster={poster} />
        </div>
        <Conversation vue={vue} occupe={occupe} poster={poster} medecin={medecin} brouillon={brouillon}
          onReformuler={(texte) => setBrouillon((b) => ({ texte, n: (b?.n ?? 0) + 1 }))}
          onRetirer={(id) => setDialogue({ type: "retirer", id })} onModifier={(id, pictos) => setEdition({ id, pictos })} />
        <div className="lg:col-span-2 xl:col-span-1 xl:min-h-0">
          <Inspecteur vue={vue} occupe={occupe} poster={poster} medecin={medecin}
            onMaintenir={(id) => setDialogue({ type: "maintenir", id })} />
        </div>
      </main>

      <DialogueTexte ouvert={dialogue?.type === "retirer"} titre="Retirer ce message de l'écran du patient ?"
        description="Le patient ne le verra plus. Le journal garde le message et son retrait, avec votre nom."
        libelle="Raison (facultatif)" defaut="Message erroné" action="Retirer de l'écran du patient" variante="danger"
        onFermer={() => setDialogue(null)}
        onValider={(raison) => { poster("/api/medecin/retirer", { decision_id: dialogue?.id, raison, medecin }); setDialogue(null); }} />
      <DialogueTexte ouvert={dialogue?.type === "maintenir"} titre="Maintenir la prescription"
        description="Le juriste demande une révision. Vous pouvez maintenir votre décision par écrit : votre nom et votre justification sont enregistrés dans le journal."
        libelle="Justification médicale" defaut="" action="Maintenir et signer" variante="primary"
        onFermer={() => setDialogue(null)}
        onValider={(justification) => { poster("/api/medecin/maintenir", { decision_id: dialogue?.id, justification, medecin }); setDialogue(null); }} />
      {edition && <EditeurPictos initial={edition.pictos} onFermer={() => setEdition(null)}
        onEnregistrer={(pictos) => { poster("/api/medecin/pictogrammes", { decision_id: edition.id, pictogrammes: pictos, medecin }); setEdition(null); }} />}
      <Dialogue ouvert={dialogue?.type === "reinit"} titre="Démarrer une nouvelle consultation ?"
        description="Le dossier, la conversation et le journal actuels sont remplacés. L'écran patient repart de zéro."
        onFermer={() => setDialogue(null)}
        actions={<>
          <Bouton onClick={() => setDialogue(null)}>{tr('Annuler')}</Bouton>
          <Bouton id="confirmerReinit" data-defaut variante="primary" icone={<RotateCcw size={15} />}
            onClick={() => { setDialogue(null); poster("/api/reinitialiser"); }}>{tr('Nouvelle consultation')}</Bouton>
        </>} />
      {loi && <TexteLoi q={loi} jeton={jeton} onFermer={() => setLoi(null)} />}
    </div>
    </ContexteLoi.Provider>
    </ContexteLangue.Provider>
  );
}

// ------------------------------------------------------------------ patient documents
const TYPES_DOC: [string, string][] = [["ordonnance", "Ordonnance (même manuscrite)"], ["facture", "Facture de pharmacie"],
  ["traitement", "Boîte ou notice de médicament"], ["radio", "Radiographie, imagerie"], ["analyse", "Résultat d'analyse"],
  ["compte_rendu", "Compte rendu médical"], ["autre", "Autre"]];

function DocumentsPatient({ vue, occupe, poster }: { vue: VueMedecin; occupe: boolean; poster: Poster }) {
  const jeton = useMemo(jetonMedecin, []);
  const [type, setType] = useState("ordonnance");
  const [envoi, setEnvoi] = useState(false);
  const docs: DocumentPatient[] = vue.documents ?? [];
  const ajouter = async (fichiers: FileList | null) => {
    if (!fichiers) return;
    setEnvoi(true);
    for (const f of Array.from(fichiers)) {
      const contenu = await new Promise<string>((ok, ko) => { const r = new FileReader(); r.onload = () => ok(String(r.result)); r.onerror = ko; r.readAsDataURL(f); });
      await poster("/api/medecin/document", { nom: f.name, type, mime: f.type || "application/octet-stream", contenu });
    }
    setEnvoi(false);
  };
  const ouvrir = async (d: DocumentPatient) => {
    const r = await fetch(`/api/medecin/document?id=${d.id}`, { headers: { "X-Jeton": jeton } });
    if (r.ok) window.open(URL.createObjectURL(await r.blob()), "_blank", "noopener");
  };
  const confirmer = (d: DocumentPatient) => {
    const donnees: Record<string, unknown> = {};
    if (d.extraction.medicaments.length) donnees.medicaments_declares = d.extraction.medicaments.map((m) => m.nom).join(", ");
    if (d.extraction.maladies.length) donnees.antecedents = d.extraction.maladies.join(", ");
    if (d.extraction.allergies.length) donnees.allergies = d.extraction.allergies.join(", ");
    poster("/api/medecin/faits", { donnees });
  };
  return (
    <Panneau titre="Documents du patient" aide="Photo d'ordonnance (même manuscrite), facture, boîte de médicament, radio, analyse… Les agents la lisent ; ce qu'ils en tirent reste « à confirmer ».">
      <div className="flex flex-col gap-2.5">
        <div className="flex gap-2">
          <select aria-label="Type de document" value={type} onChange={(e) => setType(e.target.value)} className={cx(champ, "h-9 flex-1")}>
            {TYPES_DOC.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <label className={cx("inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg bg-brand px-3 text-sm font-medium text-white", (occupe || envoi) && "opacity-50")}>
            <FileText size={15} />{envoi ? "Envoi…" : "Ajouter"}
            <input id="documentPatient" type="file" accept="image/*,application/pdf,text/plain" capture="environment" multiple className="sr-only"
              disabled={occupe || envoi} onChange={(e) => { ajouter(e.target.files); e.target.value = ""; }} />
          </label>
        </div>
        <p className="text-2xs text-ink-muted">Une photo est envoyée au modèle en ligne pour être lue : patients fictifs uniquement. Sans modèle, elle est jointe au dossier et vous la lisez.</p>
        {docs.slice().reverse().map((d) => (
          <article key={d.id} className="rounded-lg border border-line p-2.5 text-xs" data-document={d.id}>
            <div className="flex items-start justify-between gap-2">
              <button className="text-left font-medium text-ink underline decoration-dotted underline-offset-2" onClick={() => ouvrir(d)}>{d.nom}</button>
              <Pastille ton={d.extraction.statut === "lu" ? "ok" : d.extraction.statut === "en_cours" ? "action" : "warn"}>
                {d.extraction.statut === "lu" ? "Lu" : d.extraction.statut === "en_cours" ? "Lecture…" : "Non lu"}</Pastille>
            </div>
            <p className="mt-1 text-ink-muted">
              {d.auteur === "patient" && <span className="mr-1 rounded bg-action-50 px-1 font-medium text-action">envoyé par le patient</span>}
              {TYPES_DOC.find(([k]) => k === d.type)?.[1]}{d.extraction.par ? ` · lu par ${d.extraction.par}` : ""}</p>
            {d.extraction.resume && <p className="mt-1 text-ink-soft">{d.extraction.resume}</p>}
            {d.extraction.medicaments.length > 0 && <p className="mt-1 text-ink"><b>Médicaments :</b> {d.extraction.medicaments.map((m) => `${nomMedicament(m.nom)} ${m.dose} ${m.posologie}`.trim()).join(" ; ")}</p>}
            {d.extraction.maladies.length > 0 && <p className="mt-0.5 text-ink"><b>Maladies :</b> {d.extraction.maladies.join(", ")}</p>}
            {d.extraction.allergies.length > 0 && <p className="mt-0.5 text-ink"><b>Allergies :</b> {d.extraction.allergies.join(", ")}</p>}
            {d.extraction.statut === "lu" && (d.extraction.medicaments.length + d.extraction.maladies.length + d.extraction.allergies.length) > 0 && (
              <div className="mt-2 flex justify-end">
                <Bouton taille="sm" variante="secondary" data-confirmer-document={d.id} disabled={occupe} icone={<Check size={14} />} onClick={() => confirmer(d)}>Confirmer dans la fiche</Bouton>
              </div>
            )}
          </article>
        ))}
      </div>
    </Panneau>
  );
}

// ------------------------------------------------------------------ law texts cited by the jurist
const ContexteLoi = createContext<(q: string) => void>(() => {});

/** Clickable references ("A ; B"): the doctor reads the cited text. */
function Refs({ texte, className }: { texte: string; className?: string }) {
  const ouvrir = useContext(ContexteLoi);
  const parts = [...new Set((texte || "").split(" ; ").map((x) => x.trim()).filter(Boolean))];
  return (
    <span className={className}>
      {parts.map((r, i) => {
        const lisible = !/^(Garde-fou|Lecture|MEDIMCOM|Sûreté)/.test(r) && r !== "-";
        return (
          <span key={i}>
            {i > 0 && " ; "}
            {lisible ? <button type="button" data-ref={r} onClick={() => ouvrir(r)} className="text-left underline decoration-dotted underline-offset-2 hover:text-action">{r}</button> : r}
          </span>
        );
      })}
    </span>
  );
}

type Fiche = { id: string; titre: string; ref: string; texte: string; citation?: string; base?: string; source?: string; lien?: string;
  verification?: string; reference: string; extraits: { citation: string; lien?: string }[] };

function TexteLoi({ q, jeton, onFermer }: { q: string; jeton: string; onFermer: () => void }) {
  const [f, setF] = useState<Fiche | null>(null);
  const [erreur, setErreur] = useState(false);
  useEffect(() => { lire<Fiche>(`/api/fiche?q=${encodeURIComponent(q)}`, jeton).then(setF).catch(() => setErreur(true)); }, [q, jeton]);
  return (
    <Dialogue ouvert titre={tr("Texte cité par le juriste")} description={f?.reference ?? q} onFermer={onFermer}
      actions={<>
        {f?.lien && <a href={f.lien} target="_blank" rel="noopener noreferrer" className="inline-flex h-9 items-center rounded-lg px-3.5 text-sm font-medium text-action hover:bg-action-50">{tr("Ouvrir la source officielle")}</a>}
        <Bouton onClick={onFermer}>OK</Bouton>
      </>}>
      {erreur ? <p className="text-sm text-ink-muted">Référence introuvable dans la base.</p> : !f ? <p className="text-sm text-ink-muted">…</p> : (
        <div className="flex flex-col gap-3 text-sm" data-fiche={f.id}>
          <p className="font-semibold text-ink">{f.titre} <span className="font-normal text-ink-muted">({f.ref})</span></p>
          <div><p className="text-xs font-medium text-ink-muted">{tr("Résumé")}</p><p className="text-ink-soft" lang="en">{f.texte}</p></div>
          {f.citation && <div><p className="text-xs font-medium text-ink-muted">{tr("Extrait exact")}</p>
            <blockquote className="border-l-4 border-action/40 pl-3 italic text-ink" lang="en">« {f.citation} »</blockquote></div>}
          {f.extraits.map((x, i) => <blockquote key={i} className="border-l-4 border-line pl-3 text-xs text-ink-soft">{x.citation}</blockquote>)}
          <p className="text-xs text-ink-muted">{f.source} · {f.verification} · {f.base}</p>
        </div>
      )}
    </Dialogue>
  );
}

type Poster = (url: string, corps?: object, silencieux?: boolean) => Promise<unknown>;

// ------------------------------------------------------------------ top bar
function BarreHaute({ vue, jeton, medecin, setMedecin, onReinit, onLangue }:
  { vue: VueMedecin; jeton: string; medecin: string; setMedecin: (m: string) => void; onReinit: () => void; onLangue: (l: string) => void }) {
  const intact = vue.journal === "Journal intact";
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5 sm:px-6">
        <div className="flex items-center gap-3">
          <Marque />
          <span className="hidden h-5 w-px bg-line xl:block" />
          <div className="hidden xl:block">
            <p className="text-sm font-semibold leading-tight text-ink">{tr('Consultation')}</p>
            <p className="text-2xs text-ink-muted tabulaire">Session {vue.session}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Pastille ton={intact ? "ok" : "danger"} icone={intact ? <ShieldCheck size={13} /> : <ShieldAlert size={13} />}>
            <span id="journal" title="Chaque action est enregistrée dans un journal chaîné : toute modification après coup est détectée.">
              {intact ? `Journal intact, ${vue.lignes} entrées` : vue.journal}
            </span>
          </Pastille>
          {vue.modele && !vue.modele.disponible ? (<>
            <Pastille ton="warn" icone={<WifiOff size={13} />}>
              <span id="modeleIndisponible" title={`${vue.modele.modele} : ${vue.modele.message}. L'assistant continue en mode règles (veille clinique) et réessaie le modèle toutes les 90 s.`}>
                {vue.modele.modele} indisponible : assistant en mode règles
              </span>
            </Pastille>
            {/* the cause must be readable without hovering: it says what to do (key, quota, Internet, certificates…) */}
            <span id="causeModele" className="max-w-xl text-xs text-warn">Cause : {vue.modele.message}</span>
          </>) : (
            <Pastille ton="brand" icone={<Bot size={13} />}>
              <span id="modeAgents" title="Les agents (traducteur, juriste, assistant…) sont ceux de MEDIMCOM IA, avec leurs règles et leurs garde-fous. Le modèle de langage en ligne n'est qu'un outil de l'assistant : il ne décide rien seul.">
                {vue.modele ? `Agents MEDIMCOM · modèle ${vue.modele.modele} (${vue.modele.fournisseur || "xAI"})` : "Agents MEDIMCOM · règles écrites, sans modèle en ligne"}
              </span>
            </Pastille>
          )}
          {vue.reflexion_en_cours ? (
            <Pastille ton="brand" icone={<Loader2 size={13} className="animate-spin" />}>
              <span id="reflexion" title="L'assistant interroge le modèle en ligne en arrière-plan. Vous pouvez continuer : vos clics passent avant lui.">
                L'assistant réfléchit…{vue.duree_modele ? ` (dernière réponse : ${vue.duree_modele.toFixed(1).replace(".", ",")} s)` : ""}
              </span>
            </Pastille>
          ) : null}
          <Pastille ton="warn" icone={<Lock size={12} />}>{tr('Données fictives')}</Pastille>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-1">
          <a href="/patient" target="_blank" rel="noopener" title="Ouvrir l'écran patient" className="inline-flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium text-ink-soft hover:bg-canvas hover:text-ink">
            <MonitorSmartphone size={16} /><span className="hidden 2xl:inline">{tr('Écran patient')}</span>
          </a>
          <a href={`/journal?jeton=${encodeURIComponent(jeton)}`} target="_blank" rel="noopener" title="Journal lisible" className="inline-flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium text-ink-soft hover:bg-canvas hover:text-ink">
            <ScrollText size={16} /><span className="hidden 2xl:inline">{tr('Journal')}</span>
          </a>
          <a href="/credits" target="_blank" rel="noopener" title="Crédits des pictogrammes" className="inline-flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium text-ink-soft hover:bg-canvas hover:text-ink">
            <FileText size={16} /><span className="hidden 2xl:inline">{tr('Crédits')}</span>
          </a>
          <div role="group" aria-label={tr("Langue")} className="flex rounded-lg bg-canvas p-0.5 ring-1 ring-line" id="langueMedecin">
            {(["fr", "en", "ar"] as const).map((l) => (
              <button key={l} data-langue={l} aria-pressed={LANGUE_UI === l} onClick={() => onLangue(l)}
                className={cx("h-8 rounded-md px-2.5 text-xs font-semibold", LANGUE_UI === l ? "bg-brand text-white" : "text-ink-soft hover:bg-surface")}>
                {l === "ar" ? "عربي" : l.toUpperCase()}
              </button>
            ))}
          </div>
          <span className="mx-1 hidden h-5 w-px bg-line md:block" />
          <label className="relative flex items-center">
            <span className="sr-only">Médecin connecté</span>
            <UserRound size={15} className="pointer-events-none absolute left-2.5 text-ink-muted" />
            <select id="medecin" value={medecin} onChange={(e) => setMedecin(e.target.value)}
              className={cx(champ, "h-9 w-auto appearance-none pl-8 pr-8")}>
              {Object.entries(vue.prescripteurs).map(([k, n]) => <option key={k} value={k}>{n}</option>)}
            </select>
            <ChevronDown size={15} className="pointer-events-none absolute right-2.5 text-ink-muted" />
          </label>
          <Bouton id="reinit" onClick={onReinit} icone={<RotateCcw size={15} />}>{tr('Nouvelle consultation')}</Bouton>
        </div>
      </div>
    </header>
  );
}

function BarreDemo({ vue, occupe, onSuivant }: { vue: VueMedecin; occupe: boolean; onSuivant: () => void }) {
  const { etape, total, titre, prochaine } = vue.demo;
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-action-100 bg-action-50 px-4 py-2 sm:px-6">
      <Pastille ton="action" icone={<Play size={12} />}>Démonstration</Pastille>
      <p className="min-w-0 flex-1 truncate text-sm text-ink-soft"><span className="font-medium text-ink">{titre}</span></p>
      <div className="flex items-center gap-3">
        <div className="hidden w-32 sm:block" aria-hidden>
          <div className="h-1.5 rounded-full bg-action-100"><div className="h-1.5 rounded-full bg-action transition-all" style={{ width: `${(100 * etape) / Math.max(total, 1)}%` }} /></div>
        </div>
        <span className="text-xs text-ink-muted tabulaire">Étape {etape} sur {total}</span>
        <span className="hidden max-w-[320px] truncate text-xs text-ink-muted md:inline" title={prochaine ?? ""}>{prochaine ? `Ensuite : ${prochaine}` : "Scénario terminé"}</span>
        <Bouton id="demoSuivant" taille="sm" variante="primary" disabled={occupe || !prochaine} onClick={onSuivant}>Étape suivante</Bouton>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ patient record
function DossierPatient({ vue, occupe, poster }: { vue: VueMedecin; occupe: boolean; poster: Poster }) {
  const e = vue.etat;
  const identite = [e.sexe && valeur("sexe", e.sexe.valeur), e.age && valeur("age", e.age.valeur)].filter(Boolean).join(", ");
  const faits = Object.entries(e).filter(([k]) => k !== "urgence")
    .sort(([a], [b]) => (ORDRE_FAITS.indexOf(a) + 1 || 99) - (ORDRE_FAITS.indexOf(b) + 1 || 99));
  const aConfirmer = faits.filter(([, f]) => !f.confirme).length;
  return (
    <>
      <Panneau corps="p-0">
        <div className="flex items-center gap-3 px-4 pb-3 pt-4">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-brand-50 text-brand"><UserRound size={22} /></div>
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold text-ink">{tr('Patient')}</h2>
            <p className="text-sm text-ink-muted">{identite || "Identité non renseignée"}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5 px-4 pb-3">
          {e.moyen_communication?.valeur === "pictogrammes" && <Pastille ton="action" icone={<Hand size={12} />}>Communique en pictogrammes</Pastille>}
          {e.informe_usage_ia?.valeur === true && <Pastille ton="ok" icone={<Check size={12} />}>Informé de l'IA</Pastille>}
          {e.grossesse?.valeur === true && <Pastille ton="review">Enceinte</Pastille>}
          {e.allergies && e.allergies.valeur !== "aucune" && <Pastille ton="danger" icone={<AlertTriangle size={12} />}>Allergie : {String(e.allergies.valeur)}</Pastille>}
        </div>
        <div className="border-t border-line">
          <div className="flex items-center justify-between px-4 pb-1 pt-3">
            <h3 className="text-[13px] font-semibold text-ink">{tr('Informations cliniques')}</h3>
            {aConfirmer > 0 && <span className="text-xs text-warn">{aConfirmer} à confirmer</span>}
          </div>
          {faits.length ? (
            <dl id="etat" className="px-4 pb-3">
              {faits.map(([k, f]) => (
                <div key={k} className="flex items-baseline justify-between gap-3 border-b border-line/70 py-2 last:border-0" title={f.source}>
                  <dt className="text-[13px] text-ink-muted">{FAITS[k] ?? k.replace(/_/g, " ")}</dt>
                  <dd className="flex items-center gap-1.5 text-right text-[13px] font-medium text-ink">
                    {valeur(k, f.valeur)}
                    {f.confirme ? <Check size={13} className="text-ok" aria-label="confirmé" /> : <span className="rounded bg-warn-50 px-1 text-2xs font-medium text-warn">à confirmer</span>}
                  </dd>
                </div>
              ))}
            </dl>
          ) : <Vide titre="Aucune information pour l'instant" texte="Remplissez la fiche ci-dessous ou posez une question au patient." />}
        </div>
      </Panneau>
      <FichePatient occupe={occupe} poster={poster} />
      <DocumentsPatient vue={vue} occupe={occupe} poster={poster} />
    </>
  );
}

function FichePatient({ occupe, poster }: { occupe: boolean; poster: Poster }) {
  // Nothing is mandatory: the doctor fills in what they know, in free text if needed; the agents extract the useful facts.
  const [f, setF] = useState({ sexe: "", age: "", poids: "", grossesse: "", allergies: "", traitements: "", antecedents: "", autres: "", pictos: true, ia: false });
  const [libres, setLibres] = useState<{ cle: string; valeur: string }[]>([]);
  const maj = (k: keyof typeof f) => (v: string | boolean) => setF((x) => ({ ...x, [k]: v }));
  // AUTOMATIC saving (feedback of 9 November: a record filled in but not saved made the jurist say "missing
  // information"): when leaving each field, and at once for lists and check boxes. Only what changed is sent,
  // without an on-screen message; the state is shown under the record.
  const sauve = useRef<Record<string, unknown>>({});
  const [etatSauve, setEtatSauve] = useState<"" | "modifie" | "en_cours" | "ok" | "erreur">("");
  const majEtSauver = (k: keyof typeof f) => (v: string | boolean) => { const y = { ...f, [k]: v }; setF(y); void enregistrer(y); };
  const changer = (k: keyof typeof f) => (v: string | boolean) => { maj(k)(v); setEtatSauve("modifie"); };
  const enregistrer = async (x: typeof f = f, tout = false) => {
    const donnees = construire(x);
    const diff = Object.fromEntries(Object.entries(donnees).filter(([k, v]) =>
      v !== "" && v !== undefined && (tout || JSON.stringify(sauve.current[k]) !== JSON.stringify(v))));
    if (!Object.keys(diff).length) { setEtatSauve((e) => (e === "modifie" ? "ok" : e)); return; }
    setEtatSauve("en_cours");
    const r = await poster("/api/medecin/faits", { donnees: diff }, !tout);
    if (r) { Object.assign(sauve.current, diff); setEtatSauve("ok"); } else setEtatSauve("erreur");
  };
  function construire(f: { sexe: string; age: string; poids: string; grossesse: string; allergies: string; traitements: string; antecedents: string; autres: string; pictos: boolean; ia: boolean }) {
    const donnees: Record<string, unknown> = {
      sexe: f.sexe, age: f.age, poids: f.poids ? Number(f.poids) : "", allergies: f.allergies.trim(), traitements_en_cours: f.traitements.trim(),
      antecedents: f.antecedents.trim(), autres_informations: f.autres.trim(),
      grossesse: f.grossesse === "oui" ? true : f.grossesse === "non" ? false : "",
      moyen_communication: f.pictos ? "pictogrammes" : "", informe_usage_ia: f.ia || "",
    };
    for (const l of libres) if (l.cle.trim() && l.valeur.trim()) donnees[l.cle.trim().toLowerCase().replace(/\s+/g, "_")] = l.valeur.trim();
    return donnees;
  }
  const quitter = () => { void enregistrer(); };
  return (
    <Panneau titre="Fiche patient" aide="Tout est facultatif. Saisi par vous, enregistré comme information confirmée.">
      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-3 gap-2">
          <Champ libelle="Sexe" htmlFor="sexe">
            <select id="sexe" value={f.sexe} onChange={(e) => majEtSauver("sexe")(e.target.value)} className={cx(champ, "h-9 px-2")}>
              <option value="">—</option><option value="F">Femme</option><option value="M">Homme</option>
            </select>
          </Champ>
          <Champ libelle="Âge" htmlFor="age">
            <input id="age" type="number" min={0} max={120} inputMode="numeric" value={f.age} onChange={(e) => changer("age")(e.target.value)} onBlur={quitter} className={cx(champ, "h-9 tabulaire")} placeholder="ans" />
          </Champ>
          <Champ libelle="Poids" htmlFor="poids">
            <input id="poids" type="number" min={0} max={400} inputMode="decimal" value={f.poids} onChange={(e) => changer("poids")(e.target.value)} onBlur={quitter} className={cx(champ, "h-9 tabulaire")} placeholder="kg" />
          </Champ>
        </div>
        {f.sexe !== "M" && (
          <Champ libelle="Grossesse" htmlFor="grossesse">
            <select id="grossesse" value={f.grossesse} onChange={(e) => majEtSauver("grossesse")(e.target.value)} className={cx(champ, "h-9")}>
              <option value="">Non renseignée</option><option value="non">Non</option><option value="oui">Oui</option>
            </select>
          </Champ>
        )}
        <Champ libelle="Maladies connues, antécédents" htmlFor="antecedents" aide="Texte libre, par exemple : diabète, HTA, insuffisance rénale, opéré de l'appendicite.">
          <textarea id="antecedents" rows={2} value={f.antecedents} onChange={(e) => changer("antecedents")(e.target.value)} onBlur={quitter} className={cx(champ, "resize-y py-2")} />
        </Champ>
        <Champ libelle="Allergies" htmlFor="allergies">
          <input id="allergies" value={f.allergies} onChange={(e) => changer("allergies")(e.target.value)} onBlur={quitter} className={cx(champ, "h-9")} placeholder="ou « aucune »" />
        </Champ>
        <Champ libelle="Traitements en cours" htmlFor="traitements">
          <input id="traitements" value={f.traitements} onChange={(e) => changer("traitements")(e.target.value)} onBlur={quitter} className={cx(champ, "h-9")} placeholder="ou « aucun »" />
        </Champ>
        <Champ libelle="Autres informations" htmlFor="autres" aide="Tout ce qui peut aider : contexte, mode de vie, entourage…">
          <textarea id="autres" rows={2} value={f.autres} onChange={(e) => changer("autres")(e.target.value)} onBlur={quitter} className={cx(champ, "resize-y py-2")} />
        </Champ>
        {libres.map((l, i) => (
          <div key={i} className="flex gap-2">
            <input aria-label="Renseignement" value={l.cle} placeholder="Renseignement (ex. tabac)" className={cx(champ, "h-9 w-2/5")}
              onChange={(e) => setLibres((x) => x.map((y, j) => (j === i ? { ...y, cle: e.target.value } : y)))} onBlur={quitter} />
            <input aria-label="Valeur" value={l.valeur} placeholder="Valeur" className={cx(champ, "h-9 flex-1")}
              onChange={(e) => setLibres((x) => x.map((y, j) => (j === i ? { ...y, valeur: e.target.value } : y)))} onBlur={quitter} />
            <button aria-label="Supprimer" onClick={() => setLibres((x) => x.filter((_, j) => j !== i))} className="px-1 text-ink-faint hover:text-danger"><X size={16} /></button>
          </div>
        ))}
        <button id="ajouterRenseignement" onClick={() => setLibres((x) => [...x, { cle: "", valeur: "" }])}
          className="self-start text-[13px] font-medium text-action hover:underline">+ Ajouter un renseignement</button>
        <div className="flex flex-col gap-2 pt-1">
          <Case id="pictos" coche={f.pictos} onChange={majEtSauver("pictos")}>Communique en pictogrammes</Case>
          <Case id="ia" coche={f.ia} onChange={majEtSauver("ia")}>Informé qu'une IA aide le médecin</Case>
        </div>
        <p id="etatFiche" role="status" className={cx("text-xs", etatSauve === "erreur" ? "text-danger" : etatSauve === "modifie" ? "text-warn" : "text-ink-muted")}>
          {etatSauve === "en_cours" ? "Enregistrement…" : etatSauve === "ok" ? "✓ Enregistré automatiquement : les agents l'utilisent déjà"
            : etatSauve === "modifie" ? "Modification en cours : enregistrée dès que vous quittez le champ"
            : etatSauve === "erreur" ? "Non enregistré : réessayez avec le bouton" : "Enregistrement automatique à la sortie de chaque champ"}
        </p>
        <Bouton id="faits" variante="secondary" disabled={occupe} className="w-full" onClick={() => enregistrer(f, true)}>{tr('Enregistrer la fiche')}</Bouton>
      </div>
    </Panneau>
  );
}

// ------------------------------------------------------------------ conversation
type Element = { v: number; ordre: number } & ({ genre: "echange"; e: Echange } | { genre: "decision"; d: Decision });

function Conversation({ vue, occupe, poster, medecin, brouillon, onReformuler, onRetirer, onModifier }:
  { vue: VueMedecin; occupe: boolean; poster: Poster; medecin: string; brouillon: null | { texte: string; n: number };
    onReformuler: (texte: string) => void; onRetirer: (id: number) => void; onModifier: (id: number, pictos: string[]) => void }) {
  const [voirMasques, setVoirMasques] = useState(false);
  const masques = vue.decisions.filter((d) => d.masque).length;
  const elements: Element[] = [
    ...vue.fil.map((e, i) => ({ genre: "echange" as const, e, v: e.v ?? i, ordre: i })),
    ...vue.decisions.filter((d) => voirMasques || !d.masque).map((d, i) => ({ genre: "decision" as const, d, v: d.v ?? 1e6 + d.id, ordre: 1e3 + i })),
  ].sort((a, b) => a.v - b.v || a.ordre - b.ordre);
  const enAttente = vue.decisions.filter((d) => d.type === "envoi_patient" && d.statut === "attente_validation").length;
  const nomMedecin = (id?: string | null) => (id && vue.prescripteurs[id]) || id || "";
  const fil = useRef<HTMLDivElement>(null);
  const [attente, setAttente] = useState<null | { texte: string; n: number }>(null);
  useEffect(() => { if (attente && vue.decisions.length > attente.n) setAttente(null); }, [vue.decisions.length, attente]);
  const nombre = elements.length + vue.decisions.filter((d) => d.statut === "attente_validation").length;
  useEffect(() => {                       // new element: scroll to the bottom of the thread, like a messaging app
    const f = fil.current;
    if (f) f.scrollTo({ top: f.scrollHeight, behavior: "smooth" });
  }, [nombre]);
  return (
    <section className="flex min-h-[560px] flex-col rounded-xl bg-surface shadow-panel xl:min-h-0">
      <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
        <div>
          <h2 className="text-[15px] font-semibold text-ink">{tr('Conversation')}</h2>
          <p className="text-xs text-ink-muted">{tr('Vos messages sont traduits en pictogrammes. Rien ne part sans votre validation.')}</p>
        </div>
        <div className="flex items-center gap-2">
          {vue.etat.informe_usage_ia?.valeur === false ? (
            <Pastille ton="danger" icone={<AlertTriangle size={12} />}><span id="refusIA">Le patient refuse l'aide de l'IA</span></Pastille>
          ) : vue.etat.informe_usage_ia?.valeur !== true && !vue.questions.some((q) => q.cle === "informe_usage_ia" && ["en_attente", "posee"].includes(q.statut)) && (
            <Bouton id="informerIA" taille="sm" variante="ghost" disabled={occupe} icone={<Info size={14} />}
              title="Message d'accueil en pictogrammes : un ordinateur aide à traduire, le médecin décide, le patient peut refuser. Sa réponse est enregistrée."
              onClick={() => poster("/api/medecin/accueil")}>{tr("Informer le patient de l'IA")}</Bouton>
          )}
          {masques > 0 && (
            <button className="text-xs text-ink-muted underline-offset-2 hover:text-ink hover:underline" onClick={() => setVoirMasques((x) => !x)}>
              {voirMasques ? "Cacher" : "Afficher"} {masques} message{masques > 1 ? "s" : ""} masqué{masques > 1 ? "s" : ""}
            </button>
          )}
          {enAttente > 0 && <Pastille ton="action">{enAttente} à valider</Pastille>}
        </div>
      </header>
      <div id="fil" ref={fil} className="flex flex-1 flex-col gap-4 overflow-y-auto px-5 py-5 barre-fine">
        {elements.length === 0 && !vue.questions.some((q) => q.cle === "informe_usage_ia") && (
          <div className="flex flex-col items-center gap-3">
            <Vide icone={<MessageSquareText size={20} />} titre="La consultation commence"
              texte="Commencez par informer le patient qu'un ordinateur vous aide à traduire et qu'il peut refuser ; puis posez votre première question." />
            <Bouton id="accueil" variante="primary" disabled={occupe} icone={<Hand size={15} />} onClick={() => poster("/api/medecin/accueil")}>
              Message d'accueil (IA, droit de refuser)</Bouton>
          </div>
        )}
        {elements.map((x) => x.genre === "echange"
          ? <ElementEchange key={`e${x.ordre}`} e={x.e} />
          : <ElementDecision key={`d${x.d.id}`} d={x.d} occupe={occupe} nomMedecin={nomMedecin}
              parAssistant={Boolean(x.d.source_question && vue.questions.find((q) => q.id === x.d.source_question)?.auteur !== "medecin")}
              onValider={(confirme?: boolean) => poster("/api/medecin/valider", { decision_id: x.d.id, medecin, confirme_contexte: Boolean(confirme) })}
              onAnnuler={() => poster("/api/medecin/rejeter", { decision_id: x.d.id, raison: "annulé par le médecin" })}
              onReformuler={async () => {
                if (x.d.statut === "attente_validation") await poster("/api/medecin/rejeter", { decision_id: x.d.id, raison: "à reformuler" });
                onReformuler(x.d.texte ?? "");
              }}
              onRetirer={() => onRetirer(x.d.id)} onMasquer={() => poster("/api/medecin/masquer", { decision_id: x.d.id })}
              onModifier={() => onModifier(x.d.id, x.d.pictogrammes ?? [])} />)}
      </div>
      {attente && (
        <div className="mx-5 mb-3 flex items-center gap-2 self-end rounded-2xl border border-dashed border-action/50 bg-action-50 px-3.5 py-2 text-[13px] text-action" role="status">
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-action border-t-transparent" />
          « {attente.texte} » : traduction en pictogrammes en cours…
        </div>
      )}
      <Compositeur vue={vue} occupe={occupe} poster={poster} brouillon={brouillon} onEnvoye={(t) => setAttente({ texte: t, n: vue.decisions.length })} />
    </section>
  );
}

function ElementEchange({ e }: { e: Echange }) {
  if (e.pictogrammes?.length) {
    return (
      <div className="flex max-w-[92%] gap-3 self-start">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-canvas text-ink-soft ring-1 ring-line"><Hand size={15} /></div>
        <div className="min-w-0">
          <p className="mb-1 text-xs text-ink-muted"><span className="font-medium text-ink-soft">{tr('Patient')}</span>{e.en_reponse_a ? ` répond à « ${e.en_reponse_a} »` : ""}</p>
          <div className="rounded-2xl rounded-tl-md border border-line bg-surface p-3 shadow-tile">
            <div className="flex flex-wrap gap-2">{e.pictogrammes.map((p, i) => <Picto key={i} id={p} taille={60} legende />)}</div>
          </div>
          {e.interpretation && <p className="mt-1.5 text-[13px] text-ink-soft">Compris comme <span className="font-medium text-ink">« {e.interpretation} »</span></p>}
        </div>
      </div>
    );
  }
  const a = agent(e.auteur);
  const donnees = Object.entries(e.donnees ?? {});
  return (
    <div className="flex items-start gap-3 rounded-xl bg-canvas/70 px-3.5 py-3">
      <span className="mt-0.5 text-ink-muted">{a.icone}</span>
      <div className="min-w-0 text-[13px]">
        <p className="text-ink-soft"><span className="font-medium text-ink">{a.nom}</span> {e.auteur === "medecin" ? "a mis à jour la fiche patient." : ""}</p>
        {e.auteur !== "medecin" && <p className="mt-0.5 text-ink-soft">{e.texte}</p>}
        {donnees.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {donnees.map(([k, v]) => <span key={k} className="rounded-md bg-surface px-1.5 py-0.5 text-2xs text-ink-soft ring-1 ring-line">{FAITS[k] ?? k} : {valeur(k, v)}</span>)}
          </div>
        )}
      </div>
    </div>
  );
}

function ElementDecision({ d, occupe, nomMedecin, parAssistant, onValider, onAnnuler, onReformuler, onRetirer, onMasquer, onModifier }:
  { d: Decision; occupe: boolean; nomMedecin: (id?: string | null) => string; parAssistant: boolean; onValider: (confirme?: boolean) => void; onAnnuler: () => void;
    onReformuler: () => void; onRetirer: () => void; onMasquer: () => void; onModifier: () => void }) {
  const libelle = useLibelle();
  if (d.type === "prescription" || d.type === "partage_donnees") {
    const texte = d.type === "prescription"
      ? <>Prescription : <span className="font-medium text-ink">{nomMedicament(d.medicament)} {d.dose}</span></>
      : <>Demande de partage de données ({agent(d.auteur).nom.toLowerCase()})</>;
    return (
      <div className="flex items-center justify-center gap-2 text-[13px] text-ink-muted">
        <span className="h-px flex-1 bg-line" />
        {d.type === "prescription" ? <Pill size={14} /> : <Share2 size={14} />}
        <span>{texte}</span>
        <Statut statut={d.statut} />
        <span className="h-px flex-1 bg-line" />
      </div>
    );
  }
  const attente = d.statut === "attente_validation";
  const aConfirmer = attente ? d.precontrole?.constats.find((c) => c.regle === "CONTEXTE-A-CONFIRMER" && c.niveau === "A_REVOIR") : undefined;
  const origine = parAssistant ? "Question proposée par l'assistant (à valider ou annuler)" : d.contenu_type === "traitement" ? "Consignes de traitement" : tr("Votre message");
  const actionsFin = (avecReformuler: boolean) => (
    <div className="flex flex-wrap gap-1.5">
      {avecReformuler && d.texte && <Bouton taille="sm" variante="ghost" data-reformuler={d.id} disabled={occupe} onClick={onReformuler} icone={<PencilLine size={14} />}>{tr('Reformuler')}</Bouton>}
      <Bouton taille="sm" variante="ghost" data-masquer={d.id} disabled={occupe} onClick={onMasquer} icone={<EyeOff size={14} />}>{tr('Masquer')}</Bouton>
    </div>
  );
  const combinee = (d.pictogrammes ?? []).some((x) => x.includes("+"));
  return (
    <div className="flex max-w-[92%] flex-col items-end gap-1.5 self-end">
      <p className="text-xs text-ink-muted">{origine}</p>
      {d.texte && <div className="rounded-2xl rounded-tr-md bg-brand px-3.5 py-2 text-sm text-white">{d.texte}</div>}
      <div className={cx("w-full rounded-2xl border bg-surface p-3", attente ? "border-action ring-4 ring-action/10" : "border-line shadow-tile")}>
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="flex items-center gap-1.5 text-xs text-ink-muted"><Languages size={13} />{tr('Traduction en pictogrammes')}</p>
          <Statut statut={d.statut} />
        </div>
        <div className="flex flex-wrap gap-2">{(d.pictogrammes ?? []).map((p, i) => <Picto key={i} id={p} taille={56} legende />)}</div>
        {Object.keys(d.rapproches ?? {}).length > 0 && (
          <p className="mt-2 text-xs text-ink-soft" data-rapproches={d.id}>
            <span className="font-medium text-ink">Rapproché automatiquement</span> (faute de frappe ou conjugaison, à vérifier) :{" "}
            {Object.entries(d.rapproches ?? {}).map(([mot, id]) => `« ${mot} » → ${id.startsWith("lu comme") ? id.replace("lu comme ", "") : libelle(id)}`).join(" · ")}
          </p>
        )}
        {(d.precontrole?.lecture ?? []).filter((l) => l.regle !== "CONTEXTE-A-CONFIRMER").length > 0 && (
          <ul className="mt-2 flex flex-col gap-0.5" data-lecture={d.id}>
            {(d.precontrole?.lecture ?? []).filter((l) => l.regle !== "CONTEXTE-A-CONFIRMER").map((l, i) => (
              <li key={i} className="flex items-start gap-1.5 text-xs text-ink-soft"><Scale size={12} className="mt-px shrink-0 text-ink-muted" />
                <span><span className="font-medium text-ink">Lecture du juriste : </span>{l.detail}</span></li>
            ))}
          </ul>
        )}
        {aConfirmer && (
          <div className="mt-2 rounded-lg border border-warn/30 bg-warn-50 px-2.5 py-2 text-xs text-warn" data-a-confirmer={d.id}>
            <p className="font-semibold">Sens à confirmer avant l'envoi</p>
            <p className="mt-0.5 text-ink-soft">{aConfirmer.detail}</p>
            {aConfirmer.piste && <p className="mt-0.5 text-ink-soft">{aConfirmer.piste}</p>}
          </div>
        )}
        {d.non_traduits && d.non_traduits.length > 0 && d.statut !== "BLOQUE" && (
          <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-warn-50 px-2.5 py-1.5 text-xs text-warn">
            <AlertTriangle size={13} className="mt-px shrink-0" />Sans pictogramme : {d.non_traduits.join(", ")}. Reformulez si ces mots comptent.
          </p>
        )}
        {attente ? (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
            <p className="text-xs text-ink-muted">
              {d.pictogrammes_choisis_par ? `Choisis par : ${d.pictogrammes_choisis_par}` : ""}{combinee ? ", avec une image combinée" : ""}
            </p>
            <div className="flex flex-wrap gap-2">
              <Bouton taille="sm" variante="ghost" data-rejeter={d.id} disabled={occupe} onClick={onAnnuler} icone={<X size={14} />}
                title="Annuler : ce message ne partira pas">{tr('Annuler')}</Bouton>
              <Bouton taille="sm" variante="ghost" data-reformuler={d.id} disabled={occupe} onClick={onReformuler} icone={<PencilLine size={14} />}
                title="Annuler et remettre le texte dans la zone de saisie pour le corriger">{tr('Reformuler')}</Bouton>
              <Bouton taille="sm" variante="secondary" data-modifier={d.id} disabled={occupe} onClick={onModifier} icone={<Languages size={14} />}>{tr('Modifier les pictogrammes')}</Bouton>
              {aConfirmer ? (
                <Bouton taille="sm" variante="success" data-valider={d.id} data-confirmer={d.id} disabled={occupe} onClick={() => onValider(true)} icone={<Send size={14} />}
                  title="Votre confirmation et votre nom sont enregistrés au journal">Je confirme : ni consigne ni incitation, envoyer</Bouton>
              ) : (
                <Bouton taille="sm" variante="success" data-valider={d.id} disabled={occupe} onClick={() => onValider()} icone={<Send size={14} />}>{tr('Valider et envoyer')}</Bouton>
              )}
            </div>
          </div>
        ) : d.statut === "BLOQUE" && d.precontrole?.verdict === "BLOQUE" ? (
          <div className="mt-3 rounded-xl border border-danger/30 bg-danger-50 p-3" data-bloque={d.id}>
            <p className="flex items-center gap-1.5 text-[13px] font-semibold text-danger"><ShieldAlert size={15} />Bloqué par le juriste : ce message ne partira pas au patient</p>
            <ul className="mt-1.5 flex flex-col gap-1">
              {d.precontrole.constats.filter((c) => c.niveau === "BLOQUE" || (c.niveau === "A_REVOIR" && c.detail.startsWith("Pour ce patient"))).map((c, i) => (
                <li key={i} className="text-[13px] leading-snug text-ink">{c.detail}
                  <span className="mt-0.5 flex items-start gap-1 text-2xs text-ink-muted"><BookOpen size={11} className="mt-px shrink-0" />{c.base === "SURETE" ? "Sûreté du système" : c.base === "LOI" ? "Loi" : c.base === "NORME" ? "Norme" : "Recommandation clinique"} · <Refs texte={c.reference_courte} /></span>
                </li>
              ))}
            </ul>
            {d.precontrole.constats.find((c) => c.niveau === "BLOQUE" && c.piste) && (
              <p className="mt-2 rounded-lg bg-surface px-2.5 py-1.5 text-xs text-ok"><span className="font-semibold">Que faire : </span>
                {d.precontrole.constats.find((c) => c.niveau === "BLOQUE" && c.piste)?.piste}</p>
            )}
            <div className="mt-2 flex justify-end">{actionsFin(true)}</div>
          </div>
        ) : ["BLOQUE", "rejete", "retire"].includes(d.statut) ? (
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-1 text-xs text-ink-muted"><X size={13} />
              {d.statut === "BLOQUE" ? "Non envoyé : bloqué par le juriste (voir l'onglet Agents)."
                : d.statut === "retire" ? "Retiré de l'écran du patient par le médecin."
                  : "Non envoyé : annulé par le médecin."}</p>
            {actionsFin(d.statut !== "retire")}
          </div>
        ) : d.statut === "envoye" && (
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-1 text-xs text-ok"><Check size={13} />Envoyé au patient, validé par {nomMedecin(d.valide_par)}</p>
            <Bouton taille="sm" variante="ghost" data-retirer={d.id} disabled={occupe} onClick={onRetirer} icone={<Undo2 size={14} />}
              title="Le patient ne verra plus ce message (le journal le garde)">{tr("Retirer de l'écran du patient")}</Bouton>
          </div>
        )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ voice dictation (browser speech recognition)
// Chrome and Edge provide it (not Firefox). The dictated text lands in the input box: the doctor rereads and corrects it
// before "Translate"; nothing is sent to the patient without their validation. In Chrome, the audio is transcribed by
// Google's servers: fictitious patients only for the demonstration.
type Reconnaissance = {
  lang: string; continuous: boolean; interimResults: boolean; start: () => void; stop: () => void;
  onresult: ((e: { resultIndex: number; results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null;
  onend: (() => void) | null; onerror: ((e: { error: string }) => void) | null;
};
function useDictee(ajouter: (t: string) => void) {
  const Classe = (window as unknown as { SpeechRecognition?: new () => Reconnaissance; webkitSpeechRecognition?: new () => Reconnaissance })
    .SpeechRecognition ?? (window as unknown as { webkitSpeechRecognition?: new () => Reconnaissance }).webkitSpeechRecognition;
  const [actif, setActif] = useState(false);
  const [provisoire, setProvisoire] = useState("");
  const [erreur, setErreur] = useState("");
  const rec = useRef<Reconnaissance | null>(null);
  const demarrer = (langue: string) => {
    if (!Classe) return;
    const r = new Classe();
    r.lang = langue; r.continuous = true; r.interimResults = true;
    r.onresult = (e) => {
      let prov = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const x = e.results[i];
        if (x.isFinal) ajouter(x[0].transcript.trim()); else prov += x[0].transcript;
      }
      setProvisoire(prov);
    };
    r.onerror = (e) => setErreur(e.error === "not-allowed" ? "Micro refusé : autorisez-le dans le navigateur." : `Dictée interrompue (${e.error}).`);
    r.onend = () => { setActif(false); setProvisoire(""); };
    rec.current = r; setErreur(""); setActif(true);
    try { r.start(); } catch { setActif(false); }
  };
  const arreter = () => rec.current?.stop();
  return { disponible: Boolean(Classe), actif, provisoire, erreur, demarrer, arreter };
}

// Server-side dictation (Whisper at Groq, or xAI speech recognition): the browser records a WAV file, the server has it
// transcribed. Works in every recent browser (Chrome, Edge, Firefox) once the microphone is allowed.
function encoderWav(morceaux: Float32Array[], frequence: number, cible = 16000): Blob {
  const total = morceaux.reduce((n, m) => n + m.length, 0);
  const brut = new Float32Array(total);
  let o = 0;
  for (const m of morceaux) { brut.set(m, o); o += m.length; }
  const pas = frequence / cible;
  const n = Math.floor(brut.length / pas);
  const vue = new DataView(new ArrayBuffer(44 + n * 2));
  const ecrire = (p: number, t: string) => { for (let i = 0; i < t.length; i++) vue.setUint8(p + i, t.charCodeAt(i)); };
  ecrire(0, "RIFF"); vue.setUint32(4, 36 + n * 2, true); ecrire(8, "WAVE"); ecrire(12, "fmt ");
  vue.setUint32(16, 16, true); vue.setUint16(20, 1, true); vue.setUint16(22, 1, true); vue.setUint32(24, cible, true);
  vue.setUint32(28, cible * 2, true); vue.setUint16(32, 2, true); vue.setUint16(34, 16, true); ecrire(36, "data"); vue.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) {
    const x = Math.max(-1, Math.min(1, brut[Math.floor(i * pas)]));
    vue.setInt16(44 + i * 2, x < 0 ? x * 0x8000 : x * 0x7fff, true);
  }
  return new Blob([vue], { type: "audio/wav" });
}
const enBase64 = (b: Blob) => new Promise<string>((ok, ko) => { const r = new FileReader(); r.onload = () => ok(String(r.result)); r.onerror = ko; r.readAsDataURL(b); });

function useEnregistreur(transcrire: (audio: string) => Promise<void>) {
  const [etat, setEtat] = useState<"repos" | "enregistre" | "transcrit">("repos");
  const [duree, setDuree] = useState(0);
  const [niveau, setNiveau] = useState(0);
  const [erreur, setErreur] = useState("");
  const r = useRef<{ ctx: AudioContext; flux: MediaStream; proc: ScriptProcessorNode; morceaux: Float32Array[]; minuteur: number } | null>(null);
  const arreter = useCallback(async () => {
    const x = r.current;
    if (!x) return;
    r.current = null;
    clearInterval(x.minuteur);
    x.proc.disconnect(); x.flux.getTracks().forEach((t) => t.stop());
    const frequence = x.ctx.sampleRate;
    await x.ctx.close();
    const secondes = x.morceaux.reduce((n, m) => n + m.length, 0) / frequence;
    if (secondes < 0.6) { setEtat("repos"); setErreur("Enregistrement trop court : maintenez la dictée au moins une seconde."); return; }
    setEtat("transcrit");
    try { await transcrire(await enBase64(encoderWav(x.morceaux, frequence))); } finally { setEtat("repos"); setNiveau(0); }
  }, [transcrire]);
  const demarrer = async () => {
    setErreur("");
    try {
      const flux = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      const ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(flux);
      const proc = ctx.createScriptProcessor(4096, 1, 1);
      const morceaux: Float32Array[] = [];
      proc.onaudioprocess = (e) => {
        const d = e.inputBuffer.getChannelData(0);
        morceaux.push(new Float32Array(d));
        let s = 0; for (let i = 0; i < d.length; i += 16) s += d[i] * d[i];
        setNiveau(Math.min(1, Math.sqrt(s / (d.length / 16)) * 6));
      };
      source.connect(proc); proc.connect(ctx.destination);
      const debut = Date.now();
      const minuteur = window.setInterval(() => {
        const t = Math.floor((Date.now() - debut) / 1000);
        setDuree(t);
        if (t >= 120) arreter();
      }, 250);
      r.current = { ctx, flux, proc, morceaux, minuteur };
      setDuree(0); setEtat("enregistre");
    } catch {
      setErreur("Micro inaccessible : autorisez le micro pour cette page (icône à gauche de l'adresse), puis réessayez.");
    }
  };
  return { etat, duree, niveau, erreur, demarrer, arreter };
}

function Compositeur({ vue, occupe, poster, brouillon, onEnvoye }:
  { vue: VueMedecin; occupe: boolean; poster: Poster; brouillon: null | { texte: string; n: number }; onEnvoye: (t: string) => void }) {
  const [texte, setTexte] = useState("");
  useEffect(() => {                         // "Rephrase": the text comes back to the input box, ready to correct
    if (!brouillon) return;
    setTexte(brouillon.texte);
    setEnvoye("");
    const zone = document.getElementById("message") as HTMLTextAreaElement | null;
    zone?.focus();
    zone?.setSelectionRange(brouillon.texte.length, brouillon.texte.length);
  }, [brouillon]);
  const [langueDictee, setLangueDictee] = useState("fr-FR");
  const [envoye, setEnvoye] = useState("");
  const ajouter = useCallback((t: string) => setTexte((x) => (x.trim() ? `${x.trim()} ${t}` : t)), []);
  const navigateur = useDictee(ajouter);
  const serveur = useEnregistreur(useCallback(async (audio: string) => {
    const r = (await poster("/api/medecin/dictee", { audio, langue: langueDictee.slice(0, 2) })) as { texte?: string } | undefined;
    if (r?.texte) { ajouter(r.texte); document.getElementById("envoyerMessage")?.focus(); }
    else if (r) throw new Error("rien");
  }, [poster, langueDictee, ajouter]));
  const parXai = !!vue.dictee && vue.dictee !== "navigateur";   // server-side speech recognition: Whisper (Groq) or xAI
  const enregistre = parXai ? serveur.etat === "enregistre" : navigateur.actif;
  const [question, setQuestion] = useState(true);
  const [cle, setCle] = useState("");
  const envoyerTexte = async () => {
    const t = texte.trim();
    if (!t || t === envoye) return;
    setEnvoye(t);
    const r = await poster("/api/medecin/message", { texte: t, question, cle });
    if (r) { setTexte(""); setCle(""); onEnvoye(t); } else setEnvoye("");
  };
  const mm = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  const erreur = parXai ? serveur.erreur : navigateur.erreur;
  return (
    <div className="border-t border-line bg-surface p-4">
      {enregistre && (
        <div className="mb-2 flex items-center gap-3 rounded-xl bg-danger-50 px-3 py-2 text-[13px] text-danger" role="status">
          <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-danger" />
          <span className="font-medium">Enregistrement {parXai ? mm(serveur.duree) : ""} : parlez normalement</span>
          {parXai && <span className="h-2 flex-1 overflow-hidden rounded-full bg-white"><span className="block h-full bg-danger transition-all" style={{ width: `${Math.round(serveur.niveau * 100)}%` }} /></span>}
          <Bouton taille="sm" variante="danger" onClick={() => (parXai ? serveur.arreter() : navigateur.arreter())}>Terminer</Bouton>
        </div>
      )}
      {parXai && serveur.etat === "transcrit" && <p className="mb-2 text-[13px] text-ink-muted" role="status">Transcription en cours…</p>}
      <div className="rounded-xl border border-line-strong bg-surface shadow-tile focus-within:border-action focus-within:ring-4 focus-within:ring-action/10">
        <label htmlFor="message" className="sr-only">Message au patient</label>
        <textarea id="message" rows={2} value={texte} onChange={(e) => setTexte(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) envoyerTexte(); }}
          placeholder={LANGUE_UI === "en" ? "Write, or click the microphone and speak, e.g.: Do you have stomach pain?" : "Écrire, ou cliquer sur le micro et parler, par exemple : Avez-vous mal au ventre ?"}
          className="block w-full resize-none rounded-t-xl border-0 bg-transparent px-3.5 pt-3 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:ring-0" />
        {(navigateur.provisoire || erreur) && (
          <p className={cx("px-3.5 pb-1 text-xs", erreur ? "text-danger" : "italic text-ink-muted")}>{erreur || navigateur.provisoire}</p>
        )}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-3 pb-3 pt-1">
          {parXai || navigateur.disponible ? (
            <div className="flex items-center gap-1.5">
              <Bouton id="dictee" taille="sm" variante={enregistre ? "danger" : "secondary"} disabled={serveur.etat === "transcrit"}
                onClick={() => (enregistre ? (parXai ? serveur.arreter() : navigateur.arreter()) : (parXai ? serveur.demarrer() : navigateur.demarrer(langueDictee)))}
                icone={<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3" fill="currentColor" /><path d="M5 11a7 7 0 0014 0M12 18v3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>}>
                {enregistre ? "Terminer" : serveur.etat === "transcrit" ? "Transcription…" : "Dicter"}
              </Bouton>
              <select aria-label="Langue de la dictée" value={langueDictee} onChange={(e) => setLangueDictee(e.target.value)} disabled={enregistre}
                className={cx(champ, "h-8 w-auto py-0 pr-7 text-[13px]")}>
                <option value="fr-FR">FR</option><option value="en-US">EN</option><option value="ar-SA">AR</option>
              </select>
            </div>
          ) : <span className="text-xs text-ink-faint">Dictée : ajoutez une clé Groq (Whisper, open source) ou xAI, ou utilisez Chrome</span>}
          <Case id="estQuestion" coche={question} onChange={setQuestion}>{tr("C'est une question")}</Case>
          <label className="flex items-center gap-2 whitespace-nowrap text-[13px] text-ink-muted">
            Enregistrer la réponse comme
            <select id="cle" value={cle} onChange={(e) => setCle(e.target.value)} className={cx(champ, "h-8 w-auto py-0 pr-7 text-[13px]")}>
              <option value="">texte seulement</option>
              {vue.cles_fermees.map((c) => <option key={c} value={c}>{CLES_REPONSE[c] ?? c}</option>)}
            </select>
          </label>
          <Bouton id="envoyerMessage" variante="primary" className="ml-auto" disabled={occupe || !texte.trim() || texte.trim() === envoye} onClick={envoyerTexte} icone={<Languages size={15} />}>
            {tr("Faire traduire")}
          </Bouton>
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ agents inspector
type Onglet = "agents" | "assistant" | "ordonnance" | "droit" | "crise";

function Inspecteur({ vue, occupe, poster, medecin, onMaintenir }:
  { vue: VueMedecin; occupe: boolean; poster: Poster; medecin: string; onMaintenir: (id: number) => void }) {
  const suggestions = vue.suggestions.filter((s) => s.statut === "proposee_au_medecin");
  const questionsAssistant = vue.questions.filter((q) => q.auteur !== "medecin" && q.statut === "en_attente").length;
  const alertes = vue.messages.filter((m) => m.type === "alerte").length;
  const [brouillonRx, setBrouillonRx] = useState<null | { medicament: string; dose: string; posologie: string; n: number }>(null);
  const crise = vue.mesures.length + vue.incidents.length > 0;
  const onglets: { cle: Onglet; nom: string; icone: ReactNode; nombre?: number; ton?: "danger" }[] = [
    { cle: "agents", nom: tr("Agents"), icone: <Bot size={15} />, nombre: alertes || undefined, ton: "danger" },
    { cle: "assistant", nom: tr("Assistant"), icone: <Sparkles size={15} />, nombre: (suggestions.length + questionsAssistant) || undefined },
    { cle: "ordonnance", nom: tr("Ordonnance"), icone: <Pill size={15} /> },
    { cle: "droit", nom: tr("Droit"), icone: <Gavel size={15} />, nombre: vue.lacunes.length || undefined },
    ...(crise ? [{ cle: "crise" as Onglet, nom: tr("Crise"), icone: <Siren size={15} /> }] : []),
  ];
  const [onglet, setOnglet] = useState<Onglet>("agents");
  return (
    <section className="flex flex-col rounded-xl bg-surface shadow-panel xl:h-full xl:min-h-0">
      <nav role="tablist" aria-label="Agents" className="flex gap-1 overflow-x-auto border-b border-line px-2 pt-2 barre-fine">
        {onglets.map((o) => (
          <button key={o.cle} role="tab" aria-selected={onglet === o.cle} data-inspecteur={o.cle} onClick={() => setOnglet(o.cle)}
            className={cx("relative flex shrink-0 items-center gap-1.5 rounded-t-lg px-2.5 pb-2.5 pt-2 text-[13px] font-medium transition-colors",
              onglet === o.cle ? "text-ink after:absolute after:inset-x-2 after:-bottom-px after:h-0.5 after:rounded-full after:bg-action" : "text-ink-muted hover:text-ink")}>
            <span className="hidden 2xl:inline">{o.icone}</span>{o.nom}
            {o.nombre !== undefined && (
              <span className={cx("min-w-[18px] rounded-full px-1.5 text-center text-2xs font-semibold leading-[18px] tabulaire",
                o.ton === "danger" ? "bg-danger text-white" : "bg-action-50 text-action")}>{o.nombre}</span>
            )}
          </button>
        ))}
      </nav>
      <div className="flex-1 overflow-y-auto barre-fine xl:min-h-0">
        {onglet === "agents" && <OngletAgents vue={vue} occupe={occupe} poster={poster} />}
        {onglet === "assistant" && <OngletAssistant vue={vue} occupe={occupe} poster={poster} medecin={medecin}
          onPreremplir={(p) => { setBrouillonRx((b) => ({ ...p, n: (b?.n ?? 0) + 1 })); setOnglet("ordonnance"); }} />}
        {onglet === "ordonnance" && <OngletOrdonnance vue={vue} occupe={occupe} poster={poster} medecin={medecin} onMaintenir={onMaintenir}
          brouillon={brouillonRx} onPreremplir={(p) => setBrouillonRx((b) => ({ ...p, n: (b?.n ?? 0) + 1 }))} />}
        {onglet === "droit" && <OngletDroit vue={vue} />}
        {onglet === "crise" && <OngletCrise vue={vue} />}
      </div>
    </section>
  );
}

const TYPE_MESSAGE: Record<string, { nom: string; ton: "danger" | "review" | "action"; icone: ReactNode }> = {
  alerte: { nom: "Alerte", ton: "danger", icone: <AlertTriangle size={14} /> },
  demande: { nom: "Demande", ton: "review", icone: <ClipboardList size={14} /> },
  desaccord: { nom: "Désaccord", ton: "review", icone: <AlertTriangle size={14} /> },
  proposition: { nom: "Proposition", ton: "action", icone: <Sparkles size={14} /> },
  information: { nom: "Information", ton: "action", icone: <Info size={14} /> },
};

// The essentials first (first sentence, plainly), the details next: collapsed if long.
function TexteAgent({ texte }: { texte: string }) {
  const i = texte.search(/[.!?](\s|$)/);
  const essentiel = i > 0 && i < texte.length - 1 ? texte.slice(0, i + 1) : texte;
  const reste = essentiel.length < texte.length ? texte.slice(essentiel.length).trim() : "";
  return (
    <>
      <p className="text-[13px] font-medium leading-snug text-ink">{essentiel}</p>
      {reste && (reste.length > 180 ? (
        <details className="group mt-1">
          <summary className="flex cursor-pointer list-none items-center gap-1 text-xs font-medium text-action">
            <ChevronDown size={13} className="transition-transform group-open:rotate-180" />Détails
          </summary>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">{reste}</p>
        </details>
      ) : <p className="mt-0.5 text-[13px] leading-relaxed text-ink-soft">{reste}</p>)}
    </>
  );
}

function CarteMessage({ m, onMasquer }: { m: MessageAgent; onMasquer?: () => void }) {
  const t = TYPE_MESSAGE[m.type] ?? TYPE_MESSAGE.information;
  const a = agent(m.de);
  const { entete, texte, refs, piste } = analyserMessage(m.contenu);
  return (
    <article className={cx("border-b border-line px-4 py-3.5 last:border-0", m.type === "alerte" && "bg-danger-50/40")}>
      <div className="mb-1.5 flex items-center gap-2">
        <span className="grid h-6 w-6 place-items-center rounded-md bg-canvas text-ink-soft">{a.icone}</span>
        <span className="text-[13px] font-semibold text-ink">{a.nom}</span>
        {onMasquer && (
          <button data-masquer-agent={m.id} onClick={onMasquer} title="Masquer ce message (enregistré au journal)" aria-label="Masquer ce message"
            className="order-last rounded-md p-1 text-ink-faint hover:bg-canvas hover:text-ink"><X size={14} /></button>
        )}
        <Pastille ton={t.ton} icone={t.icone} className="ml-auto">{t.nom}</Pastille>
      </div>
      {entete && <p className="text-xs font-semibold text-ink">{entete.replace(/#(\d+)/, "n° $1").replace(/,\s*$/, "")}</p>}
      <TexteAgent texte={texte} />
      {piste && <p className="mt-2 rounded-lg bg-ok-50 px-2.5 py-1.5 text-xs text-ok"><span className="font-semibold">Ce qui est possible : </span>{piste}</p>}
      {refs.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1">
          {[...new Set(refs.flatMap((r) => r.split(" ; ")))].map((r, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-ink-muted"><BookOpen size={12} className="mt-0.5 shrink-0" /><Refs texte={r} /></li>
          ))}
        </ul>
      )}
    </article>
  );
}

function OngletAgents({ vue, occupe, poster }: { vue: VueMedecin; occupe: boolean; poster: Poster }) {
  const [q, setQ] = useState("");
  const [caches, setCaches] = useState<Set<number>>(new Set());
  const messages = vue.messages.filter((m) => !caches.has(m.id)).slice().reverse();
  const masquer = (id: number) => { setCaches((c) => new Set(c).add(id)); poster("/api/medecin/masquer_agent", { message_id: id }); };
  return (
    <div className="flex flex-col">
      <div id="messages">
        {messages.length ? messages.map((m) => <CarteMessage key={m.id} m={m} onMasquer={() => masquer(m.id)} />)
          : <Vide icone={<Bot size={20} />} titre="Aucun message des agents" texte="Le juriste, l'assistant et le traducteur vous écrivent ici quand une décision les concerne." />}
      </div>
      <div className="sticky bottom-0 border-t border-line bg-surface p-4">
        <Champ libelle={tr("Demander au juriste")} htmlFor="questionJuriste">
          <textarea id="questionJuriste" rows={2} value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Par exemple : un consentement donné en pictogrammes est-il valable ?" className={cx(champ, "resize-none py-2")} />
        </Champ>
        <div className="mt-2 flex justify-end">
          <Bouton id="demanderJuriste" variante="secondary" taille="sm" icone={<Scale size={14} />} disabled={occupe || !q.trim()}
            onClick={async () => { if (await poster("/api/medecin/juriste", { texte: q.trim() })) setQ(""); }}>{tr('Envoyer la question')}</Bouton>
        </div>
      </div>
    </div>
  );
}

function ApercuPictos({ texte }: { texte: string }) {
  const jeton = useMemo(jetonMedecin, []);
  const [r, setR] = useState<{ pictogrammes: string[]; non_traduits: string[] } | null>(null);
  useEffect(() => { envoyer<{ pictogrammes: string[]; non_traduits: string[] }>("/api/medecin/apercu", { texte }, jeton).then(setR).catch(() => setR(null)); }, [texte, jeton]);
  if (!r) return <p className="text-xs text-ink-faint">…</p>;
  return (
    <div className="mt-2">
      <div className="flex flex-wrap gap-1.5">{r.pictogrammes.map((p, i) => <Picto key={i} id={p} taille={40} legende />)}</div>
      {r.non_traduits.length > 0 && <p className="mt-1 text-2xs text-warn">Sans pictogramme : {r.non_traduits.join(", ")}</p>}
    </div>
  );
}

function OngletAssistant({ vue, occupe, poster, medecin, onPreremplir }:
  { vue: VueMedecin; occupe: boolean; poster: Poster; medecin: string; onPreremplir: (p: { medicament: string; dose: string; posologie: string }) => void }) {
  const [caches, setCaches] = useState<Set<number>>(new Set());
  // Alerts first, then the most recent
  const RANG: Record<string, number> = { alerte_urgence: 0, traitement_alternatif: 1, traitement: 2, question_manquante: 3, reponse: 4 };
  const suggestions = vue.suggestions.filter((s) => s.statut === "proposee_au_medecin" && !caches.has(s.id))
    .sort((a, b) => (RANG[a.type] ?? 5) - (RANG[b.type] ?? 5) || b.id - a.id);
  const ignorer = (id: number) => { setCaches((c) => new Set(c).add(id)); poster("/api/medecin/ignorer", { suggestion_id: id }); };
  // Questions the ASSISTANT proposes: they wait here, the doctor sends or refuses them (the conversation stays readable)
  const [qCaches, setQCaches] = useState<Set<number>>(new Set());
  const aPoser = vue.questions.filter((q) => q.auteur !== "medecin" && q.statut === "en_attente" && !qCaches.has(q.id)).reverse();
  const faites = vue.questions.filter((q) => q.auteur !== "medecin" && ["posee", "repondue"].includes(q.statut)).reverse().slice(0, 6);
  const agirQ = (id: number, url: string, corps: object) => { setQCaches((c) => new Set(c).add(id)); poster(url, { question_id: id, medecin, ...corps }); };
  const horsLigne = vue.modele && !vue.modele.disponible;
  return (
    <div className="flex flex-col gap-5 p-4">
      <p id="etatAssistant" className={cx("flex items-start gap-2 rounded-lg px-3 py-2 text-xs", horsLigne ? "bg-warn-50 text-warn" : "bg-ok-50 text-ok")}>
        {horsLigne ? <WifiOff size={14} className="mt-px shrink-0" /> : <ShieldCheck size={14} className="mt-px shrink-0" />}
        <span>{horsLigne
          ? <>L'assistant est actif en <b>mode règles</b> : {vue.modele?.modele} ne répond pas. Il surveille quand même chaque message, prescription et réponse du patient au regard de sa fiche ; nouvel essai du modèle toutes les 90 s.
              <details className="mt-1"><summary className="cursor-pointer font-medium">Pourquoi le modèle ne répond pas</summary>{vue.modele?.message}</details></>
          : <>L'assistant suit la consultation en temps réel : chaque message, prescription, document et réponse du patient est confronté à sa fiche.</>}</span>
      </p>
      <div>
        <h3 className="mb-2 text-[13px] font-semibold text-ink">{tr("Questions à poser")}</h3>
        <p className="mb-2 text-xs text-ink-muted">Proposées par l'assistant. Rien n'arrive dans la conversation tant que vous ne les envoyez pas.</p>
        {aPoser.length ? (
          <ul id="questionsAssistant" className="flex flex-col gap-2.5">
            {aPoser.map((q) => (
              <li key={q.id} className="rounded-xl border border-line p-3" data-question={q.id}>
                <p className="text-[13px] font-medium text-ink">{q.question}</p>
                <p className="text-xs text-ink-muted">{q.raison}</p>
                <ApercuPictos texte={q.question} />
                <div className="mt-2.5 flex flex-wrap justify-end gap-1.5">
                  <Bouton taille="sm" variante="ghost" data-refuser-question={q.id} disabled={occupe} icone={<X size={14} />}
                    onClick={() => agirQ(q.id, "/api/medecin/refuser_question", {})}>Refuser</Bouton>
                  <Bouton taille="sm" variante="secondary" data-modifier-question={q.id} disabled={occupe} icone={<Languages size={14} />}
                    title="La traduction arrive dans la conversation : vous la modifiez puis la validez"
                    onClick={() => agirQ(q.id, "/api/medecin/poser_question", { modifier: true })}>Modifier d'abord</Bouton>
                  <Bouton taille="sm" variante="success" data-envoyer-question={q.id} disabled={occupe} icone={<Send size={14} />}
                    title="Envoyée en votre nom avec ces pictogrammes, après le contrôle du juriste"
                    onClick={() => agirQ(q.id, "/api/medecin/poser_question", {})}>Envoyer</Bouton>
                </div>
              </li>
            ))}
          </ul>
        ) : <p className="text-[13px] text-ink-muted">L'assistant n'a pas de question en attente.</p>}
        {faites.length > 0 && (
          <ul className="mt-2 flex flex-col divide-y divide-line rounded-xl border border-line">
            {faites.map((q) => (
              <li key={q.id} className="flex items-center justify-between gap-3 px-3 py-2 text-xs">
                <span className="text-ink-soft">{q.question}</span>
                <Pastille ton={q.statut === "repondue" ? "ok" : "neutre"}>{q.statut === "repondue" ? "Répondue" : "Posée"}</Pastille>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <h3 className="mb-2 text-[13px] font-semibold text-ink">{tr("Suggestions")}</h3>
        <p className="mb-3 text-xs text-ink-muted">L'assistant propose, vous décidez. « Ignorer » masque aussitôt la suggestion (enregistré au journal).</p>
        <div id="suggestions" className="flex flex-col gap-2.5">
          {suggestions.length ? suggestions.map((s) => {
            const [source] = s.source.split(" — ").slice(-1);
            return (
              <article key={s.id} className={cx("rounded-xl border p-3.5", s.type === "alerte_urgence" ? "border-danger/40 bg-danger-50/40" : "border-line")}>
                <p className="whitespace-pre-line text-sm font-medium leading-snug text-ink">{s.texte}</p>
                <p className="mt-1 text-[13px] text-ink-muted">{s.raison}</p>
                <div className="mt-2.5 flex flex-wrap items-end justify-between gap-2">
                  <p className="flex items-start gap-1.5 text-xs text-ink-muted"><BookOpen size={13} className="mt-px shrink-0" /><Refs texte={source} /></p>
                  <div className="flex gap-1.5">
                    {s.prescription && (
                      <Bouton taille="sm" variante="secondary" data-preremplir={s.id} disabled={occupe} icone={<Pill size={14} />}
                        onClick={() => s.prescription && onPreremplir(s.prescription)}>Préremplir l'ordonnance</Bouton>
                    )}
                    <Bouton taille="sm" variante="ghost" data-ignorer={s.id} disabled={occupe} icone={<X size={14} />} onClick={() => ignorer(s.id)}>{tr("Ignorer")}</Bouton>
                  </div>
                </div>
              </article>
            );
          }) : <Vide icone={<Sparkles size={20} />} titre="Aucune suggestion en cours" />}
        </div>
      </div>
    </div>
  );
}

function DetailVerdict({ v }: { v?: Verdict }) {
  if (!v) return null;
  const lignes = [...v.constats, ...v.obligations];
  if (!lignes.length) return null;
  return (
    <details className="group mt-2.5">
      <summary className="flex cursor-pointer list-none items-center gap-1 text-xs font-medium text-action">
        <ChevronDown size={14} className="transition-transform group-open:rotate-180" />Analyse du juriste ({lignes.length})
      </summary>
      <ul className="mt-2 flex flex-col gap-2">
        {lignes.map((c, i) => (
          <li key={i} className="rounded-lg bg-canvas px-3 py-2">
            <div className="flex items-center gap-2"><Statut statut={c.niveau} /><span className="text-2xs text-ink-muted">{c.base === "LOI" ? "Loi" : c.base === "NORME" ? "Norme" : c.base === "SURETE" ? "Sûreté du système" : "Recommandation"}</span></div>
            <p className="mt-1 text-[13px] text-ink-soft">{c.detail}</p>
            {c.piste && <p className="mt-1 text-xs text-ink"><span className="font-medium">Que faire : </span>{c.piste}</p>}
            <p className="mt-1 flex items-start gap-1.5 text-2xs text-ink-muted"><BookOpen size={12} className="mt-px shrink-0" /><Refs texte={c.reference_courte} /></p>
          </li>
        ))}
      </ul>
    </details>
  );
}

function OngletOrdonnance({ vue, occupe, poster, medecin, onMaintenir, brouillon, onPreremplir }:
  { vue: VueMedecin; occupe: boolean; poster: Poster; medecin: string; onMaintenir: (id: number) => void;
    brouillon: null | { medicament: string; dose: string; posologie: string; n: number };
    onPreremplir: (p: { medicament: string; dose: string; posologie: string }) => void }) {
  const [f, setF] = useState({ medicament: "", dose: "", posologie: "", mode: "presentiel", remplace: "", suggestion: false });
  useEffect(() => {                         // "Prefill the prescription" from an assistant proposal
    if (brouillon) setF((x) => ({ ...x, medicament: brouillon.medicament, dose: brouillon.dose, posologie: brouillon.posologie, suggestion: true }));
  }, [brouillon]);
  const propositions = vue.suggestions.filter((s) => s.statut === "proposee_au_medecin" && s.prescription);
  const maj = (k: keyof typeof f) => (v: string | boolean) => setF((x) => ({ ...x, [k]: v }));
  const prescriptions = vue.decisions.filter((d) => d.type === "prescription" || d.type === "partage_donnees").slice().reverse();
  const actives = vue.decisions.filter((d) => d.type === "prescription" && d.statut !== "annulee");
  const verdictDe = (id: number) => vue.verdicts.filter((v) => v.decision_id === id).slice(-1)[0];
  return (
    <div className="flex flex-col gap-5 p-4">
      {propositions.length > 0 && (
        <div id="propositionsAssistant" className="rounded-xl bg-action-50/60 p-3 ring-1 ring-action/20">
          <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-action"><Sparkles size={13} />Proposition de l'assistant (contrôlée par le juriste pour ce patient)</p>
          {propositions.map((s) => s.prescription && (
            <div key={s.id} className="flex flex-wrap items-center justify-between gap-2 py-1 text-[13px]">
              <span className="text-ink">{nomMedicament(s.prescription.medicament)} {s.prescription.dose}{s.prescription.posologie ? `, ${s.prescription.posologie}` : ""}</span>
              <Bouton taille="sm" variante="secondary" data-preremplir={s.id} disabled={occupe} onClick={() => s.prescription && onPreremplir(s.prescription)}>Préremplir</Bouton>
            </div>
          ))}
        </div>
      )}
      <div className="rounded-xl border border-line p-3.5">
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-[1fr_120px] gap-3">
            <Champ libelle={tr("Médicament")} htmlFor="medicament">
              <input id="medicament" list="listeMedicaments" value={f.medicament} onChange={(e) => maj("medicament")(e.target.value)} className={cx(champ, "h-9")} placeholder="Rechercher" />
              <datalist id="listeMedicaments">{vue.medicaments.map((m) => <option key={m} value={m}>{nomMedicament(m)}</option>)}</datalist>
            </Champ>
            <Champ libelle={tr("Dose")} htmlFor="dose"><input id="dose" value={f.dose} onChange={(e) => maj("dose")(e.target.value)} className={cx(champ, "h-9")} placeholder="500 mg" /></Champ>
          </div>
          <Champ libelle={tr("Mode d'emploi")} htmlFor="posologie">
            <input id="posologie" value={f.posologie} onChange={(e) => maj("posologie")(e.target.value)} className={cx(champ, "h-9")} placeholder="3 fois par jour pendant 3 jours" />
          </Champ>
          <div className="grid grid-cols-2 gap-3">
            <Champ libelle={tr("Consultation")} htmlFor="modeConsult">
              <select id="modeConsult" value={f.mode} onChange={(e) => maj("mode")(e.target.value)} className={cx(champ, "h-9")}>
                <option value="presentiel">En présentiel</option><option value="distance">Téléconsultation</option>
              </select>
            </Champ>
            <Champ libelle={tr("Remplace")} htmlFor="remplace">
              <select id="remplace" value={f.remplace} onChange={(e) => maj("remplace")(e.target.value)} className={cx(champ, "h-9")}>
                <option value="">Aucune</option>
                {actives.map((d) => <option key={d.id} value={d.medicament ?? ""}>{nomMedicament(d.medicament)}</option>)}
              </select>
            </Champ>
          </div>
          <Case id="suggestion" coche={f.suggestion} onChange={maj("suggestion")}>Inspirée d'une suggestion de l'assistant</Case>
          <Bouton id="prescrire" variante="primary" disabled={occupe || !f.medicament.trim()} icone={<ShieldCheck size={15} />}
            onClick={async () => {
              const r = await poster("/api/medecin/prescription", { medicament: f.medicament, dose: f.dose, posologie: f.posologie, mode: f.mode,
                remplace_medicament: f.remplace, issue_de_suggestion: f.suggestion, medecin });
              if (r) setF((x) => ({ ...x, medicament: "", dose: "", posologie: "", remplace: "", suggestion: false }));
            }}>{tr('Prescrire')}</Bouton>
          <p className="-mt-1 text-center text-xs text-ink-muted">Chaque prescription est vérifiée par le juriste avant d'être transmise.</p>
        </div>
      </div>
      <div>
        <div className="mb-2 flex items-center justify-between gap-2">
          <h3 className="text-[13px] font-semibold text-ink">{tr('Décisions')}</h3>
          {(vue.ordonnances?.length ?? 0) > 0 && (
            <a id="ordonnancePdf" href="/api/patient/ordonnance.pdf" download className="text-xs font-medium text-action hover:underline">{tr("Ordonnance du patient (PDF)")}</a>
          )}
        </div>
        <div id="decisions" className="flex flex-col gap-2.5">
          {prescriptions.length ? prescriptions.map((d) => (
            <article key={d.id} className="rounded-xl border border-line p-3.5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-ink">{d.type === "prescription" ? `${nomMedicament(d.medicament)} ${d.dose ?? ""}` : "Partage de données"}</p>
                  <p className="text-xs text-ink-muted">{d.type === "prescription" ? (d.posologie || "Sans mode d'emploi") : `Demandé par : ${agent(d.auteur).nom}`}</p>
                </div>
                <Statut statut={d.statut} />
              </div>
              {d.maintien && <p className="mt-2 rounded-lg bg-held-50 px-2.5 py-1.5 text-xs text-held">Maintenue par {vue.prescripteurs[d.maintien.par] ?? d.maintien.par} : {d.maintien.justification}</p>}
              {d.statut === "PREUVES_INSUFFISANTES" && (verdictDe(d.id)?.informations_manquantes ?? []).length > 0 && (
                <div className="mt-2.5 rounded-lg bg-warn-50 p-2.5" data-manquants={d.id}>
                  <p className="text-xs font-semibold text-warn">Il manque, pour que le juriste puisse conclure :</p>
                  <ul className="mt-1.5 flex flex-col gap-1.5">
                    {(verdictDe(d.id)?.informations_manquantes ?? []).map((m) => {
                      const r = REMPLIR[m];
                      return (
                        <li key={m} className="flex flex-wrap items-center gap-1.5 text-xs text-ink">
                          <span className="mr-auto font-medium">{FAITS[m] ?? m.replace(/_/g, " ")}</span>
                          {r?.valeurs.map(([lib, val]) => (
                            <Bouton key={lib} taille="sm" variante="secondary" disabled={occupe} data-remplir={`${m}:${lib}`}
                              onClick={() => poster("/api/medecin/faits", { donnees: { [m]: val } })}>{lib}</Bouton>
                          ))}
                          {r?.question && <Bouton taille="sm" variante="ghost" disabled={occupe} data-demander={m}
                            onClick={() => poster("/api/medecin/message", { texte: r.question, question: true, cle: m })}>{tr('Demander au patient')}</Bouton>}
                        </li>
                      );
                    })}
                  </ul>
                  <p className="mt-1.5 text-2xs text-ink-muted">Ou remplissez la fiche patient : la prescription est revérifiée aussitôt.</p>
                </div>
              )}
              <DetailVerdict v={verdictDe(d.id)} />
              {d.statut === "A_REVOIR" && (
                <div className="mt-3 flex justify-end">
                  <Bouton taille="sm" data-maintenir={d.id} disabled={occupe} onClick={() => onMaintenir(d.id)}>Maintenir en justifiant</Bouton>
                </div>
              )}
            </article>
          )) : <Vide icone={<Pill size={20} />} titre="Aucune prescription" texte="Les prescriptions et leur vérification par le juriste apparaissent ici." />}
        </div>
      </div>
    </div>
  );
}

function OngletDroit({ vue }: { vue: VueMedecin }) {
  const verifs = vue.verdicts.slice().reverse();
  const OBJETS: Record<string, string> = { envoi_au_patient: "Message au patient", prescription: "Prescription", partage_de_donnees: "Partage de données" };
  return (
    <div className="flex flex-col gap-5 p-4">
      <div>
        <h3 className="mb-1 text-[13px] font-semibold text-ink">Lacunes du droit signalées</h3>
        <p className="mb-3 text-xs text-ink-muted">Situations que les textes en vigueur ne règlent pas, relevées pendant la consultation.</p>
        <div id="lacunes" className="flex flex-col gap-2">
          {vue.lacunes.length ? vue.lacunes.map((l, i) => (
            <details key={i} className="group rounded-xl border border-line px-3.5 py-2.5">
              <summary className="flex cursor-pointer list-none items-start gap-2">
                {l.id && <span className="mt-px rounded bg-brand-50 px-1.5 text-2xs font-semibold text-brand tabulaire">{l.id}</span>}
                <span className="flex-1 text-[13px] font-medium text-ink">{l.sujet}</span>
                <ChevronDown size={15} className="mt-0.5 shrink-0 text-ink-muted transition-transform group-open:rotate-180" />
              </summary>
              {l.detail && <div className="mt-2 flex flex-col gap-1.5 text-xs leading-relaxed text-ink-muted">{l.detail.split(" | ").map((x, j) => <p key={j}>{x}</p>)}</div>}
            </details>
          )) : <p className="text-[13px] text-ink-muted">Aucune lacune relevée pour cette consultation.</p>}
        </div>
      </div>
      <div>
        <h3 className="mb-2 text-[13px] font-semibold text-ink">Vérifications du juriste</h3>
        {verifs.length ? (
          <ul className="flex flex-col divide-y divide-line rounded-xl border border-line">
            {verifs.map((v, i) => (
              <li key={i} className="px-3.5 py-2.5">
                <div className="flex items-center justify-between gap-3">
                  <p className="truncate text-[13px] text-ink">{OBJETS[v.objet] ?? v.objet}{v.decision_id ? ` n° ${v.decision_id}` : ""}</p>
                  <Statut statut={v.verdict} />
                </div>
                {v.constats[0] && <p className="mt-0.5 truncate text-xs text-ink-muted" title={v.constats.map((c) => c.reference_courte).join(" ; ")}>{v.constats[0].reference_courte}</p>}
              </li>
            ))}
          </ul>
        ) : <p className="text-[13px] text-ink-muted">Aucune vérification pour l'instant.</p>}
      </div>
    </div>
  );
}

function OngletCrise({ vue }: { vue: VueMedecin }) {
  return (
    <div id="mesures" className="flex flex-col gap-2.5 p-4">
      <p className="text-xs text-ink-muted">Échanges entre institutions, sans données de patients.</p>
      {vue.incidents.map((x, i) => (
        <article key={`i${i}`} className="rounded-xl border border-danger/20 bg-danger-50/50 p-3.5">
          <div className="mb-1 flex items-center justify-between"><span className="text-[13px] font-semibold text-ink">{agent(x.par).nom}</span><Pastille ton="danger">Incident {x.gravite}</Pastille></div>
          <p className="text-[13px] text-ink-soft">{x.description}</p>
        </article>
      ))}
      {vue.mesures.map((x, i) => (
        <article key={`m${i}`} className="rounded-xl border border-line p-3.5">
          <p className="text-[13px] font-semibold text-ink">{agent(x.par).nom}</p>
          <p className="mt-0.5 text-[13px] text-ink-soft">{x.mesure}</p>
          <p className="mt-1.5 flex items-start gap-1.5 text-xs text-ink-muted"><BookOpen size={13} className="mt-px shrink-0" />{x.citation}</p>
        </article>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ page states
function DialogueTexte({ ouvert, titre, description, libelle, defaut, action, variante, onFermer, onValider }:
  { ouvert: boolean; titre: string; description: string; libelle: string; defaut: string; action: string;
    variante: "danger" | "primary"; onFermer: () => void; onValider: (t: string) => void }) {
  return ouvert ? <DialogueTexteOuvert {...{ titre, description, libelle, defaut, action, variante, onFermer, onValider }} /> : null;
}
function DialogueTexteOuvert({ titre, description, libelle, defaut, action, variante, onFermer, onValider }:
  { titre: string; description: string; libelle: string; defaut: string; action: string; variante: "danger" | "primary"; onFermer: () => void; onValider: (t: string) => void }) {
  const [t, setT] = useState(defaut);
  return (
    <Dialogue ouvert titre={titre} description={description} onFermer={onFermer}
      actions={<><Bouton onClick={onFermer}>{tr('Annuler')}</Bouton><Bouton id="confirmerDialogue" variante={variante} disabled={!t.trim()} onClick={() => onValider(t.trim())}>{action}</Bouton></>}>
      <Champ libelle={libelle} htmlFor="texteDialogue">
        <textarea id="texteDialogue" rows={3} value={t} onChange={(e) => setT(e.target.value)} className={cx(champ, "resize-none py-2")} />
      </Champ>
    </Dialogue>
  );
}

function AccesRefuse() {
  return (
    <div className="grid min-h-dvh place-items-center p-6">
      <div className="w-full max-w-sm rounded-2xl bg-surface p-6 text-center shadow-panel">
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-danger-50 text-danger"><Lock size={22} /></div>
        <h1 className="mt-4 text-lg font-semibold text-ink">Accès réservé au médecin</h1>
        <p className="mt-2 text-sm text-ink-muted">Ouvrez le lien privé affiché dans le terminal au démarrage du serveur. Il contient une clé secrète : ne le partagez pas.</p>
        <a href="/patient" className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-action hover:underline"><MonitorSmartphone size={15} />Ouvrir l'écran patient</a>
      </div>
    </div>
  );
}

function Chargement({ erreur }: { erreur: boolean }) {
  return (
    <div className="grid min-h-dvh place-items-center p-6 text-center">
      <div>
        <img src={urlPicto("ATTENDRE")} alt="" width={56} height={56} className="mx-auto opacity-60" />
        <p className="mt-3 text-sm text-ink-muted">{erreur ? "Le serveur ne répond pas. Vérifiez qu'il est lancé (python interface/serveur.py)." : "Ouverture de la consultation…"}</p>
      </div>
    </div>
  );
}



// ------------------------------------------------------------------ pictogram editor (doctor)
// The doctor corrects the translation before validating: remove, add any pictogram of the base, combine.
// The server refuses to remove the negation, the limit, the emergency, STOP, a number, a dose or a medicine.
const sansAccentsM = (t: string) => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const debutDeMotM = (texte: string, q: string) => sansAccentsM(texte).split(/[\s'’+\-/]+/).some((m) => m.startsWith(q));

function EditeurPictos({ initial, onFermer, onEnregistrer }: { initial: string[]; onFermer: () => void; onEnregistrer: (p: string[]) => void }) {
  const libelle = useLibelle();
  const [pictos, setPictos] = useState<string[]>(initial);
  // Selected slot: a click in the base REPLACES it (or is inserted after it, in "insert" mode). No selection: added at the end.
  const [choisi, setChoisi] = useState<number | null>(null);
  const [inserer, setInserer] = useState(false);
  const [palette, setPalette] = useState<Record<string, string[]>>({});
  const [onglet, setOnglet] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => { lire<Record<string, string[]>>("/api/palette").then(setPalette).catch(() => setPalette({})); }, []);
  useEffect(() => {
    const touche = (e: KeyboardEvent) => e.key === "Escape" && onFermer();
    window.addEventListener("keydown", touche);
    return () => window.removeEventListener("keydown", touche);
  }, [onFermer]);
  const onglets = Object.keys(palette);
  const actif = onglet && palette[onglet] ? onglet : onglets[0];
  const requete = sansAccentsM(q.trim());
  const tous = useMemo(() => Array.from(new Set(Object.values(palette).flat())), [palette]);
  const parSens = useRechercheSens(q);
  const directs = requete.length >= 2
    ? tous.filter((id) => (["fr", "en", "ar"] as const).some((lg) => debutDeMotM(libelle(id, lg), requete)) || debutDeMotM(id.replace(/_/g, " "), requete))
    : null;
  const presents = useMemo(() => new Set(tous), [tous]);
  const liste = directs === null ? palette[actif] ?? [] : [...directs, ...parSens.filter((id) => presents.has(id) && !directs.includes(id))];
  const sel = choisi !== null && choisi < pictos.length ? choisi : null;
  const ajouter = (id: string) => {
    if (sel === null) { if (pictos.length < 12) setPictos((p) => [...p, id]); return; }
    if (inserer) {
      if (pictos.length >= 12) return;
      setPictos((p) => [...p.slice(0, sel + 1), id, ...p.slice(sel + 1)]);
      setChoisi(sel + 1);
    } else {
      setPictos((p) => p.map((x, j) => (j === sel ? id : x)));
    }
  };
  const deplacer = (de: number) => {
    if (sel === null) return;
    const vers = sel + de;
    if (vers < 0 || vers >= pictos.length) return;
    setPictos((p) => { const c = [...p]; [c[sel], c[vers]] = [c[vers], c[sel]]; return c; });
    setChoisi(vers);
  };
  const retirer = () => { if (sel === null) return; setPictos((p) => p.filter((_, j) => j !== sel)); setChoisi(null); };
  const combiner = () => {
    if (sel === null || sel + 1 >= pictos.length) return;
    setPictos((p) => [...p.slice(0, sel), `${p[sel]}+${p[sel + 1]}`, ...p.slice(sel + 2)]);
  };
  const separer = () => {
    if (sel === null || !pictos[sel].includes("+")) return;
    setPictos((p) => [...p.slice(0, sel), ...p[sel].split("+"), ...p.slice(sel + 1)]);
  };
  const peutCombiner = sel !== null && sel + 1 < pictos.length && combinable(pictos[sel], pictos[sel + 1]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-[2px]" onMouseDown={onFermer}>
      <div role="dialog" aria-modal="true" aria-label="Modifier les pictogrammes" onMouseDown={(e) => e.stopPropagation()}
        className="flex max-h-[90dvh] w-full max-w-4xl flex-col rounded-2xl bg-surface shadow-pop">
        <div className="flex items-start justify-between gap-4 px-5 pt-5">
          <div>
            <h3 className="text-base font-semibold text-ink">{tr('Modifier les pictogrammes')}</h3>
            <p className="mt-1 text-sm text-ink-muted">
              Cliquez un pictogramme pour le sélectionner, puis choisissez-en un dans la base pour le <b>remplacer</b>.
              Sans sélection, le pictogramme choisi s'ajoute à la fin. La proposition reste à valider.
            </p>
          </div>
          <button onClick={onFermer} aria-label="Fermer" className="rounded-md p-1 text-ink-faint hover:bg-canvas hover:text-ink"><X size={18} /></button>
        </div>
        <div className="mx-5 mt-4 rounded-xl bg-canvas p-2 ring-1 ring-inset ring-line">
          <div className="flex min-h-[88px] flex-wrap items-center gap-2" onClick={(e) => { if (e.target === e.currentTarget) setChoisi(null); }}>
            {pictos.length === 0 && <span className="px-2 text-sm text-ink-muted">Aucun pictogramme : ajoutez-en ci-dessous.</span>}
            {pictos.map((id, i) => (
              <button key={`${id}-${i}`} data-choisir-picto={i} aria-pressed={sel === i} title={sel === i ? "Sélectionné" : "Sélectionner"}
                onClick={() => setChoisi(sel === i ? null : i)}
                className={cx("relative rounded-xl bg-surface p-1 shadow-panel", sel === i ? "ring-2 ring-action" : "hover:ring-2 hover:ring-action/40")}>
                <span className="absolute left-1 top-1 rounded bg-canvas px-1 text-2xs text-ink-muted tabulaire">{i + 1}</span>
                <Picto id={id} taille={60} legende />
              </button>
            ))}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-line pt-2">
            {sel === null ? (
              <p className="px-1 text-xs text-ink-muted">Sélectionnez un pictogramme pour le remplacer, le déplacer, le retirer ou insérer à côté.</p>
            ) : (
              <>
                <span className="px-1 text-xs font-medium text-ink">N° {sel + 1} « {libelle(pictos[sel].split("+")[0])} » :</span>
                <div className="flex rounded-lg ring-1 ring-line" role="radiogroup" aria-label="Que fait un clic dans la base ?">
                  <button role="radio" aria-checked={!inserer} onClick={() => setInserer(false)} data-mode-remplacer
                    className={cx("rounded-l-lg px-2.5 py-1 text-xs", !inserer ? "bg-action text-white" : "text-ink-soft hover:bg-surface")}>Remplacer</button>
                  <button role="radio" aria-checked={inserer} onClick={() => setInserer(true)} data-mode-inserer
                    className={cx("rounded-r-lg px-2.5 py-1 text-xs", inserer ? "bg-action text-white" : "text-ink-soft hover:bg-surface")}>Insérer après</button>
                </div>
                <Bouton taille="sm" variante="ghost" disabled={sel === 0} onClick={() => deplacer(-1)} icone={<ArrowLeft size={14} />} aria-label="Déplacer à gauche" />
                <Bouton taille="sm" variante="ghost" disabled={sel >= pictos.length - 1} onClick={() => deplacer(1)} icone={<ArrowRight size={14} />} aria-label="Déplacer à droite" />
                <Bouton taille="sm" variante="ghost" disabled={!peutCombiner} onClick={combiner} title="Une seule image : celui-ci en grand, le suivant en médaillon">Combiner avec le suivant</Bouton>
                {pictos[sel].includes("+") && <Bouton taille="sm" variante="ghost" onClick={separer} icone={<Split size={14} />}>Séparer</Bouton>}
                <Bouton taille="sm" variante="ghost" data-retirer-picto={sel} onClick={retirer} icone={<X size={14} />} className="text-danger">Retirer</Bouton>
                <Bouton taille="sm" variante="ghost" onClick={() => setChoisi(null)} className="ml-auto">Désélectionner</Bouton>
              </>
            )}
          </div>
        </div>
        <div className="mx-5 mt-3 flex flex-wrap items-center gap-2">
          <input id="rechercheMedecin" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Chercher dans toute la base (ex. ventre, brûlure, avaler)"
            className={cx(champ, "h-9 min-w-[240px] flex-1")} />
          <select aria-label="Catégorie" value={actif ?? ""} onChange={(e) => { setOnglet(e.target.value); setQ(""); }} className={cx(champ, "h-9 w-auto")}>
            {onglets.map((k) => <option key={k} value={k}>{k} ({palette[k].length})</option>)}
          </select>
          <span className="text-xs text-ink-muted">
            {sel === null ? "Un clic ajoute à la fin" : inserer ? `Un clic insère après le n° ${sel + 1}` : `Un clic remplace le n° ${sel + 1}`}
          </span>
        </div>
        <div className="mx-5 mt-3 grid flex-1 grid-cols-[repeat(auto-fill,minmax(92px,1fr))] gap-2 overflow-y-auto pb-2 barre-fine">
          {liste.slice(0, 240).map((id) => (
            <button key={id} data-ajouter-picto={id} disabled={(sel === null || inserer) && pictos.length >= 12} onClick={() => ajouter(id)}
              className="rounded-xl bg-surface p-1.5 shadow-panel hover:ring-2 hover:ring-action/40 disabled:opacity-50"><Picto id={id} taille={64} legende /></button>
          ))}
        </div>
        <div className="mt-2 flex justify-end gap-2 rounded-b-2xl border-t border-line bg-canvas/60 px-5 py-3">
          <Bouton onClick={onFermer}>{tr('Annuler')}</Bouton>
          <Bouton id="enregistrerPictos" variante="primary" disabled={!pictos.length} onClick={() => onEnregistrer(pictos)}>Enregistrer la modification</Bouton>
        </div>
      </div>
    </div>
  );
}
