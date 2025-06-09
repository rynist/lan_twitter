import os
import requests
import random
import json
import sqlite3
import datetime

# --- CONFIGURATION ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
LAN_TWTTR_API_URL = "http://localhost:5001/api/tweets"

PROMPT_DB_FILE = "prompts.db"

DEFAULT_PERSONAS = [
    (
        "TechOptimist",
        "You are a cheerful tech optimist. Based on the recent conversation, either post a new hopeful thought, reply to someone with encouragement, or quote a tweet to add a positive spin."
    ),
    (
        "GrumpyCatBot",
        "You are a grumpy cat. Looking at these recent human tweets, either complain about something new, sarcastically reply to one of them, or quote one to mock it."
    ),
    (
        "HistoryBuff",
        "You are a history enthusiast. Looking at the recent conversation, either share a new historical fact, reply to a tweet with a relevant fact, or quote one to provide historical context."
    ),
]

def init_prompt_db():
    conn = sqlite3.connect(PROMPT_DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS personas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            prompt TEXT NOT NULL
        )
        """
    )
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM personas")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO personas (name, prompt) VALUES (?, ?)", DEFAULT_PERSONAS
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

def get_latest_tweets():
    """Fetches the latest tweets from the LAN Twitter API."""
    try:
        # The main feed only returns top-level tweets. This is perfect for context.
        response = requests.get(LAN_TWTTR_API_URL)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Could not fetch latest tweets. {e}")
        return []

def format_context_for_llm(tweets):
    """Formats a list of tweets into a simple string for the LLM prompt."""
    if not tweets:
        return "The timeline is empty."
    
    formatted_tweets = []
    for tweet in tweets[:5]: # Only use the last 5 tweets for context
        text = tweet['text'].replace('\n', ' ') # Flatten newlines
        formatted_tweets.append(f"Tweet (ID {tweet['id']}) by @{tweet['username']}: \"{text}\"")
    return "\n".join(formatted_tweets)

def get_llm_decision(persona, context):
    """Gets a decision (tweet, reply, quote) from the OpenRouter API."""
    if not OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY environment variable not set.")
        return None

    system_prompt = f"""
{persona['prompt']}

Here is the recent conversation:
{context}

You must decide on one of three actions: TWEET, REPLY, or QUOTE.
Your response MUST be in the following format, with each part on a new line:
ACTION: [Your chosen action: TWEET, REPLY, or QUOTE]
ID: [The ID of the tweet to REPLY or QUOTE. Use 0 for a new TWEET.]
CONTENT: [The text of your tweet, reply, or quote. Must be under 280 characters.]

Example for a reply:
ACTION: REPLY
ID: 3
CONTENT: That's a fascinating point about ancient Rome!

Example for a new tweet:
ACTION: TWEET
ID: 0
CONTENT: Just learned that Vikings used sunstones for navigation. How cool is that?
"""
    
    print(f"Bot '{persona['name']}' is thinking...")
    try:
        response = requests.post(
            url=OPENROUTER_API_URL,
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json={
                "model": "mistralai/mistral-7b-instruct:free",
                "messages": [{"role": "user", "content": system_prompt}]
            }
        )
        response.raise_for_status()
        data = response.json()
        decision_text = data['choices'][0]['message']['content'].strip()
        if 'usage' in data:
            usage = data['usage']
            log_token_usage(
                usage.get('prompt_tokens'),
                usage.get('completion_tokens'),
                usage.get('total_tokens'),
                persona['name'],
            )
        print(f"-> LLM Decision:\n{decision_text}")
        return decision_text
    except Exception as e:
        print(f"ERROR: LLM decision failed. {e}")
        return None

def parse_llm_decision(decision_text):
    """Parses the structured response from the LLM into a dictionary."""
    if not decision_text:
        return None
    
    decision = {}
    try:
        for line in decision_text.strip().split('\n'):
            if ': ' in line:
                key, value = line.split(': ', 1)
                decision[key.strip().upper()] = value.strip()
        
        # Clean up quotes that LLMs sometimes add to content
        if 'CONTENT' in decision and decision['CONTENT'].startswith('"') and decision['CONTENT'].endswith('"'):
            decision['CONTENT'] = decision['CONTENT'][1:-1]
            
        return decision
    except Exception as e:
        print(f"ERROR: Could not parse LLM decision. {e}")
        return None

def post_to_lan_twitter(username, payload):
    """Posts to the LAN Twitter server with a flexible payload."""
    payload['username'] = username
    print(f"Posting to LAN Twitter: {payload}")
    try:
        response = requests.post(LAN_TWTTR_API_URL, json=payload)
        response.raise_for_status()
        print("-> Successfully posted!")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Could not post to LAN Twitter API. {e}")

if __name__ == "__main__":
    init_prompt_db()
    personas = load_personas()
    if not personas:
        print("ERROR: No personas available.")
        exit(1)
    # 1. Choose a bot persona
    chosen_persona = random.choice(personas)
    
    # 2. Perceive: Get the latest tweets
    latest_tweets = get_latest_tweets()
    context_str = format_context_for_llm(latest_tweets)
    
    # 3. Decide: Get a decision from the LLM
    llm_response = get_llm_decision(chosen_persona, context_str)
    
    # 4. Act: Parse the decision and post accordingly
    decision = parse_llm_decision(llm_response)
    
    if decision and 'ACTION' in decision and 'CONTENT' in decision:
        action = decision['ACTION'].strip().upper()
        post_payload = {"text": decision['CONTENT']}

        if action in ["REPLY", "QUOTE"] and 'ID' in decision:
            try:
                target_id = int(decision['ID'])
                if target_id > 0:
                    if action == "REPLY":
                        post_payload['replying_to'] = target_id
                    elif action == "QUOTE":
                        post_payload['quoting_tweet_id'] = target_id
                else:
                    print("WARNING: ID must be a positive integer for replies or quotes. Posting as a new tweet instead.")
            except ValueError:
                print(f"WARNING: Invalid ID '{decision['ID']}'. Posting as a new tweet instead.")

        post_to_lan_twitter(chosen_persona['name'], post_payload)
    else:
        print("Could not execute a valid action based on LLM response.")
