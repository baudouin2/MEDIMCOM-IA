/** MEDIMCOM IA logo: two overlapping pictogram cards (a sentence, an answer). */
export function Marque({ taille = 30, texte = true }: { taille?: number; texte?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <svg width={taille} height={taille} viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="8" fill="#0E3A66" />
        <rect x="6.5" y="7" width="12" height="12" rx="3.2" fill="none" stroke="#fff" strokeWidth="2.2" />
        <rect x="13.5" y="13" width="12" height="12" rx="3.2" fill="#3D8BFF" stroke="#fff" strokeWidth="2.2" />
        <path d="M17 19.2l2 2 3.6-3.8" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {texte && <span className="text-[15px] font-semibold tracking-tight text-ink">MEDIMCOM <span className="font-normal text-ink-muted">IA</span></span>}
    </span>
  );
}
