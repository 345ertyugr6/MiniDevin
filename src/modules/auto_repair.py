"""
Auto-Repair Loop Module
Orchestrates the error → search → repair → retry cycle
"""

import asyncio
from typing import Dict, Any, Optional
from .llm_client import LLMClient
from .planner import Planner, Coder
from .executor import Executor
from .error_analyzer import ErrorAnalyzer
from .web_searcher import WebSearcher
from .knowledge_cache import KnowledgeCache


class AutoRepairLoop:
    def __init__(self, 
                 llm_client: LLMClient,
                 max_retries: int = 3,
                 cache_enabled: bool = True):
        """
        Initialize auto-repair loop
        
        Args:
            llm_client: LLM client instance
            max_retries: Maximum number of repair attempts
            cache_enabled: Whether to use knowledge cache
        """
        self.llm_client = llm_client
        self.planner = Planner(llm_client)
        self.coder = Coder(llm_client)
        self.executor = Executor()
        self.error_analyzer = ErrorAnalyzer(llm_client)
        self.web_searcher = WebSearcher()
        self.knowledge_cache = KnowledgeCache() if cache_enabled else None
        self.max_retries = max_retries
        self.repair_history = []
    
    async def execute_with_repair(self, step: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a step with automatic error repair
        
        Args:
            step: Step dictionary from planner
            context: Additional context
            
        Returns:
            Final execution result
        """
        attempt = 0
        code = None
        last_error = None
        repair_log = []
        
        while attempt < self.max_retries:
            attempt += 1
            repair_log.append(f"Attempt {attempt}/{self.max_retries}")
            
            if attempt == 1:
                code = await self.coder.generate_code(step, context)
                repair_log.append(f"Generated initial code ({len(code)} chars)")
            else:
                repair_context = {
                    "previous_error": last_error,
                    "search_results": context.get("search_results") if context else None
                }
                code = await self.coder.generate_code(step, repair_context)
                repair_log.append(f"Generated repaired code ({len(code)} chars)")
            
            result = await self.executor.execute_code(code)
            
            if result["success"]:
                repair_log.append("✓ Execution successful")
                result["repair_log"] = repair_log
                result["attempts"] = attempt
                
                if self.knowledge_cache:
                    await self.knowledge_cache.store_success(step, code, result)
                
                self.repair_history.append({
                    "step": step,
                    "attempts": attempt,
                    "success": True,
                    "final_code": code,
                    "log": repair_log
                })
                
                return result
            
            last_error = result["error"]
            repair_log.append(f"✗ Error: {last_error[:100]}...")
            
            analysis = await self.error_analyzer.analyze_error(last_error, code)
            repair_log.append(f"Error type: {analysis['error_type']}")
            
            if analysis["needs_search"]:
                repair_log.append(f"Searching: {analysis['search_query']}")
                
                cached_solution = None
                if self.knowledge_cache:
                    cached_solution = await self.knowledge_cache.get_solution(analysis['search_query'])
                
                if cached_solution:
                    repair_log.append("✓ Found cached solution")
                    if not context:
                        context = {}
                    context["search_results"] = cached_solution
                else:
                    search_result = await self.web_searcher.search(analysis['search_query'])
                    
                    if search_result["success"]:
                        formatted_results = self.web_searcher.format_results_for_llm(search_result)
                        repair_log.append(f"✓ Found {len(search_result['results'])} results")
                        
                        if not context:
                            context = {}
                        context["search_results"] = formatted_results
                        
                        if self.knowledge_cache:
                            await self.knowledge_cache.store_search(analysis['search_query'], formatted_results)
                    else:
                        repair_log.append("✗ Search failed")
            
            await asyncio.sleep(0.5)
        
        repair_log.append(f"✗ Failed after {self.max_retries} attempts")
        
        final_result = {
            "success": False,
            "output": "",
            "error": last_error,
            "code": code,
            "repair_log": repair_log,
            "attempts": self.max_retries
        }
        
        self.repair_history.append({
            "step": step,
            "attempts": self.max_retries,
            "success": False,
            "final_code": code,
            "log": repair_log
        })
        
        return final_result
    
    async def execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a complete plan with auto-repair for each step
        
        Args:
            plan: Plan dictionary from planner
            
        Returns:
            Execution summary
        """
        results = []
        context = {}
        
        for idx, step in enumerate(plan["steps"]):
            print(f"\n{'='*60}")
            print(f"Executing Step {idx + 1}/{len(plan['steps'])}: {step['description']}")
            print(f"{'='*60}")
            
            result = await self.execute_with_repair(step, context)
            results.append(result)
            
            if result["success"]:
                print(f"✓ Step completed in {result['attempts']} attempt(s)")
                if result.get("output"):
                    print(f"Output: {result['output'][:200]}")
            else:
                print(f"✗ Step failed after {result['attempts']} attempts")
                print(f"Final error: {result['error'][:200]}")
                
                user_decision = input("\nContinue to next step? (y/n): ").strip().lower()
                if user_decision != 'y':
                    print("Stopping execution.")
                    break
        
        summary = {
            "total_steps": len(plan["steps"]),
            "completed_steps": sum(1 for r in results if r["success"]),
            "failed_steps": sum(1 for r in results if not r["success"]),
            "results": results
        }
        
        return summary
    
    async def close(self):
        """Close all resources"""
        await self.llm_client.close()
        await self.web_searcher.close()
        if self.knowledge_cache:
            await self.knowledge_cache.close()
    
    def get_repair_history(self) -> list:
        """Get repair history"""
        return self.repair_history
