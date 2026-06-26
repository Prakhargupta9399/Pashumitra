"""
PashuMitra AI — Flask Backend + Frontend
Run: python app.py
"""
import os, sys, logging
from flask import Flask, request, jsonify
from flask_cors import CORS

os.environ.setdefault("DATABASE_URL",         "sqlite:///./pashumitra.db")
os.environ.setdefault("GROQ_API_KEY",         "")
os.environ.setdefault("SKIP_WHISPER_LOAD",    "1")
os.environ.setdefault("ENVIRONMENT",          "development")
os.environ.setdefault("DAILY_FREE_LIMIT",     "50")

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("pashumitra")

sys.path.insert(0, os.path.dirname(__file__))

from app.services.ai_engine import ai_engine
from app.database            import engine as db_engine, Base, SessionLocal
from app.models              import Farmer, QueryLog
from app.limits              import check_and_increment, get_usage

Base.metadata.create_all(bind=db_engine)

# ── Auto-migration: add 'helpful' column if missing (SQLite doesn't auto-alter) ──
try:
    with db_engine.connect() as conn:
        from sqlalchemy import text
        existing_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(query_logs)"))]
        if "helpful" not in existing_cols:
            conn.execute(text("ALTER TABLE query_logs ADD COLUMN helpful BOOLEAN"))
            conn.commit()
            logger.info("Migration: added 'helpful' column to query_logs")
except Exception as e:
    logger.warning("Auto-migration check failed (non-fatal): %s", e)
ai_engine.load()

# Groq optional
_groq = None
_groq_ok = False
_api_key = os.environ.get("GROQ_API_KEY", "").strip()
if _api_key:
    try:
        from groq import Groq
        _groq = Groq(api_key=_api_key)
        _groq_ok = True
    except Exception:
        pass

BASE_SYSTEM_PROMPT = """You are Pashumitra, expert livestock vet AI for Indian farmers.
Reply ONLY in simple Hindi (Devanagari). Be specific to the disease. Max 200 words.

Format EXACTLY:
🔍 संभावित बीमारी: [Hindi disease name]
📊 संभावना: [High/Medium/Low] | गंभीरता: [severity]

🏠 घर पर अभी करें:
1. [step]
2. [step]
3. [step]

💊 दवाई: [medicine]
💉 खुराक: [dosage brief]
🥗 आहार: [diet 1 line]
🛡️ बचाव: [prevention 1 line]

[if emergency]: 🚨 आज ही डॉक्टर बुलाएं — 1962 पर कॉल करें
[if contagious]: ⚠️ संक्रामक रोग — अन्य पशुओं से अलग करें!
📞 राष्ट्रीय पशु चिकित्सा हेल्पलाइन: 1962"""

_sessions: dict = {}

def _groq_reply(phone: str, user_text: str, local: dict) -> str:
    conf_pct = int(local.get("confidence", 0) * 100)
    sev_map  = {"critical":"अति गंभीर 🔴","moderate":"सामान्य 🟡","mild":"हल्का 🟢"}
    context  = f"""किसान का संदेश: "{user_text}"
AI-detected: {local.get('hindi')} ({conf_pct}%) | {sev_map.get(local.get('severity',''),'')}
घरेलू उपचार: {local.get('home_remedy')}
दवाई: {local.get('medicine')} | खुराक: {local.get('dosage')}
आहार: {local.get('diet_advice')} | बचाव: {local.get('prevention')}
emergency={local.get('emergency')} contagious={local.get('is_contagious')}"""

    if phone not in _sessions:
        _sessions[phone] = []
    _sessions[phone].append({"role": "user", "content": context})
    r = _groq.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": BASE_SYSTEM_PROMPT}] + _sessions[phone][-4:],
        max_tokens=420, temperature=0.25,
    )
    reply = r.choices[0].message.content.strip()
    _sessions[phone].append({"role": "assistant", "content": reply})
    return reply

flask_app = Flask(__name__)
CORS(flask_app)

