# app/services/ai_engine.py
import io, os, logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("pashumitra.ai")

# ── synonym expansion ────────────────────────────────────────────────────────
SYNONYMS: Dict[str, List[str]] = {
    "bukhar":      ["fever", "jwar", "tapman", "garmi", "garam", "tapna", "bukhaar", "tez bukhar"],
    "dast":        ["loose motion", "diarrhea", "patlaa", "patla gobar", "pait kharab", "loose stool"],
    "doodh kam":   ["milk less", "milk reduced", "udder hard", "thick milk", "gaay ka doodh",
                    "than se kam", "doodh nahi", "dudh kam"],
    "pet fool":    ["bloat", "afara", "tympany", "pait phula", "gas", "baayi taraf",
                    "left side", "pet badh", "pait fool", "pet fool gaya"],
    "ghav":        ["wound", "skin lesion", "khal", "suji", "chot", "khujli", "kilni", "daane"],
    "khansi":      ["cough", "nasal discharge", "naak se paani", "mucus", "khaans",
                    "saans", "khaansi", "respiratory"],
    "khurpaka":    ["fmd", "foot mouth", "muh mein chhale", "khur mein ghav", "mukhpaka",
                    "liblib", "chhale", "munh mein chhaale", "langda", "mouth sore",
                    "blister", "chhaale", "khur", "munh chhale"],
    "khana band":  ["not eating", "appetite loss", "khana nahi", "feed refusal", "anorexia", "kamzori"],
    # PPR-specific
    "ppr":         ["ppr", "bakri bukhaar", "bakri bimar", "goat fever", "goat diarrhea",
                    "bakri dast", "bakri naak", "naak beh rahi", "bakri khansi",
                    "bakri ko bukhaar", "bakri mein bukhar"],
    # Newcastle-specific
    "newcastle":   ["newcastle", "nd", "gardan ghoom", "gardan ghoom gayi", "gardan mudi",
                    "hara pakhana", "murgi gardan", "murgi bimar", "murgi ki gardan",
                    "poultry neck", "twisted neck", "green droppings", "green stool murgi",
                    "murgi nahi chal rahi", "murgi girna"],
}

VACCINATION_SCHEDULE = {
    "FMD":         {"interval_months": 6,   "free": True,  "hindi": "खुरपका-मुँहपका"},
    "HS":          {"interval_months": 12,  "free": True,  "hindi": "गलघोंटू"},
    "BQ":          {"interval_months": 12,  "free": True,  "hindi": "लंगड़िया बुखार"},
    "PPR":         {"interval_months": 36,  "free": True,  "hindi": "PPR (बकरी)"},
    "Newcastle":   {"interval_months": 6,   "free": True,  "hindi": "रानीखेत रोग"},
    "Brucellosis": {"interval_months": 999, "free": True,  "hindi": "ब्रुसेलोसिस"},
    "Theileria":   {"interval_months": 999, "free": False, "hindi": "थिलेरिया"},
}

