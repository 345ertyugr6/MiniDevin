"""
Test Scenario: Syntax Error Detection and Repair
Demonstrates how MiniDevin handles Python syntax errors
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from modules.llm_client import LLMClient
from modules.executor import Executor
from modules.error_analyzer import ErrorAnalyzer


async def test_syntax_error_flow():
    """Test syntax error detection and analysis"""
    
    print("="*80)
    print("TEST: Syntax Error Detection and Analysis")
    print("="*80)
    
    code_with_syntax_error = """
def calculate_sum(a, b)
    result = a + b
    return result

print(calculate_sum(5, 3))
"""
    
    print("\n[Step 1] Executing code with syntax error...")
    print("Code:")
    print(code_with_syntax_error)
    
    executor = Executor()
    result = await executor.execute_code(code_with_syntax_error)
    
    print(f"\n[Step 2] Execution Result:")
    print(f"Success: {result['success']}")
    if result['error']:
        print(f"Error: {result['error'][:300]}...")
    
    if not result['success']:
        print("\n[Step 3] Analyzing error...")
        llm_client = LLMClient()
        error_analyzer = ErrorAnalyzer(llm_client)
        
        analysis = await error_analyzer.analyze_error(result['error'], code_with_syntax_error)
        
        print(f"Error Type: {analysis['error_type']}")
        print(f"Cause: {analysis['cause']}")
        print(f"Needs Search: {analysis['needs_search']}")
        print(f"Suggestions:")
        for suggestion in analysis['suggestions']:
            print(f"  - {suggestion}")
        
        print("\n[Step 4] Generating repair prompt...")
        repair_prompt = error_analyzer.generate_repair_prompt(analysis)
        print(f"Repair prompt generated ({len(repair_prompt)} chars)")
        print("\nRepair Prompt Preview:")
        print(repair_prompt[:400] + "...")
        
        print("\n" + "="*80)
        print("TEST COMPLETE: Syntax error detection demonstrated")
        print("="*80)
        
        await llm_client.close()


if __name__ == "__main__":
    asyncio.run(test_syntax_error_flow())
