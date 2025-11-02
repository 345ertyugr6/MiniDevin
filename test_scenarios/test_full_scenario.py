"""
Test Scenario: Complete Auto-Repair Loop
Demonstrates the full error → search → repair → retry cycle
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from modules.llm_client import LLMClient
from modules.auto_repair import AutoRepairLoop


async def test_full_auto_repair():
    """Test the complete auto-repair loop with a realistic scenario"""
    
    print("="*80)
    print("TEST: Complete Auto-Repair Loop")
    print("="*80)
    
    print("\nScenario: Create a simple HTTP request script")
    print("Expected: Code will fail with ImportError, search online, and repair")
    
    step = {
        "description": "Write a Python script that makes an HTTP GET request to httpbin.org and prints the response",
        "status": "pending",
        "code": None,
        "result": None
    }
    
    print("\n[Starting Auto-Repair Loop]")
    print(f"Step: {step['description']}")
    print(f"Max Retries: 3")
    
    llm_client = LLMClient(
        base_url="http://localhost:11434",
        model="phi3:mini",
        api_type="ollama"
    )
    
    auto_repair = AutoRepairLoop(llm_client, max_retries=3, cache_enabled=True)
    
    result = await auto_repair.execute_with_repair(step)
    
    print("\n" + "="*80)
    print("FINAL RESULT")
    print("="*80)
    print(f"Success: {result['success']}")
    print(f"Attempts: {result['attempts']}")
    print(f"\nRepair Log:")
    for log_entry in result['repair_log']:
        print(f"  {log_entry}")
    
    if result['success']:
        print(f"\n✓ Final Code ({len(result['code'])} chars):")
        print(result['code'])
        print(f"\nOutput:")
        print(result['output'])
    else:
        print(f"\n✗ Final Error:")
        print(result['error'][:500])
    
    print("\n" + "="*80)
    print("TEST COMPLETE: Full auto-repair loop demonstrated")
    print("="*80)
    
    cache_stats = auto_repair.knowledge_cache.get_stats()
    print(f"\nKnowledge Cache Stats:")
    print(f"  Search entries: {cache_stats.get('search_entries', 0)}")
    print(f"  Solution entries: {cache_stats.get('solution_entries', 0)}")
    print(f"  Cache hits: {cache_stats.get('cache_hits', 0)}")
    
    await auto_repair.close()


if __name__ == "__main__":
    asyncio.run(test_full_auto_repair())
