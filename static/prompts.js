(() => {
    async function loadPrompts() {
        const personaRes = await fetch('/api/personas');
        const personas = await personaRes.json();

        const sysRes = await fetch('/api/system_prompt');
        const sysData = await sysRes.json();

        const container = document.getElementById('prompts-container');
        const personaList = personas.map(p => `<li><strong>${p.name}</strong>: ${p.prompt}</li>`).join('');
        container.innerHTML = `
            <h2>Personas</h2>
            <ul>${personaList}</ul>
            <h2>System Instructions</h2>
            <pre>${sysData.system_prompt}</pre>
        `;
    }

    document.addEventListener('DOMContentLoaded', loadPrompts);
})();
