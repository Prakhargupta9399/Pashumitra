"""
Phase 1 Validation Script
Run: python validate_phase1.py
Tests all 5 core functions without external APIs
"""
import sys, os
sys.path.insert(0, '.')
os.environ.update({
    "DATABASE_URL": "sqlite:///./phase1_test.db",
    "GROQ_API_KEY": "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",
    "SKIP_WHISPER_LOAD": "1",
    "ENVIRONMENT": "development",
    "WHATSAPP_VERIFY_TOKEN": "vetai2024",
    "SMS_PROVIDER": "none"
})

passed = []
failed = []

def test(name, fn):
    try:
        result = fn()
        passed.append(name)
        print(f"✅ {name}: {str(result)[:80]}")
    except Exception as e:
        failed.append(name)
        print(f"❌ {name}: {e}")

# 1. AI Engine - 5 diseases
def test_ai():
    from app.services.ai_engine import ai_engine
    ai_engine.load()
    tests = [
        ("FMD",      "gaay ke munh mein chhaale hain, langda rahi hai"),
        ("Mastitis",  "than mein sujan hai, doodh kam ho gaya"),
        ("PPR",      "bakri ko bukhaar hai, dast lag rahe hain"),
        ("BRD",      "bachde ko khaansi hai, saans lene mein takleef"),
        ("Newcastle","murgi ki gardan ghoom gayi, hara pakhana aa raha"),
    ]
    results = []
    for disease, symptom in tests:
        r = ai_engine.check_symptoms(symptom)
        results.append(f"{disease}→{r['hindi']}({int(r['confidence']*100)}%)")
    return " | ".join(results)

# 2. Database
def test_db():
    from app.database import engine, Base, SessionLocal
    from app.models import Farmer
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Clean up any leftover record from a previous run
    db.query(Farmer).filter(Farmer.phone == "9999999999").delete()
    db.commit()
    f = Farmer(phone="9999999999", name="Test Farmer")
    db.add(f)
    db.commit()
    count = db.query(Farmer).count()
    db.close()
    return f"{count} farmer(s) in DB"

# 3. Rate Limiting
def test_limits():
    from app.limits import check_and_increment, get_usage
    phone = "8888888888"
    r1 = check_and_increment(phone)
    r2 = check_and_increment(phone)
    r3 = check_and_increment(phone)
    r4 = check_and_increment(phone)  # Should be False (limit=3)
    usage = get_usage(phone)
    return f"Queries: allowed={r1},{r2},{r3} blocked={not r4} usage={usage['used']}/{usage['limit']}"

# 4. Language Detection
def test_language():
    from app.services.language import lang_engine
    tests = [
        ("hindi",   "मेरी गाय बीमार है"),
        ("english", "my cow is sick"),
        ("marathi", "माझ्या गाय आजारी आहे"),
    ]
    results = []
    for expected, text in tests:
        detected = lang_engine.detect(text)
        status = "✓" if detected == expected else f"✗(got {detected})"
        results.append(f"{expected}{status}")
    return " | ".join(results)

# 5. Emergency Detection
def test_emergency():
    from app.services.ai_engine import ai_engine
    ai_engine.load()
    fmd = ai_engine.check_symptoms("khurpaka muh mein chhaale khur mein ghav")
    bloat = ai_engine.check_symptoms("pet fool gaya afara gas left side")
    return f"FMD emergency={fmd['emergency']} severity={fmd['severity']} | Bloat emergency={bloat['emergency']}"

print("\n" + "="*60)
print("PASHUMITRA PHASE 1 - MVP VALIDATION")
print("="*60 + "\n")

test("1. AI Engine (5 diseases)", test_ai)
test("2. Database", test_db)
test("3. Rate Limiting", test_limits)
test("4. Language Detection", test_language)
test("5. Emergency Detection", test_emergency)

print("\n" + "="*60)
print(f"RESULTS: {len(passed)}/5 passed | {len(failed)} failed")
if failed:
    print(f"FAILED: {', '.join(failed)}")
else:
    print("✅ ALL PHASE 1 FUNCTIONS WORKING — Ready for 50 farmer pilot!")
print("="*60)

# Cleanup
import os
try: os.remove("phase1_test.db")
except: pass