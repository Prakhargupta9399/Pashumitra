# app/services/language.py
# NEW Phase 2: Multilingual response engine
# Supports: Hindi, Marathi, Gujarati, Punjabi, Tamil, Telugu,
#           Kannada, Bengali, Odia, Bhojpuri, Urdu, English

import logging
from typing import Dict, Optional

logger = logging.getLogger("pashumitra.lang")

# ── LANGUAGE DETECTION KEYWORDS ───────────────────────────────────────────────
# Maps language code → detection trigger words (farmer's first message)
LANG_TRIGGERS: Dict[str, list] = {
    "hindi":    ["मेरी", "मेरा", "मुझे", "मेरे", "है", "नहीं", "खाना", "गाय"],
    "marathi":   ["माझ्या", "म्हैस", "बैल", "आहे", "नाही", "कसे", "मला"],
    "gujarati":  ["ગાય", "ભેંસ", "મારી", "છે", "નથી", "કેવી"],
    "punjabi":   ["ਗਾਂ", "ਮੱਝ", "ਮੇਰੀ", "ਹੈ", "ਨਹੀਂ"],
    "tamil":     ["பசு", "எருமை", "என்", "இல்லை", "உள்ளது"],
    "telugu":    ["ఆవు", "గేదె", "నా", "లేదు", "ఉంది"],
    "kannada":   ["ಹಸು", "ಎಮ್ಮೆ", "ನನ್ನ", "ಇಲ್ಲ", "ಇದೆ"],
    "bengali":   ["গরু", "মহিষ", "আমার", "নেই", "আছে"],
    "odia":      ["ଗାଈ", "ମୋ", "ନାହିଁ", "ଅଛି"],
    "bhojpuri":  ["गाय", "भैंस", "हमार", "नइखे", "बा"],
    "urdu":      ["گائے", "بھینس", "میری", "نہیں", "ہے"],
    "english":   ["cow", "buffalo", "goat", "disease", "sick", "fever", "milk"],
}

# Default is hindi — no detection trigger needed (fallback)

# ── TRANSLATED RESPONSE TEMPLATES ─────────────────────────────────────────────
# Key phrases translated for each language.
# Format: {lang: {key: translated_string}}

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "hindi": {
        "greeting":       "🐄 नमस्ते! मैं PashuMitra AI हूँ।",
        "disease_label":  "🔍 बीमारी",
        "severity_label": "गंभीरता",
        "remedy_label":   "🌿 घरेलू उपचार",
        "medicine_label": "💊 दवाई",
        "dosage_label":   "💉 खुराक",
        "diet_label":     "🥗 आहार",
        "prevention_label": "🛡️ बचाव",
        "shop_label":     "📍 दुकान",
        "emergency_msg":  "🚨 गंभीर बीमारी! तुरंत डॉक्टर बुलाएं।",
        "contagious_msg": "⚠️ यह संक्रामक रोग है! अन्य पशुओं से अलग रखें!",
        "disclaimer":     "⚠️ यह AI सलाह है — गंभीर स्थिति में डॉक्टर से मिलें।",
        "limit_msg":      "⚠️ आज की 3 मुफ्त सलाह खत्म हो गई।\nकल फिर कोशिश करें या Premium लें — ₹99/माह में असीमित सलाह 🙏",
        "differential":   "🔬 अन्य संभावना",
        "vaccination":    "💉 टीकाकरण अनुस्मारक",
        "free_vaccine":   "(मुफ्त)",
        "phc_msg":        "नजदीकी PHC से लें",
        "milk_down":      "📉 दूध उत्पादन कम हुआ",
        "next_heat":      "🌡️ अगला गर्मी चक्र",
        "calving_due":    "🐣 अगली बछड़ा तारीख",
    },
    "marathi": {
        "greeting":       "🐄 नमस्कार! मी PashuMitra AI आहे।",
        "disease_label":  "🔍 आजार",
        "severity_label": "गंभीरता",
        "remedy_label":   "🌿 घरगुती उपाय",
        "medicine_label": "💊 औषध",
        "dosage_label":   "💉 मात्रा",
        "diet_label":     "🥗 आहार",
        "prevention_label": "🛡️ प्रतिबंध",
        "shop_label":     "📍 दुकान",
        "emergency_msg":  "🚨 गंभीर आजार! ताबडतोब डॉक्टरला बोलवा।",
        "contagious_msg": "⚠️ हा संसर्गजन्य रोग आहे! इतर जनावरांपासून वेगळे करा!",
        "disclaimer":     "⚠️ हे AI सल्ला आहे — गंभीर स्थितीत डॉक्टरांना भेटा।",
        "limit_msg":      "⚠️ आजच्या 3 मोफत सल्ल्या संपल्या.\nउद्या पुन्हा प्रयत्न करा किंवा Premium घ्या — ₹99/महिना 🙏",
        "differential":   "🔬 इतर शक्यता",
        "vaccination":    "💉 लसीकरण आठवण",
        "free_vaccine":   "(मोफत)",
        "phc_msg":        "जवळच्या PHC मधून घ्या",
        "milk_down":      "📉 दूध उत्पादन कमी",
        "next_heat":      "🌡️ पुढील माजाचे चक्र",
        "calving_due":    "🐣 पुढील वासराची तारीख",
    },
    "gujarati": {
        "greeting":       "🐄 નમસ્તે! હું PashuMitra AI છું।",
        "disease_label":  "🔍 બીમારી",
        "severity_label": "ગંભીરતા",
        "remedy_label":   "🌿 ઘરેલુ ઉપચાર",
        "medicine_label": "💊 દવા",
        "dosage_label":   "💉 ડોઝ",
        "diet_label":     "🥗 આહાર",
        "prevention_label": "🛡️ બચાવ",
        "shop_label":     "📍 દુકાન",
        "emergency_msg":  "🚨 ગંભીર બીમારી! તરત ડૉક્ટર બોલાવો।",
        "contagious_msg": "⚠️ આ ચેપી રોગ છે! અન્ય પ્રાણીઓથી અલગ રાખો!",
        "disclaimer":     "⚠️ આ AI સલાહ છે — ગંભીર સ્થિતિમાં ડૉક્ટર પાસે જાઓ।",
        "limit_msg":      "⚠️ આજની 3 મફત સલાહ સમાપ્ત.\nકાલે ફરી પ્રયાસ કરો અથવા Premium લો — ₹99/મહિનો 🙏",
        "differential":   "🔬 અન્ય સંભાવના",
        "vaccination":    "💉 રસીકરણ રીમાઇન્ડર",
        "free_vaccine":   "(મફત)",
        "phc_msg":        "નજીકની PHC પરથી લો",
        "milk_down":      "📉 દૂધ ઉત્પાદન ઘટ્યું",
        "next_heat":      "🌡️ આગળનો ગરમીનો ચક્ર",
        "calving_due":    "🐣 આગળની વાછરડાની તારીખ",
    },
    "english": {
        "greeting":       "🐄 Hello! I am PashuMitra AI.",
        "disease_label":  "🔍 Disease",
        "severity_label": "Severity",
        "remedy_label":   "🌿 Home Remedy",
        "medicine_label": "💊 Medicine",
        "dosage_label":   "💉 Dosage",
        "diet_label":     "🥗 Diet Advice",
        "prevention_label": "🛡️ Prevention",
        "shop_label":     "📍 Nearest Shop",
        "emergency_msg":  "🚨 Critical condition! Call a vet immediately.",
        "contagious_msg": "⚠️ This is contagious! Isolate from other animals!",
        "disclaimer":     "⚠️ This is AI advice — consult a vet for serious conditions.",
        "limit_msg":      "⚠️ Your 3 free daily queries are exhausted.\nTry again tomorrow or upgrade to Premium — ₹99/month 🙏",
        "differential":   "🔬 Differential Diagnosis",
        "vaccination":    "💉 Vaccination Reminder",
        "free_vaccine":   "(Free)",
        "phc_msg":        "Available at nearest PHC",
        "milk_down":      "📉 Milk production declined",
        "next_heat":      "🌡️ Next heat cycle",
        "calving_due":    "🐣 Expected calving date",
    },
}

