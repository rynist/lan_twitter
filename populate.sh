#!/bin/bash
# A script to populate the LAN Twitter feed.

API_URL="http://localhost:5001/api/tweets"

# Function to post a tweet
post_tweet() {
  USERNAME=$1
  TEXT=$2
  echo "Posting as @$USERNAME: $TEXT"
  curl -s -X POST "$API_URL" \
       -H "Content-Type: application/json" \
       -d "{\"username\": \"$USERNAME\", \"text\": \"$TEXT\"}"
  echo "" # for a newline
  sleep 1 # To ensure different timestamps
}

echo "--- Populating LAN Twitter ---"
post_tweet "alice" "Just setting up my LAN twttr."
post_tweet "bob" "Hey @alice, this is pretty cool! No internet required."
post_tweet "charlie" "Is this thing on? 🎤"
post_tweet "alice" "It works! Now we can coordinate our LAN party snacks."
post_tweet "dave" "I'm bringing the pizza. 🍕"
post_tweet "bob" "I'll handle the drinks. What does everyone want?"
post_tweet "charlie" "Anything but diet soda."
post_tweet "alice" "I second that. Also, remember to bring your own controller."
echo "--- Done ---"
