// Access to the Python server's API (interface/serveur.py).

export type Fait = { valeur: unknown; source?: string; confirme: boolean };
export type Echange = {
  auteur: string; texte: string; donnees?: Record<string, unknown>; confirme?: boolean; v?: number;
  pictogrammes?: string[]; interpretation?: string; en_reponse_a?: string | null;
};
export type Decision = {
  id: number; type: string; statut: string; auteur: string; texte?: string | null;
  medicament?: string | null; dose?: string | null; posologie?: string | null; mode?: string | null;
  contenu_type?: string | null; valide_par?: string | null; pictogrammes?: string[] | null; non_traduits?: string[] | null;
  pictogrammes_choisis_par?: string | null; source_question?: number | null; source_prescription?: number | null;
  demande?: Record<string, unknown> | null; maintien?: { par: string; justification: string } | null; v?: number;
  rapproches?: Record<string, string>;
  masque?: boolean;
  precontrole?: { verdict: string; texte?: string | null; analyse?: Record<string, unknown>;
    constats: { regle: string; niveau: string; base: string; detail: string; piste?: string | null; reference_courte: string }[];
    lecture?: { regle: string; niveau: string; detail: string }[] } | null;
};
export type Constat = {
  regle: string; niveau: string; base: string; fiches: string[]; source: string; reference_courte: string;
  detail: string; piste?: string | null; lacune?: string | null;
};
export type Verdict = {
  objet: string; verdict: string; decision_id?: number; message?: string; constats: Constat[];
  obligations: Constat[]; informations: Constat[]; depassement_possible?: boolean; informations_manquantes?: string[];
};
export type Suggestion = { id: number; type: string; texte: string; raison: string; source: string; statut: string; auteur: string;
  prescription?: { medicament: string; dose: string; posologie: string } };
export type DocumentPatient = { id: number; nom: string; type: string; mime: string; taille: number; date: string; auteur?: string;
  extraction: { statut: string; par?: string | null; resume: string; medicaments: { nom: string; dose: string; posologie: string }[];
    maladies: string[]; allergies: string[]; lisibilite?: string | null; erreur_modele?: string } };
export type Question = { id: number; question: string; raison: string; cle?: string | null; statut: string; auteur: string };
export type MessageAgent = { id: number; de: string; type: string; contenu: string };
export type Lacune = { id?: string; sujet: string; detail?: string };

export type VueMedecin = {
  dictee?: "xai" | "groq" | "navigateur";
  reflexion_en_cours?: boolean;
  duree_modele?: number | null;
  modele?: { disponible: boolean; message: string; modele: string; fournisseur?: string } | null;
  langue?: string;
  ordonnances?: { id: number; medicament: string }[];
  documents?: DocumentPatient[];
  session: string; mode: string; journal: string; lignes: number;
  etat: Record<string, Fait>; fil: Echange[]; questions: Question[]; decisions: Decision[];
  suggestions: Suggestion[]; verdicts: Verdict[]; messages: MessageAgent[]; lacunes: Lacune[];
  mesures: { par: string; mesure: string; citation: string }[];
  incidents: { par: string; gravite: string; description: string }[];
  prescripteurs: Record<string, string>; medicaments: string[]; cles_fermees: string[];
  demo: { actif: boolean; titre: string | null; etape: number; total: number; prochaine: string | null };
};
export type VuePatient = {
  session: string; attend_reponse: boolean; palette: Record<string, string[]>; urgence?: "signalee" | "prise_en_charge" | null;
  medicaments?: string[];
  ordonnances?: { id: number; medicament: string; dose: string; posologie: string; prescripteur: string; valide_par: string;
    date: string; statut: string; pictogrammes: string[]; en_images: string; empreinte: string }[];
  messages: { id: number; pictogrammes: string[]; contenu_type?: string | null; texte?: string }[];
  documents?: { id: number; type: string; lu: boolean }[];
};
export type Libelles = Record<"fr" | "en" | "ar", Record<string, string>>;

/** Doctor-screen token: read from the private link (?jeton=…), kept for the life of the tab. */
export function jetonMedecin(): string {
  const q = new URLSearchParams(window.location.search).get("jeton");
  try {
    if (q) sessionStorage.setItem("medimcom-jeton", q);
    return q || sessionStorage.getItem("medimcom-jeton") || "";
  } catch {
    return q || "";
  }
}

export const urlPicto = (id: string) => `/pictos/${encodeURIComponent(id)}.svg`;

export class ErreurApi extends Error {
  constructor(message: string, public statut: number) { super(message); }
}

export async function lire<T>(url: string, jeton?: string): Promise<T> {
  const r = await fetch(url, { headers: jeton ? { "X-Jeton": jeton } : {} });
  if (!r.ok) throw new ErreurApi(r.status === 403 ? "Accès refusé" : `Erreur ${r.status}`, r.status);
  return r.json();
}

export async function envoyer<T = { retour?: string }>(url: string, corps: unknown, jeton?: string): Promise<T> {
  const entetes: Record<string, string> = { "Content-Type": "application/json" };
  if (jeton) entetes["X-Jeton"] = jeton;
  const r = await fetch(url, { method: "POST", headers: entetes, body: JSON.stringify(corps ?? {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new ErreurApi((j as { erreur?: string }).erreur || `Erreur ${r.status}`, r.status);
  return j as T;
}

// Same rules as the server (medimcom/bibliotheque.py): 3 elements at most, no duplicate,
// and never negation, limit, emergency or STOP as a badge.
const JAMAIS_COMBINE = ["NE_PAS", "MAXIMUM", "URGENCE", "STOP"];
export function combinable(a: string, b: string): boolean {
  const parts = [...a.split("+"), ...b.split("+")];
  return parts.length <= 3 && new Set(parts).size === parts.length && !parts.some((x) => JAMAIS_COMBINE.includes(x));
}