SYMPTOMS_DB = [
    # ── FMD ─────────────────────────────────────────────────────────────────
    {
        "kw": ["khurpaka", "fmd", "foot mouth", "muh mein chhale", "khur mein ghav",
               "mukhpaka", "chhale", "munh mein chhaale", "langda", "mouth sore",
               "blister", "chhaale", "munh chhale", "khur"],
        "disease": "Foot and Mouth Disease (FMD)",
        "hindi": "खुरपका-मुँहपका रोग",
        "conf": 0.91, "severity": "critical",
        "remedy": "जानवर को तुरंत अलग करें। मुंह को KMnO4 घोल से धोएं। खुर को नीम के पानी में भिगोएं।",
        "medicine": "Borax 5% mouthwash. सरकारी पशु चिकित्सक को तुरंत सूचित करें — FMD सूचनीय रोग है।",
        "dosage": "केवल सहायक उपचार। डॉक्टर की दवाई बिना न दें। एंटीबायोटिक डॉक्टर के बिना नहीं।",
        "diet": "नरम चारा — चावल का पानी, पकी सब्जियां। सूखी घास न दें।",
        "prevention": "FMD टीका हर 6 महीने में (PHC पर मुफ्त)। नए जानवर 14 दिन अलग रखें।",
        "nearest_shop": "सरकारी PHC — FMD इलाज मुफ्त",
        "emergency": True, "is_contagious": True,
        "vaccinations_due": ["FMD"],
    },

    # ── Mastitis ────────────────────────────────────────────────────────────
    {
        "kw": ["doodh kam", "milk less", "udder hard", "thick milk", "than se kam",
               "mastitis", "than mein", "sujan than", "than fool", "than sujan",
               "doodh nahi", "dudh kam"],
        "disease": "Subclinical / Clinical Mastitis",
        "hindi": "थनैला रोग (Mastitis)",
        "conf": 0.88, "severity": "moderate",
        "remedy": "थन को गर्म पानी से 3 बार धोएं। सरसों तेल से हल्की मालिश करें। हल्दी+अजवाइन पानी 500ml पिलाएं।",
        "medicine": "Mastilep ointment (intramammary) या Penicillin-Streptomycin injection",
        "dosage": "हर दूध निकालने के बाद Intramammary tube × 5 दिन। Penicillin: 5ml IM 2 बार/दिन × 5 दिन।",
        "diet": "concentrate 50% कम करें। हरा चारा बढ़ाएं। हमेशा ताजा पानी।",
        "prevention": "दिन में 3 बार दूध निकालें। दूध के बाद iodine teat dip करें। दूध से पहले थन साफ करें।",
        "nearest_shop": "कृषि सेवा केंद्र / Veterinary shop",
        "emergency": False, "vaccinations_due": [],
    },

    # ── PPR (Goat) ──────────────────────────────────────────────────────────
    {
        "kw": ["ppr", "bakri bukhaar", "bakri bimar", "goat fever", "bakri dast",
               "bakri naak", "naak beh rahi", "bakri khansi", "bakri ko bukhaar",
               "bakri mein bukhar", "bakri", "goat"],
        "disease": "Peste des Petits Ruminants (PPR)",
        "hindi": "PPR — बकरी का प्लेग",
        "conf": 0.90, "severity": "critical",
        "remedy": "बकरी को तुरंत अलग करें। गर्म पानी पिलाएं। नाक-मुंह साफ करते रहें। डॉक्टर को बुलाएं।",
        "medicine": "PPR का कोई सीधा इलाज नहीं। Oxytetracycline (secondary infection के लिए)। सरकारी डॉक्टर से PPR serum।",
        "dosage": "Oxytetracycline: 10 mg/kg IM × 5 दिन। ORS 2-4 लीटर/दिन दस्त के लिए।",
        "diet": "नरम हरा चारा, गुड़ का पानी, ORS। सूखी घास न दें।",
        "prevention": "PPR टीका (3 साल में एक बार, PHC पर मुफ्त)। नई बकरी 21 दिन अलग रखें।",
        "nearest_shop": "सरकारी पशु चिकित्सालय — PPR vaccine मुफ्त",
        "emergency": True, "is_contagious": True,
        "vaccinations_due": ["PPR"],
    },

    # ── BRD / Pneumonia ─────────────────────────────────────────────────────
    {
        "kw": ["khansi", "cough", "nasal discharge", "naak se paani", "mucus",
               "khaans", "saans", "khaansi", "respiratory", "saans lene mein",
               "takleef", "bachde ko khansi"],
        "disease": "Respiratory Infection / BRD / Pneumonia",
        "hindi": "श्वसन रोग / BRD / निमोनिया",
        "conf": 0.85, "severity": "moderate",
        "remedy": "सूखे गर्म हवादार बाड़े में रखें। नीलगिरी तेल से भाप दिलाएं। गर्म पानी पिलाएं।",
        "medicine": "Oxytetracycline injection या Enrofloxacin (डॉक्टर द्वारा)",
        "dosage": "Oxytetracycline: 10 mg/kg IM एक बार/दिन × 5 दिन। हमेशा डॉक्टर की निगरानी में।",
        "diet": "गर्म पानी, नरम हरा चारा, गुड़+अदरक का काढ़ा। ठंडा पानी न दें।",
        "prevention": "HS + BQ vaccine साल में एक बार। नम/ठंडी जगह न रखें। अच्छी हवा का इंतजाम।",
        "nearest_shop": "सरकारी पशु चिकित्सालय",
        "emergency": False,
        "vaccinations_due": ["HS", "BQ"],
    },

    # ── Newcastle Disease (Poultry) ─────────────────────────────────────────
    {
        "kw": ["newcastle", "nd", "gardan ghoom", "gardan ghoom gayi", "gardan mudi",
               "hara pakhana", "murgi gardan", "murgi bimar", "murgi ki gardan",
               "poultry neck", "twisted neck", "green droppings", "murgi nahi chal rahi",
               "murgi girna", "murgi"],
        "disease": "Newcastle Disease (Ranikhet)",
        "hindi": "रानीखेत रोग (Newcastle Disease)",
        "conf": 0.90, "severity": "critical",
        "remedy": "बीमार मुर्गियों को तुरंत अलग करें। मृत मुर्गी को जमीन में गाड़ें। पानी के बर्तन रोज साफ करें।",
        "medicine": "Newcastle का कोई सीधा इलाज नहीं। Electrolytes + Vitamin C पानी में। Secondary infection के लिए Enrofloxacin।",
        "dosage": "Enrofloxacin: 10mg/kg पानी में × 5 दिन। Electrolyte: 1 sachet/लीटर पानी।",
        "diet": "साफ ताजा पानी हर समय। मक्का दलिया + विटामिन मिश्रण।",
        "prevention": "Ranikhet (F1) vaccine हर 6 महीने (PHC पर मुफ्त)। नई मुर्गी 10 दिन अलग रखें।",
        "nearest_shop": "सरकारी पशु चिकित्सालय — Ranikhet vaccine मुफ्त",
        "emergency": True, "is_contagious": True,
        "vaccinations_due": ["Newcastle"],
    },

    # ── Bloat ────────────────────────────────────────────────────────────────
    {
        "kw": ["pet fool", "bloat", "afara", "tympany", "pait phula", "gas",
               "baayi taraf", "left side", "pet badh", "pait fool", "pet fool gaya"],
        "disease": "Rumen Tympany / Bloat",
        "hindi": "अफारा / पेट फूलना",
        "conf": 0.88, "severity": "critical",
        "remedy": "हींग+अजवाइन का लेप मुंह से दें। गाय को 20 मिनट टहलाएं। बाईं तरफ पेट की मालिश करें (anti-clockwise)।",
        "medicine": "Bloatnil / Dimethicone / Turpentine 30ml + Linseed oil 250ml",
        "dosage": "Bloatnil 50-100ml मुंह से। 30 मिनट में आराम न हो → तुरंत डॉक्टर बुलाएं।",
        "diet": "हरा चारा बंद करें। 48 घंटे सिर्फ सूखी घास। concentrate कम करें।",
        "prevention": "खाली पेट गीली घास न दें। पहले सूखा चारा, फिर हरा।",
        "nearest_shop": "पशु औषधालय / dairy cooperative",
        "emergency": True, "vaccinations_due": [],
    },

    # ── Fever (generic) ─────────────────────────────────────────────────────
    {
        "kw": ["bukhar", "jwar", "tapman", "fever", "garam", "tapna", "garmi",
               "tez bukhar", "bukhaar"],
        "disease": "Fever (FMD / Tick-borne)",
        "hindi": "बुखार (सामान्य)",
        "conf": 0.75, "severity": "moderate",
        "remedy": "शरीर पर ठंडे पानी का छिड़काव। छांव में रखें। ताजा पानी + हरा चारा।",
        "medicine": "Melonex / Metacin injection या Paracetamol bolus",
        "dosage": "Paracetamol: 10-15 mg/kg। Melonex: 0.5 mg/kg IM एक बार। डॉक्टर से सलाह जरूरी।",
        "diet": "नरम हरा चारा, चावल का पानी, गुड़ का पानी। सूखा चारा न दें।",
        "prevention": "FMD vaccine हर 6 महीने। Tick control spray हर महीने।",
        "nearest_shop": "सरकारी PHC Vet Center",
        "emergency": True, "vaccinations_due": ["FMD", "HS"],
    },

    # ── Diarrhea ─────────────────────────────────────────────────────────────
    {
        "kw": ["dast", "loose motion", "diarrhea", "patlaa", "patla gobar",
               "pait kharab", "khoon gobar"],
        "disease": "Diarrhea / Gastroenteritis",
        "hindi": "दस्त / पतला गोबर",
        "conf": 0.82, "severity": "moderate",
        "remedy": "ORS: 1 लीटर गर्म पानी + 1 चम्मच नमक + 4 चम्मच चीनी। चावल का मांड। बेल पत्र का काढ़ा।",
        "medicine": "Electral / ORS powder। Sulfaguanidine tablet। Metronidazole (डॉक्टर द्वारा)।",
        "dosage": "ORS: 2-4 लीटर/दिन। Sulfaguanidine: 1 tablet/10kg दो बार/दिन।",
        "diet": "24 घंटे हरा चारा बंद। सिर्फ घास + ORS। 2 दिन बाद हरा चारा शुरू करें।",
        "prevention": "साफ पानी + ताजा चारा। हर 6 महीने deworm करें।",
        "nearest_shop": "कोई भी medical shop (ORS)। Vet shop (Sulfaguanidine)।",
        "emergency": False, "vaccinations_due": [],
    },

    # ── Skin / Ectoparasites ─────────────────────────────────────────────────
    {
        "kw": ["ghav", "wound", "skin lesion", "tick", "khal", "suji",
               "khujli", "kilni", "daane", "rashes", "chamdi"],
        "disease": "Skin Infection / Ectoparasites",
        "hindi": "चर्म रोग / खुजली",
        "conf": 0.80, "severity": "mild",
        "remedy": "नीम तेल स्प्रे। Dettol पानी (1:20) से घाव साफ करें। हफ्ते में एक बार राख स्नान।",
        "medicine": "Ivermectin injection + Butox/Ectomin acaricide spray",
        "dosage": "Ivermectin 0.2 mg/kg SC एक बार। Butox: 1ml/1L पानी, 2 बार/हफ्ते स्प्रे।",
        "diet": "Mineral mixture के साथ संतुलित आहार। Vitamin A और Zinc।",
        "prevention": "हफ्ते में एक बार नीम स्नान। हर महीने tick powder। रोज बाड़ा साफ।",
        "nearest_shop": "Local Pashu Kendra / Veterinary pharmacy",
        "emergency": False, "vaccinations_due": [],
    },

    # ── Anorexia / Weakness ──────────────────────────────────────────────────
    {
        "kw": ["khana band", "not eating", "appetite loss", "khana nahi",
               "kamzori", "weakness", "anorexia"],
        "disease": "Anorexia / General Weakness",
        "hindi": "खाना न खाना / कमजोरी",
        "conf": 0.65, "severity": "moderate",
        "remedy": "अदरक+लहसुन+गुड़ की गोली बनाकर दें। पानी न पिए तो ORS जबरदस्ती पिलाएं। Vitamin B complex injection।",
        "medicine": "Vitamin B12 injection + Liver tonic (Hematon/Ferotone)",
        "dosage": "B12: 1ml IM × 3 दिन। Liver tonic: 50ml मुंह से 2 बार/दिन।",
        "diet": "उच्च ऊर्जा: गुड़, मक्का, सरसों तेल। भूख लगने पर हरा चारा।",
        "prevention": "नियमित deworming। Mineral mixture 50g/दिन। संतुलित आहार।",
        "nearest_shop": "Veterinary pharmacy या कृषि सेवा केंद्र",
        "emergency": False, "vaccinations_due": [],
    },
]