@flask_app.route("/api/diagnose", methods=["POST"])
def diagnose():
    body  = request.json or {}
    text  = (body.get("message") or "").strip()
    phone = body.get("phone", "demo").strip() or "demo"
    if not text:
        return jsonify({"error": "message required"}), 400

    allowed = check_and_increment(phone)
    if not allowed:
        usage = get_usage(phone)
        return jsonify({"limited": True,
            "message": "⚠️ आज की मुफ्त सलाह खत्म हो गई। कल फिर कोशिश करें।",
            "usage": usage}), 429

    local = ai_engine.check_symptoms(text)

    llm_reply = ""
    if _groq_ok:
        try:
            llm_reply = _groq_reply(phone, text, local)
        except Exception as e:
            logger.warning("Groq error: %s", e)

    try:
        db = SessionLocal()
        db.add(QueryLog(phone=phone, query_text=text[:500],
                        disease=local.get("disease"), severity=local.get("severity")))
        db.commit()
        db.close()
    except Exception as e:
        logger.warning("DB log error: %s", e)

    usage = get_usage(phone)
    return jsonify({
        "local":   local,
        "reply":   llm_reply,   # empty string if Groq unavailable
        "usage":   usage,
        "limited": False,
    })

@flask_app.route("/api/usage/<phone>")
def usage(phone):
    return jsonify(get_usage(phone))

@flask_app.route("/api/feedback", methods=["POST"])
def feedback():
    body = request.json or {}
    phone = body.get("phone", "demo")
    helpful = body.get("helpful", True)
    try:
        db = SessionLocal()
        log = db.query(QueryLog).filter(QueryLog.phone == phone).order_by(QueryLog.id.desc()).first()
        if log:
            log.helpful = helpful
            db.commit()
        db.close()
    except Exception as e:
        logger.warning("Feedback log error: %s", e)
    return jsonify({"status": "ok"})

@flask_app.route("/api/feedback/stats")
def feedback_stats():
    try:
        db = SessionLocal()
        total = db.query(QueryLog).filter(QueryLog.helpful.isnot(None)).count()
        helpful_count = db.query(QueryLog).filter(QueryLog.helpful == True).count()
        db.close()
        pct = round((helpful_count / total * 100), 1) if total > 0 else 0
        return jsonify({"total_rated": total, "helpful": helpful_count, "helpful_pct": pct})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@flask_app.route("/api/health")
def health():
    return jsonify({"status": "ok", "groq": _groq_ok, "ai_engine": ai_engine.loaded})

@flask_app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == "vetai2024":
        return request.args.get("hub.challenge", "")
    return "Forbidden", 403

@flask_app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json or {}
    try:
        import requests as req
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" in value:
            msg = value["messages"][0]
            if "text" in msg:
                local = ai_engine.check_symptoms(msg["text"]["body"])
                reply_text = _build_whatsapp(local)
                req.post(
                    f"https://graph.facebook.com/v18.0/{os.environ.get('PHONE_ID')}/messages",
                    headers={"Authorization": f"Bearer {os.environ.get('WA_TOKEN')}"},
                    json={"messaging_product":"whatsapp","to":msg["from"],
                          "type":"text","text":{"body": reply_text}},
                    timeout=10)
    except Exception as e:
        logger.error("Webhook error: %s", e)
    return "ok", 200

def _build_whatsapp(r: dict) -> str:
    sev = {"critical":"🔴 अति गंभीर","moderate":"🟡 सामान्य","mild":"🟢 हल्का"}.get(r["severity"],"⚪")
    lines = [
        f"🔍 बीमारी: {r['hindi']}",
        f"📊 {int(r['confidence']*100)}% | {sev}",
        f"🏠 घर पर करें: {r['home_remedy']}",
        f"💊 दवाई: {r['medicine']}",
        f"💉 खुराक: {r['dosage']}",
        f"🥗 आहार: {r['diet_advice']}",
    ]
    if r.get("emergency"):
        lines.append("🚨 तुरंत डॉक्टर बुलाएं — 1962 पर कॉल करें (राष्ट्रीय हेल्पलाइन)")
    lines.append("📞 हेल्पलाइन: 1962")
    return "\n".join(lines)

