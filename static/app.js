const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);

function animateValue(element, target, options = {}) {
  const duration = options.duration || 1600;
  const prefix = element.dataset.prefix || "";
  const suffix = element.dataset.suffix ?? "%";
  const startTime = performance.now();

  function frame(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const value = Math.round(easeOutCubic(progress) * target);
    if (suffix === "%") {
      element.innerHTML = `${value}<small>%</small>`;
    } else {
      element.textContent = `${prefix}${value}${suffix}`;
    }
    if (progress < 1) requestAnimationFrame(frame);
  }

  requestAnimationFrame(frame);
}

function animateProgressRing(ring) {
  const target = Number(ring.dataset.target || 0);
  const percent = ring.querySelector("[data-count-to]");
  const startTime = performance.now();
  const duration = 1800;
  ring.classList.add("is-animating");

  function frame(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = easeOutCubic(progress);
    const current = Math.round(eased * target);
    ring.style.setProperty("--value", `${current}%`);
    if (percent) percent.innerHTML = `${current}<small>%</small>`;
    if (progress < 1) {
      requestAnimationFrame(frame);
    } else {
      ring.classList.remove("is-animating");
      ring.classList.add("is-complete");
    }
  }

  requestAnimationFrame(frame);
}

function setupReveal() {
  const items = document.querySelectorAll(".hero-grid > *, .section, .page-hero .container, .main-grid, .result-grid, .recommend-card, .history-card, .footer-grid");
  items.forEach((item) => item.classList.add("reveal"));

  if (!("IntersectionObserver" in window)) {
    items.forEach((item) => item.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });

  items.forEach((item) => observer.observe(item));
}

function setupRipples() {
  document.querySelectorAll(".btn, .pill").forEach((button) => {
    button.addEventListener("click", (event) => {
      const rect = button.getBoundingClientRect();
      const ripple = document.createElement("span");
      ripple.className = "ripple";
      ripple.style.left = `${event.clientX - rect.left}px`;
      ripple.style.top = `${event.clientY - rect.top}px`;
      button.appendChild(ripple);
      setTimeout(() => ripple.remove(), 620);
    });
  });
}

function setupLoading() {
  const forms = document.querySelectorAll(".form-card");
  forms.forEach((form) => {
    form.addEventListener("submit", () => {
      if (!form.checkValidity()) return;
      let overlay = document.querySelector(".loading-overlay");
      if (!overlay) {
        overlay = document.createElement("div");
        overlay.className = "loading-overlay";
        overlay.innerHTML = '<div class="loader-card"><span></span><b>Analyzing patient data...</b><small>Running trained ML model</small></div>';
        document.body.appendChild(overlay);
      }
      overlay.classList.add("show");
    });
  });
}

function setupCounters() {
  const counters = document.querySelectorAll(".stat [data-count-to]");
  if (!counters.length) return;
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        animateValue(entry.target, Number(entry.target.dataset.countTo || 0));
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.5 });
  counters.forEach((counter) => observer.observe(counter));
}

document.addEventListener("DOMContentLoaded", () => {
  document.body.classList.add("page-ready");
  setupReveal();
  setupRipples();
  setupLoading();
  setupCounters();
  document.querySelectorAll("[data-progress-ring]").forEach(animateProgressRing);
});
