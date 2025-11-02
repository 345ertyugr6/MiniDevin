"""
Error Analyzer Module
Analyzes error logs and generates repair prompts
"""

import logging
import re
from typing import Dict, Any, Optional
from .llm_client import LLMClient


LOGGER = logging.getLogger(__name__)


class ErrorAnalyzer:
    def __init__(self, llm_client: LLMClient):
        """
        Initialize error analyzer
        
        Args:
            llm_client: LLM client for analysis
        """
        self.llm_client = llm_client
        self.error_patterns = self._load_error_patterns()
    
    def _load_error_patterns(self) -> Dict[str, str]:
        """Load common error patterns and their categories"""
        return {
            "ImportError": r"(ImportError|ModuleNotFoundError|No module named)",
            "SyntaxError": r"(SyntaxError|invalid syntax)",
            "NameError": r"(NameError|name .* is not defined)",
            "TypeError": r"(TypeError|takes .* positional argument)",
            "AttributeError": r"(AttributeError|has no attribute)",
            "ValueError": r"(ValueError|invalid literal)",
            "KeyError": r"(KeyError)",
            "IndexError": r"(IndexError|list index out of range)",
            "FileNotFoundError": r"(FileNotFoundError|No such file)",
            "ZeroDivisionError": r"(ZeroDivisionError|division by zero)",
        }
    
    async def analyze_error(self, error_text: str, code: str) -> Dict[str, Any]:
        """
        Analyze error and determine cause and solution
        
        Args:
            error_text: Error message/traceback
            code: Code that caused the error
            
        Returns:
            Analysis dictionary with error type, cause, and suggestions
        """
        LOGGER.debug("Analyzing error text (truncated): %s", error_text.strip()[:200])
        error_type = self._classify_error(error_text)
        LOGGER.debug("Classified error type: %s", error_type)

        analysis = {
            "error_type": error_type,
            "error_text": error_text,
            "code": code,
            "cause": None,
            "search_query": None,
            "suggestions": [],
            "needs_search": False,
            "missing_module": None
        }

        if error_type == "ImportError":
            missing_module = self._extract_missing_module(error_text)
            LOGGER.debug("Detected missing module: %s", missing_module)
            analysis["cause"] = "Missing module or package"
            analysis["missing_module"] = missing_module
            if missing_module and missing_module != "unknown_module":
                analysis["search_query"] = f"ModuleNotFoundError {missing_module}"
            else:
                analysis["search_query"] = "python ModuleNotFoundError"
            analysis["needs_search"] = missing_module in (None, "", "unknown_module")
            analysis["suggestions"] = [
                f"Install missing package: pip install {missing_module}" if missing_module else "Install the required package",
                "Check if module name is correct",
                "Search for alternative packages"
            ]
        elif error_type == "SyntaxError":
            analysis["cause"] = "Invalid Python syntax"
            analysis["needs_search"] = False
            analysis["suggestions"] = [
                "Check for missing colons, parentheses, or brackets",
                "Verify indentation is correct",
                "Check for invalid characters"
            ]
        elif error_type == "NameError":
            analysis["cause"] = "Variable or function not defined"
            analysis["needs_search"] = False
            analysis["suggestions"] = [
                "Define the variable before using it",
                "Check for typos in variable names",
                "Import required functions/classes"
            ]
        else:
            analysis["cause"] = "Runtime error"
            analysis["needs_search"] = True
            analysis["search_query"] = self._generate_search_query(error_text, error_type)
            analysis["suggestions"] = ["Search online for solution"]
            LOGGER.debug("Fallback search query generated: %s", analysis["search_query"])

        detailed_analysis = await self._get_llm_analysis(error_text, code, error_type)
        analysis["llm_analysis"] = detailed_analysis
        LOGGER.debug("Received LLM error analysis (%d chars)", len(detailed_analysis))

        return analysis
    
    def _classify_error(self, error_text: str) -> str:
        """Classify error type from error text"""
        for error_type, pattern in self.error_patterns.items():
            if re.search(pattern, error_text, re.IGNORECASE):
                return error_type
        return "UnknownError"
    
    def _extract_missing_module(self, error_text: str) -> str:
        """Extract missing module name from ImportError"""
        match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_text)
        if match:
            return match.group(1)

        match = re.search(r"ImportError: (.+)", error_text)
        if match:
            return match.group(1).strip()

        return "unknown_module"
    
    def _generate_search_query(self, error_text: str, error_type: str) -> str:
        """Generate search query from error"""
        lines = error_text.strip().split('\n')
        
        for line in reversed(lines):
            if error_type in line or any(err in line for err in ["Error", "Exception"]):
                query = line.strip()
                query = re.sub(r'File ".*?",', '', query)
                query = re.sub(r'line \d+', '', query)
                return f"python {query}"
        
        return f"python {error_type}"
    
    async def _get_llm_analysis(self, error_text: str, code: str, error_type: str) -> str:
        """Get detailed analysis from LLM"""
        prompt = f"""Analyze this Python error and provide a concise explanation of the cause and how to fix it.

Error Type: {error_type}
Error Message:
{error_text}

Code:
{code}

Provide:
1. Root cause (1 sentence)
2. How to fix it (1-2 sentences)
3. Corrected code approach (brief)"""

        analysis = await self.llm_client.generate(prompt, temperature=0.3)
        return analysis
    
    def generate_repair_prompt(self, analysis: Dict[str, Any], search_results: Optional[str] = None) -> str:
        """
        Generate prompt for code repair
        
        Args:
            analysis: Error analysis dictionary
            search_results: Optional search results to include
            
        Returns:
            Repair prompt string
        """
        prompt = f"""Fix the following Python code that has an error.

Error Type: {analysis['error_type']}
Error Message:
{analysis['error_text']}

Original Code:
{analysis['code']}

Cause: {analysis['cause']}
"""
        
        if search_results:
            prompt += f"\nRelevant information from search:\n{search_results}\n"
        
        if analysis.get('llm_analysis'):
            prompt += f"\nAnalysis:\n{analysis['llm_analysis']}\n"
        
        prompt += "\nProvide the corrected code. Output ONLY the fixed code, no explanations."
        
        return prompt
