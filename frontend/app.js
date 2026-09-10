/**
 * AI Interview Trainer — Client-Side JavaScript
 * Handles all three pages: index.html, interview.html, report.html
 *
 * Uses sessionStorage to pass session_id and profile between pages.
 * All API calls go to the FastAPI backend at the same origin.
 */

'use strict';

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

function showError(id, msg) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.classList.add('visible');
}

function hideError(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('visible');
}

function showInfo(id, msg) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.classList.add('visible');
}

function hideInfo(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('visible');
}

function setLoading(btn, loading, label = 'Submit') {
  if (!btn) return;
  btn.disabled = loading;
  btn.innerHTML = loading
    ? `<span class="spinner"></span> Processing…`
    : label;
}

function scoreClass(score) {
  if (score >= 8) return 'score-high';
  if (score >= 5) return 'score-mid';
  return 'score-low';
}

function categoryBadgeClass(cat) {
  const map = { technical: 'badge-technical', behavioral: 'badge-behavioral', hr: 'badge-hr' };
  return map[cat] || 'badge-hr';
}

function difficultyBadgeClass(diff) {
  const map = { easy: 'badge-easy', medium: 'badge-medium', hard: 'badge-hard' };
  return map[diff] || 'badge-medium';
}

// ---------------------------------------------------------------------------
// Page router — runs the right init function based on the current page
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  const path = window.location.pathname;
  if (path === '/' || path.endsWith('index.html')) {
    initSetupPage();
  } else if (path.startsWith('/interview') || path.endsWith('interview.html')) {
    initInterviewPage();
  } else if (path.startsWith('/report') || path.endsWith('report.html')) {
    initReportPage();
  }
});

// ===========================================================================
// PAGE 1 — Setup (index.html)
// ===========================================================================

function initSetupPage() {
  const form = document.getElementById('setup-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError('error-alert');

    const role = document.getElementById('role').value.trim();
    const experience = document.getElementById('experience').value;
    const skills = document.getElementById('skills').value.trim();
    const numQuestions = parseInt(document.getElementById('num-questions').value, 10);
    const typeCheckboxes = document.querySelectorAll('input[name="types"]:checked');
    const types = Array.from(typeCheckboxes).map(cb => cb.value);

    // Client-side validation
    if (!role) { showError('error-alert', 'Please enter your job role.'); return; }
    if (!experience) { showError('error-alert', 'Please select your experience level.'); return; }
    if (types.length === 0) { showError('error-alert', 'Please select at least one question type.'); return; }

    const btn = document.getElementById('start-btn');
    setLoading(btn, true, 'Start Interview');

    try {
      const res = await fetch('/api/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role, experience, skills, num_questions: numQuestions, types }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `Server error (${res.status})`);
      }

      const data = await res.json();

      // Persist session info for the interview page
      sessionStorage.setItem('session_id', data.session_id);
      sessionStorage.setItem('profile', JSON.stringify({ role, experience, skills }));
      sessionStorage.setItem('first_question', JSON.stringify(data.question));

      window.location.href = '/interview';

    } catch (err) {
      showError('error-alert', `Failed to start interview: ${err.message}`);
      setLoading(btn, false, 'Start Interview');
    }
  });
}

// ===========================================================================
// PAGE 2 — Interview (interview.html)
// ===========================================================================

