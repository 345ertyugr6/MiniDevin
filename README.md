# MiniDevin - Lightweight Autonomous Development AI

MiniDevin is a lightweight autonomous development AI system designed to run on CPU-only environments (4-6 cores, 8-16GB RAM). It features online search capabilities and implements a self-healing code generation loop: **code generation → execution → error analysis → web search → auto-repair**.

## 🎯 Key Features

- **Autonomous Code Generation**: Breaks down tasks into steps and generates executable Python code
- **Self-Healing Loop**: Automatically detects errors, searches for solutions online, and repairs code
- **Web Search Integration**: Uses DuckDuckGo to find solutions for errors and missing dependencies
- **Knowledge Cache**: Stores successful solutions locally to speed up future repairs
- **CPU-Optimized**: Runs on modest hardware without GPU requirements
- **LLM Agnostic**: Works with local Ollama models or OpenAI-compatible APIs

## 🏗️ Architecture

```
MiniDevinOnline/
├── src/
│   ├── main.py                    # Entry point
│   └── modules/
│       ├── prompt_interface.py    # User input parsing
│       ├── llm_client.py          # LLM API communication
│       ├── planner.py             # Task planning & code generation
│       ├── executor.py            # Sandboxed code execution
│       ├── error_analyzer.py      # Error classification & analysis
│       ├── web_searcher.py        # Online search (DuckDuckGo)
│       ├── auto_repair.py         # Auto-repair orchestrator
│       └── knowledge_cache.py     # Local solution cache (SQLite)
├── test_scenarios/                # Test cases
├── data/                          # Cache database
└── requirements.txt               # Dependencies
```

## 📋 Requirements

### Hardware
- **CPU**: 4-6 cores (e.g., Ryzen 5 5600, i5-11400)
- **RAM**: 8-16 GB
- **GPU**: None required
- **Storage**: 5+ GB for models

### Software
- **OS**: Ubuntu 22.04, WSL2, or similar Linux environment
- **Python**: 3.8+
- **LLM**: Ollama with Phi-3 mini, Mistral-7B-Instruct-Q4, or Qwen 2.5-1.5B

## 🚀 Installation

### 1. Install Ollama (for local LLM)

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a lightweight model
ollama pull phi3:mini
# OR
ollama pull mistral:7b-instruct-q4_0
# OR
ollama pull qwen2.5:1.5b
```

### 2. Install MiniDevin

```bash
# Clone or download MiniDevin
cd MiniDevinOnline

# Install Python dependencies
pip install -r requirements.txt

# Create data directory
mkdir -p data
```

## 💻 Usage

### Command Line Mode

```bash
# Run with a task description
python src/main.py "create a REST API server with FastAPI"

# Specify custom LLM settings
python src/main.py "write a web scraper" --model mistral:7b-instruct-q4_0 --max-retries 5

# Use OpenAI-compatible API
python src/main.py "build a calculator" --api-type openai --llm-url http://localhost:8000
```

### Interactive Mode

```bash
# Start interactive mode (no task argument)
python src/main.py

