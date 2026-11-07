import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { CheckCircle2, AlertCircle, X } from "lucide-react";
import { lire, urlPicto, type Libelles } from "./api";

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

// ------------------------------------------------------------------ boutons
type Variante = "primary" | "secondary" | "ghost" | "danger" | "success" | "subtle";
const VARIANTES: Record<Variante, string> = {
  primary: "bg-action text-white hover:bg-action-hover shadow-sm",
  secondary: "bg-surface text-ink border border-line-strong hover:bg-canvas shadow-tile",
  ghost: "text-ink-soft hover:bg-canvas hover:text-ink",
  danger: "bg-danger text-white hover:bg-danger-600 shadow-sm",
  success: "bg-ok text-white hover:brightness-110 shadow-sm",
  subtle: "bg-action-50 text-action hover:bg-action-100",
};
export function Bouton({ variante = "secondary", taille = "md", icone, className, children, ...p }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variante?: Variante; taille?: "sm" | "md"; icone?: ReactNode }) {
  return (
    <button
      {...p}
      className={cx("inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50 whitespace-nowrap",
        taille === "sm" ? "h-8 px-2.5 text-[13px]" : "h-9 px-3.5 text-sm", VARIANTES[variante], className)}
    >
      {icone}
      {children}
    </button>
  );
}

// ------------------------------------------------------------------ pastilles
export type Ton = "neutre" | "ok" | "warn" | "review" | "danger" | "held" | "action" | "brand";
const TONS: Record<Ton, string> = {
  neutre: "bg-canvas text-ink-soft ring-line",
  ok: "bg-ok-50 text-ok ring-ok/15",
  warn: "bg-warn-50 text-warn ring-warn/15",
  review: "bg-review-50 text-review ring-review/15",
  danger: "bg-danger-50 text-danger ring-danger/15",
  held: "bg-held-50 text-held ring-held/15",
  action: "bg-action-50 text-action ring-action/15",
  brand: "bg-brand-50 text-brand ring-brand/15",
};
export function Pastille({ ton = "neutre", icone, children, className }: { ton?: Ton; icone?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset", TONS[ton], className)}>
      {icone}
      {children}
    </span>
  );
}

/** Statut d'une décision ou verdict du juriste, en mots simples. */
export const STATUTS: Record<string, { texte: string; ton: Ton }> = {
  CONFORME: { texte: "Conforme", ton: "ok" },
  PREUVES_INSUFFISANTES: { texte: "Information manquante", ton: "warn" },
  A_REVOIR: { texte: "À revoir", ton: "review" },
  BLOQUE: { texte: "Bloquée", ton: "danger" },
  MAINTENUE: { texte: "Maintenue par le médecin", ton: "held" },
  envoye: { texte: "Envoyé", ton: "ok" },
  attente_validation: { texte: "À valider", ton: "action" },
  a_verifier: { texte: "Vérification en cours", ton: "neutre" },
  annulee: { texte: "Remplacée", ton: "neutre" },
  rejete: { texte: "Rejeté", ton: "neutre" },
};
export function Statut({ statut }: { statut: string }) {
  const s = STATUTS[statut] ?? { texte: statut, ton: "neutre" as Ton };
  return <Pastille ton={s.ton}>{s.texte}</Pastille>;
}

// ------------------------------------------------------------------ pictogrammes
const ContexteLibelles = createContext<Libelles | null>(null);
export function FournisseurLibelles({ children }: { children: ReactNode }) {
  const [l, setL] = useState<Libelles | null>(null);
  useEffect(() => { lire<Libelles>("/api/libelles").then(setL).catch(() => setL(null)); }, []);
  return <ContexteLibelles.Provider value={l}>{children}</ContexteLibelles.Provider>;
}
export function useLibelle() {
  const l = useContext(ContexteLibelles);
  return useCallback((id: string, langue: "fr" | "en" | "ar" = "fr"): string => {
    if (id.includes("+")) return id.split("+").map((x) => (l?.[langue]?.[x] ?? x)).join(" + ");
    return l?.[langue]?.[id] ?? (id.includes(":") ? id.slice(id.indexOf(":") + 1).replace(/_/g, " ") : "");
  }, [l]);
}

export function Picto({ id, taille = 56, legende, className }: { id: string; taille?: number; legende?: boolean; className?: string }) {
  const libelle = useLibelle();
  const texte = libelle(id) || id;
  return (
    <figure className={cx("flex flex-col items-center gap-1", className)} style={{ width: legende ? Math.max(taille, 64) : taille }}>
      <img src={urlPicto(id)} alt={texte} title={texte} width={taille} height={taille} className="select-none" draggable={false} />
      {legende && <figcaption className="w-full break-words text-center text-2xs leading-tight text-ink-muted line-clamp-2">{texte}</figcaption>}
    </figure>
  );
}

// ------------------------------------------------------------------ champs
export const champ = "w-full rounded-lg border border-line-strong bg-surface px-3 text-sm text-ink placeholder:text-ink-faint " +
  "shadow-tile transition-colors focus:border-action focus:outline-none focus:ring-4 focus:ring-action/10";
