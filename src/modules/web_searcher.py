"""
Web Searcher Module
Performs online searches using DuckDuckGo API
"""

import asyncio
import aiohttp
import json
from typing import Dict, Any, List, Optional
from urllib.parse import quote_plus


class WebSearcher:
    def __init__(self):
        """Initialize web searcher"""
        self.session = None
        self.search_history = []
    
    async def _ensure_session(self):
        """Ensure aiohttp session exists"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Search the web using DuckDuckGo
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            Dictionary containing search results
        """
        await self._ensure_session()
        
        result = {
            "query": query,
            "results": [],
            "success": False,
            "error": None
        }
        
        try:
            results = await self._search_duckduckgo(query, max_results)
            result["results"] = results
            result["success"] = True
        except Exception as e:
            result["error"] = str(e)
            result["success"] = False
        
        self.search_history.append(result)
        return result
    
    async def _search_duckduckgo(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """
        Search using DuckDuckGo HTML interface
        
        Args:
            query: Search query
            max_results: Maximum results
            
        Returns:
            List of search result dictionaries
        """
        encoded_query = quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            async with self.session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    html = await response.text()
                    return self._parse_duckduckgo_html(html, max_results)
                else:
                    return []
        except Exception as e:
            return []
    
    def _parse_duckduckgo_html(self, html: str, max_results: int) -> List[Dict[str, str]]:
        """
        Parse DuckDuckGo HTML results
        
        Args:
            html: HTML content
            max_results: Maximum results to extract
            
        Returns:
            List of result dictionaries
        """
        results = []
        
        import re
        
        result_pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
        snippet_pattern = r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>'
        
        matches = re.finditer(result_pattern, html, re.DOTALL)
        snippets = re.finditer(snippet_pattern, html, re.DOTALL)
        
        snippet_list = [self._clean_html(m.group(1)) for m in snippets]
        
        for idx, match in enumerate(matches):
            if idx >= max_results:
                break
            
            url = match.group(1)
            title = self._clean_html(match.group(2))
            snippet = snippet_list[idx] if idx < len(snippet_list) else ""
            
            if url and title:
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet
                })
        
        return results
    
    def _clean_html(self, text: str) -> str:
        """Remove HTML tags and clean text"""
        import re
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    async def search_stackoverflow(self, query: str) -> Dict[str, Any]:
        """
        Search Stack Overflow specifically
        
        Args:
            query: Search query
            
        Returns:
            Search results dictionary
        """
        so_query = f"site:stackoverflow.com {query}"
        return await self.search(so_query, max_results=3)
    
    async def search_documentation(self, package: str, topic: str = "") -> Dict[str, Any]:
        """
        Search for package documentation
        
        Args:
            package: Package name
            topic: Optional specific topic
            
        Returns:
            Search results dictionary
        """
        query = f"{package} python documentation {topic}".strip()
        return await self.search(query, max_results=3)
    
    def format_results_for_llm(self, search_result: Dict[str, Any]) -> str:
        """
        Format search results for LLM context
        
        Args:
            search_result: Search result dictionary
            
        Returns:
            Formatted string for LLM
        """
        if not search_result["success"] or not search_result["results"]:
            return "No relevant search results found."
        
        formatted = f"Search results for: {search_result['query']}\n\n"
        
        for idx, result in enumerate(search_result["results"], 1):
            formatted += f"{idx}. {result['title']}\n"
            if result.get('snippet'):
                formatted += f"   {result['snippet']}\n"
            formatted += f"   URL: {result['url']}\n\n"
        
        return formatted
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get search history"""
        return self.search_history
