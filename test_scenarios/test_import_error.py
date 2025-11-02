"""
Test Scenario: Import Error Recovery
Demonstrates how MiniDevin handles missing package errors
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from modules.llm_client import LLMClient
from modules.executor import Executor
from modules.error_analyzer import ErrorAnalyzer
from modules.web_searcher import WebSearcher


async def test_import_error_flow():
    """Test the complete error → search → repair flow for ImportError"""
    
    print("="*80)
    print("TEST: Import Error Recovery Flow")
    print("="*80)
    
    code_with_error = """
import requests
import beautifulsoup4

response = requests.get('https://example.com')
print(response.status_code)
"""
    
    print("\n[Step 1] Executing code with missing imports...")
    print("Code:")
    print(code_with_error)
    
    executor = Executor()
    result = await executor.execute_code(code_with_error)
    
    print(f"\n[Step 2] Execution Result:")
    print(f"Success: {result['success']}")
    if result['error']:
        print(f"Error: {result['error'][:200]}...")
    
    if not result['success']:
        print("\n[Step 3] Analyzing error...")
        llm_client = LLMClient()
        error_analyzer = ErrorAnalyzer(llm_client)
        
        analysis = await error_analyzer.analyze_error(result['error'], code_with_error)
        
        print(f"Error Type: {analysis['error_type']}")
        print(f"Cause: {analysis['cause']}")
        print(f"Needs Search: {analysis['needs_search']}")
        print(f"Search Query: {analysis['search_query']}")
        print(f"Suggestions: {analysis['suggestions']}")
        
        if analysis['needs_search']:
            print("\n[Step 4] Searching for solution online...")
            web_searcher = WebSearcher()
            
            search_result = await web_searcher.search(analysis['search_query'])
            
            print(f"Search Success: {search_result['success']}")
            print(f"Results Found: {len(search_result['results'])}")
            
            if search_result['results']:
                print("\nTop Results:")
                for idx, res in enumerate(search_result['results'][:3], 1):
                    print(f"  {idx}. {res['title']}")
                    print(f"     {res['url']}")
            
            formatted = web_searcher.format_results_for_llm(search_result)
            print(f"\n[Step 5] Formatted results for LLM ({len(formatted)} chars)")
            
            print("\n[Step 6] Generating repair prompt...")
            repair_prompt = error_analyzer.generate_repair_prompt(analysis, formatted)
            print(f"Repair prompt generated ({len(repair_prompt)} chars)")
            
            print("\n" + "="*80)
            print("TEST COMPLETE: Error → Search → Repair flow demonstrated")
            print("="*80)
            
            await web_searcher.close()
        
        await llm_client.close()


if __name__ == "__main__":
    asyncio.run(test_import_error_flow())