export function Champ({ libelle, aide, htmlFor, children, className }: { libelle: string; aide?: string; htmlFor?: string; children: ReactNode; className?: string }) {
  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      <label htmlFor={htmlFor} className="text-[13px] font-medium text-ink-soft">{libelle}</label>
      {children}
      {aide && <p className="text-xs text-ink-muted">{aide}</p>}
    </div>
  );
}
export function Case({ id, coche, onChange, children }: { id: string; coche: boolean; onChange: (v: boolean) => void; children: ReactNode }) {
  return (
    <label htmlFor={id} className="flex cursor-pointer items-start gap-2.5 text-sm text-ink-soft">
      <input id={id} type="checkbox" checked={coche} onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 rounded border-line-strong text-action accent-[#1F63E0]" />
      <span>{children}</span>
    </label>
  );
}

// ------------------------------------------------------------------ panneau
export function Panneau({ titre, aide, actions, children, className, corps = "p-4" }:
  { titre?: ReactNode; aide?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; corps?: string }) {
  return (
    <section className={cx("rounded-xl bg-surface shadow-panel", className)}>
      {titre && (
        <header className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold text-ink">{titre}</h2>
            {aide && <p className="mt-0.5 text-xs text-ink-muted">{aide}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className={corps}>{children}</div>
    </section>
  );
}

export function Vide({ icone, titre, texte }: { icone?: ReactNode; titre: string; texte?: string }) {
  return (
    <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
      {icone && <div className="grid h-10 w-10 place-items-center rounded-full bg-canvas text-ink-faint">{icone}</div>}
      <p className="text-sm font-medium text-ink-soft">{titre}</p>
      {texte && <p className="max-w-xs text-xs text-ink-muted">{texte}</p>}
    </div>
  );
}

// ------------------------------------------------------------------ boîte de dialogue
export function Dialogue({ ouvert, titre, description, children, actions, onFermer }:
  { ouvert: boolean; titre: string; description?: string; children?: ReactNode; actions: ReactNode; onFermer: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ouvert) return;
    const avant = document.activeElement as HTMLElement | null;
    const champ = ref.current?.querySelector<HTMLElement>("textarea, input, button[data-defaut]");
    champ?.focus();
    const touche = (e: KeyboardEvent) => e.key === "Escape" && onFermer();
    window.addEventListener("keydown", touche);
    return () => { window.removeEventListener("keydown", touche); avant?.focus(); };
  }, [ouvert, onFermer]);
  if (!ouvert) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-[2px] animate-fondu" onMouseDown={onFermer}>
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby="dialogue-titre"
        className="w-full max-w-md rounded-2xl bg-surface shadow-pop animate-entree" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-4 px-5 pt-5">
          <div>
            <h3 id="dialogue-titre" className="text-base font-semibold text-ink">{titre}</h3>
            {description && <p className="mt-1 text-sm text-ink-muted">{description}</p>}
          </div>
          <button onClick={onFermer} aria-label="Fermer" className="rounded-md p-1 text-ink-faint hover:bg-canvas hover:text-ink"><X size={18} /></button>
        </div>
        {children && <div className="px-5 pt-4">{children}</div>}
        <div className="mt-5 flex justify-end gap-2 rounded-b-2xl border-t border-line bg-canvas/60 px-5 py-3">{actions}</div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ notifications
type Notif = { id: number; texte: string; erreur: boolean };
const ContexteNotif = createContext<(texte: string, erreur?: boolean) => void>(() => {});
export function FournisseurNotif({ children }: { children: ReactNode }) {
  const [liste, setListe] = useState<Notif[]>([]);
  const n = useRef(0);
  const notifier = useCallback((texte: string, erreur = false) => {
    const id = ++n.current;
    setListe((l) => [...l.slice(-2), { id, texte, erreur }]);
    setTimeout(() => setListe((l) => l.filter((x) => x.id !== id)), erreur ? 6000 : 3600);
  }, []);
  return (
    <ContexteNotif.Provider value={notifier}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(420px,calc(100vw-32px))] flex-col gap-2" role="status" aria-live="polite">
        {liste.map((x) => (
          <div key={x.id} className="pointer-events-auto flex items-start gap-2.5 rounded-xl bg-ink px-4 py-3 text-sm text-white shadow-pop animate-entree">
            {x.erreur ? <AlertCircle size={18} className="mt-0.5 shrink-0 text-[#FF8A80]" /> : <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-[#7BE0A8]" />}
            <span className="leading-snug">{x.texte}</span>
          </div>
        ))}
      </div>
    </ContexteNotif.Provider>
  );
}
export const useNotifier = () => useContext(ContexteNotif);

/** Interroge régulièrement une adresse ; s'arrête quand l'onglet est caché. */
export function useSondage<T>(charger: () => Promise<T>, intervalle = 1500) {
  const [donnees, setDonnees] = useState<T | null>(null);
  const [erreur, setErreur] = useState<unknown>(null);
  const ref = useRef(charger);
  ref.current = charger;
  const rafraichir = useCallback(async () => {
    try { setDonnees(await ref.current()); setErreur(null); } catch (e) { setErreur(e); }
  }, []);
  useEffect(() => {
    rafraichir();
    const t = setInterval(() => { if (!document.hidden) rafraichir(); }, intervalle);
    return () => clearInterval(t);
  }, [rafraichir, intervalle]);
  return { donnees, erreur, rafraichir };
}

// ------------------------------------------------------------------ recherche de pictogrammes par le sens (serveur)
// Mots-clés + ressemblance d'écriture + sens (si la base est vectorisée) : « essouflement », « tête qui tourne ».
export function useRechercheSens(q: string, actif = true): string[] {
  const [ids, setIds] = useState<string[]>([]);
  useEffect(() => {
    const t = q.trim();
    if (!actif || t.length < 3) { setIds([]); return; }
    let annule = false;
    const h = window.setTimeout(() => {
      fetch(`/api/pictogrammes/chercher?q=${encodeURIComponent(t)}&k=24`)
        .then((r) => (r.ok ? r.json() : { resultats: [] }))
        .then((j: { resultats?: { id: string }[] }) => { if (!annule) setIds((j.resultats ?? []).map((x) => x.id)); })
        .catch(() => { if (!annule) setIds([]); });
    }, 250);
    return () => { annule = true; window.clearTimeout(h); };
  }, [q, actif]);
  return ids;
}
