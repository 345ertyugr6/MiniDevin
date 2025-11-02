"""
Prompt Interface Module
Handles user input and interprets task intentions
"""

import asyncio
from typing import Dict, Any


class PromptInterface:
    def __init__(self):
        self.history = []
    
    async def parse_user_input(self, user_input: str) -> Dict[str, Any]:
        """
        Parse user input and extract task intention
        
        Args:
            user_input: Raw user input string
            
        Returns:
            Dictionary containing parsed task information
        """
        task = {
            "raw_input": user_input,
            "task_type": self._identify_task_type(user_input),
            "requirements": self._extract_requirements(user_input),
            "context": self._build_context()
        }
        
        self.history.append(task)
        return task
    
    def _identify_task_type(self, user_input: str) -> str:
        """Identify the type of task from user input"""
        user_input_lower = user_input.lower()
        
        if any(keyword in user_input_lower for keyword in ["create", "build", "make", "develop"]):
            return "creation"
        elif any(keyword in user_input_lower for keyword in ["fix", "debug", "solve", "repair"]):
            return "debugging"
        elif any(keyword in user_input_lower for keyword in ["refactor", "improve", "optimize"]):
            return "refactoring"
        elif any(keyword in user_input_lower for keyword in ["explain", "analyze", "understand"]):
            return "analysis"
        else:
            return "general"
    
    def _extract_requirements(self, user_input: str) -> Dict[str, Any]:
        """Extract specific requirements from user input"""
        requirements = {
            "description": user_input,
            "keywords": self._extract_keywords(user_input),
            "constraints": []
        }
        return requirements
    
    def _extract_keywords(self, text: str) -> list:
        """Extract important keywords from text"""
        common_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for"}
        words = text.lower().split()
        keywords = [w for w in words if w not in common_words and len(w) > 3]
        return keywords[:10]
    
    def _build_context(self) -> Dict[str, Any]:
        """Build context from conversation history"""
        return {
            "previous_tasks": len(self.history),
            "session_info": "active"
        }
    
    def get_history(self) -> list:
        """Get conversation history"""
        return self.history
