(function() {
    // 1. Markdown (Links, Bold, Newlines) HTML බවට හරවන Helper Function එක
    function parseMarkdown(text) {
        if (!text) return '';
        let html = text;

        // 1. Phone Numbers එකම පේළියේ තබා ගැනීම (Line Break වීම වැළැක්වීම)
        html = html.replace(/(\+94[\d\s]+)/g, '<span style="white-space: nowrap;">$1</span>');

        // 2. **Bold** වෙනුවට <strong>
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

        // 3. [Title](URL) වෙනුවට Clickable HTML Link
        html = html.replace(/\[(.*?)\]\((https?:\/\/[^\s\)]+)\)/g, 
            '<a href="$2" target="_blank" style="color: #0066FF; text-decoration: underline; font-weight: 600;">$1</a>'
        );

        // 4. Bullet Points (* ) ලස්සනට පෙන්වීම
        html = html.replace(/^\*\s+/gm, '• ');

        // 5. Line Breaks (\n) වෙනුවට <br>
        html = html.replace(/\n/g, '<br>');

        return html;
    }

    // 2. Inject CSS Styles
    const style = document.createElement('style');
    style.innerHTML = `
        .sm-chat-toggle { position: fixed; bottom: 20px; right: 20px; width: 60px; height: 60px; border-radius: 50%; background: #0066FF; color: white; border: none; font-size: 26px; cursor: pointer; box-shadow: 0 4px 15px rgba(0,0,0,0.3); z-index: 999999; transition: transform 0.2s ease; }
        .sm-chat-toggle:hover { transform: scale(1.05); }
        .sm-chat-box { position: fixed; bottom: 90px; right: 20px; width: 380px; height: 550px; background: #ffffff; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); display: none; flex-direction: column; z-index: 999999; overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .sm-chat-header { background: #0066FF; color: white; padding: 16px; font-weight: 600; font-size: 16px; display: flex; justify-content: space-between; align-items: center; }
        .sm-chat-body { flex: 1; padding: 16px; overflow-y: auto; background: #F8FAFC; display: flex; flex-direction: column; gap: 12px; }
        .sm-chat-footer { padding: 12px; border-top: 1px solid #E2E8F0; background: #ffffff; display: flex; gap: 8px; }
        .sm-chat-input { flex: 1; padding: 10px 14px; border: 1px solid #CBD5E1; border-radius: 20px; outline: none; font-size: 14px; }
        .sm-chat-send { background: #0066FF; color: white; border: none; padding: 10px 16px; border-radius: 20px; cursor: pointer; font-weight: 600; font-size: 14px; }
        .sm-msg { padding: 10px 14px; border-radius: 14px; font-size: 14px; line-height: 1.5; max-width: 85%; word-wrap: break-word; }
        .sm-msg-user { background: #0066FF; color: white; align-self: flex-end; border-bottom-right-radius: 2px; }
        .sm-msg-bot { background: #E2E8F0; color: #1E293B; align-self: flex-start; border-bottom-left-radius: 2px; }
    `;
    document.head.appendChild(style);

    // 3. Inject HTML Layout
    const widgetContainer = document.createElement('div');
    widgetContainer.innerHTML = `
        <button class="sm-chat-toggle" id="sm-btn">💬</button>
        <div class="sm-chat-box" id="sm-box">
            <div class="sm-chat-header">
                <span>🤖 Smart Media AI Assistant</span>
                <span id="sm-close" style="cursor:pointer;">✖</span>
            </div>
            <div class="sm-chat-body" id="sm-body">
                <div class="sm-msg sm-msg-bot">Hello! 👋 How can I help you regarding Smart Media's services today?</div>
            </div>
            <div class="sm-chat-footer">
                <input type="text" class="sm-chat-input" id="sm-input" placeholder="Ask a question...">
                <button class="sm-chat-send" id="sm-send">Send</button>
            </div>
        </div>
    `;
    document.body.appendChild(widgetContainer);

    // 4. Elements Logic & API Calling
    const btn = document.getElementById('sm-btn');
    const box = document.getElementById('sm-box');
    const closeBtn = document.getElementById('sm-close');
    const input = document.getElementById('sm-input');
    const sendBtn = document.getElementById('sm-send');
    const body = document.getElementById('sm-body');

    function toggleChat() {
        const isHidden = box.style.display === 'none' || box.style.display === '';
        box.style.display = isHidden ? 'flex' : 'none';
        btn.innerHTML = isHidden ? '✖' : '💬';
    }

    btn.onclick = toggleChat;
    closeBtn.onclick = toggleChat;

    async function handleSend() {
        const text = input.value.trim();
        if (!text) return;

        body.innerHTML += `<div class="sm-msg sm-msg-user">${parseMarkdown(text)}</div>`;
        input.value = '';
        body.scrollTop = body.scrollHeight;

        const loadingId = 'sm-loading-' + Date.now();
        body.innerHTML += `<div class="sm-msg sm-msg-bot" id="${loadingId}">Thinking... ⏳</div>`;
        body.scrollTop = body.scrollHeight;

        try {
            const res = await fetch('http://localhost:8000/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });
            const data = await res.json();
            
            // 🛠️ innerText වෙනුවට innerHTML සමඟ parseMarkdown Function එක භාවිත කිරීම
            document.getElementById(loadingId).innerHTML = parseMarkdown(data.response);
        } catch (e) {
            document.getElementById(loadingId).innerHTML = "⚠️ Network connection issue. Please try again.";
        }
        body.scrollTop = body.scrollHeight;
    }

    sendBtn.onclick = handleSend;
    input.onkeypress = (e) => { if (e.key === 'Enter') handleSend(); };
})();