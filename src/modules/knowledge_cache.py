"""
Knowledge Cache Module
Stores and retrieves search results and solutions locally
"""

import asyncio
import json
import sqlite3
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime
import os


class KnowledgeCache:
    def __init__(self, db_path: str = "data/knowledge_cache.db"):
        """
        Initialize knowledge cache
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = None
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_hash TEXT UNIQUE NOT NULL,
                query TEXT NOT NULL,
                results TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                hit_count INTEGER DEFAULT 0
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS solution_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                step_hash TEXT UNIQUE NOT NULL,
                step_description TEXT NOT NULL,
                code TEXT NOT NULL,
                success INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_hash ON search_cache(query_hash)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_step_hash ON solution_cache(step_hash)
        """)
        
        self.conn.commit()
    
    def _hash_text(self, text: str) -> str:
        """Generate hash for text"""
        return hashlib.md5(text.lower().strip().encode()).hexdigest()
    
    async def store_search(self, query: str, results: str) -> bool:
        """
        Store search results in cache
        
        Args:
            query: Search query
            results: Search results (formatted string)
            
        Returns:
            Success boolean
        """
        try:
            query_hash = self._hash_text(query)
            timestamp = datetime.now().isoformat()
            
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO search_cache (query_hash, query, results, timestamp, hit_count)
                VALUES (?, ?, ?, ?, COALESCE((SELECT hit_count FROM search_cache WHERE query_hash = ?), 0))
            """, (query_hash, query, results, timestamp, query_hash))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error storing search: {e}")
            return False
    
    async def get_solution(self, query: str) -> Optional[str]:
        """
        Get cached solution for query
        
        Args:
            query: Search query
            
        Returns:
            Cached results or None
        """
        try:
            query_hash = self._hash_text(query)
            
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT results FROM search_cache WHERE query_hash = ?
            """, (query_hash,))
            
            row = cursor.fetchone()
            
            if row:
                cursor.execute("""
                    UPDATE search_cache SET hit_count = hit_count + 1 WHERE query_hash = ?
                """, (query_hash,))
                self.conn.commit()
                
                return row[0]
            
            return None
        except Exception as e:
            print(f"Error getting solution: {e}")
            return None
    
    async def store_success(self, step: Dict[str, Any], code: str, result: Dict[str, Any]) -> bool:
        """
        Store successful code execution
        
        Args:
            step: Step dictionary
            code: Successful code
            result: Execution result
            
        Returns:
            Success boolean
        """
        try:
            step_hash = self._hash_text(step['description'])
            timestamp = datetime.now().isoformat()
            
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO solution_cache (step_hash, step_description, code, success, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (step_hash, step['description'], code, 1, timestamp))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error storing success: {e}")
            return False
    
    async def get_cached_code(self, step_description: str) -> Optional[str]:
        """
        Get cached code for similar step
        
        Args:
            step_description: Step description
            
        Returns:
            Cached code or None
        """
        try:
            step_hash = self._hash_text(step_description)
            
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT code FROM solution_cache WHERE step_hash = ? AND success = 1
                ORDER BY timestamp DESC LIMIT 1
            """, (step_hash,))
            
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            print(f"Error getting cached code: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            cursor = self.conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM search_cache")
            search_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM solution_cache")
            solution_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(hit_count) FROM search_cache")
            total_hits = cursor.fetchone()[0] or 0
            
            return {
                "search_entries": search_count,
                "solution_entries": solution_count,
                "cache_hits": total_hits
            }
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {}
    
    async def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
