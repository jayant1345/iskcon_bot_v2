# 🕉️ ISKCON Spiritual Bot v2
### Multilingual · Bhagavat Gita RAG · iskconbooks.in

Supports: **English · हिंदी · ગુજરાતી · Hinglish**
Upload any ONE PDF book → Bot answers in any language.

---

## 📁 FOLDER STRUCTURE

```
iskcon_bot_v2/
│
├── app.py                             ← Main Flask app
├── Procfile                           ← Railway: gunicorn command
├── requirements.txt
├── .env.example                       ← Copy to .env
├── .gitignore
│
├── config/
│   ├── __init__.py
│   └── settings.py                    ← All config from .env
│
├── bot/
│   ├── __init__.py
│   ├── spiritual_guide.py             ← HEART: guru + RAG + multilingual
│   ├── language_detector.py           ← Detects Hindi/Gujarati/English FREE
│   ├── input_guard.py                 ← Blocks inappropriate input
│   ├── intent_detector.py             ← Detects emotion + theme
│   ├── retriever.py                   ← pgvector similarity search
│   ├── book_recommender.py            ← ISKCON book suggestions
│   ├── database.py                    ← Creates tables (run ONCE)
│   └── ingestion/
│       └── ingest_pdf.py              ← Upload any PDF book
│
├── templates/
│   ├── index.html                     ← Your existing homepage
│   └── bot_demo.html                  ← Standalone multilingual bot page
│
└── static/
    └── js/
        └── spiritual_bot_widget.js    ← Floating widget for any page
```

---

## 🚀 LOCAL SETUP — STEP BY STEP

### Step 1: PostgreSQL + pgvector

**Mac:**
```bash
brew install postgresql
brew services start postgresql
createdb iskcon_bot
psql iskcon_bot -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**Ubuntu:**
```bash
sudo apt install postgresql postgresql-contrib
sudo -u postgres createdb iskcon_bot
sudo -u postgres psql iskcon_bot -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

---

### Step 2: Python Environment

```bash
cd iskcon_bot_v2
python -m venv venv
source venv/bin/activate       # Mac/Linux
# venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

---

### Step 3: Configure .env

```bash
cp .env.example .env
# Now edit .env and fill:
```

```env
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxx
DATABASE_URL=postgresql://postgres:yourpass@localhost:5432/iskcon_bot
FLASK_SECRET_KEY=any-random-string
FLASK_ENV=development
PORT=5000
ISKCON_BOOKS_URL=https://iskconbooks.in
```

---

### Step 4: Setup Database

```bash
python bot/database.py
```

Expected output:
```
🔧 Setting up database...
✅ pgvector enabled
✅ scripture_chunks table ready
✅ Vector index ready
✅ book_recommendations table ready
✅ chat_sessions table ready
✅ Books seeded
🙏 Database ready! Hare Krishna!
```

---

### Step 5: Upload Your PDF Book

Place your PDF in the project folder, then run:

```bash
# Upload Bhagavad Gita As It Is
python bot/ingestion/ingest_pdf.py \
    --pdf "Bhagavad_Gita_As_It_Is.pdf" \
    --source "Bhagavat Gita"
```

```bash
# Upload Shrimad Bhagavatam (any volume)
python bot/ingestion/ingest_pdf.py \
    --pdf "Shrimad_Bhagavatam_Vol1.pdf" \
    --source "Shrimad Bhagavatam"
```

You can run this for multiple PDFs — all go into the same database.

Expected output:
```
🕉️  Starting ingestion of: Bhagavat Gita
📄 Reading PDF: Bhagavad_Gita_As_It_Is.pdf
✅ Extracted 892 pages with content
✂️  Chunking text...
✅ Created 3568 chunks from 892 pages
🧠 Loading embedding model...
✅ Embedding model ready
📥 Storing 3568 chunks into pgvector...
  ✅ 3568/3568 chunks stored...

🙏 Ingestion complete!
   Source  : Bhagavat Gita
   Pages   : 892
   Chunks  : 3568
```

---

### Step 6: Run Locally

```bash
python app.py
```

Open browser:
- **Bot page:** http://localhost:5000/bot
- **Your site:** http://localhost:5000/

---

## 🌍 MULTILINGUAL TESTING

Try these questions to test language detection:

| Language | Test Question |
|---|---|
| English | "I feel lost in life" |
| Hindi | "मुझे जीवन में कोई उद्देश्य नहीं दिखता" |
| Gujarati | "મને જીવનમાં કોઈ દિશા નથી મળી" |
| Hinglish | "Mujhe kuch samajh nahi aa raha, kya karu main" |

Bot auto-detects and replies in same language 🙏

---

## 🌐 RAILWAY DEPLOYMENT

### Step 1: Push to GitHub
```bash
git init
git add .
git commit -m "ISKCON Spiritual Bot v2"
git remote add origin https://github.com/yourname/iskcon-bot
git push -u origin main
```

### Step 2: Add PostgreSQL on Railway
- Railway dashboard → **+ New** → **Database** → **PostgreSQL**
- `DATABASE_URL` is auto-added to your environment

### Step 3: Connect GitHub
- Railway → your service → **Settings** → **Source** → GitHub repo
- Railway auto-deploys on every `git push`

### Step 4: Set Environment Variables
In Railway → **Variables**:
```
ANTHROPIC_API_KEY  = sk-ant-xxxxx
FLASK_SECRET_KEY   = your-random-secret
FLASK_ENV          = production
ISKCON_BOOKS_URL   = https://iskconbooks.in
```

### Step 5: Run DB Setup + Ingestion on Railway
Railway → your service → **Shell**:
```bash
python bot/database.py
python bot/ingestion/ingest_pdf.py --pdf "Bhagavad_Gita.pdf" --source "Bhagavat Gita"
```

---

## 🔌 ADD WIDGET TO YOUR SITE

### Floating button (one line):
```html
<!-- Add before </body> on any page -->
<script src="/static/js/spiritual_bot_widget.js"></script>
```

### Full page link:
```html
<a href="/bot">Ask the Spiritual Guide 🙏</a>
```

### Inline iframe:
```html
<iframe src="/bot" width="500" height="640"
        style="border:none;border-radius:16px;"></iframe>
```

---

## 💰 COST ESTIMATE

| Item | Cost |
|---|---|
| Railway PostgreSQL | ~$5/month |
| Embedding model | FREE (local) |
| Language detection | FREE (local) |
| Browser voice | FREE |
| Claude Haiku (500 users/day) | ~₹1,500-2,000/month |
| **Total** | **~₹2,500-3,000/month** |

---

## ➕ ADDING MORE BOOKS LATER

```bash
# Any time, just run for new PDF:
python bot/ingestion/ingest_pdf.py \
    --pdf "Nectar_of_Devotion.pdf" \
    --source "Nectar of Devotion"

# Bot immediately knows this new book
# No restart needed
```

---

## 🙏 Hare Krishna!

May every soul who visits iskconbooks.in
find Krishna's wisdom in their own language.
