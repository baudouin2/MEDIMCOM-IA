// Interface language (French, English, Arabic): every text of the page is shown in the user's language.
// The interface is written in French; this module translates what is displayed, at display time, from a dictionary
// (i18n_dico.json) and a few patterns, so that switching language changes ALL the page at once — what is already on
// screen included — and switching back restores the original. Texts typed by people (doctor's messages, record
// values) are never translated: their elements carry data-notr. Agents' messages are translated by the server.
import DICO from "./i18n_dico.json";

export type Langue = "fr" | "en" | "ar";
const D = DICO as unknown as Record<string, [string, string]>;
const NORMAL: Record<string, [string, string]> = {};
const MINUSCULES: Record<string, [string, string]> = {};
const norm = (t: string) => t.replace(/\s+/g, " ").trim();
for (const [fr, cibles] of Object.entries(D)) { NORMAL[norm(fr)] = cibles; MINUSCULES[norm(fr).toLowerCase()] ??= cibles; }
const majuscule = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

// Texts with numbers or names inside
const MOTIFS: [RegExp, (m: RegExpMatchArray, l: Langue) => string][] = [
  [/^(\d+) ans$/, (m, l) => (l === "en" ? `${m[1]} years` : `${m[1]} سنة`)],
  [/^(\d+(?:[.,]\d+)?) kg$/, (m) => `${m[1]} kg`],
  [/^Étape (\d+) sur (\d+)$/, (m, l) => (l === "en" ? `Step ${m[1]} of ${m[2]}` : `الخطوة ${m[1]} من ${m[2]}`)],
  [/^Étape : (.+)$/, (m, l) => (l === "en" ? `Step: ${m[1]}` : `الخطوة: ${m[1]}`)],
  [/^Journal intact, (\d+) entrées$/, (m, l) => (l === "en" ? `Log intact, ${m[1]} entries` : `السجل سليم، ${m[1]} قيدًا`)],
  [/^(\d+) masqués?$/, (m, l) => (l === "en" ? `${m[1]} hidden` : `${m[1]} مخفية`)],
  [/^(\d+) (heures?|jours?|semaines?|mois|ans?)$/, (m, l) => {
    const u: Record<string, [string, string, string]> = { heure: ["hour", "hours", "ساعة"], jour: ["day", "days", "يوم"], semaine: ["week", "weeks", "أسبوع"], mois: ["month", "months", "شهر"], an: ["year", "years", "سنة"] };
    const [s, p, a] = u[m[2].replace(/s$/, "")] ?? u[m[2]] ?? [m[2], m[2], m[2]];
    return l === "en" ? `${m[1]} ${Number(m[1]) > 1 ? p : s}` : `${m[1]} ${a}`;
  }],
  [/^Choisis par : (.+)$/, (m, l) => (l === "en" ? `Chosen by: ${tr(m[1], l)}` : `اختيرت بواسطة: ${tr(m[1], l)}`)],
  [/^Ensuite : (.+)$/, (m, l) => (l === "en" ? `Next: ${m[1]}` : `التالي: ${m[1]}`)],
  [/^Sans pictogramme : (.+)\. Reformulez si ces mots comptent\.$/, (m, l) => (l === "en" ? `No pictogram: ${m[1]}. Rephrase if these words matter.` : `بلا رمز: ${m[1]}. أعد الصياغة إذا كانت هذه الكلمات مهمة.`)],
  [/^Sans pictogramme : (.+)$/, (m, l) => (l === "en" ? `No pictogram: ${m[1]}` : `بلا رمز: ${m[1]}`)],
  [/^Analyse du juriste \((\d+)\)$/, (m, l) => (l === "en" ? `Legal agent's analysis (${m[1]})` : `تحليل الوكيل القانوني (${m[1]})`)],
  [/^Allergie : (.+)$/, (m, l) => (l === "en" ? `Allergy: ${m[1]}` : `حساسية: ${m[1]}`)],
  [/^(\d+) sur 10$/, (m, l) => (l === "en" ? `${m[1]} out of 10` : `${m[1]} من 10`)],
  [/^Session (.+)$/, (m, l) => (l === "en" ? `Session ${m[1]}` : `الجلسة ${m[1]}`)],
  [/^Envoyé au patient, validé par (.+)$/, (m, l) => (l === "en" ? `Sent to the patient, approved by ${tr(m[1], l)}` : `أُرسل إلى المريض، اعتمده ${tr(m[1], l)}`)],
  [/^Prescription n° (\d+) \((.+)\)(.*)$/, (m, l) => (l === "en" ? `Prescription no. ${m[1]} (${tr(m[2], l)})${tr(m[3], l)}` : `الوصفة رقم ${m[1]} (${tr(m[2], l)})${tr(m[3], l)}`)],
  [/^(.+?) n° (\d+)$/, (m, l) => `${tr(m[1], l)} ${l === "en" ? "no." : "رقم"} ${m[2]}`],
  [/^Agents MEDIMCOM · modèle (.+)$/, (m, l) => (l === "en" ? `MEDIMCOM agents · model ${m[1]}` : `وكلاء MEDIMCOM · النموذج ${m[1]}`)],
  [/^(.*)\(([^()]*) · modèle open source\)$/, (m, l) => `${m[1]}(${m[2]} · ${l === "en" ? "open-source model" : "نموذج مفتوح المصدر"})`],
  [/^(.+) répond à « (.+) »$/, (m, l) => (l === "en" ? `${tr(m[1], l)} answers “${m[2]}”` : `${tr(m[1], l)} يجيب عن «${m[2]}»`)],
];

