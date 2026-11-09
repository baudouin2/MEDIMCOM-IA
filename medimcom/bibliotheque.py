"""Icônes SVG de démonstration du prototype (générées par code), en attendant les pictogrammes issus de bases existantes.

Chaque pictogramme est un SVG 120 × 120, sans texte (sauf chiffres, doses et noms de médicaments),
au trait épais et aux couleurs franches, avec un cadre dont la couleur indique la catégorie :
réponses (vert), personnes (bleu), corps (orange), symptômes (rouge), soins (bleu-vert), temps (violet).

    from medimcom.bibliotheque import svg, libelle, CATALOGUE
    svg("DOULEUR")                -> texte SVG
    svg("CHIFFRE:3"), svg("DOSE:500mg"), svg("MEDICAMENT:paracetamol")   -> pictogrammes paramétrés
    libelle("VENTRE", "ar")       -> "بطن"

Statut : version 1, À TESTER avec des personnes sourdes (docs/pictogrammes/PROTOCOLE_TESTS.md) avant tout usage réel.
Les libellés arabes sont à faire relire par un locuteur natif.
"""
import html
import re
import xml.etree.ElementTree as ET

ENCRE = "#1E2B31"
ROUGE = "#E04F3A"
ROUGE_CLAIR = "#F6C9C0"
PEAU = "#F3D2B5"
BLEU = "#2F80C0"
BLEU_CLAIR = "#CFE4F5"
VERT = "#2E9B5F"
JAUNE = "#F5B82E"
VIOLET = "#6B5BA8"
GRIS = "#9AA7AE"

CADRES = {"reponse": VERT, "personne": BLEU, "corps": "#E08A2E", "symptome": ROUGE, "soin": "#1F8C8C", "temps": VIOLET,
          "nombre": "#56656D", "emotion": "#B0457E"}
T = f'stroke="{ENCRE}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"'
TF = f'stroke="{ENCRE}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"'


# ------------------------------------------------------------------ éléments de dessin
def personne(remplir_tete=PEAU, remplir_buste="#FFFFFF", buste_x=60, ech=1.0):
    """Personne debout, de face, bras le long du corps."""
    return (f'<g transform="translate({buste_x - 60 * ech} 0) scale({ech} 1)">'
            f'<circle cx="60" cy="24" r="11" fill="{remplir_tete}" {T}/>'
            f'<path d="M44 44 Q44 37 52 37 H68 Q76 37 76 44 V76 Q76 80 72 80 H48 Q44 80 44 76 Z" fill="{remplir_buste}" {T}/>'
            f'<path d="M44 46 L34 70 M76 46 L86 70 M53 80 L51 106 M67 80 L69 106" fill="none" {T}/></g>')


def eclair(x, y, s=1.0, couleur=ROUGE):
    return (f'<path transform="translate({x} {y}) scale({s})" d="M0 -12 L-7 1 H0 L-4 14 L9 -3 H2 L6 -12 Z" '
            f'fill="{couleur}" stroke="{ENCRE}" stroke-width="2.5" stroke-linejoin="round"/>')


def visage(cx=60, cy=52, r=30, bouche="neutre"):
    b = {"neutre": f"M{cx - 10} {cy + 13} H{cx + 10}",
         "ouverte": f"M{cx - 7} {cy + 10} Q{cx} {cy + 22} {cx + 7} {cy + 10} Z",
         "triste": f"M{cx - 10} {cy + 16} Q{cx} {cy + 8} {cx + 10} {cy + 16}",
         "sourire": f"M{cx - 11} {cy + 9} Q{cx} {cy + 20} {cx + 11} {cy + 9}"}[bouche]
    remplir_bouche = "#FFFFFF" if bouche == "ouverte" else "none"
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{PEAU}" {T}/>'
            f'<circle cx="{cx - 10}" cy="{cy - 6}" r="3.2" fill="{ENCRE}"/><circle cx="{cx + 10}" cy="{cy - 6}" r="3.2" fill="{ENCRE}"/>'
            f'<path d="{b}" fill="{remplir_bouche}" {TF}/>')


def soleil(cx, cy, r=13, rayons=True, couleur=JAUNE):
    s = ""
    if rayons:
        for i in range(8):
            import math
            a = i * math.pi / 4
            x1, y1 = cx + math.cos(a) * (r + 5), cy + math.sin(a) * (r + 5)
            x2, y2 = cx + math.cos(a) * (r + 12), cy + math.sin(a) * (r + 12)
            s += f'<path d="M{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f}" {TF}/>'
    return s + f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{couleur}" {TF}/>'


def gelule(cx=60, cy=60, angle=-35, l=58, h=24, couleur=BLEU):
    return (f'<g transform="rotate({angle} {cx} {cy})">'
            f'<rect x="{cx - l / 2}" y="{cy - h / 2}" width="{l}" height="{h}" rx="{h / 2}" fill="#FFFFFF" {T}/>'
            f'<path d="M{cx} {cy - h / 2} H{cx + l / 2 - h / 2} A{h / 2} {h / 2} 0 0 1 {cx + l / 2 - h / 2} {cy + h / 2} H{cx} Z" fill="{couleur}" {T}/></g>')


