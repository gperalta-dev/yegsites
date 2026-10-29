// "Ask Southsites": the landing page's chat. Claude answers through the chat server in this folder (worker.mjs, bot
// "southsites"); when the server is busy, off or out of today's budget, or says nothing for 5 seconds, the built-in answers
// below reply from the facts on the page, and nothing typed leaves it. The button sits in the page's bottom bar (#dock).
(() => {
  const CHAT_URL = 'https://sample-realty-chat.southsites.workers.dev/chat';
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const css = `
  .ss-chat { position: fixed; z-index: 25; right: 18px; bottom: 96px; width: min(390px, calc(100vw - 24px)); height: min(560px, calc(100dvh - 120px)); display: flex; flex-direction: column;
    background: var(--surface, #16191e); color: var(--ink, #f2efe6); border: 1px solid var(--line-strong, rgba(255,255,255,.2)); border-radius: 18px; box-shadow: 0 30px 80px -24px rgba(0,0,0,.9); font: 400 16px/1.5 var(--body, system-ui); overflow: hidden; }
  .ss-chat[hidden] { display: none; }
  @media (prefers-reduced-motion: no-preference) { .ss-chat { animation: ss-in .22s cubic-bezier(.2,.8,.2,1); } }
  @keyframes ss-in { from { opacity: 0; transform: translateY(12px); } }
  .ss-top { display: flex; align-items: center; gap: 12px; padding: 12px 10px 12px 16px; border-bottom: 1px solid var(--line, rgba(255,255,255,.1)); }
  .ss-top i { flex: none; width: 34px; height: 34px; border-radius: 9px; background: var(--accent, #ffc83d); display: grid; place-items: center; color: var(--accent-ink, #1a1405); font: 900 19px/1 var(--display, system-ui); font-style: normal; }
  .ss-top div { flex: 1; min-width: 0; }
  .ss-top b { display: block; font-weight: 800; line-height: 1.2; }
  .ss-top small { display: block; color: var(--muted, #b8bcc3); font-size: 13px; line-height: 1.3; }
  .ss-x { flex: none; width: 44px; height: 44px; border: 0; border-radius: 12px; background: transparent; color: var(--ink, #f2efe6); cursor: pointer; display: grid; place-items: center; }
  .ss-x svg, .ss-ask button svg { width: 20px; height: 20px; }
  @media (hover: hover) { .ss-x:hover { background: rgba(255,255,255,.08); } }
  .ss-msgs { flex: 1; overflow-y: auto; overscroll-behavior: contain; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
  .ss-msg { max-width: 88%; padding: 10px 14px; border-radius: 16px; }
  .ss-msg.bot { align-self: flex-start; background: var(--surface-2, #1d2128); border: 1px solid var(--line, rgba(255,255,255,.1)); border-bottom-left-radius: 6px; }
  .ss-msg.ai { white-space: pre-line; }
  .ss-msg.me { align-self: flex-end; background: var(--accent, #ffc83d); color: var(--accent-ink, #1a1405); font-weight: 600; border-bottom-right-radius: 6px; }
  .ss-msg a { color: var(--accent, #ffc83d); font-weight: 700; text-underline-offset: 3px; }
  .ss-msg .from { display: block; margin-top: 4px; font-size: 12.5px; color: var(--faint, #8f949c); }
  .ss-typing { display: inline-flex; gap: 5px; padding: 6px 2px; }
  .ss-typing i { width: 7px; height: 7px; border-radius: 50%; background: var(--muted, #b8bcc3); }
  @media (prefers-reduced-motion: no-preference) { .ss-typing i { animation: ss-dot 1s infinite ease-in-out; } .ss-typing i:nth-child(2) { animation-delay: .15s; } .ss-typing i:nth-child(3) { animation-delay: .3s; } }
  @keyframes ss-dot { 50% { opacity: .3; transform: translateY(-3px); } }
  .ss-chips { display: flex; gap: 8px; overflow-x: auto; padding: 0 14px 10px; scrollbar-width: none; }
  .ss-chips button { flex: none; min-height: 40px; padding: 0 14px; border-radius: 99px; border: 1px solid var(--line-strong, rgba(255,255,255,.2)); background: transparent; color: var(--ink, #f2efe6); font: 600 14px var(--body, system-ui); cursor: pointer; }
  @media (hover: hover) { .ss-chips button:hover { border-color: var(--accent, #ffc83d); } }
  .ss-ask { display: flex; gap: 8px; padding: 10px; border-top: 1px solid var(--line, rgba(255,255,255,.1)); }
  .ss-ask input { flex: 1; min-width: 0; min-height: 46px; padding: 0 14px; border-radius: 12px; border: 1px solid var(--line-strong, rgba(255,255,255,.2)); background: var(--field, #111419); color: var(--ink, #f2efe6); font: 400 16px var(--body, system-ui); }
  .ss-ask button { flex: none; width: 46px; height: 46px; border: 0; border-radius: 12px; background: var(--accent, #ffc83d); color: var(--accent-ink, #1a1405); cursor: pointer; display: grid; place-items: center; }
  .ss-sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
  .dock .ss-open svg { color: var(--accent, #ffc83d); }
  .ss-float { position: fixed; z-index: 20; right: 18px; bottom: 18px; }
  @media (max-width: 700px) { .ss-chat { left: 12px; right: 12px; width: auto; bottom: calc(94px + env(safe-area-inset-bottom)); height: min(540px, calc(100dvh - 160px)); } }`;
  const ICON = {
    chat: '<path d="M18 4a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3h-5l-5 3v-3H6a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3z"/><path d="M9.5 9h.01M14.5 9h.01M9.5 13a3.5 3.5 0 0 0 5 0"/>',
    x: '<path d="M6 6l12 12M18 6L6 18"/>',
    send: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  };
  const svg = (k) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON[k]}</svg>`;

  // the built-in answers: every fact is on this page or /pricing. 4+ letter words also match longer ones ("book" finds
  // "booking"); the topic with the most matches answers, and on a tie the earlier one, so the add-ons come before price
  const preview = '<a href="#quote">Get my free preview</a>', text = '<a href="sms:+18254615061">text 825-461-5061</a>';
  const TOPICS = [
    ['hi hello hey', 'Hi! Ask me about prices, the free preview or what\'s included.'],
    ['thanks thank thx cheers', `You're welcome. ${preview}`],
    ['booking book booked appointments appointment square fresha booksy calendar schedule', 'Online booking is $79 once, hooked up to Square Appointments, Fresha or Booksy. It also comes in the Get booked bundle: $349, then $49 a month.'],
    ['chat chatbot assistant', 'The AI chat assistant is $99 setup, then $39 a month. It answers questions about your hours, services and prices day and night, like this chat, and takes a name and number when it can\'t.'],
    ['missed miss voicemail back', 'Missed-call text back is $49 a month: when you can\'t pick up, the caller gets a text right away, so they don\'t call the next shop.'],
    ['receptionist answering answer calls', 'An AI phone receptionist starts at $149 a month, quoted for your shop. It answers your calls, books or takes messages, and texts you a summary.'],
    ['review reviews stars rating', 'Review request texts are $29 a month: after each visit, a short text asks happy customers for a Google review.'],
    ['google listing maps profile', 'The Google listing fix-up is $49 once: hours, photos, services and a working website link on your listing.'],
    ['page pages menu gallery list extra', 'Extra pages, like a menu, a price list, a gallery or a page per service, are $49 a page, once.'],
    ['bundle bundles plan plans package packages', 'Three bundles: Get found $249 then $29 a month, Get booked $349 then $49 a month, and Never miss a customer $449 then $119 a month. <a href="/pricing/">Compare them</a>'],
    ['monthly month hosting edits edit cancel update updates', '$29 a month covers hosting and small edits like new hours, photos, prices or a holiday notice. Cancel any month.'],
    ['price prices cost costs much charge pay fee expensive cheap', `A site is $249 once (the founding price for the first 3 clients, $399 after), then $29 a month. Seeing your preview is free. <a href="/pricing/">See all prices</a>`],
    ['tax taxes gst', 'Prices are in Canadian dollars, before tax.'],
    ['domain domains name names url dot', 'Your own domain is included for the first year: Jan suggests a few names and you pick. After that, the renewal is covered by your monthly plan, and the domain is yours.'],
    ['like hate refund refunds guarantee happy unhappy wrong', "Happy or it doesn't go live: Jan doesn't publish your site, or charge you, until you say it's right. If you don't like it, it doesn't go live and you don't pay."],
    ['own owner ownership leave files transfer', 'You own the site and the domain. If you ever leave, Jan hands over the files and transfers the domain to you.'],
    ['preview free start work works process how', `Jan builds a free preview from your Google listing and sends you the link. You look at it on your phone, ask for changes or say no thanks, and only pay if you keep it. ${preview}`],
    ['who jan student builds built', 'Jan Gabriel, a computer systems student in Edmonton, builds every site. You deal with him directly.'],
    ['sample samples example examples demo demos portfolio realty plumber pizza detail easykeeps', 'The samples on this page are made-up businesses: a realtor, a plumber, a pizza place and a detail shop. Easykeeps is Jan\'s own real business. <a href="#samples">See the samples</a>'],
    ['contact phone email text call reach number', 'Text or call 825-461-5061, or email contact@southsites.ca. <a href="sms:+18254615061">Text Jan</a>'],
    ['real human person robot bot', `These are the page's built-in answers. Jan is a real person: ${text}.`],
  ].map(([w, a]) => ({ w: w.split(' '), a }));
  const CHIPS = ['What does it cost?', 'How does the free preview work?', 'What\'s in the $29 a month?', 'Can customers book online?', 'Who builds it?'];
  function answer(q) {
    const words = q.toLowerCase().replace(/[^a-z0-9$' ]+/g, ' ').split(/\s+/).filter(Boolean);
    let best = null, top = 0;
    for (const t of TOPICS) {
      const n = words.filter((x) => t.w.some((w) => x === w || (w.length >= 4 && x.startsWith(w)))).length;
      if (n > top) { top = n; best = t; }
    }
    return best ? best.a : `I don't have that one. Jan can answer it: ${text}, or ask in the free preview form.`;
  }

  const style = document.createElement('style');
  style.textContent = css;
  document.head.append(style);
  const chat = document.createElement('div');
  chat.className = 'ss-chat'; chat.id = 'ss-chat'; chat.hidden = true;
  chat.setAttribute('role', 'dialog'); chat.setAttribute('aria-labelledby', 'ss-h');
  chat.innerHTML = `<div class="ss-top"><i aria-hidden="true">S</i><div><b id="ss-h">Ask Southsites</b><small>AI assistant (Claude). Answers can be wrong.</small></div><button class="ss-x" type="button" aria-label="Close chat">${svg('x')}</button></div>
    <div class="ss-msgs" role="log" aria-live="polite"></div><div class="ss-chips"></div>
    <form class="ss-ask"><label class="ss-sr" for="ss-q">Your question</label><input id="ss-q" autocomplete="off" enterkeyhint="send" maxlength="500" placeholder="Ask about prices, the preview, add-ons"><button type="submit" aria-label="Send">${svg('send')}</button></form>`;
  document.body.append(chat);
  const msgs = chat.querySelector('.ss-msgs'), chipBox = chat.querySelector('.ss-chips'), form = chat.querySelector('form'), q = form.querySelector('input');

  // the button: an icon in the bottom bar next to Text and Call, or on its own where a page has no bar
  const btn = document.createElement('button');
  btn.type = 'button'; btn.innerHTML = svg('chat');
  btn.setAttribute('aria-label', 'Ask the Southsites AI assistant'); btn.setAttribute('aria-expanded', 'false'); btn.setAttribute('aria-controls', 'ss-chat');
  const dock = document.getElementById('dock');
  if (dock) { btn.className = 'btn btn-line ic ss-open'; dock.children[0].after(btn); } else { btn.className = 'btn btn-main ic ss-open ss-float'; document.body.append(btn); }

  const TYPING = '<span class="ss-typing" aria-label="Typing"><i></i><i></i><i></i></span>';
  function add(cls, html) {
    const m = document.createElement('div');
    m.className = 'ss-msg ' + cls;
    if (cls === 'me') m.textContent = html; else m.innerHTML = html;  // built-in replies are our own strings, never the visitor's
    msgs.append(m); msgs.scrollTop = msgs.scrollHeight;
    return m;
  }
  const plain = (html) => { const d = document.createElement('div'); d.innerHTML = html; return d.textContent; };
  const hist = [], GO = { preview: ['#quote', 'Get my free preview'], pricing: ['/pricing/', 'See prices'], text: ['sms:+18254615061', 'Text 825-461-5061'], samples: ['#samples', 'See the samples'] };
  let live = !!CHAT_URL, busy = false, told = false;
  function show(m, raw, done) {
    // the AI's reply goes in as text, never HTML. a [[tag]] at the end becomes a link and a half-arrived one stays hidden
    m.textContent = raw.replace(/\[\[\w+\]\]/g, '').replace(/\[\[?\w*\]?$/, '').replace(/\*\*?/g, '')
      .replace(/(\d)\s*[–—]\s*(\d)/g, '$1-$2').replace(/\s*[–—]\s*/g, ', ').trim();
    if (done) for (const [, k] of raw.matchAll(/\[\[(\w+)\]\]/g)) if (GO[k]) { const a = document.createElement('a'); [a.href, a.textContent] = GO[k]; m.append('\n', a); }
    msgs.scrollTop = msgs.scrollHeight;
  }
  async function askLive(text) {
    const m = add('bot ai', TYPING);
    msgs.setAttribute('aria-busy', 'true');  // screen readers get the reply once it's whole, not word by word
    let raw = '';
    const stop = new AbortController(), slow = setTimeout(() => stop.abort(), 5000);
    try {
      // plain text (the server reads it as JSON), so the browser doesn't spend a round trip asking permission first
      const r = await fetch(CHAT_URL, { method: 'POST', signal: stop.signal, body: JSON.stringify({ bot: 'southsites', messages: [...hist, { role: 'user', content: text }].slice(-11) }) });
      if (r.status === 429 || r.status === 503) live = false;  // out of today's budget, too many questions this hour, or switched off
      if (!r.ok || !r.body) throw new Error(r.status);
      const rd = r.body.pipeThrough(new TextDecoderStream()).getReader();
      for (let c; !(c = await rd.read()).done;) { clearTimeout(slow); raw += c.value; if (raw.trim()) show(m, raw, false); }
    } catch (e) {}  // whatever it managed to say stays; with nothing, the built-in answer takes over
    clearTimeout(slow);
    msgs.removeAttribute('aria-busy');
    if (!raw.trim()) { m.remove(); return false; }
    show(m, raw, true);
    hist.push({ role: 'user', content: text }, { role: 'assistant', content: raw.trim() });
    return true;
  }
  // the chips have their answers ready, so they reply at once; typed questions go to the AI
  async function ask(text, quick) {
    text = text.trim().slice(0, 500);
    if (!text || busy) return;
    busy = true;
    add('me', text);
    if (live && !quick && await askLive(text)) { busy = false; return; }
    let reply = answer(text);
    hist.push({ role: 'user', content: text }, { role: 'assistant', content: plain(reply) });
    if (!quick) { reply += `<small class="from">${live || told ? 'Built-in answer' : 'The live AI is resting for now, so this is a built-in answer.'}</small>`; told ||= !live; }
    add('bot', reply);
    busy = false;
  }
  function open() {
    if (!msgs.childElementCount) {
      add('bot', 'Hi! I\'m the AI assistant for Southsites, the same kind of chat you can add to your own site. Ask about prices, the free preview or what\'s included. What you type goes to Anthropic\'s Claude to answer, so leave out personal details.');
      CHIPS.forEach((c) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = c; b.onclick = () => ask(c, true); chipBox.append(b); });
      const l = document.createElement('link'); l.rel = 'preconnect'; l.href = new URL(CHAT_URL).origin; l.crossOrigin = ''; document.head.append(l);
    }
    chat.hidden = false; btn.setAttribute('aria-expanded', 'true');
    q.focus();
  }
  function close(refocus) {
    chat.hidden = true; btn.setAttribute('aria-expanded', 'false');
    if (refocus) btn.focus();
  }
  btn.addEventListener('click', () => (chat.hidden ? open() : close(true)));
  chat.querySelector('.ss-x').addEventListener('click', () => close(true));
  chat.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(true); });
  form.addEventListener('submit', (e) => { e.preventDefault(); if (busy) return; ask(q.value); q.value = ''; });
  // a link in a reply takes you there and the chat steps out of the way; the preview link also puts the cursor in the form
  msgs.addEventListener('click', (e) => {
    const a = e.target.closest('a');
    if (!a) return;
    close(false);
    const quote = document.getElementById('quote');
    if (a.getAttribute('href') === '#quote' && quote) {
      e.preventDefault();
      quote.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' });
      setTimeout(() => quote.querySelector('input:not([type=hidden])')?.focus({ preventScroll: true }), 600);
    }
  });
})();
