(() => {
    async function loadUsage() {
        const res = await fetch('/api/token_usage');
        const data = await res.json();
        const container = document.getElementById('tokens-container');
        const list = data.map(u => `
            <li>
                <strong>${u.timestamp}</strong> - persona <em>${u.persona || ''}</em>: prompt ${u.prompt_tokens}, completion ${u.completion_tokens}, total ${u.total_tokens}
            </li>
        `).join('');
        container.innerHTML = `<ul id="usage-list">${list}</ul>`;
    }

    document.addEventListener('DOMContentLoaded', loadUsage);
})();
