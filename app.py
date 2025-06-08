# app.py
import json, datetime
from flask import Flask, request, jsonify, send_from_directory
from collections import Counter

app = Flask(__name__, static_folder='static')
TWEETS_FILE = 'tweets.json'

def load_tweets():
    try:
        with open(TWEETS_FILE, 'r') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_tweets(tweets):
    with open(TWEETS_FILE, 'w') as f: json.dump(tweets, f, indent=2)

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
    if tweet: return jsonify(tweet)
    return jsonify({'error': 'Tweet not found'}), 404

@app.route('/api/tweets', methods=['POST'])
def post_tweet():
    tweet_data = request.get_json()
    if not tweet_data or 'username' not in tweet_data or 'text' not in tweet_data:
        return jsonify({'error': 'Missing data'}), 400

    tweets = load_tweets()
    new_tweet = {
        'id': len(tweets) + 1,
        'username': tweet_data['username'],
        'text': tweet_data['text'],
        'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
        'replying_to': tweet_data.get('replying_to', None),
        'quoting_tweet_id': tweet_data.get('quoting_tweet_id', None),
        'like_count': 0  # Add like_count on creation
    }
    
    tweets.append(new_tweet)
    save_tweets(tweets)
    return jsonify(new_tweet), 201

@app.route('/api/tweets/<int:tweet_id>/like', methods=['POST'])
def like_tweet(tweet_id):
    """New endpoint to increment a tweet's like count."""
    tweets = load_tweets()
    tweet = next((t for t in tweets if t.get('id') == tweet_id), None)
    
    if not tweet:
        return jsonify({'error': 'Tweet not found'}), 404
    
    tweet['like_count'] = tweet.get('like_count', 0) + 1
    save_tweets(tweets)
    
    # Add interaction counts to the returned tweet for UI consistency
    tweet_with_counts = add_interaction_counts([tweet])[0]
    return jsonify(tweet_with_counts)

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
