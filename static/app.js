(() => {
  const logContainer = document.getElementById('log-container');
  const summaryTotal = document.getElementById('summary-total');
  const summaryCompleted = document.getElementById('summary-completed');
  const summaryFailed = document.getElementById('summary-failed');
  const summarySuccess = document.getElementById('summary-success');
  const codeContent = document.getElementById('code-content');
  const outputContent = document.getElementById('output-content');
  const llmContainer = document.getElementById('llm-container');
  const llmCount = document.getElementById('llm-count');
  const statusIndicator = document.getElementById('status-indicator');
  const statusText = document.getElementById('status-text');
  const statusTimestamp = document.getElementById('status-timestamp');
  const logLink = document.getElementById('log-link');
  const promptInput = document.getElementById('prompt-input');
  const runForm = document.getElementById('run-form');
  const runButton = document.getElementById('run-button');
  const stopButton = document.getElementById('stop-button');

  let eventSource;
  let running = false;
  let llmEntries = new Map();
  let placeholderLog = logContainer.firstElementChild;

  const statusStyles = {
    idle: 'bg-slate-600',
    running: 'bg-emerald-400 animate-pulse',
    stopping: 'bg-amber-400 animate-pulse',
    completed: 'bg-emerald-500',
    failed: 'bg-red-500',
    stopped: 'bg-amber-500',
  };

  function clearLogContainer() {
    logContainer.innerHTML = '';
    placeholderLog = null;
  }

  function appendLog(text) {
    if (placeholderLog) {
      clearLogContainer();
    }
    const line = document.createElement('div');
    line.className = 'whitespace-pre-wrap break-words text-slate-200';
    line.textContent = text;
    logContainer.appendChild(line);
    logContainer.scrollTop = logContainer.scrollHeight;
  }

  function resetSummary() {
    summaryTotal.textContent = '-';
    summaryCompleted.textContent = '-';
    summaryFailed.textContent = '-';
    summarySuccess.textContent = '-';
    updateCode('');
    updateOutput('');
  }

  function updateCode(code) {
    if (!code) {
      codeContent.textContent = '코드가 준비되지 않았습니다.';
    } else {
      codeContent.textContent = code;
    }
    if (window.Prism) {
      window.Prism.highlightElement(codeContent);
    }
  }

  function updateOutput(output) {
    outputContent.textContent = output || '실행 결과가 없습니다.';
  }

  function resetLLM() {
    llmEntries = new Map();
    llmContainer.innerHTML = '';
    const empty = document.createElement('p');
    empty.className = 'text-slate-500 text-sm';
    empty.textContent = '아직 LLM 요청이 기록되지 않았습니다.';
    llmContainer.appendChild(empty);
    llmCount.textContent = '총 0건';
  }

  function updateSummary(summary) {
    if (!summary) return;
    if (typeof summary.total_steps === 'number') {
      summaryTotal.textContent = summary.total_steps;
    }
    if (typeof summary.completed_steps === 'number') {
      summaryCompleted.textContent = summary.completed_steps;
    }
    if (typeof summary.failed_steps === 'number') {
      summaryFailed.textContent = summary.failed_steps;
    }
    if (typeof summary.success_rate === 'number') {
      summarySuccess.textContent = `${summary.success_rate.toFixed(1)}%`;
    }
  }

  function setRunningState(value) {
    running = value;
    runButton.disabled = value;
    stopButton.classList.toggle('hidden', !value);
    stopButton.disabled = !value;
    if (!value) {
      runButton.classList.remove('opacity-60');
    } else {
      runButton.classList.add('opacity-60');
    }
  }

  function updateStatusIndicator(status, timestamp) {
    Object.values(statusStyles).forEach((cls) => {
      cls.split(' ').forEach((token) => statusIndicator.classList.remove(token));
    });
    const style = statusStyles[status] || statusStyles.idle;
    style.split(' ').forEach((token) => {
      if (token) statusIndicator.classList.add(token);
    });
    statusIndicator.classList.remove('animate-pulse');
    if (style.includes('animate-pulse')) {
      statusIndicator.classList.add('animate-pulse');
    }
    statusText.textContent = renderStatusText(status);
    statusTimestamp.textContent = timestamp ? new Date(timestamp).toLocaleString('ko-KR') : '';
  }

  function renderStatusText(status) {
    switch (status) {
      case 'running':
        return '실행 중';
      case 'stopping':
        return '중단 처리 중';
      case 'completed':
        return '실행 완료';
      case 'failed':
        return '실행 실패';
      case 'stopped':
        return '사용자 중단';
      default:
        return '대기 중';
    }
  }

  function resetInterface() {
    clearLogContainer();
    resetSummary();
    resetLLM();
    logLink.classList.add('hidden');
    logLink.removeAttribute('href');
    logLink.textContent = '';
  }

  function createLLMCard(entry) {
    const wrapper = document.createElement('div');
    wrapper.className = 'border border-slate-800 rounded-lg bg-slate-950/60 overflow-hidden';
    wrapper.dataset.index = entry.index;

    const header = document.createElement('button');
    header.type = 'button';
    header.className = 'w-full flex items-center justify-between px-4 py-3 text-left hover:bg-slate-900 transition focus:outline-none';

    const headerInfo = document.createElement('div');
    headerInfo.className = 'flex flex-col gap-1';

    const titleRow = document.createElement('div');
    titleRow.className = 'flex items-center gap-2';

    const title = document.createElement('span');
    title.className = 'text-sm font-semibold text-slate-100';
    title.textContent = `요청 #${entry.index}`;

    const badge = document.createElement('span');
    badge.className = 'text-xs px-2 py-0.5 rounded-full border';

    titleRow.appendChild(title);
    titleRow.appendChild(badge);

    const metaRow = document.createElement('div');
    metaRow.className = 'text-xs text-slate-400 flex flex-wrap gap-3';

    const metaApi = document.createElement('span');
    const metaModel = document.createElement('span');
    const metaDuration = document.createElement('span');

    metaRow.appendChild(metaApi);
    metaRow.appendChild(metaModel);
    metaRow.appendChild(metaDuration);

    const previewRow = document.createElement('div');
    previewRow.className = 'text-xs text-slate-400 line-clamp-1';

    headerInfo.appendChild(titleRow);
    headerInfo.appendChild(metaRow);
    headerInfo.appendChild(previewRow);

    const toggleIcon = document.createElement('span');
    toggleIcon.className = 'text-xs text-slate-400';
    toggleIcon.textContent = '자세히 보기';

    header.appendChild(headerInfo);
    header.appendChild(toggleIcon);

    const body = document.createElement('div');
    body.className = 'hidden border-t border-slate-800 px-4 py-4 space-y-3 text-sm';

    const promptPreviewBlock = document.createElement('div');
    promptPreviewBlock.innerHTML = '<span class="block text-xs text-slate-400 uppercase tracking-wide mb-1">프롬프트 요약</span>';
    const previewText = document.createElement('p');
    previewText.className = 'text-slate-200 whitespace-pre-wrap break-words';
    promptPreviewBlock.appendChild(previewText);

    const promptFullBlock = document.createElement('div');
    promptFullBlock.innerHTML = '<span class="block text-xs text-slate-400 uppercase tracking-wide mb-1">프롬프트 전문</span>';
    const promptPre = document.createElement('pre');
    promptPre.className = 'bg-slate-900/70 border border-slate-800 rounded-lg p-3 text-xs whitespace-pre-wrap break-words';
    promptPre.textContent = '수집된 프롬프트가 없습니다.';
    promptFullBlock.appendChild(promptPre);

    const responseBlock = document.createElement('div');
    responseBlock.innerHTML = '<span class="block text-xs text-slate-400 uppercase tracking-wide mb-1">응답</span>';
    const responseText = document.createElement('p');
    responseText.className = 'text-slate-300 text-xs';
    responseText.textContent = 'MiniDevin CLI에서 응답 전문을 제공하지 않아 미리보기만 표시됩니다.';
    responseBlock.appendChild(responseText);

    body.appendChild(promptPreviewBlock);
    body.appendChild(promptFullBlock);
    body.appendChild(responseBlock);

    header.addEventListener('click', () => {
      body.classList.toggle('hidden');
      toggleIcon.textContent = body.classList.contains('hidden') ? '자세히 보기' : '접기';
    });

    wrapper.appendChild(header);
    wrapper.appendChild(body);

    llmContainer.appendChild(wrapper);

    return {
      wrapper,
      badge,
      metaApi,
      metaModel,
      metaDuration,
      previewText,
      promptPre,
    };
  }

  function renderLLMEntry(entry) {
    if (!entry || typeof entry.index === 'undefined') return;
    const index = entry.index;
    let card = llmEntries.get(index);
    if (!card) {
      if (llmEntries.size === 0) {
        llmContainer.innerHTML = '';
      }
      card = createLLMCard(entry);
      llmEntries.set(index, card);
    }

    const success = Boolean(entry.success);
    card.badge.textContent = success ? '✅ 성공' : '❌ 실패';
    card.badge.className = success
      ? 'text-xs px-2 py-0.5 rounded-full border border-emerald-500 text-emerald-400'
      : 'text-xs px-2 py-0.5 rounded-full border border-red-500 text-red-400';

    card.metaApi.textContent = entry.api ? `API: ${entry.api}` : 'API: -';
    card.metaModel.textContent = entry.model ? `모델: ${entry.model}` : '모델: -';
    if (typeof entry.duration === 'number' && !Number.isNaN(entry.duration)) {
      card.metaDuration.textContent = `소요 시간: ${entry.duration.toFixed(2)}초`;
    } else {
      card.metaDuration.textContent = '소요 시간: -';
    }

    card.previewText.textContent = entry.prompt_preview || '요약 정보가 없습니다.';
    if (entry.prompt_full) {
      card.promptPre.textContent = entry.prompt_full;
    }

    llmCount.textContent = `총 ${llmEntries.size}건`;
  }

  function updateLogLink(path) {
    if (path) {
      logLink.href = path;
      logLink.textContent = `로그 다운로드 (${path})`;
      logLink.classList.remove('hidden');
    } else {
      logLink.classList.add('hidden');
      logLink.textContent = '';
      logLink.removeAttribute('href');
    }
  }

  function handleRunStarted(data) {
    resetInterface();
    setRunningState(true);
    updateStatusIndicator('running', data.timestamp);
    updateLogLink(data.log_path);
  }

  function handleRunComplete(data) {
    setRunningState(false);
    updateStatusIndicator(data.status, Date.now());
    if (data.log_path) {
      updateLogLink(data.log_path);
    }
    if (data.summary) {
      updateSummary(data.summary);
    }
    if (data.error) {
      appendLog(`⚠️ ${data.error}`);
    }
  }

  function connectEvents() {
    if (eventSource) {
      eventSource.close();
    }
    eventSource = new EventSource('/events');

    eventSource.addEventListener('reset', () => {
      resetInterface();
    });

    eventSource.addEventListener('run_started', (event) => {
      const data = safeParse(event.data);
      handleRunStarted(data);
    });

    eventSource.addEventListener('status', (event) => {
      const data = safeParse(event.data);
      updateStatusIndicator(data.status || 'idle', data.timestamp);
      if (data.status === 'running') {
        setRunningState(true);
      }
      if (data.status && ['completed', 'failed', 'stopped'].includes(data.status)) {
        setRunningState(false);
      }
      if (data.error) {
        appendLog(`⚠️ ${data.error}`);
      }
    });

    eventSource.addEventListener('log', (event) => {
      const data = safeParse(event.data);
      appendLog(data.text ?? '');
    });

    eventSource.addEventListener('summary', (event) => {
      const data = safeParse(event.data);
      updateSummary(data.summary);
    });

    eventSource.addEventListener('code', (event) => {
      const data = safeParse(event.data);
      updateCode(data.code || '');
    });

    eventSource.addEventListener('test_output', (event) => {
      const data = safeParse(event.data);
      updateOutput(data.output || '');
    });

    eventSource.addEventListener('llm_entry', (event) => {
      const data = safeParse(event.data);
      renderLLMEntry(data.entry || data);
    });

    eventSource.addEventListener('llm_total', (event) => {
      const data = safeParse(event.data);
      if (typeof data.total_requests === 'number') {
        llmCount.textContent = `총 ${data.total_requests}건`;
      }
    });

    eventSource.addEventListener('run_complete', (event) => {
      const data = safeParse(event.data);
      handleRunComplete(data);
    });

    eventSource.addEventListener('error', (event) => {
      const data = safeParse(event.data);
      if (data?.message) {
        appendLog(`⚠️ ${data.message}`);
      }
    });

    eventSource.onerror = () => {
      statusTimestamp.textContent = '이벤트 스트림 연결이 끊어졌습니다. 자동 재연결 시도 중...';
    };
  }

  function safeParse(raw) {
    try {
      return raw ? JSON.parse(raw) : {};
    } catch (error) {
      console.warn('JSON 파싱 실패:', error);
      return {};
    }
  }

  async function requestRun(prompt) {
    try {
      const response = await fetch('/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || '실행 요청에 실패했습니다.');
      }
    } catch (error) {
      appendLog(`⚠️ ${error.message}`);
      setRunningState(false);
    }
  }

  async function requestStop() {
    try {
      const response = await fetch('/stop', { method: 'POST' });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || '중단 요청에 실패했습니다.');
      }
    } catch (error) {
      appendLog(`⚠️ ${error.message}`);
    }
  }

  async function loadInitialState() {
    try {
      const response = await fetch('/status');
      if (!response.ok) return;
      const state = await response.json();
      updateStatusIndicator(state.status || 'idle', state.start_time);
      updateSummary(state.summary);
      updateCode(state.code);
      updateOutput(state.test_output);
      if (state.log_path) {
        updateLogLink(state.log_path);
      }
      if (Array.isArray(state.llm_entries)) {
        resetLLM();
        state.llm_entries.forEach((entry) => renderLLMEntry(entry));
      }
      if (typeof state.llm_total_requests === 'number') {
        llmCount.textContent = `총 ${state.llm_total_requests}건`;
      }
      if (state.status === 'running') {
        setRunningState(true);
      }
    } catch (error) {
      console.warn('초기 상태 로드 실패:', error);
    }
  }

  runForm.addEventListener('submit', (event) => {
    event.preventDefault();
    if (running) return;
    const prompt = promptInput.value.trim();
    if (!prompt) {
      appendLog('⚠️ 프롬프트를 입력해주세요.');
      promptInput.focus();
      return;
    }
    setRunningState(true);
    requestRun(prompt);
  });

  stopButton.addEventListener('click', () => {
    if (!running) return;
    stopButton.disabled = true;
    requestStop().finally(() => {
      stopButton.disabled = false;
    });
  });

  window.addEventListener('load', () => {
    connectEvents();
    loadInitialState();
  });
})();
