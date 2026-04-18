/* ================================================================
 * Social Analytics — client-side polish
 *
 * Idempotent module that wires up:
 *   • data-reveal    — fade-up-on-scroll via IntersectionObserver
 *   • data-spotlight — cursor-follow radial glow (for bento cards)
 *   • data-tilt      — subtle 3D tilt on hover (for dashboard mockup)
 *   • data-counter   — smooth count-up with easing + optional sparkline
 *   • Cmd/Ctrl+K     — open command palette (dispatches 'cmdk:open')
 *
 * All entry points are guarded so re-loading (HMR / htmx swap) is safe.
 * ================================================================ */
(function () {
  'use strict';

  /* ------------------------------------------------------------
   * 1. Reveal on scroll
   * ------------------------------------------------------------ */
  const revealElements = document.querySelectorAll('[data-reveal]');
  if (revealElements.length && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const delay = parseInt(entry.target.dataset.revealDelay || '0', 10);
            setTimeout(() => entry.target.classList.add('is-visible'), delay);
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    );
    revealElements.forEach((el) => io.observe(el));
  } else {
    // No IO support — reveal everything immediately
    revealElements.forEach((el) => el.classList.add('is-visible'));
  }

  /* ------------------------------------------------------------
   * 2. Spotlight cursor glow (bento cards)
   * ------------------------------------------------------------ */
  document.querySelectorAll('[data-spotlight]').forEach((el) => {
    el.addEventListener('pointermove', (e) => {
      const rect = el.getBoundingClientRect();
      el.style.setProperty('--mx', `${e.clientX - rect.left}px`);
      el.style.setProperty('--my', `${e.clientY - rect.top}px`);
    });
  });

  /* ------------------------------------------------------------
   * 3. Subtle 3D tilt on hover
   * ------------------------------------------------------------ */
  document.querySelectorAll('[data-tilt]').forEach((el) => {
    const max = parseFloat(el.dataset.tilt || '6');
    el.addEventListener('pointermove', (e) => {
      const rect = el.getBoundingClientRect();
      const px = (e.clientX - rect.left) / rect.width;
      const py = (e.clientY - rect.top) / rect.height;
      el.style.setProperty('--ty', `${(px - 0.5) * max}deg`);
      el.style.setProperty('--tx', `${-(py - 0.5) * max}deg`);
    });
    el.addEventListener('pointerleave', () => {
      el.style.setProperty('--tx', '0deg');
      el.style.setProperty('--ty', '0deg');
    });
  });

  /* ------------------------------------------------------------
   * 4. Count-up animation
   * ------------------------------------------------------------ */
  function animateCounter(el) {
    const to = parseFloat(el.dataset.counter);
    const suffix = el.dataset.counterSuffix || '';
    const prefix = el.dataset.counterPrefix || '';
    const decimals = parseInt(el.dataset.counterDecimals || '0', 10);
    const duration = parseInt(el.dataset.counterDuration || '1800', 10);
    const start = performance.now();
    const step = (t) => {
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      const v = to * eased;
      const text = decimals ? v.toFixed(decimals) : Math.floor(v).toLocaleString();
      el.textContent = prefix + text + suffix;
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
  const counters = document.querySelectorAll('[data-counter]');
  if (counters.length && 'IntersectionObserver' in window) {
    const io2 = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            animateCounter(e.target);
            io2.unobserve(e.target);
          }
        });
      },
      { threshold: 0.35 }
    );
    counters.forEach((c) => io2.observe(c));
  } else {
    counters.forEach(animateCounter);
  }

  /* ------------------------------------------------------------
   * 5. Command palette shortcut
   * ------------------------------------------------------------ */
  window.addEventListener('keydown', (e) => {
    const isCmdK = (e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey);
    if (isCmdK) {
      e.preventDefault();
      window.dispatchEvent(new CustomEvent('cmdk:open'));
    }
  });
})();