# Then enter tasks interactively
MiniDevin> create a function to calculate fibonacci numbers
MiniDevin> write a script to download images from URLs
MiniDevin> exit
```

### Command Line Options

```
--llm-url URL          LLM API base URL (default: http://localhost:11434)
--model MODEL          Model name (default: phi3:mini)
--api-type TYPE        API type: ollama or openai (default: ollama)
--max-retries N        Maximum repair attempts per step (default: 3)
```

## 🔄 How It Works

### The Auto-Repair Loop

1. **Parse Input**: User provides a task description
2. **Plan**: Break down task into executable steps
3. **Generate Code**: LLM generates Python code for each step
4. **Execute**: Run code in sandboxed environment
5. **Analyze Errors**: If execution fails, classify and analyze the error
6. **Search Online**: Query DuckDuckGo for solutions (if needed)
7. **Repair**: Generate fixed code using error analysis + search results
8. **Retry**: Execute repaired code (repeat up to max_retries)
9. **Cache**: Store successful solutions for future use

### Example Flow

```
User: "create a REST API server"
  ↓
[Plan] 3 steps identified:
  1. Import FastAPI and create app instance
  2. Define API endpoints
  3. Add main execution block
  ↓
[Step 1] Generate code → Execute → ✗ ImportError: No module named 'fastapi'
  ↓
[Analyze] Error type: ImportError, Missing module: fastapi
  ↓
[Search] Query: "python fastapi installation"
  ↓
[Results] Found: "pip install fastapi uvicorn"
  ↓
[Repair] Generate code with installation instructions
  ↓
[Execute] → ✓ Success!
  ↓
[Cache] Store solution for future "fastapi" errors
```

## 📊 Example Output

```
================================================================================
MiniDevin - Lightweight Autonomous Development AI
================================================================================

[1/4] Parsing user input...
Task Type: creation
Description: create a simple calculator

[2/4] Creating execution plan...
Generated 3 steps:
  1. Define basic arithmetic functions (add, subtract, multiply, divide)
  2. Create main calculator function with user input
  3. Add error handling for division by zero

[3/4] Executing plan with auto-repair...

============================================================
Executing Step 1/3: Define basic arithmetic functions
============================================================
Attempt 1/3
Generated initial code (245 chars)
✓ Execution successful
✓ Step completed in 1 attempt(s)

============================================================
Executing Step 2/3: Create main calculator function
============================================================
Attempt 1/3
Generated initial code (512 chars)
✗ Error: NameError: name 'input' is not defined...
Error type: NameError
Attempt 2/3
Generated repaired code (498 chars)
✓ Execution successful
✓ Step completed in 2 attempt(s)

[4/4] Execution Summary
================================================================================
Total Steps: 3
Completed: 3
Failed: 0
Success Rate: 100.0%

Knowledge Cache Stats:
  Search entries: 2
  Solution entries: 3
  Cache hits: 0

================================================================================
Execution complete!
================================================================================
```

## 🧪 Test Scenarios

See `test_scenarios/` directory for example test cases:

- `test_import_error.py` - Demonstrates handling of missing packages
- `test_syntax_error.py` - Shows syntax error detection and repair
- `test_api_creation.py` - Full example of creating a REST API with error recovery

Run tests:
```bash
cd test_scenarios
python test_import_error.py
```

## 🔧 Configuration

### Using Different LLM Models

**Local Ollama:**
```bash
# Lightweight (1.5GB)
python src/main.py "task" --model qwen2.5:1.5b

# Balanced (3.8GB)
python src/main.py "task" --model phi3:mini

# More capable (4.1GB)
python src/main.py "task" --model mistral:7b-instruct-q4_0
```

**OpenAI-Compatible API:**
```bash
python src/main.py "task" \
  --api-type openai \
  --llm-url http://your-api-url/v1 \
  --model gpt-3.5-turbo
```

### Adjusting Retry Behavior

```bash
# More aggressive repair attempts
python src/main.py "task" --max-retries 5

# Quick fail for testing
python src/main.py "task" --max-retries 1
```

## 📈 Performance Tips

1. **Model Selection**: Start with `phi3:mini` for best speed/quality balance
2. **Cache Warming**: Run common tasks first to populate the knowledge cache
3. **Network**: Ensure stable internet connection for web searches
4. **RAM**: Close other applications to free up memory for LLM inference

## 🛠️ Troubleshooting

### Ollama Connection Error
```
Error: HTTP 404
```
**Solution**: Ensure Ollama is running: `ollama serve`

### Model Not Found
```
Error: model 'phi3:mini' not found
```
**Solution**: Pull the model: `ollama pull phi3:mini`

### Slow Execution
- Use a smaller model: `qwen2.5:1.5b`
- Reduce max_retries: `--max-retries 2`
- Check CPU usage and close other apps

### Search Failures
- Check internet connection
- DuckDuckGo may rate-limit; wait a few seconds between runs
- Cached solutions will be used when available

## 🚧 Limitations

- **Language**: Currently only generates Python code
- **Execution**: Runs in subprocess (limited sandboxing)
- **Search**: Relies on DuckDuckGo HTML parsing (may break if site changes)
- **LLM Quality**: Results depend on model capabilities
- **Safety**: Basic dangerous pattern detection only

## 🔮 Future Improvements

1. **Multi-language Support**: Add JavaScript, Go, Rust code generation
2. **Better Sandboxing**: Docker or VM-based execution
3. **Enhanced Search**: Add Stack Overflow API, GitHub search
4. **Code Analysis**: Static analysis and security scanning
5. **UI**: Web interface for easier interaction
6. **Collaboration**: Multi-agent system for complex tasks

## 📝 License

MIT License - Feel free to use and modify

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Additional error pattern recognition
- More robust code parsing
- Alternative search providers
- Performance optimizations
- Test coverage

## 📧 Support

For issues and questions, please check:
1. This README
2. Test scenarios in `test_scenarios/`
3. Error logs in console output

---

**MiniDevin** - Autonomous development, lightweight and accessible 🚀
