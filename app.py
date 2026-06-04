# app.py
# =======
# Main Flask application.
#
# Run locally:   python app.py
# Run Railway:   gunicorn app:app  (via Procfile)

import uuid
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from config.settings   import Config
from bot.spiritual_guide import SpiritualGuide

app   = Flask(__name__)
app.secret_key = Config.SECRET_KEY
CORS(app, resources={r"/api/*": {"origins": ["https://iskconbooks.in", "http://iskconbooks.in"]}})
guide = SpiritualGuide()
print("🙏 Spiritual Guide ready. Hare Krishna!")


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
        'reply':    result['wisdom'],
        'book':     result.get('book'),
        'language': result.get('language', 'english'),
        'blocked':  result.get('blocked', False),
        'status':   'success'
    })


@app.route('/api/bot/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'msg': 'Hare Krishna 🙏'})


# ════════════════════════════════════════
# DEMO PAGE (local testing)
# ════════════════════════════════════════

@app.route('/bot')
def bot_page():
    return render_template('bot_demo.html')


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