@flask_app.route("/")
def home():
    return FRONTEND_HTML

FRONTEND_HTML = """<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>पशुमित्र AI</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--g:#1D9E75;--gd:#157a5a;--gl:#E8F8F2;--gm:#b7e8d3;--red:#dc2626;--amber:#d97706;--border:#e5e7eb;--text:#1a1a1a;--muted:#6b7280;--r:14px;--sh:0 4px 24px rgba(0,0,0,.10)}
body{font-family:'Segoe UI',Arial,sans-serif;background:#f0faf5;color:var(--text);min-height:100vh;display:flex;flex-direction:column}

header{background:linear-gradient(135deg,#1D9E75,#0d7a57);color:#fff;padding:0 20px;display:flex;align-items:center;gap:14px;height:64px;box-shadow:0 2px 12px rgba(0,0,0,.18);position:sticky;top:0;z-index:100}
.brand h1{font-size:20px;font-weight:800}.brand p{font-size:12px;opacity:.8}
.live-pill{margin-left:auto;background:rgba(255,255,255,.15);border:1.5px solid rgba(255,255,255,.4);color:#fff;border-radius:20px;padding:4px 14px;font-size:11px;font-weight:700;display:flex;align-items:center;gap:6px}
.dot{width:8px;height:8px;border-radius:50%;background:#4ade80;box-shadow:0 0 6px #4ade80}

.page{max-width:800px;margin:0 auto;width:100%;padding:18px 14px 40px;flex:1;display:flex;flex-direction:column;gap:14px}

.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.stat{background:#fff;border-radius:var(--r);padding:14px;text-align:center;box-shadow:0 1px 6px rgba(0,0,0,.06)}
.stat .n{font-size:22px;font-weight:800;color:var(--g)}.stat .l{font-size:11px;color:var(--muted);margin-top:2px}

.sec-lbl{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:7px}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{background:#fff;border:1.5px solid var(--g);color:var(--g);border-radius:20px;padding:7px 13px;font-size:13px;cursor:pointer;transition:all .18s;font-family:inherit}
.chip:hover{background:var(--g);color:#fff;transform:translateY(-1px);box-shadow:0 3px 10px rgba(29,158,117,.3)}

.chat-card{background:#fff;border-radius:var(--r);box-shadow:var(--sh);overflow:hidden;display:flex;flex-direction:column;flex:1;min-height:420px}
.chat-top{background:var(--gl);border-bottom:1px solid var(--gm);padding:10px 16px;display:flex;justify-content:space-between;align-items:center}
.chat-top span{font-size:13px;font-weight:600;color:var(--gd)}
.ubadge{font-size:11px;background:var(--g);color:#fff;border-radius:20px;padding:3px 10px}

.msgs{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:14px;scroll-behavior:smooth}

/* user bubble */
.msg-user{align-self:flex-end;display:flex;flex-direction:column;align-items:flex-end;gap:3px;max-width:80%}
.msg-user .bbl{background:var(--g);color:#fff;padding:11px 15px;border-radius:16px 16px 4px 16px;font-size:14px;line-height:1.6;word-break:break-word}
.msg-user .ts{font-size:10px;color:var(--muted)}

/* bot card */
.msg-bot{align-self:flex-start;max-width:92%;width:100%}
.disease-card{background:#fff;border:1.5px solid var(--border);border-radius:var(--r);overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.07)}
.card-head{padding:12px 16px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px}
.card-head.critical{background:#fff1f1;border-bottom:2px solid #fca5a5}
.card-head.moderate{background:#fffbeb;border-bottom:2px solid #fcd34d}
.card-head.mild{background:#f0fdf4;border-bottom:2px solid #86efac}
.card-head.unknown{background:#f9fafb;border-bottom:1px solid var(--border)}
.disease-name{font-size:17px;font-weight:800}
.card-head.critical .disease-name{color:#b91c1c}
.card-head.moderate .disease-name{color:#92400e}
.card-head.mild .disease-name{color:#065f46}
.card-head.unknown .disease-name{color:var(--muted)}
.conf-badge{font-size:12px;font-weight:700;padding:3px 10px;border-radius:12px}
.card-head.critical .conf-badge{background:#fee2e2;color:#b91c1c}
.card-head.moderate .conf-badge{background:#fef3c7;color:#92400e}
.card-head.mild .conf-badge{background:#d1fae5;color:#065f46}
.card-head.unknown .conf-badge{background:#f3f4f6;color:var(--muted)}

.card-body{padding:14px 16px;display:flex;flex-direction:column;gap:10px;font-size:13.5px;line-height:1.7}
.row{display:flex;gap:10px}
.row .icon{font-size:16px;flex-shrink:0;margin-top:1px}
.row .content{}
.row .label{font-weight:700;color:#374151;margin-bottom:2px}
.row .val{color:#374151}
.steps{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:4px}
.steps li{display:flex;gap:7px;align-items:flex-start}
.steps li .num{background:var(--g);color:#fff;border-radius:50%;width:18px;height:18px;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:2px}

.alert-row{display:flex;gap:8px;align-items:flex-start;padding:8px 12px;border-radius:8px;font-size:13px;font-weight:600}
.alert-emergency{background:#fee2e2;color:#b91c1c}
.alert-contagious{background:#fef3c7;color:#92400e}

.diff-section{padding:0 16px 12px;font-size:12px;color:var(--muted)}
.diff-section strong{color:#374151}

.card-foot{padding:10px 16px;background:#f9fafb;border-top:1px solid var(--border);font-size:12px;color:var(--muted);display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.card-foot a{color:var(--g);font-weight:700;text-decoration:none}
.msg-bot .ts{font-size:10px;color:var(--muted);margin-top:4px;padding-left:4px}

/* typing */
.typing-bbl{background:#f5f7f9;border:1px solid var(--border);border-radius:16px 16px 16px 4px;padding:14px 18px;display:inline-flex;gap:5px;align-items:center}
.dot-anim{width:7px;height:7px;border-radius:50%;background:var(--g);animation:blink 1.2s infinite}
.dot-anim:nth-child(2){animation-delay:.2s}.dot-anim:nth-child(3){animation-delay:.4s}
@keyframes blink{0%,80%,100%{opacity:.2}40%{opacity:1}}

/* welcome */
.welcome-bbl{background:#f5f7f9;border:1px solid var(--border);border-radius:16px 16px 16px 4px;padding:14px 16px;font-size:14px;line-height:1.8}

.inp-wrap{display:flex;gap:10px;padding:13px 14px;border-top:1px solid var(--border);background:#fafafa}
.inp-wrap input{flex:1;padding:11px 15px;border:1.5px solid var(--border);border-radius:10px;font-size:14px;font-family:inherit;outline:none;background:#fff;transition:border .15s}
.inp-wrap input:focus{border-color:var(--g);box-shadow:0 0 0 3px rgba(29,158,117,.12)}
.inp-wrap input::placeholder{color:#9ca3af}
.send-btn{background:var(--g);color:#fff;border:none;border-radius:10px;padding:11px 22px;font-size:14px;cursor:pointer;font-weight:700;transition:all .18s}
.send-btn:hover:not(:disabled){background:var(--gd)}
.send-btn:disabled{opacity:.45;cursor:not-allowed}

.contact-bar{background:#fff;border-radius:var(--r);padding:13px 16px;box-shadow:0 1px 6px rgba(0,0,0,.06);display:flex;align-items:center;gap:12px;flex-wrap:wrap;font-size:13px}
.contact-bar a{color:var(--g);font-weight:700;text-decoration:none}
.contact-bar a:hover{text-decoration:underline}
.sep{width:1px;height:20px;background:var(--border)}

footer{text-align:center;font-size:11px;color:var(--muted);padding:10px 0 6px}

.msgs::-webkit-scrollbar{width:5px}.msgs::-webkit-scrollbar-thumb{background:#d1d5db;border-radius:4px}
</style>
</head>
<body>
<header>
  <div style="font-size:28px">🐄</div>
  <div class="brand"><h1>पशुमित्र AI</h1><p>पशु चिकित्सा सहायक — Chhatarpur Pilot</p></div>
  <div class="live-pill"><div class="dot" id="sdot"></div>LIVE</div>
  <button onclick="toggleLang()" id="langBtn" style="margin-left:8px;background:rgba(255,255,255,.15);border:1.5px solid rgba(255,255,255,.4);color:#fff;border-radius:20px;padding:4px 14px;font-size:12px;font-weight:700;cursor:pointer">EN</button>
</header>

<div class="page">
  <div class="stats">
    <div class="stat"><div class="n">9+</div><div class="l">रोग पहचाने</div></div>
    <div class="stat"><div class="n" id="qc">0</div><div class="l">आज के सवाल</div></div>
    <div class="stat"><div class="n">मुफ्त</div><div class="l">बिल्कुल नि:शुल्क</div></div>
  </div>

  <div>
    <div class="sec-lbl">जल्दी पूछें — एक क्लिक में</div>
    <div class="chips">
      <button class="chip" onclick="ask('gaay ke munh mein chhaale hain aur khur mein ghav hai langda rahi hai')">🐄 खुरपका (FMD)</button>
      <button class="chip" onclick="ask('than mein sujan hai doodh bilkul kam ho gaya than sakht hai')">🍼 थनैला रोग</button>
      <button class="chip" onclick="ask('bakri ko bukhaar hai naak beh rahi hai dast lag rahe hain')">🐐 PPR बकरी</button>
      <button class="chip" onclick="ask('bachde ko khaansi hai saans lene mein takleef naak se paani')">🫁 BRD सांस रोग</button>
      <button class="chip" onclick="ask('murgi ki gardan ghoom gayi hai hara pakhana aa raha')">🐔 रानीखेत</button>
      <button class="chip" onclick="ask('gaay ka pet baayi taraf fool gaya afara gas hai')">🫃 अफारा/Bloat</button>
    </div>
  </div>

  <div class="chat-card">
    <div class="chat-top">
      <span>💬 पशुमित्र से बात करें</span>
      <span class="ubadge" id="ulbl">आज: 0 सवाल</span>
    </div>
    <div class="msgs" id="msgs">
      <div class="msg-bot">
        <div class="welcome-bbl">नमस्ते! 🙏 मैं <strong>पशुमित्र AI</strong> हूँ।<br><br>
          अपने पशु के लक्षण लिखें — जैसे <em>"गाय के मुंह में छाले हैं"</em><br>
          या ऊपर से कोई बीमारी चुनें। मैं तुरंत बताऊंगा:<br>
          ✅ कौन सी बीमारी है &nbsp; ✅ घर पर क्या करें<br>
          ✅ कौन सी दवाई लें &nbsp; ✅ कब डॉक्टर बुलाएं</div>
      </div>
    </div>
    <div class="inp-wrap">
      <input id="inp" type="text" placeholder="लक्षण लिखें... जैसे: गाय खाना नहीं खा रही" autocomplete="off" onkeydown="if(event.key==='Enter')send()"/>
      <button class="send-btn" id="sbtn" onclick="send()">भेजें ➤</button>
    </div>
  </div>

  <div class="contact-bar" id="districtBar" style="flex-direction:column;align-items:stretch;gap:8px">
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <span>📍 आपका जिला/शहर बताएं ताकि सही डॉक्टर का नंबर मिले:</span>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <input id="districtInp" type="text" placeholder="जैसे: छतरपुर, इंदौर, जयपुर..." style="flex:1;min-width:160px;padding:8px 12px;border:1.5px solid var(--border);border-radius:8px;font-size:13px;font-family:inherit"/>
      <button onclick="setDistrict()" style="background:var(--g);color:#fff;border:none;border-radius:8px;padding:8px 16px;font-size:13px;font-weight:700;cursor:pointer">सेट करें</button>
      <button onclick="skipDistrict()" style="background:transparent;color:var(--muted);border:1px solid var(--border);border-radius:8px;padding:8px 16px;font-size:13px;cursor:pointer">छोड़ें (1962 इस्तेमाल होगा)</button>
    </div>
  </div>

  <div class="contact-bar" id="contactBar" style="display:none">
    <span>📞 आपके जिले का पशु चिकित्सा कार्यालय:</span>
    <a href="tel:" id="districtPhoneLink">—</a>
    <div class="sep"></div>
    <span>राष्ट्रीय हेल्पलाइन (हर जगह काम करती है):</span>
    <a href="tel:1962">1962</a>
    <div class="sep"></div>
    <button onclick="resetDistrict()" style="font-size:11px;color:var(--muted);background:none;border:none;cursor:pointer;text-decoration:underline">बदलें</button>
  </div>
</div>

<footer>पशुमित्र AI — Chhatarpur, Madhya Pradesh | Pilot v1.0 | यह AI सलाह है — गंभीर स्थिति में डॉक्टर से मिलें</footer>

<script>
const PHONE = "web_" + Math.random().toString(36).slice(2,8);
let currentLang = 'hi';

// District-wise Animal Husbandry office numbers (MP focus, extendable).
// 1962 always works nationwide as fallback — this is just a "better, local" option.
const DISTRICT_VET_NUMBERS = {
  'chhatarpur': '07682248683', 'छतरपुर': '07682248683',
  'indore': '07312411468', 'इंदौर': '07312411468',
  'bhopal': '07552661866', 'भोपाल': '07552661866',
  'jabalpur': '07612626666', 'जबलपुर': '07612626666',
  'gwalior': '07512340987', 'ग्वालियर': '07512340987',
  'sagar': '07582226666', 'सागर': '07582226666',
};

let userDistrictPhone = null;

function setDistrict(){
  const val = document.getElementById('districtInp').value.trim().toLowerCase();
  if(!val){ skipDistrict(); return; }
  const found = DISTRICT_VET_NUMBERS[val];
  document.getElementById('districtBar').style.display='none';
  document.getElementById('contactBar').style.display='flex';
  if(found){
    userDistrictPhone = found;
    document.getElementById('districtPhoneLink').textContent = found.replace(/(\d{5})(\d{6})/,'$1-$2');
    document.getElementById('districtPhoneLink').href = 'tel:'+found;
  } else {
    // District not in our database yet — be honest, fall back to 1962 only
    userDistrictPhone = null;
    document.getElementById('districtPhoneLink').textContent = 'उपलब्ध नहीं — कृपया 1962 इस्तेमाल करें';
    document.getElementById('districtPhoneLink').href = 'tel:1962';
  }
}

function skipDistrict(){
  userDistrictPhone = null;
  document.getElementById('districtBar').style.display='none';
  document.getElementById('contactBar').style.display='flex';
  document.getElementById('districtPhoneLink').textContent = '1962 इस्तेमाल करें';
  document.getElementById('districtPhoneLink').href = 'tel:1962';
}

function resetDistrict(){
  document.getElementById('contactBar').style.display='none';
  document.getElementById('districtBar').style.display='flex';
  document.getElementById('districtInp').value='';
}

function ts(){const d=new Date();return d.getHours().toString().padStart(2,'0')+':'+d.getMinutes().toString().padStart(2,'0')}

function addUser(text){
  const msgs=document.getElementById('msgs');
  const d=document.createElement('div');
  d.className='msg-user';
  d.innerHTML=`<div class="bbl">${text.replace(/</g,'&lt;')}</div><div class="ts">${ts()}</div>`;
  msgs.appendChild(d);scroll();
}

function showTyping(){
  const msgs=document.getElementById('msgs');
  const d=document.createElement('div');d.id='typing';d.className='msg-bot';
  d.innerHTML='<div class="typing-bbl"><div class="dot-anim"></div><div class="dot-anim"></div><div class="dot-anim"></div></div>';
  msgs.appendChild(d);scroll();
}
function removeTyping(){const e=document.getElementById('typing');if(e)e.remove();}
function scroll(){const m=document.getElementById('msgs');m.scrollTop=m.scrollHeight;}

function buildCard(local, llm_reply){
  const cardId = 'c'+Date.now()+Math.random().toString(36).slice(2,6);
  const sev = local.severity || 'unknown';
  const sevLabel = {critical:'🔴 अति गंभीर',moderate:'🟡 सामान्य',mild:'🟢 हल्का',unknown:'⚪ अज्ञात'}[sev]||'';
  const conf = Math.round((local.confidence||0)*100);

  // split remedy into numbered steps
  const remedySteps = (local.home_remedy||'').split(/[.।;]/).map(s=>s.trim()).filter(Boolean);
  const stepsHtml = remedySteps.map((s,i)=>
    `<li><div class="num">${i+1}</div><span>${s}</span></li>`
  ).join('');

  const emergencyPhone = userDistrictPhone || '1962';
  const emergencyDisplay = userDistrictPhone
    ? userDistrictPhone.replace(/(\d{5})(\d{6})/,'$1-$2')
    : '1962 (राष्ट्रीय हेल्पलाइन)';
  const emergencyHtml = local.emergency
    ? `<div class="alert-row alert-emergency">🚨 गंभीर बीमारी! तुरंत डॉक्टर बुलाएं</div>
       <a href="tel:${emergencyPhone}" style="display:flex;align-items:center;justify-content:center;gap:8px;background:#dc2626;color:#fff;padding:12px;border-radius:10px;font-size:15px;font-weight:800;text-decoration:none;margin:0 0 4px">📞 अभी कॉल करें — ${emergencyDisplay}</a>` : '';
  const contagiousHtml = local.is_contagious
    ? `<div class="alert-row alert-contagious">⚠️ यह संक्रामक रोग है! अन्य पशुओं से तुरंत अलग करें!</div>` : '';

  const diffHtml = (local.differential||[]).length
    ? `<div class="diff-section"><strong>अन्य संभावना:</strong> ${local.differential.map(d=>`${d.hindi} (${d.probability})`).join(' | ')}</div>` : '';

  // if Groq gave a reply, show it as a note
  const llmHtml = llm_reply
    ? `<div style="padding:10px 16px 0;font-size:13px;color:#374151;border-top:1px solid var(--border);white-space:pre-wrap">${llm_reply.replace(/</g,'&lt;')}</div>` : '';

  return `<div class="disease-card">
  <div class="card-head ${sev}">
    <div class="disease-name">${local.hindi||'लक्षण अस्पष्ट'}</div>
    <div class="conf-badge">${sevLabel} &nbsp;|&nbsp; ${conf}% संभावना</div>
  </div>
  <div style="padding:6px 16px 0;font-size:11.5px;color:var(--muted);font-style:italic">ℹ️ ${local.confidence_reason||''}</div>
  <div class="card-body">
    <div class="row"><div class="icon">🏠</div><div class="content">
      <div class="label">घर पर अभी करें:</div>
      <ul class="steps">${stepsHtml}</ul>
    </div></div>
    <div class="row"><div class="icon">💊</div><div class="content">
      <div class="label">दवाई:</div>
      <div class="val">${local.medicine||'—'}</div>
    </div></div>
    <div class="row"><div class="icon">💉</div><div class="content">
      <div class="label">खुराक:</div>
      <div class="val">${local.dosage||'—'}</div>
    </div></div>
    <div class="row"><div class="icon">🥗</div><div class="content">
      <div class="label">आहार:</div>
      <div class="val">${local.diet_advice||'—'}</div>
    </div></div>
    <div class="row"><div class="icon">🛡️</div><div class="content">
      <div class="label">बचाव:</div>
      <div class="val">${local.prevention||'—'}</div>
    </div></div>
    ${emergencyHtml}${contagiousHtml}
  </div>
  ${diffHtml}
  ${llmHtml}
  <div class="card-foot" style="flex-direction:column;align-items:flex-start;gap:6px">
    <div style="width:100%;display:flex;gap:16px;flex-wrap:wrap">
      <span>📍 ${local.nearest_shop||'नजदीकी पशु चिकित्सालय'}</span>
      <span style="margin-left:auto">📞 <a href="tel:1962">1962</a></span>
    </div>
    <div style="font-size:11px;color:var(--muted);font-style:italic;width:100%">⚠️ यह AI सलाह है — गंभीर स्थिति में डॉक्टर से मिलें</div>
  </div>
  <div class="feedback-row" id="fb-${cardId}" style="display:flex;gap:8px;padding:10px 16px;border-top:1px solid var(--border);align-items:center">
    <span style="font-size:12px;color:var(--muted)">क्या यह सहायक था?</span>
    <button onclick="feedback('${cardId}',true)" style="border:1px solid #86efac;background:#f0fdf4;color:#065f46;border-radius:8px;padding:5px 12px;font-size:13px;cursor:pointer">👍 हाँ</button>
    <button onclick="feedback('${cardId}',false)" style="border:1px solid #fca5a5;background:#fff1f1;color:#b91c1c;border-radius:8px;padding:5px 12px;font-size:13px;cursor:pointer">👎 नहीं</button>
  </div>
</div>`;
}

function addBot(local, llm_reply){
  const msgs=document.getElementById('msgs');
  const d=document.createElement('div');d.className='msg-bot';
  d.innerHTML=buildCard(local, llm_reply)+`<div class="ts">${ts()}</div>`;
  msgs.appendChild(d);scroll();
}

function addError(msg){
  const msgs=document.getElementById('msgs');
  const d=document.createElement('div');d.className='msg-bot';
  d.innerHTML=`<div class="welcome-bbl" style="color:var(--red)">❌ ${msg}</div>`;
  msgs.appendChild(d);scroll();
}

function updateUsage(u){
  document.getElementById('ulbl').textContent=`आज: ${u.used}/${u.limit} सवाल`;
  document.getElementById('qc').textContent=u.used;
}

function feedback(cardId, helpful){
  const row=document.getElementById('fb-'+cardId);
  row.innerHTML=`<span style="font-size:12px;color:var(--g);font-weight:600">${helpful?'✅ धन्यवाद!':'🙏 माफ करें, सुधार करेंगे'}</span>`;
  fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({phone:PHONE,helpful:helpful})}).catch(()=>{});
}

function toggleLang(){
  currentLang = currentLang === 'hi' ? 'en' : 'hi';
  document.getElementById('langBtn').textContent = currentLang === 'hi' ? 'EN' : 'हि';
  document.getElementById('inp').placeholder = currentLang === 'hi'
    ? 'लक्षण लिखें... जैसे: गाय खाना नहीं खा रही'
    : 'Type symptoms... e.g. cow not eating';
}

function ask(text){document.getElementById('inp').value=text;send();}

async function send(){
  const inp=document.getElementById('inp'),btn=document.getElementById('sbtn');
  const text=inp.value.trim();if(!text)return;
  addUser(text);inp.value='';btn.disabled=true;showTyping();
  try{
    const res=await fetch('/api/diagnose',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:text,phone:PHONE})
    });
    const data=await res.json();
    removeTyping();
    if(data.limited){addError(data.message||'सीमा समाप्त');}
    else{addBot(data.local, data.reply);if(data.usage)updateUsage(data.usage);}
  }catch(e){removeTyping();addError('कनेक्शन में समस्या। दोबारा कोशिश करें।');}
  btn.disabled=false;inp.focus();
}

(async()=>{
  try{const r=await fetch('/api/health');const d=await r.json();
    if(d.status!=='ok')document.getElementById('sdot').style.background='#f87171';
  }catch{document.getElementById('sdot').style.background='#f87171';}
})();
</script>
</body>
</html>"""

if __name__ == "__main__":
    import webbrowser, threading, time
    port = int(os.environ.get("PORT", 5000))
    def _open():
        time.sleep(1.4)
        webbrowser.open(f"http://localhost:{port}")
    threading.Thread(target=_open, daemon=True).start()
    print(f"\n{'='*55}")
    print(f"  🐄  PashuMitra AI  →  http://localhost:{port}")
    print(f"{'='*55}\n")
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
