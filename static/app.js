/** MCP Odoo — Chat client */

(function () {
    'use strict';

    const messagesEl = document.getElementById('messages');
    const form = document.getElementById('chatForm');
    const input = document.getElementById('messageInput');
    const btnSend = document.getElementById('btnSend');
    const statusEl = document.getElementById('status');
    const btnModels = document.getElementById('btnModels');
    const btnAgents = document.getElementById('btnAgents');
    const btnClear = document.getElementById('btnClear');

    let sessionId = localStorage.getItem('mcp_odoo_session') || generateId();
    localStorage.setItem('mcp_odoo_session', sessionId);

    function generateId() {
        return 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
    }

    function addMessage(text, type, meta) {
        const div = document.createElement('div');
        div.className = 'message ' + type;
        if (meta) {
            const metaSpan = document.createElement('span');
            metaSpan.className = 'meta';
            metaSpan.textContent = meta;
            div.appendChild(metaSpan);
        }
        div.appendChild(document.createTextNode(text));
        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function setStatus(text) {
        statusEl.textContent = text;
        statusEl.classList.remove('hidden');
    }

    function hideStatus() {
        statusEl.classList.add('hidden');
    }

    async function sendMessage(message) {
        addMessage(message, 'user');
        input.value = '';
        btnSend.disabled = true;
        setStatus('Thinking…');

        try {
            const resp = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message, session_id: sessionId }),
            });

            const data = await resp.json();

            if (data.status === 'error') {
                addMessage('Error: ' + data.message, 'error');
            } else if (data.agent) {
                let text = '';
                if (data.agent_name) text += 'Routed to: ' + data.agent_name + '\n';
                if (data.model_label) text += 'Model: ' + data.model_label + ' (' + data.model + ')\n';
                if (data.required_fields && data.required_fields.length) {
                    text += 'Required: ' + data.required_fields.join(', ') + '\n';
                }
                if (data.model_summary) text += data.model_summary;
                addMessage(text || JSON.stringify(data), 'agent', data.agent_name);
            } else if (data.available_agents) {
                let text = 'What would you like to do? Available agents:\n';
                data.available_agents.forEach(function (a) {
                    text += '  • ' + a.name + ': ' + a.description + '\n';
                });
                addMessage(text, 'agent');
            } else {
                addMessage(JSON.stringify(data, null, 2), 'agent');
            }
            hideStatus();
        } catch (err) {
            addMessage('Connection error: ' + err.message, 'error');
            hideStatus();
        }

        btnSend.disabled = false;
        input.focus();
    }

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        const msg = input.value.trim();
        if (msg) sendMessage(msg);
    });

    btnModels.addEventListener('click', async function () {
        try {
            const resp = await fetch('/api/models');
            const models = await resp.json();
            let text = 'Available Models (' + models.length + '):\n\n';
            models.forEach(function (m) {
                text += m.label + ' (' + m.model + ')\n';
                if (m.summary) text += '  ' + m.summary + '\n';
                if (m.required_fields && m.required_fields.length) {
                    text += '  Required: ' + m.required_fields.join(', ') + '\n';
                }
            });
            addMessage(text, 'agent');
        } catch (err) {
            addMessage('Error loading models: ' + err.message, 'error');
        }
    });

    btnAgents.addEventListener('click', async function () {
        try {
            const resp = await fetch('/api/agents');
            const agents = await resp.json();
            let text = 'Available Agents:\n\n';
            Object.values(agents).forEach(function (a) {
                text += a.name + ' (' + a.key + ')\n';
                text += '  ' + a.description + '\n';
                if (a.keywords) text += '  Keywords: ' + a.keywords.join(', ') + '\n';
            });
            addMessage(text, 'agent');
        } catch (err) {
            addMessage('Error loading agents: ' + err.message, 'error');
        }
    });

    btnClear.addEventListener('click', function () {
        messagesEl.innerHTML = '';
        sessionId = generateId();
        localStorage.setItem('mcp_odoo_session', sessionId);
        addMessage('Chat cleared. New session: ' + sessionId, 'agent');
    });
})();
