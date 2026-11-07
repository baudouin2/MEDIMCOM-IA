import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Delete, SendHorizontal } from "lucide-react";
import { combinable, envoyer, lire, urlPicto, type VuePatient } from "./api";
import { cx, useLibelle, useRechercheSens, useSondage } from "./ui";
import { Marque } from "./Marque";

type Langue = "" | "fr" | "en" | "ar";
const ICONES_ONGLETS: Record<string, string> = {
  reponses: "OUI", questions: "QUESTION", corps: "TETE", localisation: "GAUCHE", douleur: "DOULEUR", intensite: "CHIFFRE:5",
  sensations: "CHAUD", symptomes: "FIEVRE", ressenti: "PEUR", maladies: "PALUDISME", soins: "MEDICAMENT", alimentation: "MANGER",
  hygiene: "SE_LAVER_LES_MAINS", grossesse: "ENCEINTE", handicap: "SOURD", personnes: "MEDECIN", "vie quotidienne": "MAISON",
  temps: "MATIN", nombres: "CHIFFRE:3", urgence: "URGENCE", droits: "CONSENTEMENT", autres: "QUESTION",
  general: "MAISON",
};
const NOMS_ONGLETS: Record<string, Record<"fr" | "en" | "ar", string>> = {
  reponses: { fr: "Réponses", en: "Answers", ar: "إجابات" }, questions: { fr: "Questions", en: "Questions", ar: "أسئلة" },
  corps: { fr: "Corps", en: "Body", ar: "الجسم" }, localisation: { fr: "Où ?", en: "Where?", ar: "أين؟" },
  douleur: { fr: "Douleur", en: "Pain", ar: "الألم" }, intensite: { fr: "Intensité", en: "Intensity", ar: "الشدة" },
  sensations: { fr: "Sensations", en: "Sensations", ar: "الإحساس" }, symptomes: { fr: "Symptômes", en: "Symptoms", ar: "الأعراض" },
  ressenti: { fr: "Ressenti", en: "Feelings", ar: "المشاعر" }, maladies: { fr: "Maladies", en: "Illnesses", ar: "الأمراض" },
  soins: { fr: "Soins", en: "Care", ar: "العلاج" }, alimentation: { fr: "Alimentation", en: "Food", ar: "الطعام" },
  hygiene: { fr: "Hygiène, vie", en: "Hygiene, lifestyle", ar: "النظافة ونمط الحياة" }, grossesse: { fr: "Grossesse, enfant", en: "Pregnancy, child", ar: "الحمل والطفل" },
  handicap: { fr: "Handicap", en: "Disability", ar: "الإعاقة" }, personnes: { fr: "Personnes", en: "People", ar: "الأشخاص" },
  "vie quotidienne": { fr: "Vie quotidienne", en: "Daily life", ar: "الحياة اليومية" }, temps: { fr: "Temps", en: "Time", ar: "الوقت" },
  nombres: { fr: "Nombres", en: "Numbers", ar: "الأرقام" }, urgence: { fr: "Urgence", en: "Emergency", ar: "طوارئ" },
  droits: { fr: "Droits, accord", en: "Rights, consent", ar: "الحقوق والموافقة" },
  autres: { fr: "Autres images", en: "More images", ar: "صور أخرى" },
  general: { fr: "Tous les mots", en: "All words", ar: "كل الكلمات" },
  symboles: { fr: "Émojis, symboles", en: "Emojis, symbols", ar: "رموز" },
};
const debutDeMot = (texte: string, q: string) => sansAccents(texte).split(/[\s'’+\-/]+/).some((m) => m.startsWith(q));
const sansAccents = (t: string) => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const MAX = 12;

function langueEnregistree(): Langue {
  try { const l = localStorage.getItem("medimcom-langue"); return l === null ? "fr" : (l as Langue); } catch { return "fr"; }
}

export default function EcranPatient() {
  const { donnees: vue, rafraichir } = useSondage(() => lire<VuePatient>("/api/patient"));
  const libelleDe = useLibelle();
  const [langue, setLangueEtat] = useState<Langue>(langueEnregistree);
  const [onglet, setOnglet] = useState("reponses");
  const [recherche, setRecherche] = useState("");
  const [choix, setChoix] = useState<string[]>([]);
  const [urgence, setUrgence] = useState(false);
  const [envole, setEnvole] = useState(0);
  const [envoi, setEnvoi] = useState<"repos" | "en_cours">("repos");
  const [dernierEnvoi, setDernierEnvoi] = useState<string[]>([]);
  const [mots, setMots] = useState("");
  const [sansImage, setSansImage] = useState<string[]>([]);
  const [guide, setGuide] = useState(false);
  const session = useRef<string | null>(null);

  const setLangue = (l: Langue) => { setLangueEtat(l); try { localStorage.setItem("medimcom-langue", l); } catch { /* stockage indisponible */ } };
  const etiquette = useCallback((id: string) => (langue ? libelleDe(id, langue) : ""), [langue, libelleDe]);

  useEffect(() => {                       // nouvelle consultation : on repart de zéro
    if (!vue) return;
    if (session.current !== null && vue.session !== session.current) setChoix([]);
    session.current = vue.session;
  }, [vue]);

  const envoyerReponse = async (liste: string[]) => {
    if (envoi === "en_cours") return;              // un seul envoi à la fois : pas de double message
    setEnvoi("en_cours");
    try {
      await envoyer("/api/patient/reponse", { pictogrammes: liste });
      setEnvole((n) => n + 1);
      setDernierEnvoi(liste);
    } catch { setEnvoi("repos"); return; }        // le serveur refuse : rien n'est envoyé, le choix reste affiché
    setChoix([]);
    setEnvoi("repos");
    rafraichir();
  };
  const traduireMots = async () => {
    const t = mots.trim();
    if (!t) return;
    try {
      const r = await envoyer<{ pictogrammes: string[]; non_traduits: string[] }>("/api/patient/traduire", { texte: t });
      setChoix((c) => [...c, ...r.pictogrammes].slice(0, MAX));
      setSansImage(r.non_traduits);
      setMots("");
    } catch { /* rien */ }
  };
  const combiner = () => setChoix((c) => {
    if (c.length < 2) return c;
    const [a, b] = c.slice(-2);
    return combinable(a, b) ? [...c.slice(0, -2), `${a}+${b}`] : c;
  });
  const peutCombiner = choix.length >= 2 && combinable(choix[choix.length - 2], choix[choix.length - 1]);

  const palette = vue?.palette ?? {};
  const onglets = Object.keys(palette);
  const ongletActif = palette[onglet] ? onglet : onglets[0];
  const q = sansAccents(recherche.trim());
  const tousPatient = useMemo(() => Array.from(new Set(Object.values(palette).flat())), [palette]);
  const parSens = useRechercheSens(recherche);
  const directs = q.length < 2 ? null : tousPatient.filter((id) =>
    (["fr", "en", "ar"] as const).some((lg) => debutDeMot(libelleDe(id, lg), q)) || debutDeMot(id.replace(/_/g, " "), q));
  // d'abord les pictogrammes dont un mot commence par la saisie, puis ceux trouvés par le sens ou malgré une faute
  const presents = useMemo(() => new Set(tousPatient), [tousPatient]);
  const resultats = directs === null ? null : [...directs, ...parSens.filter((id) => presents.has(id) && !directs.includes(id))];
  const grilleComplete = resultats ?? palette[ongletActif] ?? [];
  // Des milliers d'images possibles (catalogue complet) : on en affiche 96, puis « Afficher plus ».
  const [nbAffiches, setNbAffiches] = useState(96);
  useEffect(() => setNbAffiches(96), [ongletActif, recherche]);
  const grille = grilleComplete.slice(0, nbAffiches);
  const dir = langue === "ar" ? "rtl" : undefined;

  return (
    <div className="min-h-dvh bg-[#F6F7F9] pb-48 sm:pb-40">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 pt-4 sm:px-6">
        <Marque taille={28} texte={false} />
        <div role="group" aria-label="Langue des étiquettes" className="flex rounded-xl bg-surface p-1 shadow-panel">
          {([["", "Images seules"], ["fr", "FR"], ["en", "EN"], ["ar", "عربي"]] as [Langue, string][]).map(([l, t]) => (
            <button key={l || "img"} data-lg={l} aria-pressed={langue === l} onClick={() => setLangue(l)}
              className={cx("h-9 min-w-[44px] rounded-lg px-3 text-sm font-medium transition-colors",
                langue === l ? "bg-brand text-white" : "text-ink-soft hover:bg-canvas")}>
              {l === "" ? <svg viewBox="0 0 24 24" width="18" height="18" aria-label={t} className="mx-auto"><rect x="3" y="4" width="18" height="16" rx="3" fill="none" stroke="currentColor" strokeWidth="2" /><circle cx="9" cy="10" r="2" fill="currentColor" /><path d="M5 18l5-5 3 3 3-3 3 5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" /></svg> : t}
            </button>
          ))}
        </div>
      </header>

      <main className="mx-auto flex max-w-6xl flex-col gap-5 px-4 pt-4 sm:px-6">
        {vue?.urgence && (
          <div id="urgencePatient" role="status" aria-live="assertive" dir={dir}
            className={cx("sticky top-2 z-30 flex items-center gap-3 rounded-3xl p-3 shadow-panel ring-2", vue.urgence === "signalee" ? "bg-danger-50 ring-danger/40" : "bg-ok-50 ring-ok/40")}>
            <img src={urlPicto("URGENCE")} alt="" width={64} height={64} />
            <img src={urlPicto("MEDECIN")} alt="" width={64} height={64} />
            <img src={urlPicto("OUI")} alt="" width={52} height={52} />
            <p className="text-[17px] font-semibold text-ink">
              {vue.urgence === "signalee"
                ? { "": "", fr: "Le médecin est prévenu.", en: "The doctor has been alerted.", ar: "تم إبلاغ الطبيب." }[langue]
                : { "": "", fr: "Le médecin s'occupe de vous.", en: "The doctor is taking care of you.", ar: "الطبيب يعتني بك." }[langue]}
            </p>
          </div>
        )}
        <MessageRecu vue={vue} etiquette={etiquette} dir={dir} nomMedecin={langue ? { fr: "Médecin", en: "Doctor", ar: "الطبيب" }[langue] : ""}
          incompris={() => envoyerReponse(["NE_PAS", "COMPRENDRE"])} langue={langue} />

        <div className="grid gap-3 sm:grid-cols-[auto_1fr]">
          <button id="guideDouleur" onClick={() => setGuide(true)}
            className="flex items-center gap-3 rounded-2xl bg-danger-50 px-4 py-2 text-left ring-1 ring-danger/20 hover:ring-2 hover:ring-danger/40">
            <img src={urlPicto("DOULEUR")} alt="" width={56} height={56} />
            <span className="text-[16px] font-semibold text-danger" dir={dir}>{{ "": "", fr: "Décrire ma douleur", en: "Describe my pain", ar: "صف ألمي" }[langue]}</span>
          </button>
          <div className="flex items-center gap-2 rounded-2xl bg-surface px-3 shadow-panel ring-1 ring-line focus-within:ring-2 focus-within:ring-brand">
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" className="shrink-0 text-ink-muted"><path d="M4 20h4l10-10-4-4L4 16v4z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" /></svg>
            <input id="ecrire" value={mots} onChange={(e) => setMots(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") traduireMots(); }} dir={dir}
              placeholder={{ "": "…", fr: "Ou écrivez quelques mots (ex. mal au ventre depuis hier)", en: "Or type a few words (e.g. belly pain since yesterday)", ar: "أو اكتب بضع كلمات" }[langue]}
              aria-label="Écrire quelques mots" className="h-12 w-full bg-transparent text-[15px] text-ink placeholder:text-ink-faint focus:outline-none" />
            <button id="ajouterMots" onClick={traduireMots} disabled={!mots.trim()} className="shrink-0 rounded-xl bg-brand px-3 py-2 text-sm font-medium text-white disabled:opacity-40">
              {{ "": "+", fr: "Ajouter", en: "Add", ar: "أضف" }[langue]}
            </button>
          </div>
        </div>
        {sansImage.length > 0 && <p className="-mt-2 px-2 text-sm text-ink-muted">{{ "": "", fr: "Sans image : ", en: "No picture: ", ar: "بدون صورة: " }[langue]}{sansImage.join(", ")}</p>}

        <div className="flex items-center gap-2 rounded-2xl bg-surface px-3 shadow-panel ring-1 ring-line focus-within:ring-2 focus-within:ring-brand">
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" className="shrink-0 text-ink-muted"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" strokeWidth="2" /><path d="M20 20l-4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
          <input id="recherche" type="search" value={recherche} onChange={(e) => setRecherche(e.target.value)} dir={dir}
            placeholder={{ "": "…", fr: "Chercher un pictogramme (ex. ventre, brûlure)", en: "Search a pictogram (e.g. belly, burning)", ar: "ابحث عن رمز" }[langue]}
            aria-label="Chercher un pictogramme" className="h-12 w-full bg-transparent text-[15px] text-ink placeholder:text-ink-faint focus:outline-none" />
          {resultats && <span className="shrink-0 text-sm text-ink-muted">{resultats.length}</span>}
        </div>

        <nav role="tablist" aria-label="Catégories" className="flex gap-2 overflow-x-auto pb-1 barre-fine">
          {onglets.map((k) => {
            const icone = palette[k].includes(ICONES_ONGLETS[k]) ? ICONES_ONGLETS[k] : palette[k][0];
            const actif = k === ongletActif && !resultats;
            return (
              <button key={k} role="tab" aria-selected={actif} data-onglet={k} onClick={() => { setOnglet(k); setRecherche(""); }}
                className={cx("flex shrink-0 items-center gap-2.5 rounded-2xl py-2 pl-2 pr-2 transition-all",
                  langue && "pr-4",
                  actif ? "bg-surface shadow-panel ring-2 ring-brand" : "bg-surface/60 ring-1 ring-line hover:bg-surface")}>
                <img src={urlPicto(icone)} alt={k} width={52} height={52} draggable={false} />
                {langue && <span dir={dir} className={cx("text-[15px] font-medium", actif ? "text-ink" : "text-ink-muted")}>{NOMS_ONGLETS[k]?.[langue] ?? k}</span>}
              </button>
            );
          })}
        </nav>

        <div id="grille" className="grid grid-cols-[repeat(auto-fill,minmax(124px,1fr))] gap-3">
          {grille.map((id) => (
            <button key={id} data-picto={id} aria-label={etiquette(id) || libelleDe(id) || id}
              disabled={choix.length >= MAX}
              onClick={() => setChoix((c) => (c.length < MAX ? [...c, id] : c))}
              className="group flex flex-col items-center gap-1.5 rounded-2xl bg-surface px-2 pb-3 pt-3 shadow-panel transition-transform hover:ring-2 hover:ring-action/40 active:scale-[.97] disabled:opacity-50">
              <img src={urlPicto(id)} alt="" width={96} height={96} draggable={false} loading="lazy" />
              <span dir={dir} className="min-h-[1.25rem] text-center text-sm leading-tight text-ink-soft">{etiquette(id)}</span>
            </button>
          ))}
        </div>
        {grilleComplete.length > grille.length && (
          <div className="mt-4 flex justify-center">
            <button id="afficherPlus" onClick={() => setNbAffiches((n) => n + 96)}
              className="rounded-full bg-surface px-5 py-2.5 text-sm font-medium text-action shadow-panel hover:ring-2 hover:ring-action/40">
              {{ "": "", fr: "Afficher plus", en: "Show more", ar: "عرض المزيد" }[langue]} ({grilleComplete.length - grille.length})
            </button>
          </div>
        )}
      </main>

      {dernierEnvoi.length > 0 && (
        <div id="dernierEnvoi" className="fixed inset-x-0 bottom-[160px] z-10 sm:bottom-[112px] mx-auto flex max-w-6xl items-center gap-2 px-4 sm:px-6">
          <span className="flex items-center gap-2 rounded-full bg-ok px-3 py-1.5 text-sm font-medium text-white shadow-panel" dir={dir}>
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M3 8l3 3 7-7" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" /></svg>
            {{ "": "", fr: "Envoyé au médecin", en: "Sent to the doctor", ar: "أُرسل إلى الطبيب" }[langue]}
          </span>
          {dernierEnvoi.map((id, i) => <img key={i} src={urlPicto(id)} alt={etiquette(id) || id} width={34} height={34} className="rounded-md bg-surface shadow-panel" />)}
        </div>
      )}
      {guide && <GuideDouleur palette={palette} etiquette={etiquette} dir={dir} langue={langue}
        onFermer={() => setGuide(false)} onAjouter={(ids) => { setChoix((c) => [...c, ...ids].slice(0, MAX)); setGuide(false); }} />}

      {/* plateau de réponse */}
      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface/95 shadow-[0_-8px_24px_-12px_rgba(16,24,40,.18)] backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 px-3 py-2.5 sm:flex-nowrap sm:gap-3 sm:px-6 sm:py-3" style={{ paddingBottom: "max(10px, env(safe-area-inset-bottom))" }}>
          <div id="choisis" dir={dir} aria-label="Ma réponse" className="flex min-h-[64px] w-full items-center gap-2 overflow-x-auto rounded-2xl bg-canvas px-2.5 py-2 ring-1 ring-inset ring-line barre-fine sm:min-h-[84px] sm:w-auto sm:flex-1">
            {choix.length === 0 && [0, 1, 2].map((i) => <span key={i} className="h-12 w-12 shrink-0 rounded-xl border-2 border-dashed border-line-strong/70 sm:h-[64px] sm:w-[64px]" />)}
            {choix.map((id, i) => (
              <button key={`${id}-${i}`} data-retirer={i} onClick={() => setChoix((c) => c.filter((_, j) => j !== i))}
                aria-label={`retirer ${etiquette(id) || id}`} className="relative shrink-0 rounded-xl bg-surface p-1 shadow-panel animate-entree">
                <img src={urlPicto(id)} alt={id} width={60} height={60} draggable={false} />
                <span className="absolute -right-1.5 -top-1.5 grid h-5 w-5 place-items-center rounded-full bg-ink text-white" aria-hidden>
                  <svg viewBox="0 0 10 10" width="8" height="8"><path d="M2 2l6 6M8 2L2 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
                </span>
              </button>
            ))}
          </div>
          <BoutonPlateau id="combiner" label="combiner les deux derniers pictogrammes" disabled={!peutCombiner} onClick={combiner} className="bg-action-50 text-action">
            <svg viewBox="0 0 64 64" width="44" height="44" aria-hidden="true">
              <rect x="6" y="6" width="34" height="34" rx="8" fill="#fff" stroke="currentColor" strokeWidth="4" />
              <circle cx="42" cy="42" r="15" fill="#fff" stroke="currentColor" strokeWidth="4" />
              <path d="M42 35v14M35 42h14" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
            </svg>
          </BoutonPlateau>
          <BoutonPlateau id="effacer" label="retirer le dernier pictogramme" disabled={!choix.length} onClick={() => setChoix((c) => c.slice(0, -1))} className="bg-canvas text-ink-soft">
            <Delete size={34} strokeWidth={1.75} />
          </BoutonPlateau>
          <BoutonPlateau id="envoyer" label="envoyer" disabled={!choix.length || envoi === "en_cours"} onClick={() => choix.length && envoyerReponse(choix.slice())} className="bg-ok text-white shadow-sm sm:w-[104px]">
            {envoi === "en_cours" ? <span className="h-9 w-9 animate-spin rounded-full border-4 border-white border-t-transparent" /> : <SendHorizontal size={36} strokeWidth={2} />}
          </BoutonPlateau>
          <span className="hidden h-14 w-px bg-line sm:block" />
          <BoutonPlateau id="urgence" label="urgence" onClick={() => setUrgence(true)} className="bg-danger shadow-sm">
            <img src={urlPicto("URGENCE")} alt="" width={50} height={50} className="rounded-lg" />
          </BoutonPlateau>
        </div>
      </div>

      {urgence && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink/55 p-4 animate-fondu" onClick={() => setUrgence(false)}>
          <div role="dialog" aria-modal="true" aria-label="urgence" className="rounded-3xl bg-surface p-6 shadow-pop animate-entree" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-center gap-3">
              <img src={urlPicto("URGENCE")} alt="urgence" width={128} height={128} />
              <img src={urlPicto("QUESTION")} alt="?" width={72} height={72} />
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <button id="urgOui" aria-label="oui" onClick={() => { setUrgence(false); envoyerReponse(["URGENCE"]); }}
                className="grid place-items-center rounded-2xl bg-ok-50 p-3 ring-2 ring-ok/30 active:scale-[.97]"><img src={urlPicto("OUI")} alt="" width={96} height={96} /></button>
              <button id="urgNon" aria-label="non" onClick={() => setUrgence(false)}
                className="grid place-items-center rounded-2xl bg-danger-50 p-3 ring-2 ring-danger/20 active:scale-[.97]"><img src={urlPicto("NON")} alt="" width={96} height={96} /></button>
            </div>
          </div>
        </div>
      )}
      {envole > 0 && (
        <div key={envole} className="pointer-events-none fixed inset-0 z-40 grid place-items-center" aria-hidden>
          <div className="grid h-44 w-44 place-items-center rounded-full bg-ok text-white shadow-pop animate-envol"><SendHorizontal size={84} strokeWidth={2} /></div>
        </div>
      )}
    </div>
  );
}

function BoutonPlateau({ id, label, disabled, onClick, className, children }:
  { id: string; label: string; disabled?: boolean; onClick: () => void; className?: string; children: React.ReactNode }) {
  return (
    <button id={id} aria-label={label} title={label} disabled={disabled} onClick={onClick}
      className={cx("grid h-16 flex-1 shrink-0 place-items-center rounded-2xl transition-transform active:scale-95 disabled:opacity-35 disabled:active:scale-100 sm:h-[84px] sm:w-[84px] sm:flex-none", className)}>
      {children}
    </button>
  );
}

function MessageRecu({ vue, etiquette, dir, nomMedecin, incompris, langue }:
  { vue: VuePatient | null; etiquette: (id: string) => string; dir?: "rtl"; nomMedecin: string; incompris: () => void; langue: Langue }) {
  const msgs = vue?.messages ?? [];
  const dernier = msgs[msgs.length - 1];
  const anciens = msgs.slice(0, -1).reverse().slice(0, 4);
  const [eclat, setEclat] = useState(0);
  const vu = useRef<number | null>(null);
  useEffect(() => {
    if (dernier && vu.current !== null && dernier.id !== vu.current) setEclat((n) => n + 1);
    vu.current = dernier?.id ?? 0;
  }, [dernier]);
  return (
    <section aria-live="polite" className="flex flex-col gap-3">
      <div id="recu" key={eclat} className={cx("recu relative rounded-3xl bg-surface px-5 pb-5 pt-16 shadow-panel ring-1 ring-line", eclat > 0 && "animate-arrivee")}>
        <span className={cx("absolute left-4 top-4 flex items-center gap-2 rounded-full bg-brand-50 p-1 text-brand", nomMedecin && "pr-3")}>
          <img src={urlPicto("MEDECIN")} alt="" width={30} height={30} className="rounded-full bg-surface" />
          {nomMedecin && <span className="text-xs font-medium" dir={dir}>{nomMedecin}</span>}
        </span>
        {dernier ? (
          <>
            <div dir={dir} className="bande flex flex-wrap justify-center gap-3 sm:gap-4">
              {dernier.pictogrammes.map((id, i) => (
                <figure key={i} className="flex w-[88px] flex-col items-center gap-1.5 sm:w-[112px]">
                  <img src={urlPicto(id)} alt={etiquette(id) || id} width={112} height={112} draggable={false} className="h-[88px] w-[88px] sm:h-[112px] sm:w-[112px]" />
                  <figcaption dir={dir} className="min-h-[1.25rem] text-center text-[15px] leading-tight text-ink-soft">{etiquette(id)}</figcaption>
                </figure>
              ))}
            </div>
            {etiquette("OUI") && dernier.texte && (
              <p className="mx-auto mt-4 max-w-2xl rounded-xl bg-canvas px-4 py-2 text-center text-[17px] leading-snug text-ink" lang="fr">{dernier.texte}</p>
            )}
            <div className="mt-4 flex flex-wrap items-center justify-center gap-3">
              {vue?.attend_reponse && (
                <span className="flex items-center gap-2 rounded-full bg-action-50 p-1.5 ring-1 ring-action/20">
                  <img src={urlPicto("QUESTION")} alt="à vous de répondre" width={44} height={44} className="animate-battement" />
                </span>
              )}
              {/* « Je ne comprends pas » : un geste, sans avoir à chercher les pictogrammes ; le médecin est conseillé */}
              <button id="incompris" onClick={incompris} dir={dir}
                className="flex items-center gap-2 rounded-2xl bg-warn-50 py-1.5 pl-1.5 pr-3 ring-1 ring-warn/30 active:scale-[.97]"
                aria-label={{ "": "je ne comprends pas", fr: "je ne comprends pas", en: "I don't understand", ar: "لا أفهم" }[langue]}>
                <img src={urlPicto("NE_PAS")} alt="" width={40} height={40} />
                <img src={urlPicto("COMPRENDRE")} alt="" width={40} height={40} />
                {langue && <span className="text-[15px] font-medium text-ink">{{ fr: "Je ne comprends pas", en: "I don't understand", ar: "لا أفهم" }[langue]}</span>}
              </button>
            </div>
          </>
        ) : (
          <div className="attente flex flex-col items-center gap-2 py-6 text-center">
            <img src={urlPicto("ATTENDRE")} alt="attendre" width={88} height={88} className="opacity-70" />
            <span dir={dir} className="text-[15px] text-ink-muted">{etiquette("ATTENDRE")}</span>
          </div>
        )}
      </div>
      {anciens.length > 0 && (
        <div id="anciens" className="flex flex-col gap-1.5 px-1">
          {anciens.map((m) => (
            <div key={m.id} className="flex flex-wrap items-center gap-1 opacity-70">
              {m.pictogrammes.map((id, i) => <img key={i} src={urlPicto(id)} alt={id} width={36} height={36} draggable={false} />)}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}


// ------------------------------------------------------------------ guide « Décrire ma douleur »
// Quatre questions simples, une à la fois : où, comment, combien, depuis quand. Chaque étape peut être passée.
function GuideDouleur({ palette, etiquette, dir, langue, onFermer, onAjouter }: {
  palette: Record<string, string[]>; etiquette: (id: string) => string; dir?: "rtl"; langue: Langue;
  onFermer: () => void; onAjouter: (ids: string[]) => void;
}) {
  const T = (fr: string, en: string, ar: string) => ({ "": "", fr, en, ar }[langue]);
  const etapes = [
    { cle: "ou", titre: T("Où avez-vous mal ?", "Where does it hurt?", "أين تشعر بالألم؟"), ids: [...(palette.corps ?? []), ...(palette.localisation ?? [])] },
    { cle: "comment", titre: T("Comment est la douleur ?", "What is the pain like?", "كيف هو الألم؟"), ids: palette.douleur ?? [] },
    { cle: "combien", titre: T("Combien avez-vous mal ? (0 = pas du tout, 10 = le pire)", "How much does it hurt? (0 = none, 10 = worst)", "ما شدة الألم؟ (0 لا شيء، 10 الأسوأ)"), ids: Array.from({ length: 11 }, (_, i) => `CHIFFRE:${i}`) },
    { cle: "quand", titre: T("Depuis quand ?", "Since when?", "منذ متى؟"), ids: palette.temps ?? [] },
  ];
  const [n, setN] = useState(0);
  const [choix, setChoix] = useState<Record<string, string[]>>({});
  const etape = etapes[n];
  const basculer = (id: string) => setChoix((c) => {
    const actuels = c[etape.cle] ?? [];
    const multiple = etape.cle === "ou";
    const suivant = actuels.includes(id) ? actuels.filter((x) => x !== id) : multiple ? [...actuels, id].slice(-2) : [id];
    return { ...c, [etape.cle]: suivant };
  });
  const terminer = () => {
    const ou = choix.ou ?? [], comment = choix.comment ?? [];
    const corps = ou.filter((x) => (palette.corps ?? []).includes(x));
    const cote = ou.filter((x) => !(palette.corps ?? []).includes(x));
    const douleur = comment[0] ?? "DOULEUR";
    const ids: string[] = [];
    if (corps[0] && combinable(corps[0], douleur)) {          // une image : partie du corps + type de douleur (+ côté)
      const image = cote[0] && combinable(`${corps[0]}+${douleur}`, cote[0]) ? `${corps[0]}+${douleur}+${cote[0]}` : `${corps[0]}+${douleur}`;
      ids.push(image, ...corps.slice(1));
      if (cote[0] && !image.includes(cote[0])) ids.push(cote[0]);
    } else {
      ids.push(...corps, douleur, ...cote.slice(0, 1));
    }
    if (choix.combien?.[0]) ids.push(choix.combien[0]);
    if (choix.quand?.[0]) ids.push(choix.quand[0]);
    onAjouter(ids);
  };
  const couleur = (i: number) => `hsl(${120 - i * 12} 70% 45%)`;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/40 p-3 sm:items-center" onMouseDown={onFermer}>
      <div role="dialog" aria-modal="true" aria-label="Décrire ma douleur" onMouseDown={(e) => e.stopPropagation()}
        className="flex max-h-[92dvh] w-full max-w-4xl flex-col rounded-3xl bg-surface p-5 shadow-pop">
        <div className="flex items-center justify-between gap-3">
          <div className="flex gap-1.5">{etapes.map((e, i) => <span key={e.cle} className={cx("h-2.5 w-10 rounded-full", i <= n ? "bg-brand" : "bg-line")} />)}</div>
          <button onClick={onFermer} aria-label="Fermer" className="rounded-xl px-3 py-1 text-2xl leading-none text-ink-muted hover:bg-canvas">×</button>
        </div>
        <h2 dir={dir} className="mt-3 text-[22px] font-semibold text-ink">{etape.titre}</h2>
        <div className="mt-3 grid flex-1 grid-cols-[repeat(auto-fill,minmax(112px,1fr))] gap-3 overflow-y-auto pb-2">
          {etape.ids.map((id) => {
            const actif = (choix[etape.cle] ?? []).includes(id);
            const chiffre = id.startsWith("CHIFFRE:") ? Number(id.slice(8)) : null;
            return (
              <button key={id} data-guide={id} onClick={() => basculer(id)}
                className={cx("flex flex-col items-center gap-1.5 rounded-2xl px-2 pb-3 pt-3 shadow-panel transition", actif ? "bg-brand-50 ring-4 ring-brand" : "bg-surface ring-1 ring-line")}>
                {chiffre !== null
                  ? <span className="grid h-[84px] w-[84px] place-items-center rounded-2xl text-4xl font-bold text-white" style={{ background: couleur(chiffre) }}>{chiffre}</span>
                  : <img src={urlPicto(id)} alt="" width={84} height={84} />}
                <span dir={dir} className="text-center text-sm leading-tight text-ink-soft">{chiffre === null ? etiquette(id) : ""}</span>
              </button>
            );
          })}
        </div>
        <div className="mt-3 flex items-center justify-between gap-3">
          <button onClick={() => (n ? setN(n - 1) : onFermer())} className="rounded-2xl px-5 py-3 text-[16px] font-medium text-ink-soft ring-1 ring-line">{n ? T("Retour", "Back", "رجوع") : T("Annuler", "Cancel", "إلغاء")}</button>
          {n < etapes.length - 1
            ? <button id="guideSuivant" onClick={() => setN(n + 1)} className="rounded-2xl bg-brand px-6 py-3 text-[16px] font-semibold text-white">{(choix[etape.cle] ?? []).length ? T("Suivant", "Next", "التالي") : T("Passer", "Skip", "تخطَّ")}</button>
            : <button id="guideTerminer" onClick={terminer} className="rounded-2xl bg-ok px-6 py-3 text-[16px] font-semibold text-white">{T("Ajouter à ma réponse", "Add to my answer", "أضف إلى ردي")}</button>}
        </div>
      </div>
    </div>
  );
}