function initInterviewPage() {
  const sessionId = sessionStorage.getItem('session_id');
  const profile = JSON.parse(sessionStorage.getItem('profile') || '{}');
  const firstQuestion = JSON.parse(sessionStorage.getItem('first_question') || 'null');

  if (!sessionId || !firstQuestion) {
    window.location.href = '/';
    return;
  }

  // Show role in header
  const headerRole = document.getElementById('header-role');
  if (headerRole) headerRole.textContent = `${profile.role || '—'} · ${profile.experience || ''}`;

  // State
  let currentQuestion = firstQuestion;
  let isSubmitting = false;

  renderQuestion(currentQuestion);

  // ---- Submit answer ----
  document.getElementById('submit-btn').addEventListener('click', async () => {
    if (isSubmitting) return;
    hideError('error-alert');
    hideInfo('info-alert');

    const answer = document.getElementById('answer-input').value.trim();
    if (!answer) {
      showError('error-alert', 'Please type your answer before submitting.');
      return;
    }

    isSubmitting = true;
    const submitBtn = document.getElementById('submit-btn');
    setLoading(submitBtn, true, 'Submit Answer');
    showInfo('info-alert', 'IBM Granite is evaluating your answer…');

    try {
      const res = await fetch('/api/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, answer }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `Server error (${res.status})`);
      }

      const data = await res.json();
      hideInfo('info-alert');

      renderFeedback(data.evaluation);

      // Disable answer input after submission
      document.getElementById('answer-input').disabled = true;
      submitBtn.style.display = 'none';

      if (data.is_complete) {
        // Last question answered — show finish button
        document.getElementById('finish-btn').style.display = 'inline-flex';
      } else {
        // More questions — store next and show Next button
        sessionStorage.setItem('next_question', JSON.stringify(data.next_question));
        document.getElementById('next-btn').style.display = 'inline-flex';
      }

    } catch (err) {
      hideInfo('info-alert');
      showError('error-alert', `Evaluation failed: ${err.message}`);
      setLoading(submitBtn, false, 'Submit Answer');
    } finally {
      isSubmitting = false;
    }
  });

  // ---- Next question ----
  document.getElementById('next-btn').addEventListener('click', () => {
    const nextQuestion = JSON.parse(sessionStorage.getItem('next_question') || 'null');
    if (!nextQuestion) { window.location.href = '/'; return; }

    currentQuestion = nextQuestion;
    renderQuestion(currentQuestion);

    // Reset UI
    document.getElementById('answer-input').value = '';
    document.getElementById('answer-input').disabled = false;
    document.getElementById('submit-btn').style.display = 'inline-flex';
    document.getElementById('submit-btn').disabled = false;
    document.getElementById('submit-btn').textContent = 'Submit Answer';
    document.getElementById('next-btn').style.display = 'none';
    document.getElementById('finish-btn').style.display = 'none';
    document.getElementById('feedback-panel').classList.remove('visible');
    hideError('error-alert');
    hideInfo('info-alert');
  });

  // ---- Finish / view report ----
  document.getElementById('finish-btn').addEventListener('click', () => {
    window.location.href = `/report-page?session=${sessionId}`;
  });
}

function renderQuestion(q) {
  document.getElementById('question-text').textContent = q.text;

  const catBadge = document.getElementById('q-category-badge');
  catBadge.textContent = q.category;
  catBadge.className = `badge ${categoryBadgeClass(q.category)}`;

  const diffBadge = document.getElementById('q-difficulty-badge');
  diffBadge.textContent = q.difficulty;
  diffBadge.className = `badge ${difficultyBadgeClass(q.difficulty)}`;

  document.getElementById('q-number-label').textContent = `Q${q.question_number}`;

  const total = q.total_questions;
  const current = q.question_number;
  const pct = Math.round(((current - 1) / total) * 100);

  document.getElementById('progress-text').textContent = `Question ${current} of ${total}`;
  document.getElementById('progress-pct').textContent = `${pct}%`;
  document.getElementById('progress-fill').style.width = `${pct}%`;
}

function renderFeedback(ev) {
  const panel = document.getElementById('feedback-panel');
  const score = ev.score || 0;

  // Score circle
  const circle = document.getElementById('score-circle');
  circle.className = `score-circle ${scoreClass(score)}`;
  document.getElementById('score-number').textContent = score;

  // Score label
  let label = 'Needs Work';
  if (score >= 8) label = 'Excellent!';
  else if (score >= 6) label = 'Good Answer';
  else if (score >= 4) label = 'Fair';
  document.getElementById('score-label').textContent = label;

  // Strengths
  const strengthsList = document.getElementById('strengths-list');
  strengthsList.innerHTML = '';
  (ev.strengths || []).forEach(s => {
    const li = document.createElement('li');
    li.textContent = s;
    strengthsList.appendChild(li);
  });

  // Improvement
  const improvementList = document.getElementById('improvement-list');
  improvementList.innerHTML = '';
  if (ev.improvement) {
    const li = document.createElement('li');
    li.textContent = ev.improvement;
    improvementList.appendChild(li);
  }

  // Ideal points
  const idealList = document.getElementById('ideal-list');
  idealList.innerHTML = '';
  (ev.ideal_points || []).forEach(p => {
    const li = document.createElement('li');
    li.textContent = p;
    idealList.appendChild(li);
  });

  panel.classList.add('visible');
}

// ===========================================================================
// PAGE 3 — Report (report.html)
// ===========================================================================

