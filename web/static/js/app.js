// ==========================================================================
// PUAD v2.6 Pro - Master Frontend Controller
// Real-time Optical Inspection, Zero-Delay 3-Screen Layout & Theme Engine
// ==========================================================================

(function() {
  'use strict';

  // ------------------------------------------------------------------------
  // 1. DOM Element Cache
  // ------------------------------------------------------------------------
  
  // Theme Engine Elements
  const themeToggleBtn = document.getElementById('theme-toggle-btn');
  const themeToggleIcon = document.getElementById('theme-toggle-icon');

  // Sidebar Controls
  const navStreamBtns = document.querySelectorAll('.nav-stream-btn');
  const cameraSourceSelect = document.getElementById('camera-source-select');
  
  // Sidebar Telemetry
  const fpsVal = document.getElementById('fps-val');
  const latencyVal = document.getElementById('latency-val');
  const modeVal = document.getElementById('mode-val');
  const modeDot = document.getElementById('mode-dot');
  const arduinoVal = document.getElementById('arduino-val');
  const btnSoundToggle = document.getElementById('btn-sound-toggle');
  const soundLabel = document.getElementById('sound-label');
  const btnAutoToggle = document.getElementById('btn-auto-toggle');
  const autoModeText = document.getElementById('auto-mode-text');
  const btnCameraPauseToggle = document.getElementById('btn-camera-pause-toggle');
  const cameraPauseText = document.getElementById('camera-pause-text');
  const cameraPauseIcon = document.getElementById('camera-pause-icon');

  // Center Station: Exactly 3 Screens via Native CSS Grid
  const activeStreamBadge = document.getElementById('active-stream-badge');
  const btnLayoutToggle = document.getElementById('btn-layout-toggle');
  const layoutToggleText = document.getElementById('layout-toggle-text');
  const stationViewportContainer = document.getElementById('station-viewport-container');
  const cameraStatusTag = document.getElementById('camera-status-tag');
  const latencyTag = document.getElementById('latency-tag');
  const viewfinderRoiBadge = document.getElementById('viewfinder-roi-badge');

  // Action Buttons
  const btnCapture = document.getElementById('btn-capture');
  const sampleCountBadge = document.getElementById('sample-count-badge');
  const btnTrain = document.getElementById('btn-train');
  const btnTrigger = document.getElementById('btn-trigger');
  const btnReset = document.getElementById('btn-reset');

  // Right Intelligence: Verdict & Gauges
  const verdictBanner = document.getElementById('verdict-banner');
  const verdictIcon = document.getElementById('verdict-icon');
  const verdictLabel = document.getElementById('verdict-label');
  const verdictSubtext = document.getElementById('verdict-subtext');
  const sideScoreVal = document.getElementById('side-score-val');

  const gaugeScoreText = document.getElementById('gauge-score-text');
  const gaugeLimitText = document.getElementById('gauge-limit-text');
  const gaugeFillBar = document.getElementById('gauge-fill-bar');
  const thresholdMarkerLine = document.getElementById('threshold-marker-line');
  const thresholdMarkerBubble = document.getElementById('threshold-marker-bubble');

  // Dual Sliders & ROI Position Controls
  const thresholdSlider = document.getElementById('threshold-slider');
  const thresholdValText = document.getElementById('threshold-val-text');
  const roiSlider = document.getElementById('roi-slider');
  const roiValText = document.getElementById('roi-val-text');
  const roiOffsetXSlider = document.getElementById('roi-offset-x');
  const roiOffsetYSlider = document.getElementById('roi-offset-y');
  const roiXText = document.getElementById('roi-x-text');
  const roiYText = document.getElementById('roi-y-text');
  const btnRoiCenter = document.getElementById('btn-roi-center');

  // SPC Yield Tiles
  const statTotal = document.getElementById('stat-total');
  const statPass = document.getElementById('stat-pass');
  const statPassRate = document.getElementById('stat-pass-rate');
  const statDefect = document.getElementById('stat-defect');
  const statRate = document.getElementById('stat-rate');
  const statLatency = document.getElementById('stat-latency');
  const auditLogBody = document.getElementById('audit-log-body');

  // Inspection Snapshot Modal Elements
  const inspectionModal = document.getElementById('inspection-modal');
  const modalCloseBtn = document.getElementById('modal-close-btn');
  const modalDoneBtn = document.getElementById('modal-done-btn');
  const modalTitle = document.getElementById('modal-title');
  const modalVerdictBadge = document.getElementById('modal-verdict-badge');
  const modalSnapshotImg = document.getElementById('modal-snapshot-img');
  const modalTimeVal = document.getElementById('modal-time-val');
  const modalVerdictVal = document.getElementById('modal-verdict-val');
  const modalScoreVal = document.getElementById('modal-score-val');
  const modalThresholdVal = document.getElementById('modal-threshold-val');

  // ------------------------------------------------------------------------
  // 2. Safe Storage & Theme Engine (Light / Dark Mode)
  // ------------------------------------------------------------------------
  function safeGetTheme() {
    try {
      return localStorage.getItem('puad-theme') || 'light';
    } catch (e) {
      return 'light';
    }
  }

  function safeSetTheme(theme) {
    try {
      localStorage.setItem('puad-theme', theme);
    } catch (e) {
      // Storage unavailable or restricted
    }
  }

  function applyTheme(theme) {
    const validTheme = (theme === 'dark') ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', validTheme);
    safeSetTheme(validTheme);
    
    if (themeToggleBtn) {
      themeToggleBtn.setAttribute('aria-checked', (validTheme === 'dark').toString());
      themeToggleBtn.setAttribute('title', (validTheme === 'light') ? '다크 모드로 전환 (클릭)' : '라이트 모드로 전환 (클릭)');
    }
    console.log('[PUAD Theme] Active mode:', validTheme);
  }

  function initTheme() {
    applyTheme(safeGetTheme());
  }

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const current = document.documentElement.getAttribute('data-theme') || 'light';
      const nextTheme = (current === 'dark') ? 'light' : 'dark';
      applyTheme(nextTheme);
      playTone(850, 0.05);
    });
  }

  // ------------------------------------------------------------------------
  // 3. Audio Synthesizer (Professional Clean Industrial Feedback)
  // ------------------------------------------------------------------------
  let soundEnabled = false;
  let audioCtx = null;
  let lastVerdict = null;

  function initAudio() {
    if (!audioCtx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) audioCtx = new AudioContext();
    }
    if (audioCtx && audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
  }

  function playTone(freq, duration, type = 'sine', gainLevel = 0.05) {
    if (!soundEnabled) return;
    initAudio();
    if (!audioCtx) return;

    try {
      const now = audioCtx.currentTime;
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, now);
      gain.gain.setValueAtTime(gainLevel, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + duration);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start(now);
      osc.stop(now + duration);
    } catch (e) {
      // Audio fallback silent
    }
  }

  if (btnSoundToggle) {
    btnSoundToggle.addEventListener('click', () => {
      soundEnabled = !soundEnabled;
      soundLabel.textContent = soundEnabled ? 'AUDIO: ON' : 'AUDIO: OFF';
      btnSoundToggle.style.color = soundEnabled ? 'var(--color-pass)' : 'var(--ink-secondary)';
      btnSoundToggle.style.borderColor = soundEnabled ? 'var(--color-pass)' : 'var(--border-subtle)';
      if (soundEnabled) {
        initAudio();
        playTone(880, 0.06);
      }
    });
  }

  // ------------------------------------------------------------------------
  // 3-B. Camera Pause & Inspection Pause Controller
  // ------------------------------------------------------------------------
  let isCameraPaused = false;

  function updatePauseButtonState(paused) {
    isCameraPaused = !!paused;
    if (btnCameraPauseToggle) {
      btnCameraPauseToggle.classList.toggle('is-paused', isCameraPaused);
      btnCameraPauseToggle.setAttribute('title', isCameraPaused ? '카메라 켜기 및 검사 재개' : '카메라 끄기 및 검사 일시중지');
    }
    if (cameraPauseText) {
      cameraPauseText.textContent = isCameraPaused ? '카메라 켜기 / 검사 재개' : '카메라 끄기 / 검사 일시중지';
    }
    if (cameraPauseIcon) {
      if (isCameraPaused) {
        cameraPauseIcon.innerHTML = '<polygon points="5 3 19 12 5 21 5 3"/>';
      } else {
        cameraPauseIcon.innerHTML = '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>';
      }
    }
  }

  if (btnCameraPauseToggle) {
    btnCameraPauseToggle.addEventListener('click', async (e) => {
      e.preventDefault();
      try {
        const res = await fetch('/api/toggle_pause', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'ok') {
          updatePauseButtonState(data.is_paused);
          if (data.is_paused) {
            playTone(320, 0.12, 'triangle');
          } else {
            playTone(920, 0.08);
            const now = Date.now();
            const cardM = document.getElementById('card-main');
            const cardR = document.getElementById('card-roi');
            const cardH = document.getElementById('card-heatmap');
            if (cardM) cardM.querySelector('.stream-img').src = `/video_feed?t=${now}`;
            if (cardR) cardR.querySelector('.stream-img').src = `/roi_feed?t=${now}`;
            if (cardH) cardH.querySelector('.stream-img').src = `/heatmap_feed?t=${now}`;
          }
        }
      } catch (err) {
        console.error('Camera pause toggle error:', err);
      }
    });
  }

  // ------------------------------------------------------------------------
  // 4. Zero-Delay 3-Screen Layout & Stream Switcher
  // Uses Native CSS Grid placement (Zero DOM detachment, Zero MJPEG reload)
  // ------------------------------------------------------------------------
  const STREAM_MAP = {
    main: { id: 'card-main', badge: '라이브 메인 피드' },
    roi: { id: 'card-roi', badge: '인스펙션 존 (ROI)' },
    heatmap: { id: 'card-heatmap', badge: '이상치 히트맵' }
  };

  let currentMainStream = 'main';

  function setMainStream(streamType) {
    if (!STREAM_MAP[streamType]) return;
    currentMainStream = streamType;

    // Toggle .is-main and .is-sub via CSS Grid without detaching any DOM nodes
    Object.keys(STREAM_MAP).forEach(st => {
      const card = document.getElementById(STREAM_MAP[st].id);
      if (!card) return;
      const isTarget = (st === streamType);
      
      card.classList.toggle('is-main', isTarget);
      card.classList.toggle('is-sub', !isTarget);
      
      const roleTag = card.querySelector('.card-role-tag');
      if (roleTag) {
        if (isTarget) {
          roleTag.className = 'card-role-tag main';
          roleTag.textContent = 'MAIN ACTIVE';
          card.removeAttribute('title');
        } else {
          roleTag.className = 'card-role-tag sub';
          roleTag.textContent = '클릭 시 메인 전환 ↗';
          card.setAttribute('title', '클릭 시 메인 화면으로 확대 전환');
        }
      }
    });

    // Sync Left Sidebar Buttons
    navStreamBtns.forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-stream') === streamType);
    });

    // Update Header Stream Badge
    if (activeStreamBadge) {
      activeStreamBadge.textContent = STREAM_MAP[streamType].badge;
    }

    playTone(720, 0.04);
    console.log('[PUAD Stream] Main viewport switched to:', streamType);
  }

  // Event Delegation: Clicking anywhere on a sub-card instantly swaps it to main
  if (stationViewportContainer) {
    stationViewportContainer.addEventListener('click', (e) => {
      const card = e.target.closest('.stream-card');
      if (card && card.classList.contains('is-sub')) {
        const stream = card.getAttribute('data-stream');
        if (stream) setMainStream(stream);
      }
    });
  }

  // Clicking on Left Sidebar Buttons swaps that stream to main
  navStreamBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const stream = btn.getAttribute('data-stream');
      if (stream) setMainStream(stream);
    });
  });

  // Layout Toggle: 1 Main + 2 Sub (Default) vs Triple Split (All 3 Side-by-Side)
  let isTripleSplit = false;
  if (btnLayoutToggle) {
    btnLayoutToggle.addEventListener('click', () => {
      isTripleSplit = !isTripleSplit;
      stationViewportContainer.classList.toggle('triple-split-mode', isTripleSplit);
      btnLayoutToggle.classList.toggle('active', isTripleSplit);
      layoutToggleText.textContent = isTripleSplit ? '포커스 뷰' : '3분할 뷰';
      playTone(900, 0.05);
    });
  }

  // ------------------------------------------------------------------------
  // 5. Camera Hardware Selector & iPhone Continuity Camera
  // ------------------------------------------------------------------------
  let isSwitchingCamera = false;

  if (cameraSourceSelect) {
    cameraSourceSelect.addEventListener('change', async (e) => {
      let sourceVal = e.target.value;
      if (sourceVal === 'custom') {
        const customUrl = prompt('외부/iPhone IP 웹캠 스트림 주소를 입력하세요 (예: http://192.168.0.15:8080/video):');
        if (!customUrl || customUrl.trim() === '') {
          cameraSourceSelect.value = '0';
          return;
        }
        sourceVal = customUrl.trim();
      }

      isSwitchingCamera = true;
      cameraSourceSelect.disabled = true;

      const isIphone = (sourceVal === '1');
      if (cameraStatusTag) {
        cameraStatusTag.textContent = isIphone
          ? 'CONNECTING TO IPHONE CONTINUITY CAMERA (연결 중, 잠시만 기다려주세요)...'
          : `SWITCHING OPTICAL SENSOR [${sourceVal}]...`;
      }

      try {
        const res = await fetch('/api/camera', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source: sourceVal })
        });
        const data = await res.json();
        if (data.status === 'ok') {
          playTone(950, 0.08);
          cameraSourceSelect.value = data.source;

          // If was paused and server auto-resumed, update pause button state
          if (data.is_paused === false && isPaused) {
            isPaused = false;
            updatePauseBtnUI(false);
          }

          if (cameraStatusTag) {
            cameraStatusTag.textContent = (data.source === '1')
              ? 'OPTICAL SENSOR: IPHONE CONTINUITY (연결 완료)'
              : `OPTICAL SENSOR: CAM [${data.source}] ONLINE`;
          }

          // Refresh the 3 persistent stream sockets with timestamp
          const now = Date.now();
          const cardM = document.getElementById('card-main');
          const cardR = document.getElementById('card-roi');
          const cardH = document.getElementById('card-heatmap');
          if (cardM) cardM.querySelector('.stream-img').src = `/video_feed?t=${now}`;
          if (cardR) cardR.querySelector('.stream-img').src = `/roi_feed?t=${now}`;
          if (cardH) cardH.querySelector('.stream-img').src = `/heatmap_feed?t=${now}`;
        } else {
          alert('카메라 전환 실패:\n\n' + (data.message || '장치를 열 수 없습니다.'));
          if (data.current) {
            cameraSourceSelect.value = data.current;
          }
          if (cameraStatusTag) {
            cameraStatusTag.textContent = 'OPTICAL SENSOR CONNECTION FAILED';
          }
        }
      } catch (err) {
        console.error('Camera switch error:', err);
        alert('카메라 통신 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
      } finally {
        cameraSourceSelect.disabled = false;
        isSwitchingCamera = false;
      }
    });

    fetch('/api/cameras')
      .then(res => res.json())
      .then(data => {
        if (data.current && !isSwitchingCamera) {
          cameraSourceSelect.value = data.current;
        }
      })
      .catch(() => {});
  }

  // ------------------------------------------------------------------------
  // 6. Dynamic Inspection Zone (ROI) Sizing & Zero-Lag 2-Axis Position Tuning
  // ------------------------------------------------------------------------
  let isRoiUserInteracting = false;
  let lastRoiInteractionTime = 0;
  let roiSyncInFlight = false;
  let roiSyncPending = false;

  function updateRoiDisplay(size, ox, oy) {
    const curSize = (size !== undefined && size !== null) ? size : (roiSlider ? parseInt(roiSlider.value, 10) : 320);
    if (roiValText) roiValText.textContent = `${curSize} px`;
    if (viewfinderRoiBadge) viewfinderRoiBadge.textContent = `${curSize}px`;
    
    const currX = (ox !== undefined && ox !== null) ? ox : (roiOffsetXSlider ? parseInt(roiOffsetXSlider.value, 10) : 0);
    const currY = (oy !== undefined && oy !== null) ? oy : (roiOffsetYSlider ? parseInt(roiOffsetYSlider.value, 10) : 0);
    if (roiXText) roiXText.textContent = `${currX > 0 ? '+' : ''}${currX}px`;
    if (roiYText) roiYText.textContent = `${currY > 0 ? '+' : ''}${currY}px`;
  }

  function triggerRoiSync() {
    if (roiSyncInFlight) {
      roiSyncPending = true;
      return;
    }

    roiSyncInFlight = true;
    roiSyncPending = false;

    const curSize = roiSlider ? parseInt(roiSlider.value, 10) : 320;
    const curX = roiOffsetXSlider ? parseInt(roiOffsetXSlider.value, 10) : 0;
    const curY = roiOffsetYSlider ? parseInt(roiOffsetYSlider.value, 10) : 0;

    fetch('/api/roi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ roi_size: curSize, offset_x: curX, offset_y: curY })
    })
    .then(res => res.json())
    .then(data => {
      roiSyncInFlight = false;
      if (roiSyncPending) {
        triggerRoiSync();
      }
    })
    .catch(err => {
      roiSyncInFlight = false;
      console.error('ROI sync error:', err);
    });
  }

  if (roiSlider) {
    roiSlider.addEventListener('input', (e) => {
      isRoiUserInteracting = true;
      lastRoiInteractionTime = Date.now();
      const val = parseInt(e.target.value, 10);
      if (roiValText) roiValText.textContent = `${val} px`;
      if (viewfinderRoiBadge) viewfinderRoiBadge.textContent = `${val}px`;
      triggerRoiSync();
    });

    roiSlider.addEventListener('change', (e) => {
      lastRoiInteractionTime = Date.now();
      const val = parseInt(e.target.value, 10);
      if (roiValText) roiValText.textContent = `${val} px`;
      if (viewfinderRoiBadge) viewfinderRoiBadge.textContent = `${val}px`;
      triggerRoiSync();
      playTone(650, 0.04);
      setTimeout(() => { isRoiUserInteracting = false; }, 1000);
    });
  }

  if (roiOffsetXSlider) {
    roiOffsetXSlider.addEventListener('input', (e) => {
      isRoiUserInteracting = true;
      lastRoiInteractionTime = Date.now();
      const val = parseInt(e.target.value, 10);
      if (roiXText) roiXText.textContent = `${val > 0 ? '+' : ''}${val}px`;
      triggerRoiSync();
    });

    roiOffsetXSlider.addEventListener('change', (e) => {
      lastRoiInteractionTime = Date.now();
      const val = parseInt(e.target.value, 10);
      if (roiXText) roiXText.textContent = `${val > 0 ? '+' : ''}${val}px`;
      triggerRoiSync();
      playTone(620, 0.03);
      setTimeout(() => { isRoiUserInteracting = false; }, 1000);
    });
  }

  if (roiOffsetYSlider) {
    roiOffsetYSlider.addEventListener('input', (e) => {
      isRoiUserInteracting = true;
      lastRoiInteractionTime = Date.now();
      const val = parseInt(e.target.value, 10);
      if (roiYText) roiYText.textContent = `${val > 0 ? '+' : ''}${val}px`;
      triggerRoiSync();
    });

    roiOffsetYSlider.addEventListener('change', (e) => {
      lastRoiInteractionTime = Date.now();
      const val = parseInt(e.target.value, 10);
      if (roiYText) roiYText.textContent = `${val > 0 ? '+' : ''}${val}px`;
      triggerRoiSync();
      playTone(620, 0.03);
      setTimeout(() => { isRoiUserInteracting = false; }, 1000);
    });
  }

  if (btnRoiCenter) {
    btnRoiCenter.addEventListener('click', (e) => {
      e.preventDefault();
      isRoiUserInteracting = true;
      lastRoiInteractionTime = Date.now();
      if (roiOffsetXSlider) roiOffsetXSlider.value = 0;
      if (roiOffsetYSlider) roiOffsetYSlider.value = 0;
      if (roiXText) roiXText.textContent = '0px';
      if (roiYText) roiYText.textContent = '0px';
      triggerRoiSync();
      playTone(850, 0.05);
      setTimeout(() => {
        isRoiUserInteracting = false;
      }, 1000);
    });
  }

  // Presets (180px, 320px, 500px, 700px)
  document.querySelectorAll('.chip-btn[data-roi]').forEach(chip => {
    chip.addEventListener('click', (e) => {
      e.preventDefault();
      const sizeVal = parseInt(chip.getAttribute('data-roi'), 10);
      isRoiUserInteracting = true;
      lastRoiInteractionTime = Date.now();
      if (roiSlider) roiSlider.value = sizeVal;
      if (roiValText) roiValText.textContent = `${sizeVal} px`;
      if (viewfinderRoiBadge) viewfinderRoiBadge.textContent = `${sizeVal}px`;
      triggerRoiSync();
      playTone(680, 0.04);
      setTimeout(() => {
        isRoiUserInteracting = false;
      }, 1000);
    });
  });

  // ------------------------------------------------------------------------
  // 7. Decision Threshold Slider & Preset Chips
  // ------------------------------------------------------------------------
  let thDebounceTimer = null;

  function updateThresholdDisplay(val) {
    const thPct = (val * 100).toFixed(1);
    if (thresholdValText) thresholdValText.textContent = `${val.toFixed(2)} (${thPct}%)`;
    if (gaugeLimitText) gaugeLimitText.textContent = `${thPct}%`;
    if (thresholdMarkerBubble) thresholdMarkerBubble.textContent = `기준선 ${thPct}%`;
    if (thresholdMarkerLine) thresholdMarkerLine.style.left = `${val * 100}%`;
  }

  function sendThresholdUpdate(val) {
    fetch('/api/threshold', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ threshold: val })
    }).catch(err => console.error('Threshold update error:', err));
  }

  if (thresholdSlider) {
    thresholdSlider.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      updateThresholdDisplay(val);
      clearTimeout(thDebounceTimer);
      thDebounceTimer = setTimeout(() => {
        sendThresholdUpdate(val);
      }, 40);
    });

    thresholdSlider.addEventListener('change', (e) => {
      const val = parseFloat(e.target.value);
      sendThresholdUpdate(val);
    });
  }

  document.querySelectorAll('.chip-btn[data-preset]').forEach(chip => {
    chip.addEventListener('click', (e) => {
      e.preventDefault();
      const val = parseFloat(chip.getAttribute('data-preset'));
      if (thresholdSlider) thresholdSlider.value = val;
      updateThresholdDisplay(val);
      sendThresholdUpdate(val);
      playTone(700, 0.04);
    });
  });

  // ------------------------------------------------------------------------
  // 8. WebSocket Telemetry Receiver & UI Dispatcher
  // ------------------------------------------------------------------------
  function setupWebSocket() {
    const proto = (window.location.protocol === 'https:') ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/ws`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = function(event) {
      try {
        const data = JSON.parse(event.data);
        renderTelemetry(data);
      } catch (e) {
        console.error('WebSocket telemetry error:', e);
      }
    };

    ws.onclose = function() {
      setTimeout(setupWebSocket, 1500);
    };

    ws.onerror = function() {
      ws.close();
    };
  }

  function renderTelemetry(data) {
    // 1. Sidebar Telemetry
    if (fpsVal) fpsVal.textContent = `${data.fps.toFixed(1)} FPS`;
    const latStr = `${data.latency_ms.toFixed(1)} ms`;
    if (latencyVal) latencyVal.textContent = latStr;
    if (latencyTag) latencyTag.textContent = `LATENCY: ${latStr}`;
    if (statLatency) statLatency.textContent = data.latency_ms.toFixed(1);

    if (modeVal && modeDot) {
      if (data.mode === 'ENROLL') {
        modeVal.textContent = `ENROLL [${data.sample_count}/15]`;
        modeDot.className = 'status-dot amber';
      } else {
        modeVal.textContent = 'INSPECT: ONLINE';
        modeDot.className = 'status-dot green';
      }
    }

    if (arduinoVal) {
      if (data.arduino_connected) {
        arduinoVal.textContent = 'PLC: CONNECTED';
        arduinoVal.style.color = 'var(--color-pass)';
      } else {
        arduinoVal.textContent = 'PLC: STANDALONE';
        arduinoVal.style.color = 'var(--ink-secondary)';
      }
    }

    if (autoModeText) {
      autoModeText.textContent = data.auto_inspect ? '자동 검사 (ON)' : '수동 검사 (SPACE)';
      autoModeText.style.color = data.auto_inspect ? 'var(--color-pass)' : 'var(--ink-secondary)';
    }

    if (sampleCountBadge) {
      sampleCountBadge.textContent = `[${data.sample_count}/15]`;
    }

    // 2. Keep Sliders in sync (Locked during and immediately after user drag)
    if (thresholdSlider && !thresholdSlider.matches(':active')) {
      thresholdSlider.value = data.threshold;
      updateThresholdDisplay(data.threshold);
    }

    if (roiSlider && !isRoiUserInteracting && (Date.now() - lastRoiInteractionTime > 1200) && data.roi_size) {
      if (parseInt(roiSlider.value, 10) !== data.roi_size) {
        roiSlider.value = data.roi_size;
      }
    }

    if (roiOffsetXSlider && !isRoiUserInteracting && (Date.now() - lastRoiInteractionTime > 1200) && data.roi_offset_x !== undefined) {
      if (parseInt(roiOffsetXSlider.value, 10) !== data.roi_offset_x) {
        roiOffsetXSlider.value = data.roi_offset_x;
      }
    }

    if (roiOffsetYSlider && !isRoiUserInteracting && (Date.now() - lastRoiInteractionTime > 1200) && data.roi_offset_y !== undefined) {
      if (parseInt(roiOffsetYSlider.value, 10) !== data.roi_offset_y) {
        roiOffsetYSlider.value = data.roi_offset_y;
      }
    }

    if (!isRoiUserInteracting && (Date.now() - lastRoiInteractionTime > 1200) && data.roi_size) {
      updateRoiDisplay(data.roi_size, data.roi_offset_x, data.roi_offset_y);
    }

    if (cameraSourceSelect && !isSwitchingCamera && !cameraSourceSelect.matches(':focus') && data.camera_id) {
      cameraSourceSelect.value = data.camera_id;
    }

    // 3. Score Progress Bar & Percentage
    const score = data.score;
    const scorePct = Math.min(100, Math.max(0, score * 100));
    if (gaugeScoreText) gaugeScoreText.textContent = `${scorePct.toFixed(1)}%`;
    if (sideScoreVal) sideScoreVal.textContent = `${scorePct.toFixed(1)}%`;
    if (gaugeFillBar) gaugeFillBar.style.width = `${scorePct}%`;

    const thPct = (data.threshold * 100).toFixed(1);
    if (gaugeFillBar) {
      if (scorePct > (data.threshold * 100)) {
        gaugeFillBar.classList.add('fail');
      } else {
        gaugeFillBar.classList.remove('fail');
      }
    }

    // 4. Verdict Banner & Optical Guidance Tag
    if (data.is_paused) {
      updatePauseButtonState(true);
      if (fpsVal) fpsVal.textContent = '0.0 FPS';
      if (latencyVal) latencyVal.textContent = 'PAUSED';
      if (latencyTag) latencyTag.textContent = 'LATENCY: PAUSED';
      if (cameraStatusTag) cameraStatusTag.textContent = '카메라 센서 일시 정지';
      if (modeVal && modeDot) {
        modeVal.textContent = 'PAUSED (STANDBY)';
        modeDot.className = 'status-dot amber';
      }
      if (verdictBanner) verdictBanner.className = 'verdict-banner standby';
      if (verdictIcon) verdictIcon.textContent = '||';
      if (verdictLabel) verdictLabel.textContent = 'INSPECTION PAUSED';
      if (verdictSubtext) verdictSubtext.textContent = '카메라 센서가 꺼져 있습니다. 좌측 하단 버튼을 눌러 검사를 재개하십시오.';
      if (gaugeFillBar) gaugeFillBar.style.width = '0%';
      if (gaugeScoreText) gaugeScoreText.textContent = '0.0%';
      if (sideScoreVal) sideScoreVal.textContent = '0.0%';
    } else if (data.mode === 'ENROLL') {
      updatePauseButtonState(false);
      if (verdictBanner) verdictBanner.className = 'verdict-banner enroll';
      if (verdictIcon) verdictIcon.textContent = 'EN';
      if (verdictLabel) verdictLabel.textContent = `SAMPLE ENROLLMENT [${data.sample_count}/15]`;
      if (verdictSubtext) verdictSubtext.textContent = '정상 부품 데이터 수집 중 (카메라 중앙 정렬 후 [C] 클릭)';
      if (cameraStatusTag) cameraStatusTag.textContent = `샘플 등록 모드 [${data.sample_count}/15]`;
    } else {
      if (!data.part_present || data.verdict === 'WAITING') {
        if (verdictBanner) verdictBanner.className = 'verdict-banner standby';
        if (verdictIcon) verdictIcon.textContent = '--';
        if (verdictLabel) verdictLabel.textContent = '부품 감지 대기 중';
        if (verdictSubtext) verdictSubtext.textContent = '인스펙션 존에 부품을 위치시키면 검사 대기 상태가 됩니다.';
        if (cameraStatusTag) cameraStatusTag.textContent = '광학 비전 대기 중';
        if (gaugeFillBar) gaugeFillBar.style.width = '0%';
        if (gaugeScoreText) gaugeScoreText.textContent = '0.0%';
        if (sideScoreVal) sideScoreVal.textContent = '0.0%';
        lastVerdict = 'WAITING';
      } else if (data.verdict === 'READY') {
        if (verdictBanner) verdictBanner.className = 'verdict-banner ready';
        if (verdictIcon) verdictIcon.textContent = 'RDY';
        if (verdictLabel) verdictLabel.textContent = '검사 대기 [스페이스 바]';
        if (verdictSubtext) verdictSubtext.textContent = '부품 정렬 완료. 스페이스 바(SPACE) 또는 [검사] 버튼을 누르면 이상치를 판정합니다.';
        if (cameraStatusTag) cameraStatusTag.textContent = '부품 감지됨 · 스페이스 바를 눌러 검사';
        if (gaugeFillBar) gaugeFillBar.style.width = '0%';
        if (gaugeScoreText) gaugeScoreText.textContent = '0.0%';
        if (sideScoreVal) sideScoreVal.textContent = '0.0%';
        lastVerdict = 'READY';
      } else {
        if (data.verdict === 'PASS') {
          if (verdictBanner) verdictBanner.className = 'verdict-banner pass';
          if (verdictIcon) verdictIcon.textContent = 'OK';
          if (verdictLabel) verdictLabel.textContent = 'PASS // 규격 적합 양품';
          if (verdictSubtext) verdictSubtext.textContent = `이상치 점수(${scorePct.toFixed(1)}%)가 관리 임계치(${thPct}%) 이내입니다.`;
          if (cameraStatusTag) cameraStatusTag.textContent = '정상 판정 (PASS)';
          if (lastVerdict !== 'PASS') {
            playTone(980, 0.08); // Confirmation chime
            lastVerdict = 'PASS';
          }
        } else if (data.verdict === 'FAIL') {
          if (verdictBanner) verdictBanner.className = 'verdict-banner fail';
          if (verdictIcon) verdictIcon.textContent = 'NG';
          if (verdictLabel) verdictLabel.textContent = 'REJECT // 이상치 결함 감지';
          if (verdictSubtext) verdictSubtext.textContent = `이상치 점수(${scorePct.toFixed(1)}%)가 임계치(${thPct}%)를 초과하여 선별 배출합니다.`;
          if (cameraStatusTag) cameraStatusTag.textContent = '이상 결함 감지 (REJECT)';
          if (lastVerdict !== 'FAIL') {
            playTone(320, 0.16, 'sawtooth'); // Defect warning tone
            lastVerdict = 'FAIL';
          }
        }
      }
    }

    // 5. SPC Statistical Metrics
    if (statTotal) statTotal.textContent = data.total_tested;
    if (statPass) statPass.textContent = data.pass_count;
    if (statPassRate) statPassRate.textContent = `${data.pass_rate.toFixed(1)}% YIELD`;
    if (statDefect) statDefect.textContent = data.fail_count;
    if (statRate) statRate.textContent = `${data.defect_rate.toFixed(1)}% DEFECT`;

    // 6. Audit Trail Logs & Still Snapshot History
    if (data.inspections && data.inspections.length > 0) {
      renderInspectionHistory(data.inspections);
    } else if (data.logs && data.logs.length > 0) {
      renderAuditLogs(data.logs);
    }
  }

  function renderInspectionHistory(inspections) {
    if (!auditLogBody) return;
    auditLogBody.innerHTML = '';
    // Show newest first, up to 6 records
    const displayList = inspections.slice().reverse().slice(0, 6);

    displayList.forEach(rec => {
      const tr = document.createElement('tr');
      tr.className = 'has-snapshot';
      tr.title = '클릭하여 검사 시점 히트맵 스틸사진 및 상세 기록 보기';
      const isPass = (rec.verdict === 'PASS');
      const badgeClass = isPass ? 'pass' : 'fail';
      const eventTitle = rec.event || 'QC_INSPECT';

      tr.innerHTML = `
        <td>${rec.time}</td>
        <td style="font-weight: 600; color: var(--ink-primary);">${eventTitle}</td>
        <td><span class="badge-pill ${badgeClass}">${rec.verdict}</span></td>
        <td style="color: var(--ink-secondary); font-size: 0.70rem;">${rec.detail}</td>
        <td style="text-align: center;">
          <button type="button" class="chip-snapshot-view" data-record-id="${rec.id}">스틸사진 ↗</button>
        </td>
      `;

      tr.addEventListener('click', () => {
        openInspectionModal(rec);
      });

      const btn = tr.querySelector('.chip-snapshot-view');
      if (btn) {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          openInspectionModal(rec);
        });
      }

      auditLogBody.appendChild(tr);
    });
  }

  function renderAuditLogs(logs) {
    if (!auditLogBody) return;
    auditLogBody.innerHTML = '';
    const displayLogs = logs.slice().reverse().slice(0, 5);
    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0];

    displayLogs.forEach(log => {
      const tr = document.createElement('tr');
      let badgeClass = 'info';
      let verdictTag = 'INFO';
      let eventTitle = 'SYSTEM';

      if (log.includes('PASS')) {
        badgeClass = 'pass';
        verdictTag = 'PASS';
        eventTitle = 'QC_CHECK';
      } else if (log.includes('FAIL') || log.includes('Defect') || log.includes('REJECT')) {
        badgeClass = 'fail';
        verdictTag = 'REJECT';
        eventTitle = 'DEFECT_ALARM';
      } else if (log.includes('Enrolled') || log.includes('Trained')) {
        badgeClass = 'info';
        verdictTag = 'TRAIN';
        eventTitle = 'MEMORY_BANK';
      } else if (log.includes('Reset')) {
        badgeClass = 'info';
        verdictTag = 'SYSTEM';
        eventTitle = 'DATA_RESET';
      }

      tr.innerHTML = `
        <td>${timeStr}</td>
        <td style="font-weight: 600; color: var(--ink-primary);">${eventTitle}</td>
        <td><span class="badge-pill ${badgeClass}">${verdictTag}</span></td>
        <td style="color: var(--ink-secondary); font-size: 0.70rem;">${log}</td>
        <td style="text-align: center; color: var(--ink-muted); font-size: 0.70rem;">-</td>
      `;
      auditLogBody.appendChild(tr);
    });
  }

  function openInspectionModal(record) {
    if (!inspectionModal) return;
    if (modalTitle) modalTitle.textContent = `검사 기록 [#${record.id}] 스틸사진 상세`;
    if (modalVerdictBadge) {
      modalVerdictBadge.className = `badge-pill ${record.verdict === 'PASS' ? 'pass' : 'fail'}`;
      modalVerdictBadge.textContent = record.verdict;
    }
    if (modalSnapshotImg) {
      modalSnapshotImg.src = record.image_url;
    }
    if (modalTimeVal) {
      modalTimeVal.textContent = `${record.date || ''} ${record.time}`;
    }
    if (modalVerdictVal) {
      const isPass = (record.verdict === 'PASS');
      modalVerdictVal.textContent = isPass ? 'PASS // 양품 (규격 적합)' : 'REJECT // 이상치 결함 감지';
      modalVerdictVal.style.color = isPass ? 'var(--color-pass)' : 'var(--color-fail)';
    }
    if (modalScoreVal) {
      modalScoreVal.textContent = `${record.score.toFixed(1)}%`;
    }
    if (modalThresholdVal) {
      modalThresholdVal.textContent = `${record.threshold.toFixed(1)}%`;
    }
    inspectionModal.style.display = 'flex';
    playTone(900, 0.04);
  }

  function closeInspectionModal() {
    if (inspectionModal) {
      inspectionModal.style.display = 'none';
    }
  }

  if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeInspectionModal);
  if (modalDoneBtn) modalDoneBtn.addEventListener('click', closeInspectionModal);
  if (inspectionModal) {
    inspectionModal.addEventListener('click', (e) => {
      if (e.target === inspectionModal) {
        closeInspectionModal();
      }
    });
  }

  // ------------------------------------------------------------------------
  // 9. Action Buttons & Hardware Endpoints
  // ------------------------------------------------------------------------
  if (btnCapture) {
    btnCapture.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/capture', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'ok') {
          if (sampleCountBadge) sampleCountBadge.textContent = `[${data.samples_count}/15]`;
          playTone(650, 0.05);
        }
      } catch (e) {
        console.error('Capture error:', e);
      }
    });
  }

  if (btnTrain) {
    btnTrain.addEventListener('click', async () => {
      btnTrain.disabled = true;
      btnTrain.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
          <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/>
          <path d="M12 2a10 10 0 0 1 10 10"/>
        </svg>
        학습 진행 중...
      `;
      try {
        const res = await fetch('/api/train', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'ok') {
          playTone(1200, 0.14);
        } else {
          alert(data.message || '학습에 실패했습니다.');
        }
      } catch (e) {
        console.error('Train error:', e);
      } finally {
        btnTrain.disabled = false;
        btnTrain.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="5 3 19 12 5 21 5 3"/>
          </svg>
          모델 학습 및 배포
          <span class="key-tag">T</span>
        `;
      }
    });
  }

  if (btnTrigger) {
    btnTrigger.addEventListener('click', async () => {
      try {
        await fetch('/api/trigger', { method: 'POST' });
        playTone(750, 0.05);
      } catch (e) {
        console.error('Trigger error:', e);
      }
    });
  }

  if (btnReset) {
    btnReset.addEventListener('click', async () => {
      if (confirm('모든 수집된 샘플 데이터와 검사 통계를 초기화하시겠습니까?')) {
        try {
          await fetch('/api/reset', { method: 'POST' });
          playTone(450, 0.08);
        } catch (e) {
          console.error('Reset error:', e);
        }
      }
    });
  }

  if (btnAutoToggle) {
    btnAutoToggle.addEventListener('click', async () => {
      try {
        await fetch('/api/auto_inspect', { method: 'POST' });
      } catch (e) {
        console.error('Auto inspect toggle error:', e);
      }
    });
  }

  // ------------------------------------------------------------------------
  // 10. Keyboard Ergonomics ([C], [T], [R], [Space])
  // ------------------------------------------------------------------------
  window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
      return;
    }

    if (e.key === 'Escape') {
      closeInspectionModal();
    } else if (e.key === 'c' || e.key === 'C') {
      if (btnCapture) btnCapture.click();
    } else if (e.key === 't' || e.key === 'T') {
      if (btnTrain) btnTrain.click();
    } else if (e.key === 'r' || e.key === 'R') {
      if (btnReset) btnReset.click();
    } else if (e.code === 'Space') {
      e.preventDefault();
      if (btnTrigger) btnTrigger.click();
    }
  });

  // Auto-recovery for stream image disconnects
  ['img-stream-main', 'img-stream-roi', 'img-stream-heatmap'].forEach(id => {
    const img = document.getElementById(id);
    if (img) {
      img.addEventListener('error', () => {
        setTimeout(() => {
          if (!isSwitchingCamera) {
            const feedType = (id === 'img-stream-main') ? 'video_feed' : (id === 'img-stream-roi') ? 'roi_feed' : 'heatmap_feed';
            img.src = `/${feedType}?t=${Date.now()}`;
          }
        }, 500);
      });
    }
  });

  // ------------------------------------------------------------------------
  // 11. Initialization
  // ------------------------------------------------------------------------
  initTheme();
  setupWebSocket();
  console.log('[PUAD] Controller mounted successfully. Theme:', safeGetTheme());

})();

