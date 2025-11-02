"""
MiniDevin - Lightweight Autonomous Development AI
Main entry point
"""

import asyncio
import sys
import argparse
from modules.llm_client import LLMClient
from modules.prompt_interface import PromptInterface
from modules.planner import Planner
from modules.auto_repair import AutoRepairLoop


class MiniDevin:
    def __init__(self, 
                 llm_base_url: str = "http://localhost:11434",
                 llm_model: str = "phi3:mini",
                 api_type: str = "ollama",
                 max_retries: int = 3):
        """
        Initialize MiniDevin
        
        Args:
            llm_base_url: Base URL for LLM API
            llm_model: Model name
            api_type: API type (ollama or openai)
            max_retries: Maximum repair attempts per step
        """
        self.llm_client = LLMClient(llm_base_url, llm_model, api_type)
        self.prompt_interface = PromptInterface()
        self.planner = Planner(self.llm_client)
        self.auto_repair = AutoRepairLoop(self.llm_client, max_retries=max_retries)
    
    async def run(self, user_input: str):
        """
        Run MiniDevin with user input
        
        Args:
            user_input: User's task description
        """
        print("\n" + "="*80)
        print("MiniDevin - Lightweight Autonomous Development AI")
        print("="*80)
        
        print("\n[1/4] Parsing user input...")
        task = await self.prompt_interface.parse_user_input(user_input)
        print(f"Task Type: {task['task_type']}")
        print(f"Description: {task['raw_input']}")
        
        print("\n[2/4] Creating execution plan...")
        plan = await self.planner.create_plan(task)
        print(f"Generated {len(plan['steps'])} steps:")
        for idx, step in enumerate(plan['steps'], 1):
            print(f"  {idx}. {step['description']}")
        
        print("\n[3/4] Executing plan with auto-repair...")
        summary = await self.auto_repair.execute_plan(plan)
        
        print("\n[4/4] Execution Summary")
        print("="*80)
        print(f"Total Steps: {summary['total_steps']}")
        print(f"Completed: {summary['completed_steps']}")
        print(f"Failed: {summary['failed_steps']}")
        print(f"Success Rate: {summary['completed_steps']/summary['total_steps']*100:.1f}%")
        
        if self.auto_repair.knowledge_cache:
            stats = self.auto_repair.knowledge_cache.get_stats()
            print(f"\nKnowledge Cache Stats:")
            print(f"  Search entries: {stats.get('search_entries', 0)}")
            print(f"  Solution entries: {stats.get('solution_entries', 0)}")
            print(f"  Cache hits: {stats.get('cache_hits', 0)}")
        
        print("\n" + "="*80)
        print("Execution complete!")
        print("="*80 + "\n")
        
        await self.auto_repair.close()
    
    async def interactive_mode(self):
        """Run MiniDevin in interactive mode"""
        print("\n" + "="*80)
        print("MiniDevin - Interactive Mode")
        print("="*80)
        print("Type 'exit' or 'quit' to stop\n")
        
        while True:
            try:
                user_input = input("MiniDevin> ").strip()
                
                if user_input.lower() in ['exit', 'quit', 'q']:
                    print("Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                await self.run(user_input)
                
            except KeyboardInterrupt:
                print("\n\nInterrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}")
                import traceback
                traceback.print_exc()
        
        await self.auto_repair.close()


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="MiniDevin - Lightweight Autonomous Development AI"
    )
    parser.add_argument(
        "task",
        nargs="*",
        help="Task description (if not provided, enters interactive mode)"
    )
    parser.add_argument(
        "--llm-url",
        default="http://localhost:11434",
        help="LLM API base URL (default: http://localhost:11434)"
    )
    parser.add_argument(
        "--model",
        default="phi3:mini",
        help="LLM model name (default: phi3:mini)"
    )
    parser.add_argument(
        "--api-type",
        choices=["ollama", "openai"],
        default="ollama",
        help="API type (default: ollama)"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum repair attempts per step (default: 3)"
    )
    
    args = parser.parse_args()
    
    mini_devin = MiniDevin(
        llm_base_url=args.llm_url,
        llm_model=args.model,
        api_type=args.api_type,
        max_retries=args.max_retries
    )
    
    if args.task:
        task_description = " ".join(args.task)
        await mini_devin.run(task_description)
    else:
        await mini_devin.interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())