def horloge(cx, cy, r=14):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#FFFFFF" {TF}/>'
            f'<path d="M{cx} {cy - r + 5} V{cy} L{cx + r - 6} {cy + 3}" fill="none" {TF}/>')


def horizon(nom, interieur):
    """Ce qui est dessiné au-dessus de la ligne d'horizon (y = 82) seulement."""
    return (f'<defs><clipPath id="horizon-{nom}"><rect x="0" y="0" width="120" height="82"/></clipPath></defs>'
            f'<g clip-path="url(#horizon-{nom})">{interieur}</g><path d="M12 82 H108" {T}/>')


def calendrier(x, y, w, h, contenu=""):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#FFFFFF" {T}/>'
            f'<path d="M{x} {y + 16} H{x + w}" {T}/><path d="M{x + 14} {y - 6} V{y + 6} M{x + w - 14} {y - 6} V{y + 6}" {T}/>' + contenu)


def texte(x, y, t, taille=30, couleur=ENCRE, poids=800):
    return (f'<text x="{x}" y="{y}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="{taille}" '
            f'font-weight="{poids}" fill="{couleur}">{html.escape(t)}</text>')


def fleche(x1, y1, x2, y2, couleur=ENCRE):
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    p1 = (x2 - 12 * math.cos(a - 0.5), y2 - 12 * math.sin(a - 0.5))
    p2 = (x2 - 12 * math.cos(a + 0.5), y2 - 12 * math.sin(a + 0.5))
    return (f'<path d="M{x1} {y1} L{x2} {y2} M{p1[0]:.1f} {p1[1]:.1f} L{x2} {y2} L{p2[0]:.1f} {p2[1]:.1f}" fill="none" '
            f'stroke="{couleur}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>')


# ------------------------------------------------------------------ catalogue : id -> (catégorie, fr, en, ar, dessin)
def _d(*parts):
    return "".join(parts)