/** One text in language l (unknown text is returned unchanged). */
export function tr(texte: string, l: Langue = langue): string {
  if (l === "fr" || !texte) return texte;
  const n = norm(texte);
  if (!n) return texte;
  const i = l === "en" ? 0 : 1;
  const avant = texte.match(/^\s*/)?.[0] ?? "", apres = texte.match(/\s*$/)?.[0] ?? "";
  const exact = NORMAL[n];
  if (exact) return avant + (exact[i] || exact[0]) + apres;
  const bas = MINUSCULES[n.toLowerCase()];                 // « Ventre », « ventre »
  if (bas) { const x = bas[i] || bas[0]; return avant + (n[0] === n[0].toUpperCase() ? majuscule(x) : x) + apres; }
  for (const [motif, f] of MOTIFS) {
    const m = n.match(motif);
    if (m) return avant + f(m, l) + apres;
  }
  if (n.includes(", ")) {                                   // « Femme, 25 ans »: a list of known values
    const parties = n.split(", ").map((x) => tr(x, l));
    if (parties.some((x, k) => x !== n.split(", ")[k])) return avant + parties.join(l === "ar" ? "، " : ", ") + apres;
  }
  return texte;
}

let langue: Langue = "fr";
const ATTRIBUTS = ["placeholder", "title", "aria-label", "alt"];
type Etat = { fr: string; vu: string };
const textes = new WeakMap<Text, Etat>();
const attributs = new WeakMap<Element, Record<string, Etat>>();

// texts typed by people are never translated: data-notr, and what is inside a text box (its placeholder is translated)
const exclu = (n: Node | null, attribut = false): boolean => {
  for (let e = n instanceof Element ? n : n?.parentElement ?? null; e; e = e.parentElement) {
    if (e.hasAttribute("data-notr") || e.tagName === "SCRIPT" || e.tagName === "STYLE") return true;
    if (e.tagName === "TEXTAREA" && !attribut) return true;
  }
  return false;
};

function texte(t: Text) {
  if (exclu(t)) return;
  const etat = textes.get(t);
  const actuel = t.nodeValue ?? "";
  // React changed the text since our last pass: the new value is the new original
  const fr = etat && actuel === etat.vu ? etat.fr : actuel;
  const vu = tr(fr);
  textes.set(t, { fr, vu });
  if (vu !== actuel) t.nodeValue = vu;
}

function attribut(e: Element, a: string) {
  if (!e.hasAttribute(a) || exclu(e, true)) return;
  const etats = attributs.get(e) ?? {};
  const actuel = e.getAttribute(a) ?? "";
  const fr = etats[a] && actuel === etats[a].vu ? etats[a].fr : actuel;
  const vu = tr(fr);
  etats[a] = { fr, vu };
  attributs.set(e, etats);
  if (vu !== actuel) e.setAttribute(a, vu);
}

function parcourir(racine: Node) {
  if (racine.nodeType === Node.TEXT_NODE) return texte(racine as Text);
  if (!(racine instanceof Element)) return;
  const w = document.createTreeWalker(racine, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  for (let n: Node | null = racine; n; n = w.nextNode()) {
    if (n.nodeType === Node.TEXT_NODE) texte(n as Text);
    else for (const a of ATTRIBUTS) attribut(n as Element, a);
  }
}

let observateur: MutationObserver | null = null;

/** Sets the language of the whole page (and keeps translating what React adds or changes). */
export function choisirLangue(l: Langue) {
  if (l === langue && observateur) return;
  langue = l;
  document.documentElement.lang = l;
  document.documentElement.dir = l === "ar" ? "rtl" : "ltr";
  if (!observateur) {
    observateur = new MutationObserver((changements) => {
      for (const c of changements) {
        if (c.type === "characterData") texte(c.target as Text);
        else if (c.type === "attributes" && c.attributeName) attribut(c.target as Element, c.attributeName);
        else c.addedNodes.forEach(parcourir);
      }
    });
    observateur.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRIBUTS });
  }
  parcourir(document.body);
}

export const langueActuelle = () => langue;
