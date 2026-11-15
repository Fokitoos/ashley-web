import { mountOrb } from './orb.js';

const LOCALE = 'en-GB';
const SLIDE_INTERVAL_MS = 6000;

/* ---------- Hero carousel ---------- */

function initCarousel(root) {
  const slides = [...root.querySelectorAll('[data-slide]')];
  const dots = [...root.querySelectorAll('[data-dot]')];
  if (slides.length < 2) return;

  const autoplay = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let current = 0;
  let timer = null;

  const show = (index) => {
    current = (index + slides.length) % slides.length;
    slides.forEach((slide, i) => {
      slide.classList.toggle('is-active', i === current);
      slide.toggleAttribute('aria-hidden', i !== current);
    });
    dots.forEach((dot, i) => dot.setAttribute('aria-current', String(i === current)));
  };

  const restart = () => {
    clearInterval(timer);
    if (autoplay) timer = setInterval(() => show(current + 1), SLIDE_INTERVAL_MS);
  };

  const go = (index) => {
    show(index);
    restart();
  };

  root.querySelector('[data-carousel-prev]').addEventListener('click', () => go(current - 1));
  root.querySelector('[data-carousel-next]').addEventListener('click', () => go(current + 1));
  dots.forEach((dot, i) => dot.addEventListener('click', () => go(i)));
  restart();
}

/* ---------- Hero orb ---------- */

function initOrb(root) {
  const css = getComputedStyle(root);
  const token = (name) => css.getPropertyValue(name).trim();
  mountOrb(root, {
    colors: [token('--accent'), token('--glow'), token('--g4')],
    // The shader paints this colour wherever the ring is not; the CSS mask on .arch__orb
    // then fades that fill out so only the ring and its glow sit over the page.
    backgroundColor: token('--ground'),
    // The fade-in passes through murky half-transparent greys on a light page.
    intro: false,
  });
}

/* ---------- Sticky header ---------- */

function initSiteBar(bar) {
  // Publish the bar's height so the hero can sit beneath it and anchor jumps clear it.
  const root = document.documentElement;
  new ResizeObserver(() => root.style.setProperty('--bar-h', `${bar.offsetHeight}px`)).observe(bar);

  const update = () => bar.classList.toggle('is-scrolled', window.scrollY > 8);
  window.addEventListener('scroll', update, { passive: true });
  update();
}

/* ---------- Booking ---------- */

const pad = (n) => String(n).padStart(2, '0');
const parseDay = (key) => {
  const [y, m, d] = key.split('-').map(Number);
  return new Date(y, m - 1, d);
};
const longDate = (key) =>
  parseDay(key).toLocaleDateString(LOCALE, { weekday: 'long', day: 'numeric', month: 'long' });

