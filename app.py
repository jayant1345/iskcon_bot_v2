# app.py
# =======
# Main Flask application.
#
# Run locally:   python app.py
# Run Railway:   gunicorn app:app  (via Procfile)

import uuid
from flask import Flask, request, jsonify, render_template, redirect, make_response
from flask_cors import CORS
from config.settings     import Config
from bot.spiritual_guide import SpiritualGuide
from bot.admin_sessions  import (
    init_table, create_session, refresh_session,
    end_session, get_active_sessions, get_recent_logins,
    SESSION_COOKIE,
)

app   = Flask(__name__)
app.secret_key = Config.SECRET_KEY
CORS(app, resources={r"/api/*": {"origins": ["https://iskconbooks.in", "http://iskconbooks.in"]}})
guide = SpiritualGuide()
init_table()   # ensure admin_sessions table exists
print("🙏 Spiritual Guide ready. Hare Krishna!")


def _get_admin_token() -> str:
    return request.cookies.get(SESSION_COOKIE, "")

def _admin_required():
    """Returns None if authenticated, else a redirect response."""
    token = _get_admin_token()
    if token and refresh_session(token):
        return None
    return redirect("/admin/login")


# ════════════════════════════════════════
# YOUR EXISTING ROUTES
# ════════════════════════════════════════

@app.route('/')
def home():
    from flask import redirect
    return redirect('/bot')


# ════════════════════════════════════════
# BOT API ROUTES
# ════════════════════════════════════════

@app.route('/api/bot/greet', methods=['GET'])
def greet():
    """
    Called when chat widget opens.
    Optional: pass ?lang=hi or ?lang=gu to force language.
    Or pass initial text for auto-detection.
    """
    hint = request.args.get('hint', '')    # optional first words for language detection
    result = guide.get_greeting(hint)
    return jsonify({
        'session_id': result['session_id'],
        'message':    result['message'],
        'language':   result['language'],
        'status':     'success'
    })


@app.route('/api/bot/chat', methods=['POST'])
def chat():
    """
    Main chat endpoint.

    Request JSON:
    {
        "message":    "user text in any language",
        "session_id": "uuid from /greet"
    }

    Response JSON:
    {
        "reply":    "guru response in user's language",
        "book":     { title, url, why, suggestion_text } or null,
        "language": "hindi" | "gujarati" | "english" | "hinglish",
        "status":   "success"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data', 'status': 'error'}), 400

    message    = data.get('message', '').strip()
    session_id = data.get('session_id', str(uuid.uuid4()))

    if not message:
        return jsonify({'error': 'Empty message', 'status': 'error'}), 400

    result = guide.respond(message=message, session_id=session_id)

    return jsonify({
        'reply':          result['wisdom'],
        'book':           result.get('book'),
        'language':       result.get('language', 'english'),
        'blocked':        result.get('blocked', False),
        'scripture_ref':  result.get('scripture_ref'),   # {"source", "chapter", "verse"}
        'status':         'success'
    })


@app.route('/api/bot/health', methods=['GET'])
def health():
    from bot.retriever import get_chunk_count
    count = get_chunk_count()
    if count == 0:
        print("⚠️  WARNING: scripture_chunks table is EMPTY — PDF not ingested!")
    return jsonify({'status': 'healthy', 'msg': 'Hare Krishna 🙏', 'chunks_in_db': count})


# ════════════════════════════════════════
# DEBUG ROUTES (check RAG is working)
# ════════════════════════════════════════

@app.route('/api/debug/chunks', methods=['GET'])
def debug_chunks():
    """Check how many scripture chunks are in the DB."""
    from bot.retriever import get_chunk_count
    count = get_chunk_count()
    status = "✅ DB has data" if count > 0 else "❌ DB is EMPTY — run ingest_pdf.py"
    return jsonify({'total_chunks': count, 'status': status})


@app.route('/api/debug/retrieve', methods=['GET'])
def debug_retrieve():
    """Test retrieval. Usage: /api/debug/retrieve?q=your+question"""
    from bot.retriever import retrieve_relevant_chunks
    q = request.args.get('q', 'what is dharma')
    chunks = retrieve_relevant_chunks(q, [])
    return jsonify({
        'query':        q,
        'chunks_found': len(chunks),
        'chunks': [
            {
                'source':     c['source'],
                'chapter':    c['chapter'],
                'verse':      c['verse'],
                'similarity': round(c['similarity'], 3),
                'preview':    c['text'][:120] + '...'
            }
            for c in chunks
        ]
    })


@app.route('/api/debug/rag', methods=['GET'])
def debug_rag():
    """
    Shows the EXACT context that gets sent to Claude for a question.
    Use this to verify RAG is working and references are correct.
    Usage: /api/debug/rag?q=what+is+karma
    """
    from bot.retriever import retrieve_relevant_chunks, format_chunks_for_prompt
    from bot.intent_detector import detect_intent
    q      = request.args.get('q', 'what is karma')
    intent = detect_intent(q)
    chunks = retrieve_relevant_chunks(q, intent['themes'])
    context = format_chunks_for_prompt(chunks)
    return jsonify({
        'query':          q,
        'themes_detected': intent['themes'],
        'chunks_found':   len(chunks),
        'similarity_scores': [round(c['similarity'], 3) for c in chunks],
        'references':     [
            f"Ch {c['chapter']} V {c['verse']}" if c['chapter'] else 'no ref'
            for c in chunks
        ],
        'context_sent_to_claude': context,
    })


# ════════════════════════════════════════
# DEMO PAGE (local testing)
# ════════════════════════════════════════

@app.route('/bot')
def bot_page():
    return render_template('bot_demo.html')


# ════════════════════════════════════════
# ADMIN ROUTES
# ════════════════════════════════════════

@app.route('/admin/login', methods=['GET'])
def admin_login_page():
    return render_template('admin_login.html')


@app.route('/admin/login', methods=['POST'])
def admin_login():
    password = request.form.get('password', '')
    if password != Config.ADMIN_PASSWORD:
        return render_template('admin_login.html', error="Wrong password. Hare Krishna 🙏")

    ip         = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    user_agent = request.headers.get('User-Agent', '')
    token      = create_session(ip, user_agent)

    resp = make_response(redirect('/admin'))
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite='Lax', max_age=60 * 60 * 8)
    return resp


@app.route('/admin')
def admin_dashboard():
    redir = _admin_required()
    if redir:
        return redir

    active  = get_active_sessions()
    history = get_recent_logins(20)
    return render_template('admin_dashboard.html',
                           active_sessions=active,
                           recent_logins=history,
                           active_count=len(active))


@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    token = _get_admin_token()
    if token:
        end_session(token)
    resp = make_response(redirect('/admin/login'))
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.route('/admin/api/sessions')
def admin_api_sessions():
    """JSON endpoint — call from monitoring tools."""
    redir = _admin_required()
    if redir:
        return jsonify({'error': 'Unauthorized'}), 401
    active = get_active_sessions()
    return jsonify({'active_count': len(active), 'sessions': active})


# ════════════════════════════════════════
# ERROR HANDLERS
# ════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Server error'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
