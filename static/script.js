// A self-executing anonymous function to encapsulate the entire application
// and avoid polluting the global namespace.
(() => {
    // The main application object. It will hold our state and methods.
    const App = {
        // --- STATE ---
        // We initialize state properties to null or empty objects.
        elements: {
            mainContent: null,
        },
        state: {
            allTweetsById: {},
            composer: { replying_to: null, quoting: null },
            lastUsername: '',
        },

        // --- INITIALIZATION ---
        // The init method is the entry point of our application.
        init() {
            // Store main DOM element
            this.elements.mainContent = document.getElementById('main-content');
            
            // Load the last used username from browser's local storage
            this.state.lastUsername = localStorage.getItem('lanTwttrUsername') || '';

            // Set up routing
            window.addEventListener('hashchange', () => this.router());
            this.router(); // Call router on initial page load
        },
        
        // --- ROUTING ---
        // The router determines which view to render based on the URL hash.
        async router() {
            // On every view change, we fetch the latest tweets.
            const response = await fetch('/api/tweets');
            const tweets = await response.json();
            this.state.allTweetsById = Object.fromEntries(tweets.map(t => [t.id, t]));
            this.state.composer = { replying_to: null, quoting: null }; // Reset composer state

            const hash = window.location.hash;
            const tweetDetailMatch = hash.match(/^#\/tweet\/(\d+)$/);
            const quotesMatch = hash.match(/^#\/tweet\/(\d+)\/quotes$/);

            if (tweetDetailMatch) {
                this.renderTweetDetailView(parseInt(tweetDetailMatch[1]), tweets);
            } else if (quotesMatch) {
                this.renderQuotesView(parseInt(quotesMatch[1]), tweets);
            } else {
                this.renderMainFeed(tweets);
            }
            this.attachEventListeners(); // Re-attach listeners to the new DOM
        },

        // --- TEMPLATE GENERATORS ---
        // These methods return HTML strings. They are the "blueprints" for our UI.
        
        formatDate: (isoString) => new Date(isoString).toLocaleString(),

        getTweetHTML(tweet, isParent = false) {
            let replyingToHTML = '';
            if (tweet.replying_to && this.state.allTweetsById[tweet.replying_to]) {
                const parentUsername = this.state.allTweetsById[tweet.replying_to].username;
                replyingToHTML = `<p class="replying-to-info">Replying to <a href="#/tweet/${tweet.replying_to}">@${parentUsername}</a></p>`;
            }

            let quotedTweetHTML = '';
            if (tweet.quoting_tweet_id && this.state.allTweetsById[tweet.quoting_tweet_id]) {
                const quotedTweet = this.state.allTweetsById[tweet.quoting_tweet_id];
                quotedTweetHTML = `
                    <div class="quoted-tweet-container" data-tweet-id="${quotedTweet.id}">
                        <p class="tweet-header">@${quotedTweet.username}</p>
                        <p class="tweet-text">${quotedTweet.text}</p>
                        <p class="tweet-timestamp">${this.formatDate(quotedTweet.timestamp)}</p>
                    </div>`;
            }

            return `
                <div class="${isParent ? 'tweet parent-tweet' : 'tweet'}" data-tweet-id="${tweet.id}">
                    ${replyingToHTML}
                    <p class="tweet-header">@${tweet.username}</p>
                    <p class="tweet-text">${tweet.text}</p>
                    ${quotedTweetHTML}
                    <p class="tweet-meta">${this.formatDate(tweet.timestamp)}</p>
                    <div class="tweet-actions">
                        <button class="action-button reply-btn" data-tweet-id="${tweet.id}" data-username="${tweet.username}">
                            Reply (${tweet.reply_count})
                        </button>
                        <a href="#/tweet/${tweet.id}/quotes" class="action-link quote-btn" data-tweet-id="${tweet.id}" data-username="${tweet.username}">
                            Quote (${tweet.quote_count})
                        </a>
                    </div>
                </div>`;
        },

        getComposerHTML() {
            return `
                <div id="composer-context"></div>
                <div class="tweet-form-container">
                    <form id="tweet-form">
                        <input type="text" id="username-input" placeholder="Your Username" value="${this.state.lastUsername}" required>
                        <textarea id="tweet-text-input" placeholder="What's happening?" required maxlength="280"></textarea>
                        <button type="submit">Tweet</button>
                    </form>
                </div>`;
        },

        // --- VIEW RENDERERS ---
        // These methods build the full UI for each "page" of the app.
        
        renderMainFeed(tweets) {
            const topLevelTweets = tweets.filter(t => !t.replying_to);
            this.elements.mainContent.innerHTML = `
                <header><h1>LAN Twitter</h1></header>
                ${this.getComposerHTML()}
                <div id="tweet-feed">${topLevelTweets.map(t => this.getTweetHTML(t)).join('')}</div>`;
        },

        renderTweetDetailView(tweetId, tweets) {
            const parentTweet = this.state.allTweetsById[tweetId];
            if (!parentTweet) { this.elements.mainContent.innerHTML = `<h2>Tweet not found</h2><a href="#">Back</a>`; return; }
            
            const replies = tweets.filter(t => t.replying_to === parentTweet.id);
            this.elements.mainContent.innerHTML = `
                <div class="view-header"><a href="#" class="back-button">←</a><h2>Thread</h2></div>
                <div id="tweet-feed">
                    ${this.getTweetHTML(parentTweet, true)}
                    ${replies.map(t => this.getTweetHTML(t)).join('')}
                </div>
                ${this.getComposerHTML()}`;
            
            this.state.composer = { replying_to: { id: parentTweet.id, username: parentTweet.username }, quoting: null };
            document.getElementById('composer-context').innerHTML = `Replying to @${parentTweet.username} <button id="cancel-action">Cancel</button>`;
        },
        
        renderQuotesView(tweetId, tweets) {
            const parentTweet = this.state.allTweetsById[tweetId];
            if (!parentTweet) { this.elements.mainContent.innerHTML = `<h2>Tweet not found</h2><a href="#">Back</a>`; return; }

            const quotes = tweets.filter(t => t.quoting_tweet_id === parentTweet.id);
            this.elements.mainContent.innerHTML = `
                <div class="view-header"><a href="#/tweet/${tweetId}" class="back-button">←</a><h2>Quotes for Tweet by @${parentTweet.username}</h2></div>
                <div id="tweet-feed">${quotes.map(t => this.getTweetHTML(t)).join('')}</div>`;
        },

        // --- EVENT HANDLING ---
        // Centralized event listeners.
        
        attachEventListeners() {
            // Using event delegation on the main container is efficient.
            this.elements.mainContent.addEventListener('click', e => this.handleMainClick(e));

            const tweetForm = document.getElementById('tweet-form');
            if (tweetForm) {
                tweetForm.addEventListener('submit', e => this.handleFormSubmit(e));
                document.getElementById('tweet-text-input').addEventListener('keydown', e => this.handleKeyDown(e));
            }
        },

        handleMainClick(e) {
            const target = e.target;
            const tweetId = target.closest('[data-tweet-id]')?.dataset.tweetId;

            if (target.closest('.tweet:not(.parent-tweet)') && !target.closest('.action-button, .action-link') && !target.closest('a')) {
                window.location.hash = `#/tweet/${tweetId}`;
            } else if (target.closest('.quoted-tweet-container')) {
                window.location.hash = `#/tweet/${tweetId}`;
            }

            if (target.classList.contains('reply-btn')) {
                const username = target.dataset.username;
                this.state.composer = { replying_to: { id: tweetId, username }, quoting: null };
                document.getElementById('composer-context').innerHTML = `Replying to @${username} <button id="cancel-action">Cancel</button>`;
                document.getElementById('tweet-text-input').focus();
            }

            if (target.id === 'cancel-action') {
                this.state.composer = { replying_to: null, quoting: null };
                document.getElementById('composer-context').innerHTML = '';
            }
        },

        async handleFormSubmit(e) {
            e.preventDefault();
            const usernameInput = document.getElementById('username-input');
            const username = usernameInput.value.trim();
            const text = document.getElementById('tweet-text-input').value.trim();
            
            if (!username || !text) return;
    
            const payload = { username, text };
            if (this.state.composer.replying_to) payload.replying_to = parseInt(this.state.composer.replying_to.id);
    
            await fetch('/api/tweets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            
            // Save username for next time
            localStorage.setItem('lanTwttrUsername', username);
            this.state.lastUsername = username;

            this.router(); // Re-render the current view
        },

        handleKeyDown(e) {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                document.getElementById('tweet-form').requestSubmit();
            }
        }
    };

    // Kick off the application.
    document.addEventListener('DOMContentLoaded', () => App.init());

})();