CATALOGUE = {
    # ----- réponses
    "OUI": ("reponse", "oui", "yes", "نعم",
            _d(f'<circle cx="60" cy="60" r="40" fill="{VERT}" {T}/>', f'<path d="M40 61 L54 75 L81 46" fill="none" stroke="#FFFFFF" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>')),
    "NON": ("reponse", "non", "no", "لا",
            _d(f'<circle cx="60" cy="60" r="40" fill="{ROUGE}" {T}/>', '<path d="M44 44 L76 76 M76 44 L44 76" stroke="#FFFFFF" stroke-width="10" stroke-linecap="round"/>')),
    "NE_PAS": ("reponse", "ne pas", "do not", "لا تفعل",
               _d(f'<circle cx="60" cy="60" r="40" fill="#FFFFFF" stroke="{ROUGE}" stroke-width="10"/>', f'<path d="M32 32 L88 88" stroke="{ROUGE}" stroke-width="10" stroke-linecap="round"/>')),
    "ACCORD": ("reponse", "d'accord", "agree", "موافق",
               _d(f'<path d="M38 96 V58 H50 L62 26 Q72 24 72 36 L68 52 H88 Q96 54 94 62 L88 90 Q86 96 80 96 Z" fill="{PEAU}" {T}/>',
                  f'<rect x="24" y="56" width="14" height="42" rx="3" fill="{VERT}" {T}/>')),
    "QUESTION": ("reponse", "question", "question", "سؤال",
                 _d(f'<circle cx="60" cy="60" r="40" fill="{BLEU_CLAIR}" {T}/>',
                    f'<path d="M46 48 Q46 32 60 32 Q74 32 74 46 Q74 56 62 60 V70" fill="none" stroke="{ENCRE}" stroke-width="8" stroke-linecap="round"/>',
                    f'<circle cx="62" cy="84" r="5" fill="{ENCRE}"/>')),
    "COMPRENDRE": ("reponse", "comprendre", "understand", "أفهم",
                   _d(visage(54, 64, 28, "sourire"), f'<circle cx="92" cy="30" r="17" fill="{VERT}" {TF}/>',
                      '<path d="M84 30 L90 36 L100 24" fill="none" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>')),
    "STOP": ("reponse", "stop", "stop", "توقف",
             _d(f'<path d="M42 18 H78 L102 42 V78 L78 102 H42 L18 78 V42 Z" fill="{ROUGE}" {T}/>',
                f'<path d="M48 84 V48 Q48 42 53 42 Q58 42 58 48 V40 Q58 34 63 34 Q68 34 68 40 V46 Q68 40 73 40 Q78 40 78 46 V72 Q78 86 64 86 Z" fill="#FFFFFF" {TF}/>')),
    "ATTENDRE": ("reponse", "attendre", "wait", "انتظر",
                 _d(f'<path d="M36 18 H84 M36 102 H84" {T}/>',
                    f'<path d="M40 20 Q40 46 60 60 Q40 74 40 100 H80 Q80 74 60 60 Q80 46 80 20 Z" fill="#FFFFFF" {T}/>',
                    f'<path d="M48 96 Q52 80 60 76 Q68 80 72 96 Z" fill="{JAUNE}"/><path d="M50 32 H70 Q66 44 60 48 Q54 44 50 32 Z" fill="{JAUNE}"/>')),
    # ----- personnes
    "VOUS": ("personne", "vous", "you", "أنت",
             _d(personne(remplir_buste=BLEU_CLAIR, buste_x=72, ech=0.85), fleche(14, 60, 40, 60, BLEU))),
    "MOI": ("personne", "moi", "me", "أنا",
            _d(f'<circle cx="60" cy="24" r="11" fill="{PEAU}" {T}/>',
               f'<path d="M44 44 Q44 37 52 37 H68 Q76 37 76 44 V76 Q76 80 72 80 H48 Q44 80 44 76 Z" fill="{BLEU_CLAIR}" {T}/>',
               f'<path d="M44 46 L34 70 M53 80 L51 106 M67 80 L69 106 M76 44 L88 62 L66 56" fill="none" {T}/>',
               f'<circle cx="64" cy="55" r="5.5" fill="{PEAU}" {TF}/>')),
    "MEDECIN": ("personne", "médecin", "doctor", "طبيب",
                _d(personne(remplir_buste="#FFFFFF"), f'<path d="M52 38 Q50 58 60 60 Q70 58 68 38" fill="none" stroke="{BLEU}" stroke-width="4"/>',
                   f'<circle cx="60" cy="62" r="4" fill="{BLEU}"/>', f'<path d="M66 68 H74 M70 64 V72" stroke="{ROUGE}" stroke-width="4" stroke-linecap="round"/>')),
    "BEBE": ("personne", "bébé", "baby", "طفل رضيع",
             _d(visage(60, 62, 34, "sourire"), f'<path d="M54 30 Q60 18 66 30" fill="none" {TF}/>',
                f'<circle cx="60" cy="88" r="5" fill="{BLEU_CLAIR}" {TF}/>')),
    "ENCEINTE": ("personne", "enceinte", "pregnant", "حامل",
                 _d(f'<circle cx="56" cy="22" r="11" fill="{PEAU}" {T}/>',
                    f'<path d="M50 36 H62 Q68 38 68 46 Q86 54 84 68 Q82 80 66 80 H48 Q44 80 44 74 V44 Q44 36 50 36 Z" fill="{ROUGE_CLAIR}" {T}/>',
                    f'<path d="M48 80 L47 106 M62 80 L64 106 M46 46 L38 70" fill="none" {T}/>',
                    f'<path d="M70 62 Q74 58 78 62 Q74 70 70 62 Z" fill="{ROUGE}" stroke="none"/>')),
    # ----- corps
    "TETE": ("corps", "tête", "head", "رأس",
             _d(f'<circle cx="60" cy="24" r="19" fill="#FBE3D2"/>', personne(), f'<circle cx="60" cy="24" r="16" fill="none" stroke="#E08A2E" stroke-width="4"/>')),
    "POITRINE": ("corps", "poitrine", "chest", "صدر",
                 _d(personne(), f'<ellipse cx="60" cy="49" rx="13" ry="8" fill="{ROUGE_CLAIR}" stroke="{ROUGE}" stroke-width="3"/>')),
    "VENTRE": ("corps", "ventre", "belly", "بطن",
               _d(personne(), f'<ellipse cx="60" cy="67" rx="13" ry="9" fill="{ROUGE_CLAIR}" stroke="{ROUGE}" stroke-width="3"/>')),
    # ----- symptômes
    "DOULEUR": ("symptome", "douleur", "pain", "ألم",
                _d(f'<path d="M60 14 L68 40 L94 30 L78 52 L104 62 L76 70 L86 96 L62 80 L48 104 L44 78 L18 84 L36 62 L14 46 L42 44 L36 18 L54 36 Z" fill="{ROUGE}" {TF}/>',
                   f'<circle cx="60" cy="60" r="12" fill="#FFFFFF" {TF}/>')),
    "FIEVRE": ("symptome", "fièvre", "fever", "حمّى",
               _d(f'<path d="M52 22 Q52 14 60 14 Q68 14 68 22 V68 Q78 74 76 86 Q74 100 60 100 Q46 100 44 86 Q42 74 52 68 Z" fill="#FFFFFF" {T}/>',
                  f'<circle cx="60" cy="85" r="10" fill="{ROUGE}"/><rect x="56" y="30" width="8" height="52" rx="4" fill="{ROUGE}"/>',
                  f'<path d="M80 28 Q86 34 80 40 Q74 46 80 52 M92 28 Q98 34 92 40 Q86 46 92 52" fill="none" stroke="{ROUGE}" stroke-width="4" stroke-linecap="round"/>')),
    "TOUX": ("symptome", "toux", "cough", "سعال",
             _d(visage(48, 62, 28, "ouverte"), f'<path d="M84 52 Q92 48 98 52 M86 64 Q96 64 104 64 M84 76 Q92 80 98 76" fill="none" stroke="{GRIS}" stroke-width="5" stroke-linecap="round"/>')),
    "VOMIR": ("symptome", "vomir", "vomit", "تقيؤ",
              _d(visage(56, 48, 28, "ouverte"), f'<path d="M50 76 Q46 88 50 94 Q54 98 58 94 Q62 88 56 76" fill="#9CC46A" {TF}/>',
                 f'<path d="M66 82 Q64 92 70 96 Q76 92 72 84" fill="#9CC46A" {TF}/>')),
    "RESPIRER": ("symptome", "respirer", "breathe", "تنفّس",
                 _d(f'<path d="M60 18 V54 M60 54 Q50 54 46 60 M60 54 Q70 54 74 60" fill="none" {T}/>',
                    f'<path d="M44 46 Q24 50 22 78 Q20 98 36 98 Q50 98 50 82 V60 Q50 48 44 46 Z" fill="{BLEU_CLAIR}" {T}/>',
                    f'<path d="M76 46 Q96 50 98 78 Q100 98 84 98 Q70 98 70 82 V60 Q70 48 76 46 Z" fill="{BLEU_CLAIR}" {T}/>')),
    "SANG": ("symptome", "sang", "blood", "دم",
             _d(f'<path d="M60 14 Q86 52 86 72 Q86 98 60 98 Q34 98 34 72 Q34 52 60 14 Z" fill="{ROUGE}" {T}/>',
                '<path d="M48 70 Q48 82 58 86" fill="none" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round"/>')),
    "ALLERGIE": ("symptome", "allergie", "allergy", "حساسية",
                 _d(f'<path d="M36 104 V58 Q36 50 43 50 Q50 50 50 58 V40 Q50 32 57 32 Q64 32 64 40 V36 Q64 28 71 28 Q78 28 78 36 V44 Q78 38 84 38 Q90 38 90 46 V78 Q90 104 66 104 Z" fill="{PEAU}" {T}/>',
                    *[f'<circle cx="{x}" cy="{y}" r="4.5" fill="{ROUGE}"/>' for x, y in ((50, 70), (64, 62), (76, 74), (58, 86), (72, 92), (82, 58))])),
    # ----- soins
    "MEDICAMENT": ("soin", "médicament", "medicine", "دواء", gelule()),
    "COMPRIME": ("soin", "comprimé", "tablet", "قرص",
                 _d(f'<ellipse cx="46" cy="68" rx="26" ry="20" fill="{BLEU_CLAIR}" {T}/>', f'<path d="M34 58 L58 78" stroke="{ENCRE}" stroke-width="3.5" stroke-linecap="round"/>',
                    f'<ellipse cx="78" cy="48" rx="26" ry="20" fill="#FFFFFF" {T}/>', f'<path d="M66 38 L90 58" stroke="{ENCRE}" stroke-width="3.5" stroke-linecap="round"/>')),
    "PRENDRE": ("soin", "prendre (avaler)", "take (swallow)", "تناول",
                _d(visage(44, 58, 30, "ouverte"), gelule(94, 60, 0, 30, 14), fleche(80, 60, 64, 66))),
    "HOPITAL": ("soin", "hôpital", "hospital", "مستشفى",
                _d(f'<path d="M20 102 V40 H100 V102 Z" fill="#FFFFFF" {T}/>', f'<path d="M14 102 H106" {T}/>',
                   f'<rect x="48" y="50" width="24" height="24" fill="{ROUGE}" stroke="none"/>',
                   '<path d="M60 54 V70 M52 62 H68" stroke="#FFFFFF" stroke-width="6" stroke-linecap="round"/>',
                   f'<rect x="50" y="82" width="20" height="20" fill="{BLEU_CLAIR}" {TF}/>', f'<path d="M30 30 H90 L100 40 H20 Z" fill="{BLEU_CLAIR}" {TF}/>')),
    "URGENCE": ("soin", "urgence", "emergency", "طوارئ",
                _d(f'<path d="M36 92 V60 Q36 36 60 36 Q84 36 84 60 V92 Z" fill="{ROUGE}" {T}/>', f'<rect x="26" y="92" width="68" height="12" rx="3" fill="{ENCRE}"/>',
                   f'<path d="M60 14 V24 M24 30 L32 38 M96 30 L88 38 M14 62 H24 M96 62 H106" {T}/>',
                   '<path d="M50 52 Q52 46 58 46" fill="none" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round"/>')),
    "ANALYSE": ("soin", "analyse", "test (lab)", "تحليل",
                _d(f'<path d="M48 16 H72 M52 16 V82 Q52 96 60 96 Q68 96 68 82 V16" fill="#FFFFFF" {T}/>', f'<path d="M53 60 H67 V82 Q67 92 60 92 Q53 92 53 82 Z" fill="{ROUGE}" stroke="none"/>',
                   f'<path d="M80 30 H96 M80 46 H92 M80 62 H96" stroke="{GRIS}" stroke-width="4" stroke-linecap="round"/>')),
    "EXAMEN": ("soin", "examen", "examination", "فحص",
               _d(f'<path d="M34 18 V44 Q34 62 52 62 Q70 62 70 44 V18" fill="none" {T}/>', f'<path d="M52 62 V78 Q52 98 72 98 Q88 98 88 82 V74" fill="none" {T}/>',
                  f'<circle cx="88" cy="66" r="10" fill="{BLEU}" {T}/>', f'<circle cx="34" cy="16" r="4" fill="{ENCRE}"/><circle cx="70" cy="16" r="4" fill="{ENCRE}"/>')),
    "MANGER": ("soin", "manger", "eat", "أكل",
               _d(f'<circle cx="60" cy="64" r="30" fill="#FFFFFF" {T}/>', f'<circle cx="60" cy="64" r="18" fill="none" stroke="{GRIS}" stroke-width="3"/>',
                  f'<path d="M18 30 V58 M14 30 V44 Q14 50 18 50 Q22 50 22 44 V30 M18 58 V98" fill="none" {TF}/>',
                  f'<path d="M102 30 Q94 40 98 58 H102 V98" fill="none" {TF}/>')),
    "BOIRE": ("soin", "boire", "drink", "شرب",
              _d(f'<path d="M36 22 H84 L76 100 H44 Z" fill="#FFFFFF" {T}/>', f'<path d="M41 50 H79 L74 96 H46 Z" fill="{BLEU_CLAIR}" stroke="none"/>',
                 f'<path d="M41 50 H79" stroke="{BLEU}" stroke-width="3"/>')),
    "EAU": ("soin", "eau", "water", "ماء",
            _d(f'<path d="M60 14 Q86 52 86 72 Q86 98 60 98 Q34 98 34 72 Q34 52 60 14 Z" fill="{BLEU}" {T}/>',
               '<path d="M48 70 Q48 82 58 86" fill="none" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round"/>')),
    "DORMIR": ("soin", "dormir", "sleep", "نوم",
               _d(f'<path d="M14 98 V48 M14 78 H106 V98 M14 66 H70 Q80 66 80 74 V78" fill="none" {T}/>', f'<circle cx="32" cy="58" r="9" fill="{PEAU}" {TF}/>',
                  f'<path d="M44 66 H100 V78 H44 Z" fill="{BLEU_CLAIR}" {TF}/>', texte(82, 36, "Z", 22), texte(98, 22, "Z", 16))),
    # ----- temps
    "MATIN": ("temps", "matin", "morning", "صباح",
              _d(horizon("matin", soleil(60, 80, 18)), fleche(60, 106, 60, 92, VIOLET))),
    "MIDI": ("temps", "midi", "noon", "ظهر",
             _d(soleil(60, 44, 16), f'<path d="M16 100 H104" {T}/>', f'<path d="M60 74 V96" stroke="{GRIS}" stroke-width="4" stroke-dasharray="4 4"/>')),
    "SOIR": ("temps", "soir", "evening", "مساء",
             _d(horizon("soir", soleil(60, 80, 18, couleur="#F08A3C")), fleche(60, 92, 60, 106, VIOLET))),
    "NUIT": ("temps", "nuit", "night", "ليل",
             _d(f'<path d="M70 18 Q40 22 40 56 Q40 90 76 96 Q50 104 32 88 Q14 70 22 44 Q32 18 70 18 Z" fill="{JAUNE}" {T}/>',
                f'<path d="M88 28 L90 34 L96 36 L90 38 L88 44 L86 38 L80 36 L86 34 Z M96 66 L97 70 L101 71 L97 72 L96 76 L95 72 L91 71 L95 70 Z" fill="{JAUNE}" stroke="{ENCRE}" stroke-width="2"/>')),
    "JOUR": ("temps", "jour", "day", "يوم",
             calendrier(24, 26, 72, 72, f'<rect x="48" y="52" width="24" height="30" rx="4" fill="{VIOLET}"/>')),
    "SEMAINE": ("temps", "semaine", "week", "أسبوع",
                calendrier(14, 26, 92, 72, "".join(f'<rect x="{20 + i * 12.4:.1f}" y="58" width="9" height="22" rx="2" fill="{VIOLET}"/>' for i in range(7)))),
    # Durées : « depuis 3 mois » (guide de la douleur du patient) ; dessinées ici pour que toutes les bases les aient
    "HEURE": ("temps", "heure", "hour", "ساعة",
              _d(f'<circle cx="60" cy="60" r="38" fill="#fff" {T}/>', f'<path d="M60 60 V34 M60 60 L78 70" fill="none" {T}/>',
                 f'<circle cx="60" cy="60" r="4" fill="{VIOLET}"/>')),
    "MOIS": ("temps", "mois", "month", "شهر",
             calendrier(14, 26, 92, 72, "".join(f'<rect x="{20 + (i % 7) * 12.4:.1f}" y="{50 + (i // 7) * 9}" width="9" height="6" rx="1.5" fill="{VIOLET}"/>'
                                                for i in range(30)))),
    "AN": ("temps", "an (année)", "year", "سنة",
           calendrier(14, 26, 92, 72, "".join(f'<rect x="{22 + (i % 4) * 20}" y="{50 + (i // 4) * 11}" width="15" height="8" rx="2" fill="{VIOLET}"/>'
                                              for i in range(12)))),
    "FOIS": ("nombre", "fois (répéter)", "times (repeat)", "مرة",
             _d(f'<path d="M30 52 Q32 28 60 28 Q82 28 88 46" fill="none" {T}/>', f'<path d="M78 44 L90 48 L92 34" fill="none" {T}/>',
                f'<path d="M90 68 Q88 92 60 92 Q38 92 32 74" fill="none" {T}/>', f'<path d="M42 76 L30 72 L28 86" fill="none" {T}/>')),
    "PLUS": ("nombre", "plus (davantage)", "more", "أكثر",
             _d(*[f'<rect x="{22 + i * 26}" y="{88 - h}" width="18" height="{h}" rx="3" fill="{VIOLET if i == 2 else BLEU_CLAIR}" {TF}/>' for i, h in enumerate((22, 42, 66))],
                fleche(22, 30, 54, 16, VIOLET))),
    "MOINS": ("nombre", "moins (réduire)", "less", "أقل",
              _d(*[f'<rect x="{22 + i * 26}" y="{88 - h}" width="18" height="{h}" rx="3" fill="{VIOLET if i == 2 else BLEU_CLAIR}" {TF}/>' for i, h in enumerate((66, 42, 22))],
                 fleche(66, 16, 98, 30, VIOLET))),
    "MAXIMUM": ("nombre", "au maximum (jusqu'à)", "at most (up to)", "كحد أقصى",
                _d(f'<path d="M20 30 H100" stroke="{ROUGE}" stroke-width="7" stroke-linecap="round"/>',
                   f'<rect x="38" y="44" width="44" height="50" rx="4" fill="{BLEU_CLAIR}" {T}/>', fleche(60, 80, 60, 40, ENCRE))),
    "AVANT": ("temps", "avant", "before", "قبل", _d(horloge(78, 60, 22), fleche(48, 60, 14, 60, VIOLET))),
    "APRES": ("temps", "après", "after", "بعد", _d(horloge(42, 60, 22), fleche(72, 60, 106, 60, VIOLET))),
}

