(() => {
    async function loadPrompts() {
        const personaRes = await fetch('/api/personas');
        const personas = await personaRes.json();

        const sysRes = await fetch('/api/system_prompt');
        const sysData = await sysRes.json();

        const container = document.getElementById('prompts-container');
        const personaList = personas.map(p => `
            <li data-name="${p.name}">
                <strong>${p.name}</strong>: <span class="prompt-text">${p.prompt}</span>
                <button class="edit-persona-btn">Edit</button>
                <button class="delete-persona-btn">Delete</button>
            </li>
        `).join('');
        container.innerHTML = `
            <h2>Personas</h2>
            <ul id="persona-list">${personaList}</ul>
            <button id="add-persona-btn">Add Persona</button>
            <h2>System Instructions</h2>
            <textarea id="system-prompt-input" rows="10" style="width:100%;">${sysData.system_prompt}</textarea>
            <br><button id="save-system-prompt">Save</button>
        `;

        attachEvents();
    }

    async function addPersona() {
        const name = prompt('Persona name:');
        if (!name) return;
        const promptText = prompt('Persona prompt:');
        if (!promptText) return;
        await fetch('/api/personas', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, prompt: promptText })
        });
        loadPrompts();
    }

    async function editPersona(e) {
        const li = e.target.closest('li');
        const oldName = li.dataset.name;
        const newName = prompt('Persona name:', oldName);
        if (!newName) return;
        const oldPrompt = li.querySelector('.prompt-text').textContent;
        const newPrompt = prompt('Persona prompt:', oldPrompt);
        if (newPrompt === null) return;
        await fetch('/api/personas/' + encodeURIComponent(oldName), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName, prompt: newPrompt })
        });
        loadPrompts();
    }

    async function deletePersona(e) {
        const li = e.target.closest('li');
        const name = li.dataset.name;
        if (!confirm(`Delete persona ${name}?`)) return;
        await fetch('/api/personas/' + encodeURIComponent(name), { method: 'DELETE' });
        loadPrompts();
    }

    async function saveSystemPrompt() {
        const text = document.getElementById('system-prompt-input').value;
        await fetch('/api/system_prompt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ system_prompt: text })
        });
        alert('Saved');
    }

    function attachEvents() {
        document.getElementById('add-persona-btn').addEventListener('click', addPersona);
        document.querySelectorAll('.edit-persona-btn').forEach(btn => btn.addEventListener('click', editPersona));
        document.querySelectorAll('.delete-persona-btn').forEach(btn => btn.addEventListener('click', deletePersona));
        document.getElementById('save-system-prompt').addEventListener('click', saveSystemPrompt);
    }

    document.addEventListener('DOMContentLoaded', loadPrompts);
})();