# Tamil, Telugu, Kannada, Bengali, Odia, Bhojpuri, Urdu
# use Hindi translations as fallback (farmers reading Devanagari script
# are served correctly; Phase 3 will add full script translations)
for _lang in ["tamil", "telugu", "kannada", "bengali", "odia", "bhojpuri", "urdu", "punjabi"]:
    TRANSLATIONS[_lang] = TRANSLATIONS["hindi"]


class LanguageEngine:
    """Detect language from farmer message and provide translated UI strings."""

    def detect(self, text: str, stored_lang: Optional[str] = None) -> str:
        """
        Returns ISO-style language code.
        Priority: 1) stored_lang from DB  2) script/keyword detection  3) 'hindi'
        """
        if stored_lang and stored_lang in TRANSLATIONS:
            return stored_lang

        for lang, triggers in LANG_TRIGGERS.items():
            for trigger in triggers:
                if trigger in text:
                    return lang
        return "hindi"

    def t(self, lang: str, key: str) -> str:
        """Translate a key to the given language."""
        lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS["hindi"])
        return lang_dict.get(key, TRANSLATIONS["hindi"].get(key, key))

    def format_reply(self, result: dict, lang: str, request_id: str) -> str:
        """
        Build the full WhatsApp reply in the farmer's language.
        Centralises all formatting — main.py calls this instead of building strings.
        """
        t = lambda key: self.t(lang, key)

        conf_pct  = int(result["confidence"] * 100)
        sev_icon  = {"critical": "🔴", "moderate": "🟡", "mild": "🟢"}.get(
                     result["severity"], "⚪")

        reply = (
            f"🐄 *PashuMitra AI* [{request_id}]\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"{t('disease_label')}: {result['hindi']}\n"
            f"{sev_icon} *{t('severity_label')}:* {result['severity'].upper()} ({conf_pct}%)\n\n"
            f"*{t('remedy_label')}:*\n{result['home_remedy']}\n\n"
            f"*{t('medicine_label')}:* {result['medicine']}\n"
            f"*{t('dosage_label')}:* {result['dosage']}\n\n"
            f"*{t('diet_label')}:* {result['diet_advice']}\n"
            f"*{t('prevention_label')}:* {result['prevention']}\n"
            f"*{t('shop_label')}:* {result['nearest_shop']}\n"
        )

        if result.get("differential"):
            reply += f"\n*{t('differential')}:*\n"
            for d in result["differential"]:
                reply += f"  • {d['hindi']} ({d['probability']})\n"

        if result.get("vaccinations_due"):
            reply += f"\n*{t('vaccination')}:*\n"
            for v in result["vaccinations_due"]:
                info = result["vaccination_schedule"].get(v, {})
                free = f" {t('free_vaccine')}" if info.get("free") else ""
                reply += f"  • {info.get('hindi', v)}{free} — {t('phc_msg')}\n"

        if result.get("is_contagious"):
            reply += f"\n{t('contagious_msg')}\n"

        reply += f"\n\n_{t('disclaimer')}_"
        return reply

    def get_limit_message(self, lang: str) -> str:
        return self.t(lang, "limit_msg")


lang_engine = LanguageEngine()