# Cadres des pictogrammes paramétrés
PARAMETRES = {"CHIFFRE": ("nombre", "chiffre", "number", "رقم"), "DOSE": ("soin", "dose", "dose", "جرعة"),
              "MEDICAMENT": ("soin", "médicament (nom)", "medicine (name)", "دواء"), "GEN": ("soin", "image générée", "generated image", "صورة")}


def _cadre(categorie: str, interieur: str, titre: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="120" height="120" role="img" aria-label="{html.escape(titre)}">'
            f'<title>{html.escape(titre)}</title>'
            f'<rect x="3" y="3" width="114" height="114" rx="18" fill="#FFFFFF" stroke="{CADRES[categorie]}" stroke-width="6"/>'
            f'{interieur}</svg>')


# --------------------------------------------------------------- pictogrammes combinés (une seule image)
# « TETE+DOULEUR » = le pictogramme principal en grand, le second en médaillon dans un coin (2 ou 3 éléments).
# La négation, la limite (« au maximum ») et l'urgence ne sont JAMAIS réduites en médaillon : elles restent des
# pictogrammes entiers, bien visibles, pour qu'aucune interdiction ni limite de dose ne passe inaperçue.
JAMAIS_EN_MEDAILLON = {"NE_PAS", "MAXIMUM", "URGENCE", "STOP"}
MAX_ELEMENTS = 3


