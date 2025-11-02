"""
Planner & Coder Module
Breaks down tasks into steps and generates code
"""

import asyncio
import json
from typing import Dict, Any, List
from .llm_client import LLMClient


class Planner:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.plans = []
    
    async def create_plan(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a step-by-step plan for the given task
        
        Args:
            task: Task dictionary from PromptInterface
            
        Returns:
            Plan dictionary with steps
        """
        prompt = self._build_planning_prompt(task)
        response = await self.llm_client.generate(prompt)
        
        plan = {
            "task": task,
            "steps": self._parse_steps(response),
            "status": "pending"
        }
        
        self.plans.append(plan)
        return plan
    
    def _build_planning_prompt(self, task: Dict[str, Any]) -> str:
        """Build prompt for planning"""
        return f"""You are a software development planner. Break down the following task into clear, executable steps.

Task: {task['raw_input']}
Task Type: {task['task_type']}

Provide a numbered list of steps needed to complete this task. Each step should be specific and actionable.
Format your response as a numbered list (1., 2., 3., etc.)."""
    
    def _parse_steps(self, response: str) -> List[Dict[str, Any]]:
        """Parse steps from LLM response"""
        steps = []
        lines = response.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-') or line.startswith('*')):
                step_text = line.lstrip('0123456789.-*) ').strip()
                if step_text:
                    steps.append({
                        "description": step_text,
                        "status": "pending",
                        "code": None,
                        "result": None
                    })
        
        return steps if steps else [{"description": response, "status": "pending", "code": None, "result": None}]


class Coder:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
    
    async def generate_code(self, step: Dict[str, Any], context: Dict[str, Any] = None) -> str:
        """
        Generate code for a specific step
        
        Args:
            step: Step dictionary from plan
            context: Additional context (previous steps, errors, etc.)
            
        Returns:
            Generated code as string
        """
        prompt = self._build_coding_prompt(step, context)
        code = await self.llm_client.generate(prompt)
        
        code = self._extract_code_block(code)
        return code
    
    def _build_coding_prompt(self, step: Dict[str, Any], context: Dict[str, Any] = None) -> str:
        """Build prompt for code generation"""
        base_prompt = f"""You are an expert Python programmer. Generate clean, working Python code for the following task.

Task: {step['description']}

Requirements:
- Write complete, executable Python code
- Include necessary imports
- Add minimal error handling
- Keep it simple and efficient
- Output ONLY the code, no explanations"""

        if context and context.get("previous_error"):
            base_prompt += f"\n\nPrevious attempt failed with error:\n{context['previous_error']}\n\nFix the error and provide corrected code."
        
        if context and context.get("search_results"):
            base_prompt += f"\n\nRelevant information from search:\n{context['search_results']}\n\nUse this information to improve your solution."
        
        return base_prompt
    
    def _extract_code_block(self, response: str) -> str:
        """Extract code from markdown code blocks or raw response"""
        lines = response.split('\n')
        code_lines = []
        in_code_block = False
        
        for line in lines:
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                continue
            if in_code_block or (not any(line.strip().startswith(x) for x in ['#', 'Here', 'This', 'The', 'Note']) and line.strip()):
                code_lines.append(line)
        
        code = '\n'.join(code_lines).strip()
        
        if not code or len(code) < 10:
            code = response.strip()
        
        return code
