# app.py
import datetime
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
from threading import Thread
import llm_bot
from collections import Counter

PROMPT_DB_FILE = 'prompts.db'

DEFAULT_PERSONAS = [
    (
        "TechOptimist",
        "You are a cheerful tech optimist. Based on the recent conversation, either post a new hopeful thought, reply to someone with encouragement, or quote a tweet to add a positive spin.",
    ),
    (
        "GrumpyCatBot",
        "You are a grumpy cat. Looking at these recent human tweets, either complain about something new, sarcastically reply to one of them, or quote one to mock it.",
    ),
    (
        "HistoryBuff",
        "You are a history enthusiast. Looking at the recent conversation, either share a new historical fact, reply to a tweet with a relevant fact, or quote one to provide historical context.",
    ),
]

SYSTEM_INSTRUCTIONS = """Here is the recent conversation:\n{context}\n\nYou must decide on one of three actions: TWEET, REPLY, or QUOTE.\nYour response MUST be in the following format, with each part on a new line:\nACTION: [Your chosen action: TWEET, REPLY, or QUOTE]\nID: [The ID of the tweet to REPLY or QUOTE. Use 0 for a new TWEET.]\nCONTENT: [The text of your tweet, reply, or quote. Must be under 280 characters.]\n\nExample for a reply:\nACTION: REPLY\nID: 3\nCONTENT: That's a fascinating point about ancient Rome!\n\nExample for a new tweet:\nACTION: TWEET\nID: 0\nCONTENT: Just learned that Vikings used sunstones for navigation. How cool is that?\n"""

app = Flask(__name__, static_folder='static')

DB_FILE = 'tweets.db'

def init_db():
    """Create the SQLite database and tweets table if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tweets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            replying_to INTEGER,
            quoting_tweet_id INTEGER,
            like_count INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()

def load_tweets():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT * FROM tweets')
    tweets = [dict(row) for row in cur.fetchall()]
    conn.close()
    return tweets

def insert_tweet(tweet):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO tweets (username, text, timestamp, replying_to, quoting_tweet_id, like_count) VALUES (?, ?, ?, ?, ?, ?)',
        (
            tweet['username'],
            tweet['text'],
            tweet['timestamp'],
            tweet['replying_to'],
            tweet['quoting_tweet_id'],
            tweet['like_count'],
        ),
    )
    conn.commit()
    tweet_id = cur.lastrowid
    conn.close()
    return tweet_id

def delete_tweet_db(tweet_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('DELETE FROM tweets WHERE id=?', (tweet_id,))
    conn.commit()
    rows = cur.rowcount
    conn.close()
    return rows > 0

def get_tweet(tweet_id):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT * FROM tweets WHERE id=?', (tweet_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def init_prompt_db():
    conn = sqlite3.connect(PROMPT_DB_FILE)
    cur = conn.cursor()
    # Personas table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS personas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            prompt TEXT NOT NULL
        )
        """
    )
    # System prompt table with a single row
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS system_prompt (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            instructions TEXT NOT NULL
        )
        """
    )
    # Table to log LLM token usage
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            persona TEXT
        )
        """
    )
    conn.commit()

    # Seed personas if empty
    cur.execute("SELECT COUNT(*) FROM personas")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO personas (name, prompt) VALUES (?, ?)",
            DEFAULT_PERSONAS,
        )
        conn.commit()

    # Ensure system prompt row exists
    cur.execute("SELECT COUNT(*) FROM system_prompt")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO system_prompt (id, instructions) VALUES (1, ?)",
            (SYSTEM_INSTRUCTIONS,),
        )
        conn.commit()

    conn.close()