# --------------------------------------------------------------- images nouvelles fournies par le moteur de l'agent 1
# Un moteur qui GÉNÈRE des images expose image(ident) -> SVG pour des identifiants « GEN:… ». L'image n'est
# acceptée que si c'est un SVG fait uniquement de formes et de texte (liste blanche) ; sinon l'identifiant est inconnu (« ? »).
_fournisseur_images = None
_BALISES_PERMISES = {"svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text", "tspan",
                     "title", "desc", "defs", "clipPath", "linearGradient", "radialGradient", "stop", "image"}


def _svg_sur(t: str) -> bool:
    """Liste blanche : formes et texte seulement, aucun script, aucune animation, aucun lien externe, aucun style."""
    if "<!" in t or "<?" in t.lstrip()[2:] or len(t) > 300_000:
        return False
    try:
        racine = ET.fromstring(t)
    except ET.ParseError:
        return False
    if not racine.tag.endswith("svg"):
        return False
    for el in racine.iter():
        nom = el.tag.rsplit("}", 1)[-1]
        if nom not in _BALISES_PERMISES:
            return False
        for att, val in el.attrib.items():
            a, v = att.rsplit("}", 1)[-1].lower(), val.strip().lower()
            if a.startswith("on") or a == "style" or "javascript:" in v or ("url(" in v and not v.startswith("url(#")):
                return False
            if a == "href" and not (v.startswith("#") or (nom == "image" and re.match(r"data:image/(png|jpeg);base64,", v))):
                return False
    return True


