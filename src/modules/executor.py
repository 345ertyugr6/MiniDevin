"""Executor Module
Executes code in a sandboxed environment and captures output/errors."""

import asyncio
import tempfile
import os
import sys
from typing import Dict, Any, Optional, List, Tuple
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

        shell_commands, python_code = self._split_shell_and_python(code)
        combined_output: List[str] = []
        total_time = 0.0

        # Execute shell commands generated via notebook-style syntax (e.g. !pip install ...)
        for command in shell_commands:
            command_result = await self._execute_shell_command(command)
            total_time += command_result["duration"]

            combined_output.append(f"$ {command}")
            if command_result["stdout"]:
                combined_output.append(command_result["stdout"].rstrip())
            if command_result["stderr"]:
                combined_output.append(command_result["stderr"].rstrip())

            if not command_result["success"]:
                result["output"] = "\n".join(part for part in combined_output if part)
                error_msg = command_result["stderr"].strip() if command_result["stderr"] else ""
                if not error_msg:
                    error_msg = f"Command '{command}' failed with exit code {command_result['returncode']}"
                result["error"] = error_msg
                result["execution_time"] = total_time
                self.execution_history.append(result)
                return result

        # If there is no Python code to run, the result depends solely on shell command execution
        if not python_code.strip():
            result["success"] = True
            result["output"] = "\n".join(part for part in combined_output if part)
            result["execution_time"] = total_time
            self.execution_history.append(result)
            return result

        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(python_code)
                temp_file = f.name

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
                python_time = end_time - start_time
                total_time += python_time

                stdout_text = stdout.decode('utf-8', errors='replace')
                if stdout_text:
                    combined_output.append(stdout_text.rstrip())

                if stderr:
                    error_text = stderr.decode('utf-8', errors='replace')
                    combined_output.append(error_text.rstrip())
                    result["error"] = error_text
                    result["success"] = False
                else:
                    result["success"] = True

            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                total_time += asyncio.get_event_loop().time() - start_time
                result["error"] = f"Execution timed out after {self.timeout} seconds"
                result["success"] = False

        except Exception as e:
            result["error"] = f"Execution failed: {str(e)}\n{traceback.format_exc()}"
            result["success"] = False
        finally:
            if temp_file:
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass

        result["output"] = "\n".join(part for part in combined_output if part)
        result["execution_time"] = total_time
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

    def _split_shell_and_python(self, code: str) -> Tuple[List[str], str]:
        """Split notebook-style shell commands from Python code."""

        shell_commands: List[str] = []
        python_lines: List[str] = []

        for line in code.splitlines():
            stripped = line.lstrip()
            if stripped.startswith('!'):
                shell_commands.append(stripped[1:].strip())
            else:
                python_lines.append(line)

        python_code = "\n".join(python_lines)
        return shell_commands, python_code

    async def _execute_shell_command(self, command: str) -> Dict[str, Any]:
        """Execute a shell command asynchronously and capture its result."""

        start_time = asyncio.get_event_loop().time()
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout
            )
            duration = asyncio.get_event_loop().time() - start_time
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            duration = asyncio.get_event_loop().time() - start_time
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command timed out after {self.timeout} seconds",
                "returncode": None,
                "duration": duration
            }

        return {
            "success": process.returncode == 0,
            "stdout": stdout.decode('utf-8', errors='replace'),
            "stderr": stderr.decode('utf-8', errors='replace'),
            "returncode": process.returncode,
            "duration": duration
        }
