import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import { FournisseurLibelles, FournisseurNotif } from "./ui";

const EcranMedecin = lazy(() => import("./Medecin"));
const EcranPatient = lazy(() => import("./Patient"));
const Accueil = lazy(() => import("./Accueil"));

const chemin = window.location.pathname.replace(/\/+$/, "") || "/";
const Page = chemin === "/medecin" ? EcranMedecin : chemin === "/patient" ? EcranPatient : Accueil;
document.title = chemin === "/medecin" ? "Consultation · MEDIMCOM IA" : chemin === "/patient" ? "MEDIMCOM IA" : "MEDIMCOM IA";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <FournisseurLibelles>
      <FournisseurNotif>
        <Suspense fallback={null}><Page /></Suspense>
      </FournisseurNotif>
    </FournisseurLibelles>
  </StrictMode>,
);
