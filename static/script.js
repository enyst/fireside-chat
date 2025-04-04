// static/script.js

document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const chatOutput = document.getElementById('chat-output');
    const promptInput = document.getElementById('prompt-input');
    const sendButton = document.getElementById('send-button');
    const historyList = document.getElementById('history-list');
    const newChatButton = document.getElementById('new-chat-button');

    // --- State ---
    let currentConversationId = null;
    let isLoading = false;

    // --- Functions ---

    /** Adds a message to the chat output area */
    function addMessage(role, text) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', role); // 'user' or 'model'

        const strong = document.createElement('strong');
        strong.textContent = role === 'user' ? 'You:' : 'Model:';
        messageDiv.appendChild(strong);

        // Handle potential markdown/newlines later if needed
        // For now, just append text content, escaping HTML
        const textNode = document.createTextNode(' ' + text); // Add space after role
        messageDiv.appendChild(textNode);

        chatOutput.appendChild(messageDiv);
        // Scroll to the bottom
        chatOutput.scrollTop = chatOutput.scrollHeight;
    }

    /** Adds a loading indicator to the chat output */
    function addLoadingIndicator() {
        const loadingDiv = document.createElement('div');
        loadingDiv.classList.add('message', 'model', 'loading'); // Style as model message but indicate loading
        loadingDiv.id = 'loading-indicator'; // To easily remove it
        loadingDiv.textContent = 'Model is thinking...';
        chatOutput.appendChild(loadingDiv);
        chatOutput.scrollTop = chatOutput.scrollHeight;
    }

    /** Removes the loading indicator */
    function removeLoadingIndicator() {
        const indicator = document.getElementById('loading-indicator');
        if (indicator) {
            indicator.remove();
        }
    }

    /** Clears the chat output area */
    function clearChatOutput() {
        chatOutput.innerHTML = '';
         // Optionally add a welcome message back
         addMessage('model', 'Started a new chat.');
    }

    /** Sets the loading state and updates UI */
    function setLoading(loading) {
        isLoading = loading;
        sendButton.disabled = loading;
        promptInput.disabled = loading;
        if (loading) {
            addLoadingIndicator();
        } else {
            removeLoadingIndicator();
        }
    }

    /** Fetches the list of conversations and updates the history panel */
    async function loadHistoryList() {
        historyList.innerHTML = '<li>Loading history...</li>'; // Clear existing
        try {
            const response = await fetch('/api/history');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const conversations = await response.json();

            historyList.innerHTML = ''; // Clear loading message
            if (conversations.length === 0) {
                historyList.innerHTML = '<li>No past conversations found.</li>';
            } else {
                conversations.forEach(conv => {
                    const li = document.createElement('li');
                    li.textContent = conv.summary; // Use summary from API
                    li.dataset.conversationId = conv.id; // Store ID on the element
                    li.title = `ID: ${conv.id}\nLast Modified: ${conv.last_modified}`; // Tooltip
                    if (conv.id === currentConversationId) {
                        li.classList.add('active');
                    }
                    li.addEventListener('click', () => loadConversation(conv.id));
                    historyList.appendChild(li);
                });
            }
        } catch (error) {
            console.error('Error loading history list:', error);
            historyList.innerHTML = '<li>Error loading history.</li>';
        }
    }

    /** Loads a specific conversation into the chat area */
    async function loadConversation(conversationId) {
        console.log(`Loading conversation: ${conversationId}`);
        if (isLoading) return; // Don't load if already processing
        setLoading(true);
        clearChatOutput();
        currentConversationId = conversationId;

        // Update active state in history list
        document.querySelectorAll('#history-list li').forEach(li => {
            li.classList.toggle('active', li.dataset.conversationId === conversationId);
        });

        try {
            const response = await fetch(`/api/history/${conversationId}`);
            if (!response.ok) {
                 if (response.status === 404) {
                     addMessage('model', 'Error: Conversation not found.');
                 } else {
                    throw new Error(`HTTP error! status: ${response.status}`);
                 }
            } else {
                const messages = await response.json();
                messages.forEach(msg => addMessage(msg.role, msg.text));
            }
        } catch (error) {
            console.error('Error loading conversation:', error);
            addMessage('model', `Error loading conversation: ${error.message}`);
        } finally {
            setLoading(false);
        }
    }

    /** Sends the prompt to the backend */
    async function sendPrompt() {
        const promptText = promptInput.value.trim();
        if (!promptText || isLoading) {
            return; // Do nothing if input is empty or already loading
        }

        setLoading(true);
        addMessage('user', promptText);
        promptInput.value = ''; // Clear input field

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    prompt: promptText,
                    conversation_id: currentConversationId
                    // Add settings_override here if implementing settings UI
                }),
            });

            removeLoadingIndicator(); // Remove indicator once response starts coming

            if (!response.ok) {
                // Try to get error detail from response body
                let errorDetail = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorDetail = errorData.detail || errorDetail;
                } catch (e) { /* Ignore if response body isn't valid JSON */ }
                throw new Error(errorDetail);
            }

            const data = await response.json();
            addMessage('model', data.response);

            // If it was a new chat, update the conversation ID and reload history
            if (currentConversationId !== data.conversation_id) {
                currentConversationId = data.conversation_id;
                loadHistoryList(); // Refresh history list to show the new chat
                 // Update active state in history list for the new conversation
                document.querySelectorAll('#history-list li').forEach(li => {
                    li.classList.toggle('active', li.dataset.conversationId === currentConversationId);
                });
            }

        } catch (error) {
            console.error('Error sending prompt:', error);
            removeLoadingIndicator(); // Ensure indicator is removed on error
            addMessage('model', `Error: ${error.message}`); // Display error in chat
        } finally {
            // Ensure loading state is reset even if errors occurred before removeLoadingIndicator was called
            setLoading(false);
            promptInput.focus(); // Return focus to input
        }
    }

    /** Starts a new chat session */
    function startNewChat() {
        if (isLoading) return;
        console.log("Starting new chat");
        currentConversationId = null;
        clearChatOutput();
        promptInput.value = '';
        promptInput.focus();
        // Deactivate any active item in history list
        document.querySelectorAll('#history-list li.active').forEach(li => li.classList.remove('active'));
        // Optionally, reload history list in case it helps sync state, though not strictly necessary
        // loadHistoryList();
    }


    // --- Event Listeners ---
    sendButton.addEventListener('click', sendPrompt);
    promptInput.addEventListener('keypress', (event) => {
        // Send on Enter key press (Shift+Enter for newline)
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault(); // Prevent default newline insertion
            sendPrompt();
        }
    });
    newChatButton.addEventListener('click', startNewChat);

    // --- Initial Load ---
    loadHistoryList(); // Load conversation history on page load
    promptInput.focus(); // Focus input on load

});