function initReportPage() {
  const params = new URLSearchParams(window.location.search);
  const sessionId = params.get('session') || sessionStorage.getItem('session_id');

  if (!sessionId) {
    showError('error-alert', 'No session found. Please start a new interview.');
    document.getElementById('loading-msg').classList.remove('visible');
    return;
  }

  fetch(`/api/report/${sessionId}`)
    .then(res => {
      if (!res.ok) return res.json().then(e => { throw new Error(e.detail || res.status); });
      return res.json();
    })
    .then(data => {
      document.getElementById('loading-msg').classList.remove('visible');
      renderReport(data.report);
      document.getElementById('report-content').style.display = 'block';
    })
    .catch(err => {
      document.getElementById('loading-msg').classList.remove('visible');
      showError('error-alert', `Could not load report: ${err.message}`);
    });
}

function renderReport(report) {
  const profile = report.profile || {};

  // Profile strip
  document.getElementById('rpt-role').textContent = profile.role || '—';
  document.getElementById('rpt-experience').textContent = profile.experience || '—';
  document.getElementById('rpt-skills').textContent = profile.skills || 'Not specified';
  document.getElementById('rpt-count').textContent =
    `${report.questions_answered} / ${report.questions_total} answered`;

  // Overall score
  const overall = report.overall_score || 0;
  document.getElementById('rpt-overall-score').textContent = overall.toFixed(1);

  const banner = document.getElementById('overall-banner');
  banner.style.borderLeft = `5px solid ${overall >= 8 ? '#16a34a' : overall >= 5 ? '#d97706' : '#dc2626'}`;

  let verdict, verdictSub;
  if (overall >= 8) {
    verdict = '🏆 Outstanding Performance';
    verdictSub = 'You demonstrated strong, well-structured answers across all categories.';
  } else if (overall >= 6) {
    verdict = '👍 Good Performance';
    verdictSub = 'Solid answers with room to add more specifics and structure.';
  } else if (overall >= 4) {
    verdict = '📈 Fair Performance';
    verdictSub = 'Key concepts are there — focus on structure and specific examples.';
  } else {
    verdict = '💪 Keep Practising';
    verdictSub = 'Review the feedback below and practise with more specific examples.';
  }
  document.getElementById('rpt-verdict').textContent = verdict;
  document.getElementById('rpt-verdict-sub').textContent = verdictSub;

  // Category breakdown
  const catGrid = document.getElementById('category-grid');
  catGrid.innerHTML = '';
  const catColors = { technical: '#1d4ed8', behavioral: '#6d28d9', hr: '#92400e' };
  Object.entries(report.category_averages || {}).forEach(([cat, avg]) => {
    const card = document.createElement('div');
    card.className = 'category-card';
    card.innerHTML = `
      <div class="cat-label">${cat}</div>
      <div class="cat-score" style="color:${catColors[cat] || '#374151'}">${avg.toFixed(1)}</div>
      <div style="font-size:11px;color:#57606a;">/ 10 avg</div>`;
    catGrid.appendChild(card);
  });

  // Top strengths
  const strengthsList = document.getElementById('rpt-strengths');
  strengthsList.innerHTML = '';
  (report.top_strengths || []).forEach(s => {
    const li = document.createElement('li');
    li.textContent = s;
    strengthsList.appendChild(li);
  });
  if (!report.top_strengths?.length) {
    strengthsList.innerHTML = '<li>Complete the interview to see strengths.</li>';
  }

  // Top improvements
  const improvList = document.getElementById('rpt-improvements');
  improvList.innerHTML = '';
  (report.top_improvements || []).forEach(s => {
    const li = document.createElement('li');
    li.textContent = s;
    improvList.appendChild(li);
  });
  if (!report.top_improvements?.length) {
    improvList.innerHTML = '<li>Complete the interview to see improvement areas.</li>';
  }

  // Per-question table
  const tbody = document.getElementById('rpt-table-body');
  tbody.innerHTML = '';
  (report.rows || []).forEach((row, i) => {
    const tr = document.createElement('tr');
    const scoreCol = `<span style="font-weight:700;color:${row.score >= 8 ? '#16a34a' : row.score >= 5 ? '#d97706' : '#dc2626'}">${row.score}/10</span>`;
    const feedback = [
      row.strengths?.length ? `✓ ${row.strengths[0]}` : '',
      row.improvement ? `⚡ ${row.improvement}` : '',
    ].filter(Boolean).join('<br>');

    tr.innerHTML = `
      <td>${i + 1}</td>
      <td style="max-width:260px">
        <span class="badge ${categoryBadgeClass(row.category)}" style="margin-bottom:4px;display:inline-block">${row.category}</span><br>
        ${escHtml(row.question)}
      </td>
      <td><span class="badge ${difficultyBadgeClass(row.difficulty)}">${row.difficulty}</span></td>
      <td>${scoreCol}</td>
      <td style="font-size:13px;line-height:1.6">${feedback}</td>`;
    tbody.appendChild(tr);
  });
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
