"""
test_gemini_key.py - Direct diagnostic for Gemini API Key and ListModels
"""

import sys
import os
import requests
import db

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def diagnose():
    print("==========================================")
    print("🔍 GEMINI API DIAGNOSTICS")
    print("==========================================")
    
    key = os.getenv("GEMINI_API_KEY") or db.get_setting("GEMINI_API_KEY")
    print(f"Key in DB / ENV: {'FOUND (' + key[:8] + '...' + key[-4:] + ')' if key else 'NOT FOUND'}")
    
    if not key:
        print("❌ Error: No key saved in DB or ENV!")
        return

    # Step 1: List models for this API key
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    print(f"\n📡 Requesting ListModels: GET {url[:60]}...")
    
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        
        if "error" in data:
            print(f"❌ ListModels API Error: {json.dumps(data['error'], ensure_ascii=False, indent=2)}")
        elif "models" in data:
            print(f"✅ Available models ({len(data['models'])} total):")
            generate_content_models = []
            for m in data['models']:
                name = m.get("name", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    clean_name = name.replace("models/", "")
                    generate_content_models.append(clean_name)
                    print(f"  - {clean_name} (supported: {methods})")
            
            print(f"\n🎯 Models supporting generateContent: {generate_content_models}")
            
            # Step 2: Test generateContent on the first supported model
            if generate_content_models:
                target_model = generate_content_models[0]
                print(f"\n🚀 Testing generateContent on model '{target_model}'...")
                gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={key}"
                payload = {"contents": [{"parts": [{"text": "Привет! Ответь коротко: ты работаешь?"}]}]}
                
                gen_r = requests.post(gen_url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
                gen_data = gen_r.json()
                
                if "candidates" in gen_data and len(gen_data["candidates"]) > 0:
                    ans = gen_data["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"✅ SUCCESS! Response: {ans.strip()}")
                else:
                    print(f"❌ generateContent failed: {gen_data}")
        else:
            print(f"❓ Unexpected response: {data}")
    except Exception as e:
        print(f"❌ Request Exception: {e}")

if __name__ == "__main__":
    diagnose()
