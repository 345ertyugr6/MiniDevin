# MiniDevin - 가벼운 자율 개발 AI

MiniDevin은 CPU 전용 환경(4-6코어, 8-16GB RAM)에서 실행되도록 설계된 가벼운 자율 개발 AI 시스템입니다. 온라인 검색 기능을 제공하며, **코드 생성 → 실행 → 오류 분석 → 웹 검색 → 자동 복구**의 자체 치유 코드 생성 루프를 구현합니다.

## 🎯 주요 특징

- **자율 코드 생성**: 작업을 단계로 분해하고 실행 가능한 Python 코드를 생성합니다.
- **자체 치유 루프**: 오류를 자동으로 감지하고, 온라인에서 해결책을 검색하며, 코드를 복구합니다.
- **웹 검색 통합**: DuckDuckGo를 사용해 오류나 누락된 의존성에 대한 해결책을 찾습니다.
- **지식 캐시**: 성공한 해결책을 로컬에 저장하여 향후 복구 속도를 높입니다.
- **CPU 최적화**: GPU 없이도 소형 하드웨어에서 실행됩니다.
- **LLM 독립적**: 로컬 Ollama 모델이나 OpenAI 호환 API와 함께 사용할 수 있습니다.

## 🏗️ 아키텍처

```
MiniDevinOnline/
├── src/
│   ├── main.py                    # 진입점
│   └── modules/
│       ├── prompt_interface.py    # 사용자 입력 파싱
│       ├── llm_client.py          # LLM API 통신
│       ├── planner.py             # 작업 계획 및 코드 생성
│       ├── executor.py            # 샌드박스 코드 실행
│       ├── error_analyzer.py      # 오류 분류 및 분석
│       ├── web_searcher.py        # 온라인 검색(DuckDuckGo)
│       ├── auto_repair.py         # 자동 복구 오케스트레이션
│       └── knowledge_cache.py     # 로컬 해결책 캐시(SQLite)
├── test_scenarios/                # 테스트 케이스
├── data/                          # 캐시 데이터베이스
└── requirements.txt               # 의존성 목록
```

## 📋 요구 사항

### 하드웨어
- **CPU**: 4-6코어 (예: Ryzen 5 5600, i5-11400)
- **RAM**: 8-16 GB
- **GPU**: 필요 없음
- **저장공간**: 모델 용량 5GB 이상

### 소프트웨어
- **OS**: Ubuntu 22.04, WSL2 또는 유사한 Linux 환경
- **Python**: 3.8+
- **LLM**: Ollama( Phi-3 mini, Mistral-7B-Instruct-Q4, Qwen 2.5-1.5B 등 )

## 🚀 설치 방법

### 1. Ollama 설치(로컬 LLM용)

```bash
# Ollama 설치
curl -fsSL https://ollama.ai/install.sh | sh

# 경량 모델 다운로드
ollama pull phi3:mini
# 또는
ollama pull mistral:7b-instruct-q4_0
# 또는
ollama pull qwen2.5:1.5b
```

### 2. MiniDevin 설치

```bash
# MiniDevin 클론 혹은 다운로드
cd MiniDevinOnline

# Python 의존성 설치
pip install -r requirements.txt

# 데이터 디렉터리 생성
mkdir -p data
```

## 💻 사용 방법

### 커맨드 라인 모드

```bash
# 작업 설명과 함께 실행
python src/main.py "create a REST API server with FastAPI"

# 사용자 지정 LLM 설정 사용
python src/main.py "write a web scraper" --model mistral:7b-instruct-q4_0 --max-retries 5

# OpenAI 호환 API 사용
python src/main.py "build a calculator" --api-type openai --llm-url http://localhost:8000
```

#### OpenAI API 키 전달

OpenAI API 유형을 사용할 때 MiniDevin은 자동으로 `OPENAI_API_KEY` 환경 변수를 확인하고 값이 있으면 `Authorization` 헤더에 Bearer 토큰으로 실어 보냅니다. MiniDevin을 실행하기 전에 다음과 같이 설정하세요.

```bash
export OPENAI_API_KEY=sk-********************************
python src/main.py "build a calculator" --api-type openai --llm-url https://api.openai.com
```

인증이 필요 없는 OpenAI 호환 프록시에 연결하는 경우에는 환경 변수를 생략해도 됩니다.

### 인터랙티브 모드

```bash
# 작업 인자 없이 인터랙티브 모드 시작
python src/main.py

# 이후 상호작용 방식으로 작업 입력
MiniDevin> create a function to calculate fibonacci numbers
MiniDevin> write a script to download images from URLs
MiniDevin> exit
```

### 커맨드 라인 옵션

```
--llm-url URL          LLM API 기본 URL (기본값: http://localhost:11434)
--model MODEL          모델 이름 (기본값: phi3:mini)
--api-type TYPE        API 유형: ollama 또는 openai (기본값: ollama)
--max-retries N        단계당 최대 복구 시도 횟수 (기본값: 3)
```

## 🔄 작동 방식

### 자동 복구 루프

1. **입력 파싱**: 사용자가 작업 설명을 제공합니다.
2. **계획 수립**: 작업을 실행 가능한 단계로 분해합니다.
3. **코드 생성**: 각 단계에 대해 LLM이 Python 코드를 생성합니다.
4. **실행**: 샌드박스 환경에서 코드를 실행합니다.
5. **오류 분석**: 실행이 실패하면 오류를 분류하고 분석합니다.
6. **온라인 검색**: 필요할 경우 DuckDuckGo로 해결책을 검색합니다.
7. **복구**: 오류 분석과 검색 결과를 사용해 수정된 코드를 생성합니다.
8. **재시도**: 복구된 코드를 실행하고, 최대 재시도 횟수까지 반복합니다.
9. **캐시**: 성공한 해결책을 저장해 이후에 재사용합니다.

### 예시 흐름

```
사용자: "create a REST API server"
  ↓
[Plan] 3개의 단계 식별:
  1. FastAPI를 임포트하고 앱 인스턴스를 생성한다
  2. API 엔드포인트를 정의한다
  3. 메인 실행 블록을 추가한다
  ↓
[Step 1] 코드 생성 → 실행 → ✗ ImportError: No module named 'fastapi'
  ↓
[Analyze] 오류 유형: ImportError, 누락된 모듈: fastapi
  ↓
[Search] 검색어: "python fastapi installation"
  ↓
[Results] 발견: "pip install fastapi uvicorn"
  ↓
[Repair] 설치 지침을 포함하여 코드를 생성
  ↓
[Execute] → ✓ 성공!
  ↓
[Cache] 향후 "fastapi" 오류를 위해 해결책 저장
```

## 📊 예시 출력

```
================================================================================
MiniDevin - Lightweight Autonomous Development AI
================================================================================

[1/4] Parsing user input...
Task Type: creation
Description: create a simple calculator
```