function shiftMonth(month, delta) {
  const [y, m] = month.split('-').map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}`;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function initBooking(root) {
  const $ = (name) => root.querySelector(`[data-${name}]`);
  const picker = $('picker');
  const confirmation = $('confirmation');
  const prevBtn = $('prev-month');
  const nextBtn = $('next-month');
  const daysEl = $('days');
  const slotsEl = $('slots');
  const errorEl = $('error');
  const submitBtn = picker.querySelector('[type="submit"]');

  // month: "YYYY-MM" on screen; days: { "YYYY-MM-DD": ["09:00", …] } for that month.
  // date/time/slots: the visitor's selection; token: their confirmed booking, if any.
  const state = { month: null, days: {}, date: null, time: null, slots: [], token: null };

  const setError = (message) => {
    errorEl.textContent = message;
    errorEl.hidden = !message;
  };

  function renderCalendar() {
    const [y, m] = state.month.split('-').map(Number);
    const first = new Date(y, m - 1, 1);
    $('month-label').textContent = first.toLocaleDateString(LOCALE, { month: 'long', year: 'numeric' });

    const cells = [];
    const lead = (first.getDay() + 6) % 7; // weeks start on Monday
    for (let i = 0; i < lead; i++) cells.push(el('div', 'cal__day'));

    const daysInMonth = new Date(y, m, 0).getDate();
    for (let day = 1; day <= daysInMonth; day++) {
      const key = `${state.month}-${pad(day)}`;
      if (!state.days[key]) {
        cells.push(el('div', 'cal__day cal__day--closed', day));
        continue;
      }
      const button = el('button', 'pill', day);
      button.type = 'button';
      button.setAttribute('aria-label', longDate(key));
      button.setAttribute('aria-pressed', String(key === state.date));
      button.addEventListener('click', () => {
        state.date = key;
        state.time = null;
        state.slots = state.days[key];
        setError('');
        renderCalendar();
        renderSlots();
      });
      cells.push(button);
    }
    daysEl.replaceChildren(...cells);
  }

  function renderSlots() {
    $('no-date').hidden = Boolean(state.date);
    $('times').hidden = !state.date;
    if (!state.date) return;

    $('date-label').textContent = longDate(state.date);
    slotsEl.replaceChildren(
      ...state.slots.map((time) => {
        const button = el('button', 'pill pill--time', time);
        button.type = 'button';
        button.setAttribute('aria-pressed', String(time === state.time));
        button.addEventListener('click', () => {
          state.time = time;
          setError('');
          renderSlots();
        });
        return button;
      }),
    );
  }

  async function loadMonth(month) {
    const response = await fetch(`/api/availability${month ? `?month=${month}` : ''}`);
    if (!response.ok) throw new Error(`availability: ${response.status}`);
    const data = await response.json();
    state.month = data.month;
    state.days = data.days;
    prevBtn.disabled = !data.prev;
    nextBtn.disabled = !data.next;

    // Drop a selection that is no longer open (someone else booked it meanwhile).
    if (state.date?.startsWith(state.month)) {
      state.slots = state.days[state.date] ?? [];
      if (!state.slots.length) state.date = null;
      if (!state.slots.includes(state.time)) state.time = null;
      renderSlots();
    }
    renderCalendar();
  }

  const navigate = (month) =>
    loadMonth(month).catch(() => setError('We couldn’t load the calendar. Please try again.'));

  prevBtn.addEventListener('click', () => navigate(shiftMonth(state.month, -1)));
  nextBtn.addEventListener('click', () => navigate(shiftMonth(state.month, 1)));

  picker.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = new FormData(picker);
    const name = form.get('name').trim();
    const email = form.get('email').trim();

    submitBtn.disabled = true;
    try {
      const response = await fetch('/api/bookings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date: state.date,
          time: state.time,
          name,
          email,
          note: form.get('note'),
          replaces: state.token,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error);
        if (response.status === 409) await loadMonth(state.month);
        return;
      }
      state.token = data.token;
      setError('');
      $('first-name').textContent = name.split(/\s+/)[0] || 'friend';
      $('when').textContent = `${longDate(data.date)} at ${data.time}`;
      $('email').textContent = email;
      picker.hidden = true;
      confirmation.hidden = false;
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      submitBtn.disabled = false;
    }
  });

  $('reset').addEventListener('click', () => {
    state.time = null;
    confirmation.hidden = true;
    picker.hidden = false;
    renderSlots();
  });

  navigate(null);
}

/* ---------- Session shop ---------- */

// Mirrors format_euros in orders.py: 4200 -> "€42", 4250 -> "€42.50".
const euros = (cents) => `€${cents % 100 ? (cents / 100).toFixed(2) : cents / 100}`;

function initCheckout(form) {
  const quantity = form.elements.quantity;
  const total = form.querySelector('[data-total]');
  const steppers = [...form.querySelectorAll('[data-quantity-step]')];
  const min = Number(quantity.min);
  const max = Number(quantity.max);
  const count = () => Math.min(max, Math.max(min, Math.round(Number(quantity.value)) || min));

  const render = () => {
    const session = form.querySelector('input[name="session"]:checked');
    total.textContent = euros(count() * Number(session.dataset.priceCents));
    steppers.forEach((button) => {
      button.disabled = count() + Number(button.dataset.quantityStep) < min
        || count() + Number(button.dataset.quantityStep) > max;
    });
  };

  steppers.forEach((button) => button.addEventListener('click', () => {
    quantity.value = count() + Number(button.dataset.quantityStep);
    render();
  }));
  quantity.addEventListener('change', () => { quantity.value = count(); });
  form.addEventListener('input', render);

  // The total is computed here for display only; the server prices the order itself.
  form.querySelector('[data-total-row]').hidden = false;
  render();
  // After a rejected submission the page reloads at the top; bring the reason into view.
  form.querySelector('.form-error')?.scrollIntoView({ block: 'center' });
}

document.querySelectorAll('[data-site-bar]').forEach(initSiteBar);
document.querySelectorAll('[data-checkout]').forEach(initCheckout);
document.querySelectorAll('[data-orb]').forEach(initOrb);
document.querySelectorAll('[data-carousel]').forEach(initCarousel);
document.querySelectorAll('[data-booking]').forEach(initBooking);
