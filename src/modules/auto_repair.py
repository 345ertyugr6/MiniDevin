"""
Auto-Repair Loop Module
Orchestrates the error → search → repair → retry cycle
"""

import asyncio
import logging
from typing import Dict, Any, Set
from .llm_client import LLMClient
from .planner import Planner, Coder
from .executor import Executor
from .error_analyzer import ErrorAnalyzer
from .web_searcher import WebSearcher
from .knowledge_cache import KnowledgeCache


LOGGER = logging.getLogger(__name__)


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
        self.installed_packages: Set[str] = set()
    
    async def execute_with_repair(self, step: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a step with automatic error repair
        
        Args:
            step: Step dictionary from planner
            context: Additional context
            
        Returns:
            Final execution result
        """
        if context is None:
            context = {}

        LOGGER.debug("Starting auto-repair loop for step: %s", step.get("description", "<unknown>"))

        attempt = 0
        code = None
        last_error = None
        repair_log = []

        while attempt < self.max_retries:
            attempt += 1
            LOGGER.debug("Step '%s' attempt %d/%d", step.get("description", "<unknown>"), attempt, self.max_retries)
            repair_log.append(f"Attempt {attempt}/{self.max_retries}")

            if attempt == 1:
                code = await self.coder.generate_code(step, context)
                LOGGER.debug("Generated initial code snippet (%d chars)", len(code))
                repair_log.append(f"Generated initial code ({len(code)} chars)")
            else:
                repair_context = {
                    "previous_error": last_error,
                    "search_results": context.get("search_results") if context else None
                }
                if context and context.get("installed_packages"):
                    repair_context["installed_packages"] = context["installed_packages"]
                code = await self.coder.generate_code(step, repair_context)
                LOGGER.debug("Generated repair code snippet (%d chars)", len(code))
                repair_log.append(f"Generated repaired code ({len(code)} chars)")

            result = await self.executor.execute_code(code)
            LOGGER.debug("Execution result success=%s", result["success"])

            if result["success"]:
                repair_log.append("✓ Execution successful")
                result["repair_log"] = repair_log
                result["attempts"] = attempt

                if self.knowledge_cache:
                    await self.knowledge_cache.store_success(step, code, result)
                    LOGGER.debug("Stored successful result in knowledge cache for step '%s'", step.get("description"))

                self.repair_history.append({
                    "step": step,
                    "attempts": attempt,
                    "success": True,
                    "final_code": code,
                    "log": repair_log
                })
                
                return result
            
            last_error = result["error"]
            error_summary = ((last_error or "").strip().split("\n") or [""])[-1]
            LOGGER.debug(
                "Attempt %d for step '%s' failed with error: %s",
                attempt,
                step.get("description"),
                error_summary,
            )
            repair_log.append(f"✗ Error: {last_error[:100]}...")

            analysis = await self.error_analyzer.analyze_error(last_error, code)
            LOGGER.debug(
                "Error analysis for step '%s': type=%s needs_search=%s",
                step.get("description"),
                analysis["error_type"],
                analysis["needs_search"],
            )
            repair_log.append(f"Error type: {analysis['error_type']}")

            if analysis["error_type"] == "ImportError":
                missing_module = analysis.get("missing_module") or analysis.get("search_query")
                normalized_name = self._normalize_package_name(missing_module) if missing_module else None

                if normalized_name and normalized_name not in self.installed_packages:
                    repair_log.append(f"Attempting to install missing package: {normalized_name}")
                    LOGGER.debug("Installing missing package '%s' for step '%s'", normalized_name, step.get("description"))
                    install_result = await self.executor.execute_code(f"!pip install {normalized_name}")

                    if install_result["success"]:
                        repair_log.append("✓ Package installation succeeded")
                        if install_result.get("output"):
                            repair_log.append(install_result["output"][:200])
                        self.installed_packages.add(normalized_name)
                        context.setdefault("installed_packages", [])
                        if normalized_name not in context["installed_packages"]:
                            context["installed_packages"].append(normalized_name)
                        analysis["needs_search"] = False
                        LOGGER.debug("Package '%s' installed successfully", normalized_name)
                    else:
                        error_msg = install_result.get("error") or install_result.get("output") or "Unknown installation error"
                        repair_log.append(f"✗ Installation failed: {error_msg[:200]}")
                        analysis["needs_search"] = True
                        LOGGER.debug("Package installation failed for '%s': %s", normalized_name, error_msg.strip().split("\n")[-1])

            if analysis["needs_search"]:
                repair_log.append(f"Searching: {analysis['search_query']}")
                LOGGER.debug("Initiating search with query '%s'", analysis["search_query"])

                cached_solution = None
                if self.knowledge_cache:
                    cached_solution = await self.knowledge_cache.get_solution(analysis['search_query'])

                if cached_solution:
                    repair_log.append("✓ Found cached solution")
                    if not context:
                        context = {}
                    context["search_results"] = cached_solution
                    LOGGER.debug("Using cached search results for query '%s'", analysis["search_query"])
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
                        LOGGER.debug(
                            "Search successful for query '%s' with %d results",
                            analysis["search_query"],
                            len(search_result["results"]),
                        )
                    else:
                        repair_log.append("✗ Search failed")
                        LOGGER.debug("Search failed for query '%s'", analysis["search_query"])

            await asyncio.sleep(0.5)

        repair_log.append(f"✗ Failed after {self.max_retries} attempts")
        LOGGER.debug("Auto-repair loop exhausted retries for step '%s'", step.get("description"))

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
        LOGGER.debug("Starting plan execution with %d steps", len(plan.get("steps", [])))

        results = []
        context = {}

        for idx, step in enumerate(plan["steps"]):
            LOGGER.debug("Beginning execution of step %d: %s", idx + 1, step.get("description"))
            print(f"\n{'='*60}")
            print(f"Executing Step {idx + 1}/{len(plan['steps'])}: {step['description']}")
            print(f"{'='*60}")

            result = await self.execute_with_repair(step, context)
            results.append(result)

            if result["success"]:
                LOGGER.debug("Step %d completed successfully after %d attempt(s)", idx + 1, result.get("attempts", 1))
                print(f"✓ Step completed in {result.get('attempts', 1)} attempt(s)")
                if result.get("output"):
                    LOGGER.debug("Step %d truncated output: %s", idx + 1, result["output"][:120].replace("\n", " "))
                    print(f"Output: {result['output'][:200]}")
            else:
                LOGGER.debug(
                    "Step %d failed after %d attempts with error: %s",
                    idx + 1,
                    result.get("attempts", self.max_retries),
                    ((result.get("error") or "").strip().split("\n") or [""])[-1],
                )
                print(f"✗ Step failed after {result.get('attempts', self.max_retries)} attempts")
                print(f"Final error: {(result.get('error') or '')[:200]}")

                print("Auto-continue enabled: proceeding to next step.")

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

    @staticmethod
    def _normalize_package_name(module_name: str) -> str:
        """Map common module names to their pip-installable package names."""

        if not module_name:
            return module_name

        cleaned = module_name.strip().strip("'\"")
        base_name = cleaned.split('.')[0]
        mapping = {
            "cv2": "opencv-python",
            "sklearn": "scikit-learn",
            "Crypto": "pycryptodome",
            "PIL": "Pillow",
            "yaml": "PyYAML",
            "bs4": "beautifulsoup4",
        }

        normalized = mapping.get(cleaned, cleaned)
        normalized = mapping.get(base_name, normalized)
        return normalized
