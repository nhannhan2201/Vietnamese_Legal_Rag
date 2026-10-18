/* Same-origin UI: text -> /ask -> answer and exact source records.
   All provider credentials stay in Python. History is in memory for this tab. */
'use strict';
(() => {
  const $ = (id) => document.getElementById(id);
  const methods = {hybrid: 'Kết hợp từ khóa & ngữ nghĩa', dense: 'Tìm kiếm ngữ nghĩa', bm25: 'Tìm kiếm từ khóa'};
  const entries = [];
  let current = null;
  let controller = null;
  let serial = 0;
  let returnFocus = null;
  let toastTimer;
  const node = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  };

  // A small, deliberately limited Markdown renderer. Never parse model output
  // as HTML. Unsupported Markdown is displayed literally, including raw HTML.
  function inline(parent, text, availableSources) {
    const pattern = /(\*\*([^*\n]+)\*\*|`([^`\n]+)`|\[([1-9][0-9]*)\])/g;
    let offset = 0;
    for (const match of text.matchAll(pattern)) {
      parent.append(document.createTextNode(text.slice(offset, match.index)));
      if (match[2]) {
        const strong = node('strong');
        inline(strong, match[2], availableSources);
        parent.append(strong);
      }
      else if (match[3]) parent.append(node('code', match[3]));
      else if (availableSources.has(Number(match[4]))) {
        const button = node('button', match[4], 'citation');
        button.type = 'button';
        button.setAttribute('aria-label', `Đọc nguồn trích dẫn ${match[4]}`);
        button.addEventListener('click', () => openSources(Number(match[4]), button));
        parent.append(button);
      } else parent.append(document.createTextNode(match[0]));
      offset = match.index + match[0].length;
    }
    parent.append(document.createTextNode(text.slice(offset)));
  }

  function renderAnswer(text, sources) {
    const target = $('answer-text');
    target.replaceChildren();
    const available = new Set(sources.map((s) => s.source_id));
    let paragraph = null;
    let list = null;
    for (const line of text.replace(/\r\n/g, '\n').split('\n')) {
      if (!line.trim()) { paragraph = null; list = null; continue; }
      const heading = line.match(/^#{1,4}\s+(.+)/);
      const item = line.match(/^\s*(?:([-*])\s+|([0-9]+)[.)]\s+)(.*)/);
      if (heading) {
        const element = node('h3'); inline(element, heading[1], available); target.append(element);
        paragraph = null; list = null;
      } else if (item) {
        const tag = item[2] ? 'OL' : 'UL';
        if (!list || list.tagName !== tag) {
          list = node(tag.toLowerCase());
          if (item[2]) list.start = Number(item[2]);
          target.append(list);
        }
        const element = node('li'); inline(element, item[3], available); list.append(element);
        paragraph = null;
      } else {
        list = null;
        if (!paragraph) { paragraph = node('p'); target.append(paragraph); }
        else paragraph.append(document.createElement('br'));
        inline(paragraph, line, available);
      }
    }
  }

  function showToast(text) {
    $('toast').textContent = text; $('toast').hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { $('toast').hidden = true; }, 3000);
  }

  function history() {
    $('history').replaceChildren();
    $('history-count').textContent = entries.length;
    $('empty-history').hidden = entries.length > 0;
    [...entries].reverse().forEach((entry) => {
      const button = node('button', entry.question, entry === current ? 'active' : '');
      button.title = entry.question;
      if (entry === current) button.setAttribute('aria-current', 'true');
      button.addEventListener('click', () => { cancelPending(); closeSources(false); display(entry); });
      $('history').append(button);
    });
  }

  function setBusy(busy) {
    $('submit').disabled = busy;
    $('submit').querySelector('span').textContent = busy ? 'Đang xử lý' : 'Gửi câu hỏi';
    $('ask-form').setAttribute('aria-busy', String(busy));
    $('retry').disabled = busy;
    // Editing the next question is fine; duplicate submission is blocked.
  }

  function display(entry) {
    current = entry;
    $('welcome').hidden = Boolean(entry);
    $('conversation').hidden = !entry;
    $('loading-state').hidden = true;
    $('error-state').hidden = true;
    $('answer-card').hidden = true;
    if (!entry) { history(); return; }
    $('asked-question').textContent = entry.question;
    if (entry.error) {
      $('error-message').textContent = entry.error;
      $('error-state').hidden = false;
    } else if (entry.result) {
      const result = entry.result;
      renderAnswer(result.answer, result.sources);
      $('answer-status').textContent = result.status === 'answered' ? 'Có trích dẫn nguồn' : 'Chưa đủ bằng chứng';
      $('method-label').textContent = methods[entry.method];
      $('source-count').textContent = `(${result.sources.length})`;
      $('source-summary-title').textContent = result.sources.length ? 'Bằng chứng đi cùng câu trả lời' : 'Chưa tìm thấy nguồn phù hợp';
      $('source-summary-note').textContent = result.sources.length ? 'Bấm số trích dẫn để đọc nguyên văn đoạn nguồn.' : 'Bạn có thể bổ sung tên văn bản hoặc mô tả cụ thể hơn.';
      $('open-sources').disabled = !result.sources.length;
      $('answer-card').hidden = false;
    } else $('loading-state').hidden = false;
    history();
  }

  function chooseSource(id) {
    const result = current?.result;
    const source = result?.sources.find((s) => s.source_id === id);
    if (!source) return;
    $('source-tabs').replaceChildren();
    result.sources.forEach((s) => {
      const button = node('button', `[${s.source_id}]`);
      button.setAttribute('aria-label', `Nguồn ${s.source_id}${result.cited_source_ids.includes(s.source_id) ? ', đã trích dẫn' : ''}`);
      button.setAttribute('aria-pressed', String(s.source_id === id));
      button.addEventListener('click', () => {
        chooseSource(s.source_id);
        $('source-tabs').querySelector('[aria-pressed="true"]').focus();
      });
      $('source-tabs').append(button);
    });
    const content = $('source-content'); content.replaceChildren();
    const metadata = source.metadata || {};
    content.append(node('span', result.cited_source_ids.includes(id) ? 'Đã được trích dẫn trong câu trả lời' : 'Nguồn tham khảo đã gửi cho mô hình', 'source-cited'));
    content.append(node('h3', metadata.title || 'Văn bản chưa có tiêu đề'));
    const details = node('dl', undefined, 'source-metadata');
    [['Số hiệu', metadata.so_ky_hieu], ['Loại văn bản', metadata.loai_van_ban], ['Ban hành', metadata.ngay_ban_hanh], ['Cơ quan', metadata.co_quan_ban_hanh], ['Phạm vi', metadata.pham_vi]].forEach(([label, value]) => {
      details.append(node('dt', label), node('dd', typeof value === 'string' && value.trim() ? value : 'Chưa có thông tin'));
    });
    content.append(details, node('h4', 'NGUYÊN VĂN ĐOẠN NGUỒN'));
    content.append(node('div', source.text, 'source-excerpt'));
    content.append(node('p', `Mã văn bản: ${source.doc_id} · Chunk: ${source.chunk_id}\nVị trí trong text sạch: [${source.start_char}:${source.end_char}]`, 'source-provenance'));
    $('source-panel').scrollTop = 0;
  }

  function openSources(id, trigger) {
    const sources = current?.result?.sources || [];
    if (!sources.length) return;
    returnFocus = trigger || document.activeElement;
    chooseSource(id || sources[0].source_id);
    $('source-panel').hidden = false; $('source-backdrop').hidden = false;
    document.body.classList.add('dialog-open');
    document.querySelector('.app-shell').inert = true;
    $('close-sources').focus();
  }

  function closeSources(restore = true) {
    const wasOpen = !$('source-panel').hidden;
    $('source-panel').hidden = true; $('source-backdrop').hidden = true;
    document.body.classList.remove('dialog-open');
    document.querySelector('.app-shell').inert = false;
    if (wasOpen && restore && returnFocus?.isConnected) returnFocus.focus();
  }

  // Only client waiting is cancelled. The backend/provider may still finish
  // an already accepted request; never silently retry a potentially paid call.
  function cancelPending() {
    serial += 1;
    if (controller) {
      controller.abort(); controller = null;
      if (current && !current.result && !current.error) current.error = 'Bạn đã rời lượt tra cứu này. Yêu cầu đã gửi có thể vẫn được xử lý ở máy chủ.';
    }
    setBusy(false);
  }

  function validResult(result) {
    if (!result || typeof result.answer !== 'string' || !['answered', 'no_sources', 'insufficient_context'].includes(result.status) || !Array.isArray(result.sources) || !Array.isArray(result.cited_source_ids)) return false;
    const seen = new Set();
    for (const source of result.sources) {
      if (!Number.isInteger(source.source_id) || source.source_id < 1 || seen.has(source.source_id) || typeof source.text !== 'string' || !source.metadata || typeof source.metadata !== 'object') return false;
      seen.add(source.source_id);
    }
    return result.cited_source_ids.every((id) => seen.has(id));
  }

  async function ask(question, method, reuse = null) {
    if (controller) return;
    const entry = reuse || {question, method};
    if (!reuse) entries.push(entry);
    delete entry.error;
    closeSources(false); display(entry); setBusy(true);
    const token = ++serial;
    controller = new AbortController();
    const requestController = controller;
    const signal = requestController.signal;
    $('search-options').open = false;
    $('question').value = ''; $('question').style.height = '';
    $('asked-question').scrollIntoView({block: 'start', behavior: 'auto'});
    // Allow slow first inference but don't leave a permanently stuck UI.
    const timeout = setTimeout(() => requestController.abort(), 240000);
    try {
      const response = await fetch('/ask', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({question, method}), signal});
      if (!response.ok) {
        const errors = {422: 'Câu hỏi chưa hợp lệ. Vui lòng kiểm tra nội dung và gửi lại.', 502: 'Dịch vụ embedding hoặc tạo câu trả lời chưa phản hồi hợp lệ. Hãy kiểm tra Kaggle/ngrok và dịch vụ LLM rồi thử lại.', 503: 'Hệ thống chưa nạp xong dữ liệu. Vui lòng đợi rồi thử lại.'};
        throw new Error(errors[response.status] || 'Máy chủ gặp lỗi khi xử lý câu hỏi. Vui lòng thử lại sau.');
      }
      const result = await response.json();
      if (!validResult(result)) throw new Error('Phản hồi từ máy chủ không đúng định dạng. Vui lòng kiểm tra dịch vụ.');
      if (token !== serial) return;
      entry.result = result; display(entry);
    } catch (error) {
      if (token !== serial) return;
      entry.error = error.name === 'AbortError' ? 'Đã chờ quá lâu nên giao diện ngừng đợi. Yêu cầu có thể vẫn đang được xử lý ở máy chủ; hãy kiểm tra dịch vụ trước khi gửi lại.' : error instanceof TypeError ? 'Không kết nối được máy chủ. Hãy kiểm tra kết nối và tiến trình FastAPI.' : error.message;
      display(entry);
    } finally {
      clearTimeout(timeout);
      if (token === serial) { controller = null; setBusy(false); }
    }
  }

  $('ask-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const question = $('question').value.trim();
    if (!question) { $('question').focus(); return; }
    ask(question, $('method').value);
  });
  $('question').addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); $('ask-form').requestSubmit(); }
  });
  $('question').addEventListener('input', () => { $('question').style.height = 'auto'; $('question').style.height = `${Math.min($('question').scrollHeight, 180)}px`; });
  document.querySelectorAll('.suggestion').forEach((button) => button.addEventListener('click', () => {
    $('question').value = button.dataset.question; $('question').dispatchEvent(new Event('input')); $('question').focus();
  }));
  $('new-chat').addEventListener('click', () => { cancelPending(); closeSources(false); display(null); $('question').value = ''; $('question').style.height = ''; $('question').focus(); });
  $('retry').addEventListener('click', () => { if (current) ask(current.question, current.method, current); });
  $('copy-answer').addEventListener('click', async () => {
    if (!current?.result) return;
    try { await navigator.clipboard.writeText(current.result.answer); showToast('Đã sao chép câu trả lời.'); }
    catch { showToast('Không sao chép được. Bạn có thể chọn và sao chép trực tiếp đoạn trả lời.'); }
  });
  $('open-sources').addEventListener('click', (event) => openSources(null, event.currentTarget));
  $('close-sources').addEventListener('click', () => closeSources());
  $('source-backdrop').addEventListener('click', () => closeSources());
  document.addEventListener('keydown', (event) => {
    if ($('source-panel').hidden) return;
    if (event.key === 'Escape') { event.preventDefault(); closeSources(); }
    if (event.key === 'Tab') {
      const focusable = [...$('source-panel').querySelectorAll('button')];
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (!focusable.includes(document.activeElement)) { event.preventDefault(); first.focus(); }
      else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  // Local readiness only. Embedding/LLM reachability is checked by a real /ask.
  fetch('/health', {signal: AbortSignal.timeout(5000)}).then((response) => {
    if (!response.ok) throw new Error('unready');
    $('connection').className = 'connection ready'; $('connection').replaceChildren(node('i'), document.createTextNode('Dữ liệu đã sẵn sàng'));
  }).catch(() => { $('connection').className = 'connection offline'; $('connection').replaceChildren(node('i'), document.createTextNode('Chưa kết nối dịch vụ')); });
})();
