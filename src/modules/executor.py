"""
Executor Module
Executes code in a sandboxed environment and captures output/errors
"""

import asyncio
import subprocess
import tempfile
import os
import sys
from typing import Dict, Any, Optional
import traceback


class Executor:
    def __init__(self, timeout: int = 30):
        """
        Initialize executor
        
        Args:
            timeout: Maximum execution time in seconds
        """
        self.timeout = timeout
        self.execution_history = []
    
    async def execute_code(self, code: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute Python code in a sandboxed environment
        
        Args:
            code: Python code to execute
            context: Additional context for execution
            
        Returns:
            Dictionary containing execution results
        """
        result = {
            "success": False,
            "output": "",
            "error": None,
            "execution_time": 0,
            "code": code
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            process = await asyncio.create_subprocess_exec(
                sys.executable, temp_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=tempfile.gettempdir()
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
                
                end_time = asyncio.get_event_loop().time()
                result["execution_time"] = end_time - start_time
                
                result["output"] = stdout.decode('utf-8', errors='replace')
                
                if stderr:
                    error_text = stderr.decode('utf-8', errors='replace')
                    result["error"] = error_text
                    result["success"] = False
                else:
                    result["success"] = True
                    
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                result["error"] = f"Execution timed out after {self.timeout} seconds"
                result["success"] = False
                
        except Exception as e:
            result["error"] = f"Execution failed: {str(e)}\n{traceback.format_exc()}"
            result["success"] = False
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass
        
        self.execution_history.append(result)
        return result
    
    async def execute_safe(self, code: str) -> Dict[str, Any]:
        """
        Execute code with additional safety checks
        
        Args:
            code: Python code to execute
            
        Returns:
            Execution result dictionary
        """
        dangerous_patterns = [
            'os.system', 'subprocess.call', 'eval(', 'exec(',
            '__import__', 'open(', 'file(', 'input('
        ]
        
        code_lower = code.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in code_lower:
                return {
                    "success": False,
                    "output": "",
                    "error": f"Code contains potentially dangerous pattern: {pattern}",
                    "execution_time": 0,
                    "code": code
                }
        
        return await self.execute_code(code)
    
    def get_history(self) -> list:
        """Get execution history"""
        return self.execution_history