def brancher_images(fournisseur) -> None:
    """Branche la fonction image(ident) -> SVG du moteur de pictogrammes (None pour débrancher)."""
    global _fournisseur_images
    _fournisseur_images = fournisseur


def _image_generee(ident: str) -> str | None:
    if _fournisseur_images is None:
        return None
    try:
        t = _fournisseur_images(ident)
    except Exception:
        return None
    return t if isinstance(t, str) and t and _svg_sur(t) else None


# --------------------------------------------------------------- pictogrammes issus de bases existantes
# pictogrammes/bases/manifeste_externe.json (produit par telecharger_arasaac.py et importer_fichiers.py) :
# identifiant -> fichier image, base d'origine, auteur, licence. Ces images remplacent les icônes de démonstration
# (variable MEDIMCOM_PICTOS=demo pour revenir aux icônes) et ajoutent le vocabulaire médical de
# pictogrammes/bases/vocabulaire_medical.json. Chaque image est affichée dans le cadre de couleur de sa catégorie.
import base64 as _b64
import json as _json
import os as _os
from pathlib import Path as _Path

DOSSIER_BASES = _Path(__file__).resolve().parent.parent / "pictogrammes" / "bases"
VOCABULAIRE: dict = {}
EXTERNES: dict = {}
_TYPES_IMAGES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}


