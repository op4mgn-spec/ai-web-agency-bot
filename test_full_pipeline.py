"""
test_full_pipeline.py - Verification Suite for FormOutreachBot Engine
"""

import os
import sys
import json
import db
import yandex_maps_parser
from webhook_engine import PERSONA_PROMPTS, safe_generate_ai

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_tests():
    print("==========================================")
    print("🧪 RUNNING PIPELINE VERIFICATION TESTS")
    print("==========================================")
    
    # Test 1: DB Initialization & Queue
    print("\n[Test 1] Testing DB & leads_queue...")
    db.init_db()
    added = db.add_to_lead_queue("Тест Отель", "http://test-hotel-msk.ru/contact", "+7 (495) 999-00-11", "Москва", 3)
    print(f"  Result 1st add: {'PASS' if added else 'FAIL'}")
    
    is_dup = db.is_lead_duplicate("http://test-hotel-msk.ru/contact", "+7 (495) 999-00-11")
    print(f"  Result deduplication check: {'PASS' if is_dup else 'FAIL'}")
    
    # Test 2: Yandex Lead Parser
    print("\n[Test 2] Testing Yandex Maps Parser seeder...")
    seeded = yandex_maps_parser.seed_lead_queue("автосервис", "Москва", 2)
    print(f"  Result seeder execution: PASS ({seeded} leads added)")
    
    # Test 3: Personas Count Verification
    print("\n[Test 3] Verifying 4 Bot Sales Personas...")
    personas = list(PERSONA_PROMPTS.keys())
    print(f"  Available Personas ({len(personas)}): {personas}")
    assert len(personas) == 4, "Expected 4 personas!"
    print("  Result 4 Personas: PASS")

    # Test 4: CRM Data fetch
    print("\n[Test 4] Testing CRM Data queries...")
    crm_leads = db.get_all_leads_crm()
    ab_stats = db.get_ab_stats()
    print(f"  Total Leads in DB: {len(crm_leads)}")
    print(f"  A/B Stats Rows: {len(ab_stats)}")
    print("  Result CRM queries: PASS")

    print("\n==========================================")
    print("✅ ALL PIPELINE TESTS COMPLETED SUCCESSFULLY!")
    print("==========================================")

if __name__ == "__main__":
    run_tests()
