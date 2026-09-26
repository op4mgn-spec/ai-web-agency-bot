"""
test_auto_discovery.py - Verify dynamic model discovery logic
"""

import os
import sys
import requests
import db

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

CACHED_WORKING_MODEL = None

def get_working_models(key):
    global CACHED_WORKING_MODEL
    if CACHED_WORKING_MODEL:
        return [CACHED_WORKING_MODEL]
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        r = requests.get(url, timeout=5)
        data = r.json()
        if "models" in data:
            valid_models = []
            for m in data["models"]:
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    valid_models.append(name)
            if valid_models:
                print(f"✅ Discovered valid models for key: {valid_models}")
                return valid_models
        elif "error" in data:
            print(f"❌ ListModels API Error: {data['error']}")
    except Exception as e:
        print(f"❌ Exception in ListModels: {e}")
    
    return ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro']

def test_discovery():
    db.init_db()
    key = os.getenv("GEMINI_API_KEY") or db.get_setting("GEMINI_API_KEY")
    print(f"Testing with Key: {key[:8]}... if present")
    if key:
        models = get_working_models(key)
        print(f"Models to use: {models}")
    else:
        print("No key in DB/ENV yet.")

if __name__ == "__main__":
    test_discovery()
