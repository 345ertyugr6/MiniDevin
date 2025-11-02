# MiniDevin Demo Scenarios

This document provides detailed demonstration scenarios showing how MiniDevin's error → search → repair loop works in practice.

## 📋 Table of Contents

1. [Scenario 1: Missing Package Import](#scenario-1-missing-package-import)
2. [Scenario 2: Syntax Error Recovery](#scenario-2-syntax-error-recovery)
3. [Scenario 3: REST API Creation](#scenario-3-rest-api-creation)
4. [Scenario 4: Web Scraping with Dependencies](#scenario-4-web-scraping-with-dependencies)

---

## Scenario 1: Missing Package Import

### Task
```bash
python src/main.py "create a script to fetch data from a REST API"
```

### Expected Flow

**Step 1: Initial Code Generation**
```python
import requests

response = requests.get('https://api.github.com')
print(response.json())
```

**Step 2: Execution Failure**
```
ImportError: No module named 'requests'
```

**Step 3: Error Analysis**
- Error Type: `ImportError`
- Cause: Missing module 'requests'
- Search Query: `python requests installation`
- Needs Search: `True`

**Step 4: Web Search**
```
Searching: python requests installation
Found 5 results:
1. Requests: HTTP for Humans - PyPI
   pip install requests
2. Python Requests Tutorial
   Installation guide for requests library
...
```

**Step 5: Code Repair**
```python
# Note: Install requests with: pip install requests
import sys
import subprocess

try:
    import requests
except ImportError:
    print("Installing requests...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

response = requests.get('https://api.github.com')
print(response.json())
```

**Step 6: Success**
```
✓ Execution successful
Output: {'current_user_url': 'https://api.github.com/user', ...}
```

### Key Observations

- **Attempts**: 2
- **Search Performed**: Yes
- **Cache Updated**: Yes (future 'requests' errors will be faster)
- **Time**: ~15-30 seconds (depending on LLM speed)

---

## Scenario 2: Syntax Error Recovery

### Task
```bash
python src/main.py "write a function to calculate factorial"
```

### Expected Flow

**Step 1: Initial Code Generation (with error)**
```python
def factorial(n)
    if n == 0:
        return 1
    return n * factorial(n - 1)

print(factorial(5))
```

**Step 2: Execution Failure**
```
SyntaxError: invalid syntax
```

**Step 3: Error Analysis**
- Error Type: `SyntaxError`
- Cause: Invalid Python syntax (missing colon)
- Needs Search: `False` (syntax errors don't need online search)
- Suggestions: Check for missing colons, parentheses, or brackets

**Step 4: Code Repair (without search)**
```python
def factorial(n):
    if n == 0:
        return 1
    return n * factorial(n - 1)

print(factorial(5))
```

**Step 5: Success**
```
✓ Execution successful
Output: 120
```

### Key Observations

- **Attempts**: 2
- **Search Performed**: No (syntax errors handled by LLM analysis)
- **Cache Updated**: Yes
- **Time**: ~10-20 seconds

---

## Scenario 3: REST API Creation

### Task
```bash
python src/main.py "create a REST API server with FastAPI"
```

### Expected Flow

**Step 1: Plan Generation**
```
Generated 4 steps:
1. Import FastAPI and create app instance
2. Define GET endpoint for root path
3. Define POST endpoint for data submission
4. Add uvicorn server startup code
```

**Step 2: Execute Step 1**
```python
from fastapi import FastAPI

app = FastAPI()
```
```
✗ ImportError: No module named 'fastapi'
```

**Step 3: Search & Repair**
```
Searching: python fastapi installation
Found: pip install fastapi uvicorn
```

**Step 4: Repaired Code**
```python
# Install: pip install fastapi uvicorn
try:
    from fastapi import FastAPI
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn"])
    from fastapi import FastAPI

app = FastAPI()
print("FastAPI app created successfully")
```
```
✓ Success
```

**Step 5-7: Continue with remaining steps**
- Each step builds on previous success
- Final result: Complete FastAPI server code

### Key Observations

- **Total Steps**: 4
- **Failed Steps**: 1 (initial import)
- **Success Rate**: 100% (after repairs)
- **Total Time**: ~60-90 seconds

---

## Scenario 4: Web Scraping with Dependencies

### Task
```bash
python src/main.py "create a web scraper to extract titles from a webpage"
```

### Expected Flow

**Step 1: Initial Attempt**
```python
import requests
from bs4 import BeautifulSoup

url = 'https://example.com'
response = requests.get(url)
soup = BeautifulSoup(response.text, 'html.parser')
titles = soup.find_all('h1')
for title in titles:
    print(title.text)
```

**Step 2: Multiple Import Errors**
```
ImportError: No module named 'requests'
```

**Step 3: First Repair (requests)**
- Search: "python requests installation"
- Install requests
- Retry execution

**Step 4: Second Error**
```
ImportError: No module named 'bs4'
```

**Step 5: Second Repair (beautifulsoup4)**
- Search: "python beautifulsoup installation"
- Install beautifulsoup4
- Retry execution

**Step 6: Success**
```
✓ Execution successful
Output: Example Domain
```

### Key Observations

- **Attempts**: 3 (original + 2 repairs)
- **Multiple Dependencies**: Handled sequentially
- **Cache Benefit**: Both 'requests' and 'bs4' solutions cached
- **Total Time**: ~45-60 seconds

---

## 🔄 Auto-Repair Loop Visualization

```
┌─────────────────────────────────────────────────────────────┐
│                    User Input: "Task"                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Parse & Plan (Break into steps)                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │   For Each Step (Loop)       │
        └──────────┬───────────────────┘
                   │
                   ▼
        ┌──────────────────────────────┐
        │   Generate Code (LLM)        │
        └──────────┬───────────────────┘
                   │
                   ▼
        ┌──────────────────────────────┐
        │   Execute Code               │
        └──────────┬───────────────────┘
                   │
                   ▼
              ┌─────────┐
              │Success? │
              └────┬────┘
                   │
        ┌──────────┴──────────┐
        │                     │
       YES                   NO
        │                     │
        ▼                     ▼
   ┌─────────┐      ┌──────────────────┐
   │  Done!  │      │  Analyze Error   │
   └─────────┘      └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  Need Search?    │
                    └────────┬─────────┘
                             │
                  ┌──────────┴──────────┐
                  │                     │
                 YES                   NO
                  │                     │
                  ▼                     │
         ┌──────────────────┐          │
         │  Web Search      │          │
         │  (DuckDuckGo)    │          │
         └────────┬─────────┘          │
                  │                     │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │  Generate Repair     │
                  │  (with search info)  │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │  Retry < Max?        │
                  └──────────┬───────────┘
                             │
                  ┌──────────┴──────────┐
                  │                     │
                 YES                   NO
                  │                     │
                  └─────────┐           ▼
                            │    ┌──────────┐
                            │    │  Failed  │
                            │    └──────────┘
                            │
                            └─────► (Loop back to Execute)
```

---

## 📊 Performance Metrics

### Typical Execution Times (on 4-core CPU, 8GB RAM)

| Scenario | Steps | Attempts | Search | Time |
|----------|-------|----------|--------|------|
| Simple calculation | 1 | 1 | No | 5-10s |
| Import error fix | 1 | 2 | Yes | 15-30s |
| Syntax error fix | 1 | 2 | No | 10-20s |
| Multi-step API | 4 | 5 | Yes | 60-90s |
| Complex scraper | 3 | 6 | Yes | 45-75s |

### Cache Impact

| Run | Cache State | Time | Speedup |
|-----|-------------|------|---------|
| 1st | Empty | 30s | - |
| 2nd | Warmed | 18s | 1.7x |
| 3rd | Full | 12s | 2.5x |

---

## 🧪 Running Demo Tests

### Test Individual Components

```bash
# Test import error handling
cd test_scenarios
python test_import_error.py

# Test syntax error detection
python test_syntax_error.py

# Test full auto-repair loop
python test_full_scenario.py
```

### Test Complete System

```bash
# Simple task
python src/main.py "write hello world"

# Task requiring dependencies
python src/main.py "create a JSON parser"

# Complex multi-step task
python src/main.py "build a command-line calculator with history"
```

---

## 💡 Tips for Best Results

1. **Be Specific**: "Create a REST API with user authentication" is better than "make an API"
2. **Start Simple**: Test with basic tasks first to warm up the cache
3. **Check Ollama**: Ensure `ollama serve` is running before starting
4. **Monitor Resources**: Watch CPU/RAM usage during execution
5. **Review Logs**: Check repair logs to understand what MiniDevin learned

---

## 🐛 Common Issues in Demos

### Issue: "Connection refused to localhost:11434"
**Solution**: Start Ollama with `ollama serve`

### Issue: "Model not found"
**Solution**: Pull model with `ollama pull phi3:mini`

### Issue: "Search returns no results"
**Solution**: Check internet connection; cached results will be used if available

### Issue: "Code still fails after 3 attempts"
**Solution**: Task may be too complex; try breaking it into smaller steps manually

---

## 🎯 Success Indicators

A successful demo should show:

✅ Error detection and classification  
✅ Appropriate web search (when needed)  
✅ Code repair with context from search  
✅ Successful execution after repair  
✅ Knowledge cache updates  
✅ Faster execution on repeated similar tasks  

---

**End of Demo Scenarios** 🚀
