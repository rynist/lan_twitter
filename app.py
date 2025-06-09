# app.py
import datetime
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
from collections import Counter

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

def get_tweet(tweet_id):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT * FROM tweets WHERE id=?', (tweet_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

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

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

# Ensure the database schema exists when the application starts
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
