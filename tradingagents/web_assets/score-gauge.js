/**
 * ScoreGauge - Animated sentiment score gauge with glowing ring
 *
 * Features:
 * - Animated score transitions with ease-out easing
 * - Dynamic color based on score (cyan/purple/red)
 * - Light/dark theme support
 * - 270-degree arc display
 */

(function() {
  'use strict';

  // State for animation
  const animationState = new Map();

  /**
   * Get sentiment label based on score
   */
  function getSentimentLabel(score) {
    if (score >= 80) return '强烈看好';
    if (score >= 60) return '偏多';
    if (score >= 40) return '中性';
    if (score >= 20) return '偏空';
    return '强烈看空';
  }

  /**
   * Get sentiment key for color mapping
   */
  function getSentimentKey(score) {
    if (score >= 60) return 'greed';
    if (score >= 40) return 'neutral';
    return 'fear';
  }

  /**
   * Check if dark mode is active
   */
  function isDarkMode() {
    return document.documentElement.classList.contains('dark') ||
           window.matchMedia('(prefers-color-scheme: dark)').matches;
  }

  /**
   * Create SVG element with attributes
   */
  function createSVGElement(tag, attrs) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, value] of Object.entries(attrs)) {
      el.setAttribute(key, value);
    }
    return el;
  }

  /**
   * Animate score change
   */
  function animateScore(elementId, startScore, endScore, duration, callback) {
    const startTime = performance.now();

    function animate(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Ease-out cubic
      const easeOut = 1 - Math.pow(1 - progress, 3);
      const currentScore = startScore + (endScore - startScore) * easeOut;

      callback(currentScore, progress);

      if (progress < 1) {
        animationState.set(elementId, requestAnimationFrame(animate));
      }
    }

    animationState.set(elementId, requestAnimationFrame(animate));
  }

  /**
   * Render ScoreGauge component
   */
  function renderScoreGauge(container, options = {}) {
    const {
      score = 50,
      size = 'md',
      showLabel = true
    } = options;

    const elementId = container.id || `gauge-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    container.id = elementId;

    // Cancel any existing animation
    if (animationState.has(elementId)) {
      cancelAnimationFrame(animationState.get(elementId));
    }

    const isDark = isDarkMode();
    const sentimentKey = getSentimentKey(score);

    // Sentiment colors
    const sentimentColors = {
      greed: {
        color: '#00d4ff',
        glowFilter: 'rgba(0, 212, 255, 0.66)',
        lightColor: '#22d3ee',
        lightEndColor: '#0891b2'
      },
      neutral: {
        color: '#a855f7',
        glowFilter: 'rgba(168, 85, 247, 0.66)',
        lightColor: '#c084fc',
        lightEndColor: '#9333ea'
      },
      fear: {
        color: '#ff4466',
        glowFilter: 'rgba(255, 68, 102, 0.66)',
        lightColor: '#fb7185',
        lightEndColor: '#e11d48'
      }
    };

    const colors = sentimentColors[sentimentKey];

    // Size configuration
    const sizeConfig = {
      sm: { width: 100, stroke: 8, fontSize: '1.5rem', labelSize: '0.75rem', gap: 6 },
      md: { width: 140, stroke: 10, fontSize: '2.25rem', labelSize: '0.875rem', gap: 8 },
      lg: { width: 180, stroke: 12, fontSize: '3rem', labelSize: '1rem', gap: 10 }
    };

    const { width, stroke, fontSize, labelSize, gap } = sizeConfig[size];
    const radius = (width - stroke) / 2;
    const circumference = 2 * Math.PI * radius;
    const arcLength = circumference * 0.75;

    const uniqueId = `${sentimentKey}-${score}`;

    // Theme-specific styles
    const gaugeTheme = isDark ? {
      svgFilter: `drop-shadow(0 0 12px ${colors.glowFilter})`,
      glowBlur: 4,
      glowOpacity: 0.3,
      glowStrokeExtra: gap,
      valueTextShadow: `0 0 30px ${colors.glowFilter}`
    } : {
      svgFilter: `drop-shadow(0 0 8px ${colors.glowFilter.replace('0.66', '0.28')})`,
      glowBlur: 3.4,
      glowOpacity: 0.26,
      glowStrokeExtra: Math.max(3, gap * 0.55),
      valueTextShadow: `0 0 16px ${colors.glowFilter.replace('0.66', '0.22')}`
    };

    // Build HTML
    const html = `
      <div class="score-gauge-container" style="display: flex; flex-direction: column; align-items: center;">
        ${showLabel ? `<span class="score-gauge-label" style="margin-bottom: 12px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.16em; color: var(--muted, #58646a);">情绪指数</span>` : ''}

        <div class="score-gauge-ring" style="position: relative; width: ${width}px; height: ${width}px;">
          <svg
            class="gauge-ring"
            width="${width}"
            height="${width}"
            style="overflow: visible; ${gaugeTheme.svgFilter ? `filter: ${gaugeTheme.svgFilter};` : ''}"
          >
            <defs>
              <linearGradient id="gauge-gradient-${uniqueId}" x1="0%" y1="0%" x2="100%" y2="100%">
                ${isDark ? `
                  <stop offset="0%" stop-color="${colors.color}" stop-opacity="0.6" />
                  <stop offset="100%" stop-color="${colors.color}" stop-opacity="1" />
                ` : `
                  <stop offset="0%" stop-color="${colors.lightColor}" stop-opacity="0.9" />
                  <stop offset="100%" stop-color="${colors.lightEndColor}" stop-opacity="1" />
                `}
              </linearGradient>

              <filter id="gauge-glow-${uniqueId}">
                <feGaussianBlur stdDeviation="${gaugeTheme.glowBlur}" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            <!-- Background track -->
            <circle
              cx="${width / 2}"
              cy="${width / 2}"
              r="${radius}"
              fill="none"
              stroke="rgba(255, 255, 255, 0.05)"
              stroke-width="${stroke}"
              stroke-linecap="round"
              stroke-dasharray="${arcLength} ${circumference}"
              transform="rotate(135 ${width / 2} ${width / 2})"
            />

            <!-- Glow layer -->
            <circle
              id="${elementId}-glow"
              cx="${width / 2}"
              cy="${width / 2}"
              r="${radius}"
              fill="none"
              stroke="${isDark ? colors.color : colors.lightColor}"
              stroke-width="${stroke + gaugeTheme.glowStrokeExtra}"
              stroke-linecap="round"
              stroke-dasharray="0 ${circumference}"
              transform="rotate(135 ${width / 2} ${width / 2})"
              opacity="${gaugeTheme.glowOpacity}"
              filter="url(#gauge-glow-${uniqueId})"
            />

            <!-- Progress arc -->
            <circle
              id="${elementId}-progress"
              cx="${width / 2}"
              cy="${width / 2}"
              r="${radius}"
              fill="none"
              stroke="url(#gauge-gradient-${uniqueId})"
              stroke-width="${stroke}"
              stroke-linecap="round"
              stroke-dasharray="0 ${circumference}"
              transform="rotate(135 ${width / 2} ${width / 2})"
            />
          </svg>

          <!-- Center value -->
          <div style="position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;">
            <span
              id="${elementId}-value"
              style="font-size: ${fontSize}; font-weight: 700; color: ${isDark ? '#fff' : 'var(--ink, #1f2a2d)'}; ${gaugeTheme.valueTextShadow ? `text-shadow: ${gaugeTheme.valueTextShadow};` : ''}"
            >
              0
            </span>
            ${showLabel ? `
              <span
                id="${elementId}-label"
                style="font-size: ${labelSize}; font-weight: 600; margin-top: 4px; color: ${isDark ? colors.color : colors.lightEndColor};"
              >
                ${getSentimentLabel(score).toUpperCase()}
              </span>
            ` : ''}
          </div>
        </div>
      </div>
    `;

    container.innerHTML = html;

    // Animate from 0 to target score
    const progressEl = document.getElementById(`${elementId}-progress`);
    const glowEl = document.getElementById(`${elementId}-glow`);
    const valueEl = document.getElementById(`${elementId}-value`);

    if (progressEl && valueEl) {
      const prevScore = parseFloat(container.dataset.prevScore) || 0;

      animateScore(elementId, prevScore, score, 1000, (currentScore, progress) => {
        const displayScore = Math.round(currentScore);
        const currentProgress = (currentScore / 100) * arcLength;

        progressEl.setAttribute('stroke-dasharray', `${currentProgress} ${circumference}`);
        if (glowEl) {
          glowEl.setAttribute('stroke-dasharray', `${currentProgress} ${circumference}`);
        }
        valueEl.textContent = displayScore;
      });

      container.dataset.prevScore = score;
    }
  }

  // Export to global scope
  window.ScoreGauge = {
    render: renderScoreGauge
  };

})();
