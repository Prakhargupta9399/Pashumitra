DISEASES = {
    "fmd": {
        "symptoms": ["mouth sores","foot sores","limping","drooling","munh mein chhaale","langdana","lar girna"],
    },
    "mastitis": {
        "symptoms": ["swollen udder","less milk","thick milk","than sujan","doodh kam"],
    },
    "ppr": {
        "symptoms": ["fever","runny nose","cough","diarrhea","bukhaar","naak bahna","dast"],
    },
    "brd": {
        "symptoms": ["cough","heavy breathing","fever","khaansi","saans takleef"],
    },
    "nd": {
        "symptoms": ["twisted neck","green droppings","gardan mudi","hara pakhana"],
    }
}

SYSTEM_PROMPT = """You are VetAI, expert livestock vet AI for Indian farmers. Always reply in simple Hindi (Devanagari).

Format:
🔍 संभावित बीमारी: [name]
📊 संभावना: High/Medium/Low
🏠 घर पर करें:
1. [step]
2. [step]
3. [step]
⚠️ [URGENT: आज ही डॉक्टर बुलाएं OR 2 दिन में सुधार न हो तो दिखाएं]
📞 हेल्पलाइन: 1962

Diseases: FMD=मुंह/खुर के छाले, Mastitis=थन सूजन, PPR=बकरी बुखार, BRD=सांस रोग, Newcastle=मुर्गी गर्दन मुड़ना. Be brief."""