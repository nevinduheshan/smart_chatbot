(function() {
    // 1. Markdown Parser Function
    function parseMarkdown(text) {
        if (!text) return '';
        let html = text;

        // display phone numbers in a single line
        html = html.replace(/(\+94[\d\s]+)/g, '<span style="white-space: nowrap;">$1</span>');

        // **Bold** replace <strong>
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

        // [Title](URL) replace Clickable HTML Link
        html = html.replace(/\[(.*?)\]\((https?:\/\/[^\s\)]+)\)/g, 
            '<a href="$2" target="_blank" style="color: #0066FF; text-decoration: underline; font-weight: 600;">$1</a>'
        );

        // Bullet Points
        html = html.replace(/^\*\s+/gm, '• ');

        // Line Breaks (\n)
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
        .sm-chat-footer { padding: 12px; border-top: 1px solid #E2E8F0; background: #ffffff; display: flex; gap: 6px; align-items: center; }
        .sm-chat-input { flex: 1; padding: 10px 14px; border: 1px solid #CBD5E1; border-radius: 20px; outline: none; font-size: 14px; }
        .sm-chat-btn-icon { background: #F1F5F9; color: #1E293B; border: 1px solid #CBD5E1; width: 40px; height: 40px; border-radius: 50%; cursor: pointer; font-size: 18px; display: flex; align-items: center; justify-content: center; transition: background 0.2s; }
        .sm-chat-btn-icon:hover { background: #E2E8F0; }
        .sm-chat-mic-active { background: #EF4444 !important; color: white !important; animation: pulse 1.2s infinite; }
        .sm-chat-send { background: #0066FF; color: white; border: none; padding: 10px 16px; border-radius: 20px; cursor: pointer; font-weight: 600; font-size: 14px; }
        .sm-msg { padding: 10px 14px; border-radius: 14px; font-size: 14px; line-height: 1.5; max-width: 85%; word-wrap: break-word; }
        .sm-msg-user { background: #0066FF; color: white; align-self: flex-end; border-bottom-right-radius: 2px; }
        .sm-msg-bot { background: #E2E8F0; color: #1E293B; align-self: flex-start; border-bottom-left-radius: 2px; }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }
    `;
    document.head.appendChild(style);

    // 3. Inject HTML Layout with Mic Button
    const widgetContainer = document.createElement('div');
    widgetContainer.innerHTML = `
        <button class="sm-chat-toggle" id="sm-btn">💬</button>
        <div class="sm-chat-box" id="sm-box">
            <div class="sm-chat-header">
                <span>🤖 Smart Media AI Assistant</span>
                <span id="sm-close" style="cursor:pointer;">✖</span>
            </div>
            <div class="sm-chat-body" id="sm-body">
                <div class="sm-msg sm-msg-bot">Hello! 👋 How can I help you today? You can type or click the 🎤 icon to speak!</div>
            </div>
            <div class="sm-chat-footer">
                <input type="text" class="sm-chat-input" id="sm-input" placeholder="Ask a question...">
                <button class="sm-chat-btn-icon" id="sm-mic" title="Voice Input">🎤</button>
                <button class="sm-chat-send" id="sm-send">Send</button>
            </div>
        </div>
    `;
    document.body.appendChild(widgetContainer);

    // 4. Elements Logic
    const btn = document.getElementById('sm-btn');
    const box = document.getElementById('sm-box');
    const closeBtn = document.getElementById('sm-close');
    const input = document.getElementById('sm-input');
    const sendBtn = document.getElementById('sm-send');
    const micBtn = document.getElementById('sm-mic');
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
            document.getElementById(loadingId).innerHTML = parseMarkdown(data.response);
        } catch (e) {
            document.getElementById(loadingId).innerHTML = "⚠️ Network connection issue. Please try again.";
        }
        body.scrollTop = body.scrollHeight;
    }

    sendBtn.onclick = handleSend;
    input.onkeypress = (e) => { if (e.key === 'Enter') handleSend(); };

    // 🎙️ 5. Voice Recognition Logic (Speech-to-Text)
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.lang = 'en-US'; // for the English language en-US (can use sinhala 'si-LK')

        let isListening = false;

        micBtn.onclick = () => {
            if (!isListening) {
                recognition.start();
            } else {
                recognition.stop();
            }
        };

        recognition.onstart = () => {
            isListening = true;
            micBtn.classList.add('sm-chat-mic-active');
            micBtn.innerText = '🎙️';
            input.placeholder = 'Listening... Speak now!';
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            input.value = transcript;
            handleSend(); // auto send after speech recognition
        };

        recognition.onerror = (event) => {
            console.error("Speech recognition error:", event.error);
            recognition.stop();
        };

        recognition.onend = () => {
            isListening = false;
            micBtn.classList.remove('sm-chat-mic-active');
            micBtn.innerText = '🎤';
            input.placeholder = 'Ask a question...';
        };
    } else {
        // If SpeechRecognition is not supported, hide the mic button
        micBtn.style.display = 'none';
    }
})();