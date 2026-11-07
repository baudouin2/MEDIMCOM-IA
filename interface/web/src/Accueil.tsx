import { KeyRound, MonitorSmartphone, Stethoscope } from "lucide-react";
import { urlPicto } from "./api";
import { Marque } from "./Marque";

export default function Accueil() {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Marque />
          <a href="/credits" className="text-sm font-medium text-ink-muted hover:text-ink">Crédits des pictogrammes</a>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-12 sm:py-16">
        <div className="grid items-center gap-10 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <h1 className="text-[34px] font-semibold leading-[1.15] tracking-tight text-ink sm:text-[40px]">
              Une consultation médicale avec un patient sourd, en pictogrammes.
            </h1>
            <p className="mt-4 max-w-[52ch] text-[17px] leading-relaxed text-ink-soft">
              Le médecin écrit, des agents traduisent en pictogrammes et vérifient chaque décision au regard du droit.
              Le patient répond en touchant des images. Le médecin valide tout ce qui est envoyé.
            </p>
            <div className="mt-6 flex items-center gap-2" aria-hidden>
              {["MEDECIN", "VENTRE+DOULEUR", "QUESTION", "OUI"].map((id) => (
                <img key={id} src={urlPicto(id)} alt="" width={64} height={64} className="rounded-xl bg-surface p-1 shadow-panel" />
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-4">
            <a href="/patient" className="group flex items-start gap-4 rounded-2xl bg-surface p-5 shadow-panel transition-shadow hover:shadow-pop">
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-action-50 text-action"><MonitorSmartphone size={22} /></span>
              <span>
                <span className="block text-base font-semibold text-ink group-hover:text-action">Ouvrir l'écran patient</span>
                <span className="mt-1 block text-sm text-ink-muted">Sur cet ordinateur ou sur une tablette connectée au même réseau.</span>
              </span>
            </a>
            <div className="flex items-start gap-4 rounded-2xl bg-surface p-5 shadow-panel">
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand"><Stethoscope size={22} /></span>
              <span>
                <span className="block text-base font-semibold text-ink">Écran médecin</span>
                <span className="mt-1 block text-sm text-ink-muted">
                  Ouvrez le lien privé affiché dans le terminal au démarrage du serveur.
                </span>
                <span className="mt-3 flex items-center gap-1.5 text-xs text-ink-muted"><KeyRound size={13} />Il contient une clé secrète : ne le partagez pas.</span>
              </span>
            </div>
          </div>
        </div>
      </main>
      <footer className="border-t border-line">
        <p className="mx-auto max-w-5xl px-6 py-4 text-xs text-ink-muted">Prototype en cours de développement pour le hackathon UIT AI for Good. Patients fictifs uniquement ; ce n'est pas un dispositif médical.</p>
      </footer>
    </div>
  );
}
