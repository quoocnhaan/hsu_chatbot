// HSU Chatbot Frontend SPA Logic (Decoupled Double-Token Auth Version)
document.addEventListener("DOMContentLoaded", () => {
    
    // Dynamically calculate the backend URL on port 8000 based on the current frontend domain
    // (Treats localhost and 127.0.0.1 as separate origins, avoiding CORS mismatches)
    const BACKEND_URL = window.location.hostname === "localhost" 
        ? "http://localhost:8000" 
        : "http://127.0.0.1:8000";

    const API_AUTH = `${BACKEND_URL}/api/auth`;
    const API_CHAT = `${BACKEND_URL}/api/chat`;

    // Application State - ACCESS_TOKEN IS HELD IN RAM ONLY (NO LOCAL STORAGE)
    let accessToken = null;
    let username = null;
    let activeSessionId = null;
    let sessions = [];
    let refreshTimeoutId = null;

    // DOM Elements Cache
    const authView = document.getElementById("auth-view");
    const dashboardView = document.getElementById("dashboard-view");
    const authAlert = document.getElementById("auth-alert");
    
    // Forms
    const loginForm = document.getElementById("login-form");
    const registerForm = document.getElementById("register-form");
    const chatInputForm = document.getElementById("chat-input-form");
    
    // Toggles
    const toRegister = document.getElementById("to-register");
    const toLogin = document.getElementById("to-login");
    const mobileSidebarOpen = document.getElementById("mobile-sidebar-open");
    const mobileSidebarClose = document.getElementById("mobile-sidebar-close");
    const sidebar = document.querySelector(".sidebar");
    
    // Inputs & Buttons
    const chatInput = document.getElementById("chat-input");
    const btnSend = document.getElementById("btn-send");
    const displayUsername = document.getElementById("display-username");
    const btnLogout = document.getElementById("btn-logout");
    const btnNewChat = document.getElementById("btn-new-chat");
    const sessionsList = document.getElementById("sessions-list");
    const chatTitleText = document.getElementById("chat-title-text");
    const chatHeaderActions = document.getElementById("chat-header-actions");
    const messagesContainer = document.getElementById("messages-container");
    const chatMessagesWrapper = document.getElementById("chat-messages-wrapper");
    const welcomeState = document.getElementById("welcome-state");
    const typingIndicator = document.getElementById("typing-indicator");
    
    // Rename Modal Elements
    const renameModal = document.getElementById("rename-modal");
    const renameInput = document.getElementById("rename-input");
    const btnRenameCancel = document.getElementById("btn-rename-cancel");
    const btnRenameSave = document.getElementById("btn-rename-save");
    let sessionToRename = null;

    // Initialize App
    init();

    async function init() {
        // Automatically adjust textarea height as the user types
        chatInput.addEventListener("input", autoGrowTextarea);
        
        // Press Enter to send, Shift+Enter to create a new line
        chatInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submitUserMessage();
            }
        });
        
        // Suggestion Card click handler
        document.querySelectorAll(".suggestion-card").forEach(card => {
            card.addEventListener("click", () => {
                const prompt = card.getAttribute("data-prompt");
                chatInput.value = prompt;
                autoGrowTextarea();
                submitUserMessage();
            });
        });

        // View Toggles
        toRegister.addEventListener("click", (e) => {
            e.preventDefault();
            loginForm.classList.add("hidden");
            registerForm.classList.remove("hidden");
            hideAlert();
        });
        toLogin.addEventListener("click", (e) => {
            e.preventDefault();
            registerForm.classList.add("hidden");
            loginForm.classList.remove("hidden");
            hideAlert();
        });

        // Mobile Sidebar toggles
        mobileSidebarOpen.addEventListener("click", () => sidebar.classList.add("open"));
        mobileSidebarClose.addEventListener("click", () => sidebar.classList.remove("open"));

        // Form Submit Listeners
        loginForm.addEventListener("submit", handleLogin);
        registerForm.addEventListener("submit", handleRegister);
        chatInputForm.addEventListener("submit", (e) => {
            e.preventDefault();
            submitUserMessage();
        });

        // Logout
        btnLogout.addEventListener("click", handleLogoutBtn);

        // Start New Chat Session
        btnNewChat.addEventListener("click", () => startNewSession(true));

        // Rename Session Actions
        document.getElementById("btn-rename-session").addEventListener("click", openRenameModal);
        btnRenameCancel.addEventListener("click", closeRenameModal);
        btnRenameSave.addEventListener("click", saveSessionRename);

        // Delete Session
        document.getElementById("btn-delete-session").addEventListener("click", deleteActiveSession);

        // Silent login check: Attempt to refresh session using the HttpOnly cookie
        console.log("Attempting silent login via HttpOnly cookies...");
        const isLogged = await refreshSession();
        if (isLogged) {
            showDashboard();
        } else {
            showView("auth");
        }
    }

    // ==========================================================================
    // UTILITY HELPERS
    // ==========================================================================

    function showView(view) {
        if (view === "auth") {
            authView.classList.remove("hidden");
            dashboardView.classList.add("hidden");
        } else {
            authView.classList.add("hidden");
            dashboardView.classList.remove("hidden");
        }
    }

    function showAlert(message, type = "error") {
        authAlert.textContent = message;
        authAlert.className = `alert alert-${type}`;
        authAlert.classList.remove("hidden");
    }

    function hideAlert() {
        authAlert.classList.add("hidden");
    }

    function autoGrowTextarea() {
        chatInput.style.height = "auto";
        chatInput.style.height = (chatInput.scrollHeight) + "px";
    }

    // ==========================================================================
    // SILENT REFRESH & TOKEN ROTATION SERVICE
    // ==========================================================================

    async function refreshSession() {
        try {
            // Call the refresh endpoint. Since HttpOnly cookies are managed by
            // the browser, we must add credentials: "include" to send cross-origin cookies.
            const response = await fetch(`${API_AUTH}/refresh`, { 
                method: "POST",
                credentials: "include"
            });
            
            if (!response.ok) {
                throw new Error("No active session cookie found.");
            }
            
            const res = await response.json();
            accessToken = res.access_token; // Store Access Token in RAM (private variable)
            
            // Retrieve and verify user profile
            const user = await apiCall(`${API_AUTH}/me`);
            username = user.username;
            
            // Schedule next silent token refresh in 14 minutes (before the 15-minute token expires)
            if (refreshTimeoutId) clearTimeout(refreshTimeoutId);
            refreshTimeoutId = setTimeout(refreshSession, 14 * 60 * 1000);
            
            console.log("Access Token refreshed successfully in memory.");
            return true;
        } catch (e) {
            console.log("Silent refresh failed:", e.message);
            return false;
        }
    }

    // ==========================================================================
    // API CALL INTERCEPTOR (WITH AUTO-REFRESH RETRY & CREDENTIALS INCLUDE)
    // ==========================================================================

    async function apiCall(endpoint, method = "GET", body = null, isFormData = false) {
        const headers = {};
        
        if (accessToken) {
            headers["Authorization"] = `Bearer ${accessToken}`;
        }

        // credentials: "include" is required for cross-origin setups (FE on port 5500, BE on port 8000)
        // to permit HTTP cookie read/write access.
        let options = { method, headers, credentials: "include" };

        if (body) {
            if (isFormData) {
                options.body = body;
            } else {
                headers["Content-Type"] = "application/json";
                options.body = JSON.stringify(body);
            }
        }

        try {
            let response = await fetch(endpoint, options);
            
            // API CALL INTERCEPTOR: If 401 occurs, try to rotate token once and retry
            if (response.status === 401 && endpoint !== `${API_AUTH}/login` && endpoint !== `${API_AUTH}/refresh`) {
                console.log("Access Token expired (401). Attempting automatic refresh rotation...");
                const refreshed = await refreshSession();
                
                if (refreshed) {
                    console.log("Token rotation succeeded. Retrying original request...");
                    // Update Authorization header with the new token
                    options.headers["Authorization"] = `Bearer ${accessToken}`;
                    response = await fetch(endpoint, options);
                } else {
                    console.log("Token rotation failed. Forcing logout.");
                    logout();
                    throw new Error("Session expired. Please log in again.");
                }
            }

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Request failed");
            }
            return await response.json();
        } catch (error) {
            console.error(`API Error on ${endpoint}:`, error);
            throw error;
        }
    }

    // ==========================================================================
    // AUTH SERVICE
    // ==========================================================================

    async function handleLogin(e) {
        e.preventDefault();
        hideAlert();
        
        const usernameVal = document.getElementById("login-username").value.trim();
        const passwordVal = document.getElementById("login-password").value;
        
        const formData = new URLSearchParams();
        formData.append("username", usernameVal);
        formData.append("password", passwordVal);

        try {
            const res = await apiCall(`${API_AUTH}/login`, "POST", formData, true);
            accessToken = res.access_token; // Store Access Token in RAM (private variable)
            
            // Get user details
            const user = await apiCall(`${API_AUTH}/me`);
            username = user.username;

            // Schedule the auto-refresh cycle
            if (refreshTimeoutId) clearTimeout(refreshTimeoutId);
            refreshTimeoutId = setTimeout(refreshSession, 14 * 60 * 1000);
            
            showDashboard();
        } catch (error) {
            showAlert(error.message || "Invalid credentials");
        }
    }

    async function handleRegister(e) {
        e.preventDefault();
        hideAlert();
        
        const usernameVal = document.getElementById("reg-username").value.trim();
        const emailVal = document.getElementById("reg-email").value.trim();
        const passwordVal = document.getElementById("reg-password").value;

        try {
            await apiCall(`${API_AUTH}/register`, "POST", {
                username: usernameVal,
                email: emailVal,
                password: passwordVal
            });
            showAlert("Registration successful! Please log in.", "success");
            setTimeout(() => {
                registerForm.classList.add("hidden");
                loginForm.classList.remove("hidden");
                hideAlert();
            }, 1500);
        } catch (error) {
            showAlert(error.message || "Registration failed");
        }
    }

    async function handleLogoutBtn() {
        try {
            // Tell backend to clear HttpOnly refresh cookie
            await apiCall(`${API_AUTH}/logout`, "POST");
        } catch (e) {
            console.error("Server logout request failed, clearing local memory anyway.", e);
        } finally {
            logout();
        }
    }

    function logout() {
        accessToken = null;
        username = null;
        activeSessionId = null;
        sessions = [];
        if (refreshTimeoutId) {
            clearTimeout(refreshTimeoutId);
            refreshTimeoutId = null;
        }
        
        // Reset DOM UI state to prevent visual leaks between users
        chatMessagesWrapper.innerHTML = "";
        sessionsList.innerHTML = "";
        chatTitleText.textContent = "Select or start a conversation";
        chatHeaderActions.classList.add("hidden");
        welcomeState.classList.remove("hidden");
        
        showView("auth");
        // Reset forms
        loginForm.reset();
        registerForm.reset();
    }

    function showDashboard() {
        displayUsername.textContent = username;
        showView("dashboard");
        loadSessionsList(true);
    }

    // ==========================================================================
    // CHAT CONVERSATION SERVICE
    // ==========================================================================

    async function loadSessionsList(selectLatest = false) {
        try {
            sessions = await apiCall(`${API_CHAT}/sessions`);
            renderSessions();
            
            if (selectLatest && sessions.length > 0) {
                loadSession(sessions[0].id);
            } else if (sessions.length === 0) {
                startNewSession(false);
            }
        } catch (e) {
            console.error("Failed to load sessions", e);
        }
    }

    function renderSessions() {
        sessionsList.innerHTML = "";
        if (sessions.length === 0) {
            sessionsList.innerHTML = `<li class="no-session">No chats active</li>`;
            return;
        }

        sessions.forEach(session => {
            const li = document.createElement("li");
            li.setAttribute("data-id", session.id);
            if (session.id === activeSessionId) {
                li.classList.add("active");
            }

            li.innerHTML = `
                <div class="session-left">
                    <i class="fa-solid fa-comments"></i>
                    <span class="session-title">${escapeHTML(session.title)}</span>
                </div>
                <div class="session-actions">
                    <button class="rename-btn" title="Rename"><i class="fa-solid fa-pen"></i></button>
                    <button class="delete-btn delete-action" title="Delete"><i class="fa-solid fa-trash-can"></i></button>
                </div>
            `;

            li.addEventListener("click", (e) => {
                if (e.target.closest(".rename-btn")) {
                    e.stopPropagation();
                    openRenameModalFor(session);
                } else if (e.target.closest(".delete-btn")) {
                    e.stopPropagation();
                    deleteSession(session.id);
                } else {
                    loadSession(session.id);
                    sidebar.classList.remove("open");
                }
            });

            sessionsList.appendChild(li);
        });
    }

    function startNewSession(clearMessages = true) {
        activeSessionId = null;
        chatTitleText.textContent = "New Conversation";
        chatHeaderActions.classList.add("hidden");
        
        document.querySelectorAll(".sessions-list li").forEach(li => li.classList.remove("active"));
        
        if (clearMessages) {
            chatMessagesWrapper.innerHTML = "";
            welcomeState.classList.remove("hidden");
        }
        chatInput.focus();
    }

    async function loadSession(sessionId) {
        activeSessionId = sessionId;
        
        document.querySelectorAll(".sessions-list li").forEach(li => {
            if (li.getAttribute("data-id") === sessionId) {
                li.classList.add("active");
            } else {
                li.classList.remove("active");
            }
        });

        const currentSession = sessions.find(s => s.id === sessionId);
        if (currentSession) {
            chatTitleText.textContent = currentSession.title;
            chatHeaderActions.classList.remove("hidden");
        }

        welcomeState.classList.add("hidden");
        chatMessagesWrapper.innerHTML = "";
        
        try {
            const history = await apiCall(`${API_CHAT}/history?session_id=${sessionId}`);
            history.forEach(msg => {
                appendMessage(msg.role, msg.content);
            });
            scrollToBottom();
        } catch (error) {
            console.error("Failed to load chat history", error);
        }
    }

    async function submitUserMessage() {
        const content = chatInput.value.trim();
        if (!content) return;

        chatInput.value = "";
        chatInput.style.height = "auto";
        welcomeState.classList.add("hidden");

        appendMessage("user", content);
        scrollToBottom();

        chatInput.disabled = true;
        btnSend.disabled = true;

        typingIndicator.classList.remove("hidden");
        scrollToBottom();

        try {
            const res = await apiCall(`${API_CHAT}/message`, "POST", {
                content: content,
                session_id: activeSessionId
            });

            if (!activeSessionId) {
                activeSessionId = res.session_id;
                await loadSessionsList(false);
                chatHeaderActions.classList.remove("hidden");
                document.querySelectorAll(".sessions-list li").forEach(li => {
                    if (li.getAttribute("data-id") === activeSessionId) {
                        li.classList.add("active");
                    }
                });
                const sessionMeta = sessions.find(s => s.id === activeSessionId);
                if (sessionMeta) chatTitleText.textContent = sessionMeta.title;
            }

            typingIndicator.classList.add("hidden");
            appendMessage("assistant", res.content);
            scrollToBottom();
        } catch (e) {
            typingIndicator.classList.add("hidden");
            appendMessage("assistant", "⚠️ Error: Connection to backend server was lost. Please verify your internet or retry later.");
            scrollToBottom();
        } finally {
            chatInput.disabled = false;
            btnSend.disabled = false;
            chatInput.focus();
        }
    }

    function appendMessage(role, content) {
        const messageDiv = document.createElement("div");
        messageDiv.className = `message ${role}`;
        
        const avatarHtml = role === "user" 
            ? `<div class="message-avatar" title="You"><i class="fa-solid fa-user"></i></div>`
            : `<div class="message-avatar" title="HSU Assistant"><i class="fa-solid fa-robot"></i></div>`;
            
        messageDiv.innerHTML = `
            ${avatarHtml}
            <div class="message-content">
                ${escapeHTML(content).replace(/\n/g, '<br>')}
            </div>
        `;
        chatMessagesWrapper.appendChild(messageDiv);
    }

    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // ==========================================================================
    // RENAME / DELETE CRUD OPERATIONS
    // ==========================================================================

    function openRenameModal() {
        const currentSession = sessions.find(s => s.id === activeSessionId);
        if (currentSession) openRenameModalFor(currentSession);
    }

    function openRenameModalFor(session) {
        sessionToRename = session;
        renameInput.value = session.title;
        renameModal.classList.remove("hidden");
        renameInput.focus();
    }

    function closeRenameModal() {
        renameModal.classList.add("hidden");
        sessionToRename = null;
    }

    async function saveSessionRename() {
        const newTitle = renameInput.value.trim();
        if (!newTitle || !sessionToRename) return;

        const sessionId = sessionToRename.id;

        try {
            await apiCall(`${API_CHAT}/sessions/${sessionId}`, "PUT", {
                title: newTitle
            });
            closeRenameModal();
            await loadSessionsList(false);
            if (activeSessionId === sessionId) {
                chatTitleText.textContent = newTitle;
            }
        } catch (error) {
            alert("Failed to rename session: " + error.message);
        }
    }

    async function deleteActiveSession() {
        if (activeSessionId) {
            await deleteSession(activeSessionId);
        }
    }

    async function deleteSession(sessionId) {
        if (!confirm("Are you sure you want to delete this conversation session and all its message history?")) {
            return;
        }

        try {
            await apiCall(`${API_CHAT}/sessions/${sessionId}`, "DELETE");
            if (sessionId === activeSessionId) {
                startNewSession(true);
            }
            await loadSessionsList(false);
        } catch (error) {
            alert("Failed to delete session: " + error.message);
        }
    }

    function escapeHTML(str) {
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});