def charger_bases(dossier: _Path | None = None) -> int:
    """(Re)charge le vocabulaire et le manifeste des pictogrammes externes ; renvoie le nombre d'images utilisables."""
    global DOSSIER_BASES
    DOSSIER_BASES = _Path(dossier) if dossier else DOSSIER_BASES
    VOCABULAIRE.clear(); EXTERNES.clear()
    v = DOSSIER_BASES / "vocabulaire_medical.json"
    if v.exists():
        VOCABULAIRE.update({x["id"]: x for x in _json.loads(v.read_text(encoding="utf-8"))["vocabulaire"]})
    m = DOSSIER_BASES / "manifeste_externe.json"
    if m.exists() and _os.environ.get("MEDIMCOM_PICTOS", "bases") != "demo":
        for ident, x in _json.loads(m.read_text(encoding="utf-8")).get("pictogrammes", {}).items():
            f = DOSSIER_BASES / x["fichier"]
            if ident in VOCABULAIRE and f.suffix.lower() in _TYPES_IMAGES and f.is_file() and DOSSIER_BASES in f.resolve().parents:
                EXTERNES[ident] = {**x, "chemin": f}
    return len(EXTERNES)


def _svg_externe(ident: str) -> str | None:
    x = EXTERNES.get(ident)
    if not x:
        return None
    donnees = x["chemin"].read_bytes()
    type_ = _TYPES_IMAGES[x["chemin"].suffix.lower()]
    if type_ == "image/svg+xml" and not _svg_sur(donnees.decode("utf-8", "replace")):
        return None
    if type_ == "image/png" and not donnees.startswith(b"\x89PNG"):
        return None
    if type_ == "image/jpeg" and not donnees.startswith(b"\xff\xd8"):
        return None
    uri = f"data:{type_};base64,{_b64.b64encode(donnees).decode()}"
    cat = VOCABULAIRE[ident]["categorie"]
    return _cadre(cat if cat in CADRES else "nombre", f'<image href="{uri}" x="13" y="13" width="94" height="94" '
                  f'preserveAspectRatio="xMidYMid meet"/>', VOCABULAIRE[ident]["fr"])


def credits() -> list[dict]:
    """Attribution de chaque pictogramme externe affiché (exigée par les licences)."""
    return [{"pictogramme": i, "base": x.get("base"), "auteur": x.get("auteur", ""), "licence": x.get("licence", ""),
             "source": x.get("url", ""), "attribution": x.get("attribution", "")} for i, x in sorted(EXTERNES.items())]


def _categorie(ident: str) -> str:
    if ident in EXTERNES:
        return VOCABULAIRE[ident]["categorie"]
    if ident in CATALOGUE:
        return CATALOGUE[ident][0]
    return PARAMETRES[ident.split(":", 1)[0]][0]


