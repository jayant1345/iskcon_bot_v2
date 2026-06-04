/**
 * static/js/spiritual_bot_widget.js
 * ====================================
 * Floating chat widget — add to ANY page with one line:
 * <script src="/static/js/spiritual_bot_widget.js"></script>
 *
 * Auto-detects language. Works in English, Hindi, Gujarati, Hinglish.
 */
(function () {
    'use strict';

    let sessionId = null, waiting = false, open = false;

    const LANG_LABELS = {
        english: 'English', hindi: 'हिंदी',
        gujarati: 'ગુજરાતી', hinglish: 'Hinglish', bengali: 'বাংলা'
    };

    // ── Styles ──────────────────────────────────────────────
    const style = document.createElement('style');
    style.textContent = `
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600&family=Crimson+Pro:wght@300;400&display=swap');

    #isb-btn {
        position:fixed; bottom:22px; right:22px;
        width:58px; height:58px;
        background:linear-gradient(135deg,#c8923a,#7a4010);
        border-radius:50%; cursor:pointer;
        display:flex; align-items:center; justify-content:center;
        font-size:1.4rem;
        box-shadow:0 4px 18px rgba(200,146,58,0.5);
        z-index:9999; border:none;
        transition:transform .2s,box-shadow .2s;
    }
    #isb-btn:hover{transform:scale(1.08);box-shadow:0 6px 26px rgba(200,146,58,0.7);}
    #isb-btn .isb-tip{
        position:absolute; bottom:110%; right:0; margin-bottom:6px;
        background:rgba(13,10,7,.92); color:#e8d5b0;
        font-family:'Crimson Pro',serif; font-size:.72rem;
        white-space:nowrap; padding:5px 10px; border-radius:7px;
        border:1px solid rgba(200,146,58,.3); pointer-events:none;
    }
    #isb-win {
        position:fixed; bottom:92px; right:22px;
        width:350px; max-height:540px;
        background:#0b0804;
        border:1px solid rgba(200,146,58,.22);
        border-radius:16px;
        display:flex; flex-direction:column; overflow:hidden;
        box-shadow:0 8px 36px rgba(0,0,0,.6);
        z-index:9998;
        transform:scale(.94) translateY(10px); opacity:0;
        transition:transform .24s ease,opacity .24s ease;
        pointer-events:none;
    }
    #isb-win.open{transform:scale(1) translateY(0);opacity:1;pointer-events:all;}
    .isb-head{
        background:linear-gradient(135deg,rgba(200,146,58,.12),rgba(150,70,15,.08));
        border-bottom:1px solid rgba(200,146,58,.18);
        padding:12px 15px; display:flex; align-items:center; gap:10px;
    }
    .isb-av{
        width:36px;height:36px;
        background:linear-gradient(135deg,#c8923a,#7a4010);
        border-radius:50%;display:flex;align-items:center;justify-content:center;
        font-size:1rem;flex-shrink:0;
    }
    .isb-ttl{font-family:'Cormorant Garamond',serif;font-size:.92rem;color:#e8d5b0;}
    .isb-sub{font-size:.65rem;color:#5a4530;font-family:'Crimson Pro',serif;}
    .isb-langbadge{font-size:.6rem;color:#4a3820;text-transform:uppercase;letter-spacing:.07em;transition:all .3s;}
    .isb-close{
        margin-left:auto;background:none;border:none;
        color:#3a2a1a;cursor:pointer;font-size:1rem;
        padding:4px;transition:color .2s;
    }
    .isb-close:hover{color:#c8923a;}
    .isb-msgs{
        flex:1;overflow-y:auto;padding:14px;
        display:flex;flex-direction:column;gap:11px;
        max-height:360px;scroll-behavior:smooth;
    }
    .isb-msgs::-webkit-scrollbar{width:3px;}
    .isb-msgs::-webkit-scrollbar-thumb{background:rgba(200,146,58,.2);border-radius:2px;}
    .isb-m{max-width:90%;animation:isbFade .24s ease;}
    @keyframes isbFade{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:translateY(0)}}
    .isb-m.bot{align-self:flex-start;}
    .isb-m.usr{align-self:flex-end;}
    .isb-bbl{padding:10px 13px;border-radius:12px;font-family:'Crimson Pro',serif;font-size:.87rem;line-height:1.65;}
    .isb-m.bot .isb-bbl{
        background:rgba(200,146,58,.07);border:1px solid rgba(200,146,58,.13);
        border-bottom-left-radius:3px;color:#e0ceaa;font-style:italic;
    }
    .isb-m.usr .isb-bbl{
        background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);
        border-bottom-right-radius:3px;color:#b0a07a;
    }
    .isb-book{
        align-self:flex-start;max-width:90%;
        background:rgba(200,146,58,.05);border:1px solid rgba(200,146,58,.2);
        border-radius:11px;padding:11px 13px;
        animation:isbFade .3s ease .3s both;
    }
    .isb-blbl{font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;color:#c8923a;margin-bottom:5px;font-family:'Crimson Pro',serif;}
    .isb-bttl{font-family:'Cormorant Garamond',serif;font-size:.88rem;color:#e8d5b0;margin-bottom:3px;}
    .isb-bwhy{font-size:.74rem;color:#5a4530;font-style:italic;margin-bottom:8px;font-family:'Crimson Pro',serif;line-height:1.4;}
    .isb-burl{
        display:inline-block;
        background:rgba(200,146,58,.12);border:1px solid rgba(200,146,58,.28);
        color:#c8923a;text-decoration:none;
        font-size:.7rem;padding:4px 12px;border-radius:16px;
        font-family:'Crimson Pro',serif;transition:background .2s;
    }
    .isb-burl:hover{background:rgba(200,146,58,.22);}
    .isb-typ{
        align-self:flex-start;display:none;gap:4px;align-items:center;
        padding:9px 13px;
        background:rgba(200,146,58,.07);border:1px solid rgba(200,146,58,.13);
        border-radius:12px;border-bottom-left-radius:3px;
    }
    .isb-typ.show{display:flex;}
    .isb-d{width:5px;height:5px;background:#c8923a;border-radius:50%;animation:isbB 1.4s ease-in-out infinite;}
    .isb-d:nth-child(2){animation-delay:.2s;}.isb-d:nth-child(3){animation-delay:.4s;}
    @keyframes isbB{0%,60%,100%{transform:translateY(0);opacity:.4}30%{transform:translateY(-5px);opacity:1}}
    .isb-inp-row{
        border-top:1px solid rgba(200,146,58,.12);
        padding:11px 13px;display:flex;gap:8px;align-items:flex-end;
        background:rgba(0,0,0,.18);
    }
    .isb-txt{
        flex:1;background:rgba(255,255,255,.03);
        border:1px solid rgba(200,146,58,.15);border-radius:10px;
        padding:8px 12px;color:#e8d5b0;
        font-family:'Crimson Pro',serif;font-size:.85rem;
        resize:none;outline:none;line-height:1.5;max-height:76px;
    }
    .isb-txt::placeholder{color:#1e1610;}
    .isb-txt:focus{border-color:rgba(200,146,58,.32);}
    .isb-snd{
        width:36px;height:36px;
        background:linear-gradient(135deg,#c8923a,#7a4010);
        border:none;border-radius:50%;cursor:pointer;
        display:flex;align-items:center;justify-content:center;
        flex-shrink:0;transition:transform .15s;
        box-shadow:0 2px 10px rgba(200,146,58,.3);
    }
    .isb-snd:hover{transform:scale(1.07);}
    .isb-snd svg{width:14px;height:14px;fill:white;}
    .isb-foot{
        padding:5px 13px 8px;text-align:center;
        font-size:.62rem;color:#1e1610;
        background:rgba(0,0,0,.18);font-family:'Crimson Pro',serif;
    }
    .isb-foot a{color:#2a2018;text-decoration:none;}
    .isb-foot a:hover{color:#c8923a;}
    @media(max-width:400px){
        #isb-win{width:calc(100vw - 18px);right:9px;bottom:84px;}
    }`;
    document.head.appendChild(style);

    // ── HTML ─────────────────────────────────────────────────
    document.body.insertAdjacentHTML('beforeend', `
    <button id="isb-btn" onclick="isbToggle()">
        🙏 <span class="isb-tip">Ask the Spiritual Guide</span>
    </button>
    <div id="isb-win">
        <div class="isb-head">
            <div class="isb-av">🙏</div>
            <div>
                <div class="isb-ttl">Spiritual Guide</div>
                <div class="isb-sub">Gita · Bhagavatam · हिंदी · ગુજરાતી</div>
            </div>
            <div style="margin-left:auto;display:flex;flex-direction:column;align-items:flex-end;gap:3px;">
                <div style="width:7px;height:7px;background:#5cb88a;border-radius:50%;box-shadow:0 0 6px rgba(92,184,138,.5);"></div>
                <span class="isb-langbadge" id="isb-lb">—</span>
            </div>
            <button class="isb-close" onclick="isbToggle()">✕</button>
        </div>
        <div class="isb-msgs" id="isb-msgs">
            <div class="isb-typ" id="isb-typ">
                <div class="isb-d"></div><div class="isb-d"></div><div class="isb-d"></div>
            </div>
        </div>
        <div class="isb-inp-row">
            <textarea class="isb-txt" id="isb-txt"
                placeholder="Any language... / कोई भी भाषा... / કોઈ પણ ભાષા..."
                rows="1"></textarea>
            <button class="isb-snd" onclick="isbSend()">
                <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
            </button>
        </div>
        <div class="isb-foot">
            <a href="https://iskconbooks.in" target="_blank">iskconbooks.in</a> · Hare Krishna 🙏
        </div>
    </div>`);

    // ── Wire up textarea ──────────────────────────────────────
    const txt = document.getElementById('isb-txt');
    txt.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 76) + 'px';
    });
    txt.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); isbSend(); }
    });

    // ── Public functions ──────────────────────────────────────
    window.isbToggle = function () {
        open = !open;
        document.getElementById('isb-win').classList.toggle('open', open);
        if (open && !sessionId) isbInit();
    };

    async function isbInit() {
        try {
            const r    = await fetch('/api/bot/greet');
            const data = await r.json();
            sessionId  = data.session_id;
            updateLang(data.language);
            addBot(data.message, null);
        } catch {
            sessionId = 'w-' + Date.now();
            addBot('Hare Krishna 🙏\n\nDear soul, what is in your heart today?', null);
        }
    }

    window.isbSend = async function () {
        const msg = txt.value.trim();
        if (!msg || waiting) return;
        addUsr(msg);
        txt.value = ''; txt.style.height = 'auto';
        waiting = true; showTyp(true);

        try {
            const r    = await fetch('/api/bot/chat', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ message: msg, session_id: sessionId })
            });
            const data = await r.json();
            showTyp(false);
            updateLang(data.language);
            addBot(data.reply, data.book);
        } catch {
            showTyp(false);
            addBot('Dear one, please try again in a moment 🙏', null);
        }
        waiting = false;
    };

    function addBot(text, book) {
        const area = document.getElementById('isb-msgs');
        const typ  = document.getElementById('isb-typ');
        const d    = document.createElement('div');
        d.className = 'isb-m bot';
        d.innerHTML = `<div class="isb-bbl">${text.replace(/\n/g,'<br>').replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>')}</div>`;
        area.insertBefore(d, typ);
        if (book) {
            setTimeout(() => {
                const c = document.createElement('div');
                c.className = 'isb-book';
                c.innerHTML = `
                    <div class="isb-blbl">📖 Srila Prabhupada suggests</div>
                    <div class="isb-bttl">${book.title}</div>
                    <div class="isb-bwhy">${book.why}</div>
                    <a class="isb-burl" href="${book.url}" target="_blank">Read this book →</a>`;
                area.insertBefore(c, typ);
                scroll();
            }, 600);
        }
        scroll();
    }

    function addUsr(text) {
        const area = document.getElementById('isb-msgs');
        const typ  = document.getElementById('isb-typ');
        const d    = document.createElement('div');
        d.className = 'isb-m usr';
        d.innerHTML = `<div class="isb-bbl">${text}</div>`;
        area.insertBefore(d, typ);
        scroll();
    }

    function showTyp(s)   { document.getElementById('isb-typ').classList.toggle('show', s); if (s) scroll(); }
    function updateLang(l){ if (l) document.getElementById('isb-lb').textContent = LANG_LABELS[l] || l; }
    function scroll()     { const a = document.getElementById('isb-msgs'); setTimeout(() => a.scrollTop = a.scrollHeight, 55); }

})();