def load_personas():
    conn = sqlite3.connect(PROMPT_DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT name, prompt FROM personas")
    personas = [dict(row) for row in cur.fetchall()]
    conn.close()
    return personas

def load_system_prompt():
    conn = sqlite3.connect(PROMPT_DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT instructions FROM system_prompt WHERE id=1")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else SYSTEM_INSTRUCTIONS

def update_system_prompt_db(instructions):
    conn = sqlite3.connect(PROMPT_DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "UPDATE system_prompt SET instructions=? WHERE id=1",
        (instructions,),
    )
    conn.commit()
    conn.close()
    global SYSTEM_INSTRUCTIONS
    SYSTEM_INSTRUCTIONS = instructions

def log_token_usage(prompt_tokens, completion_tokens, total_tokens, persona):
    conn = sqlite3.connect(PROMPT_DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO token_usage (timestamp, prompt_tokens, completion_tokens, total_tokens, persona) VALUES (?, ?, ?, ?, ?)",
        (
            datetime.datetime.utcnow().isoformat() + 'Z',
            prompt_tokens,
            completion_tokens,
            total_tokens,
            persona,
        ),
    )
    conn.commit()
    conn.close()

def load_token_usage():
    conn = sqlite3.connect(PROMPT_DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT timestamp, prompt_tokens, completion_tokens, total_tokens, persona FROM token_usage ORDER BY id DESC")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows

def increment_like(tweet_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('UPDATE tweets SET like_count = COALESCE(like_count, 0) + 1 WHERE id=?', (tweet_id,))
    conn.commit()
    conn.close()

def add_interaction_counts(tweets):
    reply_counts = Counter(t['replying_to'] for t in tweets if t.get('replying_to'))
    quote_counts = Counter(t['quoting_tweet_id'] for t in tweets if t.get('quoting_tweet_id'))
    
    for tweet in tweets:
        tweet['reply_count'] = reply_counts.get(tweet['id'], 0)
        tweet['quote_count'] = quote_counts.get(tweet['id'], 0)
    return tweets

@app.route('/api/tweets', methods=['GET'])
def get_tweets():
    all_tweets = load_tweets()
    all_tweets_with_counts = add_interaction_counts(all_tweets)
    
    replying_to_id = request.args.get('replying_to', type=int)
    quoting_id = request.args.get('quoting', type=int)
    
    if replying_to_id:
        filtered_tweets = [t for t in all_tweets_with_counts if t.get('replying_to') == replying_to_id]
    elif quoting_id:
        filtered_tweets = [t for t in all_tweets_with_counts if t.get('quoting_tweet_id') == quoting_id]
    else:
        filtered_tweets = all_tweets_with_counts

    return jsonify(sorted(filtered_tweets, key=lambda t: t['timestamp'], reverse=True))

@app.route('/api/tweets/<int:tweet_id>', methods=['GET'])
def get_tweet_by_id(tweet_id):
    all_tweets = load_tweets()
    all_tweets_with_counts = add_interaction_counts(all_tweets)
    tweet = next((t for t in all_tweets_with_counts if t.get('id') == tweet_id), None)
    if tweet:
        return jsonify(tweet)
    return jsonify({'error': 'Tweet not found'}), 404

@app.route('/api/tweets/<int:tweet_id>', methods=['DELETE'])
def delete_tweet(tweet_id):
    if delete_tweet_db(tweet_id):
        return jsonify({'status': 'deleted'})
    return jsonify({'error': 'Tweet not found'}), 404

@app.route('/api/tweets', methods=['POST'])
def post_tweet():
    tweet_data = request.get_json()
    if not tweet_data or 'username' not in tweet_data or 'text' not in tweet_data:
        return jsonify({'error': 'Missing data'}), 400

    new_tweet = {
        'username': tweet_data['username'],
        'text': tweet_data['text'],
        'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
        'replying_to': tweet_data.get('replying_to', None),
        'quoting_tweet_id': tweet_data.get('quoting_tweet_id', None),
        'like_count': 0,
    }

    new_tweet['id'] = insert_tweet(new_tweet)
    return jsonify(new_tweet), 201

@app.route('/api/tweets/<int:tweet_id>/like', methods=['POST'])
def like_tweet(tweet_id):
    """New endpoint to increment a tweet's like count."""
    tweet = get_tweet(tweet_id)
    if not tweet:
        return jsonify({'error': 'Tweet not found'}), 404

    increment_like(tweet_id)
    updated_tweet = get_tweet(tweet_id)

    tweet_with_counts = add_interaction_counts([updated_tweet])[0]
    return jsonify(tweet_with_counts)

@app.route('/api/personas', methods=['GET'])
def get_personas():
    return jsonify(load_personas())

@app.route('/api/personas', methods=['POST'])
def add_persona():
    data = request.get_json()
    if not data or 'name' not in data or 'prompt' not in data:
        return jsonify({'error': 'Missing data'}), 400
    conn = sqlite3.connect(PROMPT_DB_FILE)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO personas (name, prompt) VALUES (?, ?)",
            (data['name'], data['prompt']),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Persona already exists'}), 400
    conn.close()
    return jsonify({'status': 'added'}), 201

@app.route('/api/personas/<string:name>', methods=['PUT'])
def update_persona(name):
    data = request.get_json()
    if not data or 'name' not in data or 'prompt' not in data:
        return jsonify({'error': 'Missing data'}), 400
    conn = sqlite3.connect(PROMPT_DB_FILE)
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE personas SET name=?, prompt=? WHERE name=?",
            (data['name'], data['prompt'], name),
        )
        if cur.rowcount == 0:
            conn.close()
            return jsonify({'error': 'Persona not found'}), 404
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Persona with that name already exists'}), 400
    conn.close()
    return jsonify({'status': 'updated'})

@app.route('/api/personas/<string:name>', methods=['DELETE'])
def delete_persona(name):
    conn = sqlite3.connect(PROMPT_DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM personas WHERE name=?", (name,))
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Persona not found'}), 404
    conn.close()
    return jsonify({'status': 'deleted'})

@app.route('/api/system_prompt', methods=['GET'])
def get_system_prompt():
    return jsonify({'system_prompt': load_system_prompt()})

@app.route('/api/system_prompt', methods=['POST'])
def set_system_prompt():
    data = request.get_json()
    if not data or 'system_prompt' not in data:
        return jsonify({'error': 'Missing data'}), 400
    update_system_prompt_db(data['system_prompt'])
    return jsonify({'status': 'updated'})

@app.route('/api/token_usage', methods=['GET'])
def get_token_usage():
    return jsonify(load_token_usage())


@app.route('/api/run_bot', methods=['POST'])
def trigger_bot():
    """Start a single LLM bot cycle in a background thread."""
    Thread(target=llm_bot.run_bot).start()
    return jsonify({'status': 'running'}), 202

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/prompts')
def serve_prompts():
    return send_from_directory(app.static_folder, 'prompts.html')

@app.route('/tokens')
def serve_tokens():
    return send_from_directory(app.static_folder, 'tokens.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

# Ensure the database schema exists when the application starts
init_db()
init_prompt_db()
SYSTEM_INSTRUCTIONS = load_system_prompt()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