def _simple_connu(ident: str) -> bool:
    base = ident.split(":", 1)[0]
    if ident in EXTERNES:
        return True
    if base == "GEN":
        return ":" in ident and _image_generee(ident) is not None
    return ident in CATALOGUE or (base in PARAMETRES and ":" in ident)


def combinaison_valide(ident: str) -> bool:
    parties = ident.split("+")
    return (2 <= len(parties) <= MAX_ELEMENTS and len(set(parties)) == len(parties)
            and not any(x.startswith("GEN:") for x in parties)
            and all(_simple_connu(x) for x in parties) and not (set(parties) & JAMAIS_EN_MEDAILLON))


def combiner(*parties: str) -> str:
    """Identifiant d'une image combinée, par exemple combiner("TETE", "DOULEUR") -> "TETE+DOULEUR"."""
    ident = "+".join(parties)
    if not combinaison_valide(ident):
        raise ValueError(f"combinaison impossible : {ident}")
    return ident


def connu(ident: str) -> bool:
    if "+" in ident:
        return combinaison_valide(ident)
    return _simple_connu(ident)


def libelle(ident: str, langue: str = "fr") -> str:
    if "+" in ident:
        return " + ".join(libelle(x, langue) for x in ident.split("+"))
    if ident in VOCABULAIRE and ident not in CATALOGUE:
        return VOCABULAIRE[ident][langue]
    i = {"fr": 1, "en": 2, "ar": 3}[langue]
    if ident in CATALOGUE:
        return CATALOGUE[ident][i]
    base, _, valeur = ident.partition(":")
    if base in PARAMETRES:
        return f"{PARAMETRES[base][i]} {valeur}".strip()
    return ident


def _interieur(svg_complet: str) -> str:
    """Contenu dessiné d'un pictogramme, sans son cadre ni son titre (pour le réutiliser dans une image combinée)."""
    corps = re.sub(r"^<svg[^>]*>|</svg>$", "", svg_complet)
    corps = re.sub(r"<title>.*?</title>", "", corps, count=1)
    return re.sub(r'<rect x="3" y="3" width="114" height="114"[^>]*/>', "", corps, count=1)


def _svg_combine(ident: str) -> str:
    principal, *autres = ident.split("+")
    cat = _categorie(principal)
    o = _interieur(svg(principal))
    # médaillons à l'intérieur du cadre : en bas à droite puis en haut à droite ; si le principal porte un texte
    # en bas (nom du médicament, dose), on commence en haut pour ne pas le cacher
    coins = [(87, 87), (87, 33)]
    if principal.split(":", 1)[0] in ("MEDICAMENT", "DOSE"):
        coins.reverse()
    for (cx, cy), autre in zip(coins, autres):
        c = _categorie(autre)
        o += (f'<circle cx="{cx}" cy="{cy}" r="23" fill="#FFFFFF" stroke="{CADRES[c]}" stroke-width="3.5"/>'
              f'<g transform="translate({cx - 21} {cy - 21}) scale(0.35)">{_interieur(svg(autre))}</g>')
    return _cadre(cat, o, libelle(ident))


def svg(ident: str) -> str:
    """SVG du pictogramme ; un identifiant inconnu donne un cadre gris avec « ? » (jamais une image inventée)."""
    if "+" in ident:
        if combinaison_valide(ident):
            return _svg_combine(ident)
        return _cadre("nombre", texte(60, 78, "?", 60, GRIS), f"combinaison refusée {ident}")
    externe = _svg_externe(ident)
    if externe:
        return externe
    if ident.startswith("GEN:"):
        img = _image_generee(ident)
        return img if img else _cadre("nombre", texte(60, 78, "?", 60, GRIS), "image non disponible")
    if ident in CATALOGUE:
        cat, fr, *_ , dessin = CATALOGUE[ident]
        return _cadre(cat, dessin, fr)
    base, _, valeur = ident.partition(":")
    valeur = re.sub(r"[^\w.,%µ-]", "", valeur)[:14]
    if base == "CHIFFRE" and valeur:
        return _cadre("nombre", texte(60, 60 + (34 if len(valeur) < 3 else 24) / 1.6, valeur, 68 if len(valeur) < 3 else 44), f"chiffre {valeur}")
    if base == "DOSE" and valeur:
        return _cadre("soin", gelule(60, 44, -20, 48, 20) + texte(60, 98, valeur, 24 if len(valeur) < 7 else 18), f"dose {valeur}")
    if base == "MEDICAMENT" and valeur:
        return _cadre("soin", gelule(60, 46, -30, 56, 22) + texte(60, 100, valeur[:12], 17 if len(valeur) < 10 else 13, ENCRE, 700),
                      f"médicament {valeur}")
    return _cadre("nombre", texte(60, 78, "?", 60, GRIS), f"inconnu {ident}")


charger_bases()