def _normalize(text: str) -> str:
    t = text.lower()
    for canonical, variants in SYNONYMS.items():
        for v in variants:
            if v in t:
                t += " " + canonical
    return t


def _score(text_norm: str, entry: dict) -> float:
    matched = [kw for kw in entry["kw"] if kw in text_norm]
    if not matched:
        return 0.0, []
    # Confidence grows with number of DISTINCT matched symptoms, not density
    # against full keyword list (which unfairly punishes short farmer messages).
    n = len(matched)
    if n >= 4:
        boost = 1.0
    elif n == 3:
        boost = 0.92
    elif n == 2:
        boost = 0.78
    else:
        boost = 0.55
    return entry["conf"] * boost, matched


class PashuAI:
    def __init__(self):
        self.whisper_model = None
        self._whisper_ok = None
        self.loaded = False

    def load(self):
        if self.loaded:
            return
        if os.getenv("SKIP_WHISPER_LOAD") == "1":
            self._whisper_ok = False
            logger.info("Whisper skipped — using Groq API")
            self.loaded = True
            return
        try:
            import whisper  # type: ignore
            self.whisper_model = whisper.load_model("base")
            self._whisper_ok = True
        except ImportError:
            self._whisper_ok = False
            logger.warning("openai-whisper not installed — voice disabled")
        except Exception as e:
            self._whisper_ok = False
            logger.error("Whisper load failed: %s", e)
        self.loaded = True
        logger.info("PashuMitra AI ready (voice=%s)", self._whisper_ok)

    def transcribe_voice(self, audio_bytes: bytes) -> str:
        if not audio_bytes:
            return ""
        try:
            from groq import Groq  # type: ignore
            import tempfile
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
                f.write(audio_bytes)
                fname = f.name
            try:
                with open(fname, "rb") as f:
                    result = client.audio.transcriptions.create(
                        model="whisper-large-v3", file=f, language="hi")
                return result.text.strip()
            finally:
                try:
                    os.unlink(fname)
                except OSError:
                    pass
        except Exception as e:
            logger.error("Groq voice error: %s", e)
            return ""

    def detect_from_photo(self, image_bytes: bytes) -> Dict[str, Any]:
        try:
            from PIL import Image  # type: ignore
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            if img.size[0] < 150 or img.size[1] < 150:
                return self._fallback("Image too small/blurry")
        except Exception as e:
            return self._fallback(f"Cannot read image: {e}")
        result = self._find_best("doodh kam ghav sujan")
        result["type"] = "image"
        result["note"] = "Phase 1 mock — Phase 2 uses ViT model"
        return result

    def check_symptoms(self, text: str) -> Dict[str, Any]:
        r = self._find_best(text)
        r["type"] = "text"
        return r

    def _find_best(self, text: str) -> Dict[str, Any]:
        norm = _normalize(text)
        scored = []
        for e in SYMPTOMS_DB:
            s, matched_kw = _score(norm, e)
            if s > 0:
                scored.append((s, e, matched_kw))
        if not scored:
            return self._fallback(text)
        scored.sort(key=lambda x: x[0], reverse=True)
        best_s, best, best_matched = scored[0]
        differential = [
            {"disease": e["disease"], "hindi": e["hindi"], "probability": f"{s:.0%}"}
            for s, e, _ in scored[1:3] if s >= best_s * 0.65
        ]
        # Human-readable reason for the confidence score — shown to the farmer
        # so the % is never a black box.
        n = len(best_matched)
        unique_symptoms = ", ".join(sorted(set(best_matched))[:4])
        if n >= 4:
            reason = f"आपके बताए {n} लक्षण ({unique_symptoms}) इस बीमारी से पूरी तरह मेल खाते हैं।"
        elif n == 3:
            reason = f"आपके बताए {n} लक्षण ({unique_symptoms}) इस बीमारी से अच्छी तरह मेल खाते हैं।"
        elif n == 2:
            reason = f"सिर्फ {n} लक्षण ({unique_symptoms}) मिले — पूरा यकीन के लिए और लक्षण बताएं या फोटो भेजें।"
        else:
            reason = f"सिर्फ 1 लक्षण ({unique_symptoms}) मिला — सटीक जानकारी के लिए कृपया और लक्षण बताएं।"

        return {
            "disease":    best["disease"],
            "hindi":      best["hindi"],
            "confidence": round(min(best_s, 0.95), 2),
            "confidence_reason": reason,
            "matched_symptoms_count": n,
            "severity":   best["severity"],
            "home_remedy":   best["remedy"],
            "medicine":      best["medicine"],
            "dosage":        best["dosage"],
            "diet_advice":   best["diet"],
            "prevention":    best["prevention"],
            "nearest_shop":  best["nearest_shop"],
            "emergency":       best.get("emergency", False),
            "is_contagious":   best.get("is_contagious", False),
            "vaccinations_due": best.get("vaccinations_due", []),
            "differential": differential,
            "vaccination_schedule": {
                k: v for k, v in VACCINATION_SCHEDULE.items()
                if k in best.get("vaccinations_due", [])
            },
        }

    def generate_response(self, text: str, media_type: Optional[str] = None,
                          media_bytes: Optional[bytes] = None) -> Dict[str, Any]:
        if media_type == "image" and media_bytes:
            return self.detect_from_photo(media_bytes)
        return self.check_symptoms(text or "")

    def _fallback(self, msg: str) -> Dict[str, Any]:
        return {
            "disease": "Symptoms Unclear", "hindi": "लक्षण अस्पष्ट",
            "confidence": 0.0,
            "confidence_reason": "कोई जाना-पहचाना लक्षण नहीं मिला। कृपया और विस्तार से बताएं या फोटो भेजें।",
            "matched_symptoms_count": 0,
            "severity": "unknown",
            "home_remedy": "साफ पानी, संतुलित आहार दें। 24 घंटे नजर रखें।",
            "medicine": "अभी कुछ नहीं — और लक्षण बताएं या फोटो भेजें।",
            "dosage": "N/A",
            "diet_advice": "सामान्य संतुलित आहार। हमेशा ताजा पानी।",
            "prevention": "नियमित deworming + vaccination।",
            "nearest_shop": "नजदीकी dairy cooperative देखें।",
            "emergency": False, "is_contagious": False,
            "vaccinations_due": [], "differential": [], "vaccination_schedule": {},
            "type": "fallback",
            "note": f"Could not identify: '{str(msg)[:80]}'",
        }


ai_engine = PashuAI()
