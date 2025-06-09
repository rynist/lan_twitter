(() => {
    const App = {
        elements: { mainContent: null },
        state: { allTweetsById: {}, composer: {}, lastUsername: '' },

        init() {
            this.elements.mainContent = document.getElementById('main-content');
            this.state.lastUsername = localStorage.getItem('lanTwttrUsername') || '';
            window.addEventListener('hashchange', () => this.router());
            this.router();
            // Refresh the view periodically to show new tweets
            setInterval(() => this.router(), 1000);
        },
        
        async router() {
            const response = await fetch('/api/tweets');
            const tweets = await response.json();
            this.state.allTweetsById = Object.fromEntries(tweets.map(t => [t.id, t]));
            this.state.composer = { replying_to: null, quoting: null };

            const hash = window.location.hash;
            const tweetDetailMatch = hash.match(/^#\/tweet\/(\d+)$/);
            const quotesMatch = hash.match(/^#\/tweet\/(\d+)\/quotes$/);

            if (tweetDetailMatch) this.renderTweetDetailView(parseInt(tweetDetailMatch[1]), tweets);
            else if (quotesMatch) this.renderQuotesView(parseInt(quotesMatch[1]), tweets);
            else this.renderMainFeed(tweets);
            this.attachEventListeners();
        },

        formatDate: (isoString) => new Date(isoString).toLocaleString(),

        getTweetHTML(tweet, isParent = false) {
            // --- HIDE ZERO COUNTS LOGIC ---
            const replyCount = tweet.reply_count > 0 ? `(${tweet.reply_count})` : '';
            const quoteCount = tweet.quote_count > 0 ? `(${tweet.quote_count})` : '';
            const likeCount = tweet.like_count > 0 ? `(${tweet.like_count})` : '';
            
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
                        <button class="action-button reply-btn" data-tweet-id="${tweet.id}" data-username="${tweet.username}">Reply ${replyCount}</button>
                        <a href="#/tweet/${tweet.id}/quotes" class="action-link quote-btn">Quote ${quoteCount}</a>
                        <button class="action-button like-btn" data-tweet-id="${tweet.id}">Like ${likeCount}</button>
                        <button class="action-button delete-btn" data-tweet-id="${tweet.id}">Delete</button>
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
                        <div class="button-row">
                            <button type="button" id="run-bot-btn">Run Bot</button>
                            <button type="button" id="run-bot-five-btn">Run Bot 5x</button>
                            <button type="submit">Tweet</button>
                        </div>
                    </form>
                </div>`;
        },
        renderMainFeed(tweets) {
            this.elements.mainContent.innerHTML = `
                <header><h1>LAN Twitter</h1><a href="prompts.html" class="prompts-link">Prompts</a> <a href="tokens.html" class="prompts-link">Usage</a></header>
                ${this.getComposerHTML()}
                <div id="tweet-feed">
                    ${tweets.map(t => this.getTweetHTML(t)).join('')}
                </div>`;
        },
        renderTweetDetailView(tweetId, tweets) { const parentTweet = this.state.allTweetsById[tweetId]; if (!parentTweet) { this.elements.mainContent.innerHTML = `<h2>Tweet not found</h2><a href="#">Back</a>`; return; } const replies = tweets.filter(t => t.replying_to === parentTweet.id); this.elements.mainContent.innerHTML = `<div class="view-header"><a href="#" class="back-button">←</a><h2>Thread</h2></div><div id="tweet-feed">${this.getTweetHTML(parentTweet, true)}${replies.map(t => this.getTweetHTML(t)).join('')}</div>${this.getComposerHTML()}`; this.state.composer = { replying_to: { id: parentTweet.id, username: parentTweet.username }, quoting: null }; document.getElementById('composer-context').innerHTML = `Replying to @${parentTweet.username} <button id="cancel-action">Cancel</button>`; },
        renderQuotesView(tweetId, tweets) { const parentTweet = this.state.allTweetsById[tweetId]; if (!parentTweet) { this.elements.mainContent.innerHTML = `<h2>Tweet not found</h2><a href="#">Back</a>`; return; } const quotes = tweets.filter(t => t.quoting_tweet_id === parentTweet.id); this.elements.mainContent.innerHTML = `<div class="view-header"><a href="#/tweet/${tweetId}" class="back-button">←</a><h2>Quotes for Tweet by @${parentTweet.username}</h2></div><div id="tweet-feed">${quotes.map(t => this.getTweetHTML(t)).join('')}</div>`; },

        attachEventListeners() {
            this.elements.mainContent.addEventListener('click', e => this.handleMainClick(e));
            const tweetForm = document.getElementById('tweet-form');
            if (tweetForm) {
                tweetForm.addEventListener('submit', e => this.handleFormSubmit(e));
                document.getElementById('tweet-text-input').addEventListener('keydown', e => this.handleKeyDown(e));
            }
            const runBotBtn = document.getElementById('run-bot-btn');
            if (runBotBtn) runBotBtn.addEventListener('click', () => this.runBot());
            const runBotFiveBtn = document.getElementById('run-bot-five-btn');
            if (runBotFiveBtn) runBotFiveBtn.addEventListener('click', () => this.runBotFive());
        },

        async handleMainClick(e) {
            const target = e.target;
            const tweetElement = target.closest('[data-tweet-id]');
            if (!tweetElement) return;
            const tweetId = tweetElement.dataset.tweetId;

            // --- LIKE BUTTON LOGIC ---
            if (target.classList.contains('like-btn')) {
                const response = await fetch(`/api/tweets/${tweetId}/like`, { method: 'POST' });
                const updatedTweet = await response.json();
                this.state.allTweetsById[tweetId] = updatedTweet; // Update local cache
                this.router(); // Re-render to show new count
                return; // Stop further processing
            }

            if (target.classList.contains('delete-btn')) {
                await fetch(`/api/tweets/${tweetId}`, { method: 'DELETE' });
                this.router();
                return;
            }

            if (target.closest('.tweet:not(.parent-tweet)') && !target.closest('.action-button, .action-link') && !target.closest('a')) { window.location.hash = `#/tweet/${tweetId}`; } 
            else if (target.closest('.quoted-tweet-container')) { window.location.hash = `#/tweet/${tweetId}`; }

            if (target.classList.contains('reply-btn')) { const username = target.dataset.username; this.state.composer = { replying_to: { id: tweetId, username }, quoting: null }; document.getElementById('composer-context').innerHTML = `Replying to @${username} <button id="cancel-action">Cancel</button>`; document.getElementById('tweet-text-input').focus(); }
            if (target.id === 'cancel-action') { this.state.composer = { replying_to: null, quoting: null }; document.getElementById('composer-context').innerHTML = ''; }
        },

        async handleFormSubmit(e) { e.preventDefault(); const usernameInput = document.getElementById('username-input'); const username = usernameInput.value.trim(); const text = document.getElementById('tweet-text-input').value.trim(); if (!username || !text) return; const payload = { username, text }; if (this.state.composer.replying_to) payload.replying_to = parseInt(this.state.composer.replying_to.id); await fetch('/api/tweets', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), }); localStorage.setItem('lanTwttrUsername', username); this.state.lastUsername = username; this.router(); },
        async runBot() { await fetch('/api/run_bot', { method: 'POST' }); },
        runBotFive() {
            for (let i = 0; i < 5; i++) {
                setTimeout(() => this.runBot(), i * 2000);
            }
        },
        handleKeyDown(e) { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); document.getElementById('tweet-form').requestSubmit(); } }
    };

    document.addEventListener('DOMContentLoaded', () => App.init());
})();
