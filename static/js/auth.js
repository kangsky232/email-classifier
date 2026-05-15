const AuthPage = {
    user: null,

    async init() {
        try {
            const data = await API.get("/api/auth/me");
            if (data.authenticated && data.user) {
                this.user = data.user;
                this.updateUI();
            }
        } catch (error) {}
    },

    updateUI() {
        const btn = document.getElementById("user-btn-text");
        if (this.user) {
            btn.textContent = this.user.username;
            document.getElementById("user-btn").onclick = () => this.showUserMenu();
        } else {
            btn.textContent = "Login";
            document.getElementById("user-btn").onclick = () => this.showLogin();
        }
    },

    showLogin(mode = "login") {
        const isLogin = mode === "login";
        App.showModal(`
            <div class="modal-header">
                <h3>${isLogin ? "Login" : "Register"}</h3>
                <button class="modal-close" type="button" onclick="App.closeModal()">&times;</button>
            </div>
            <div class="form-grid">
                <div class="form-group">
                    <label>Username</label>
                    <input id="auth-username" type="text" autocomplete="username" placeholder="Enter username" maxlength="30">
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input id="auth-password" type="password" autocomplete="${isLogin ? 'current-password' : 'new-password'}" placeholder="Enter password" maxlength="50">
                </div>
                <div id="auth-error" class="text-muted"></div>
                <div class="form-actions">
                    <button class="btn" type="button" onclick="AuthPage.showLogin('${isLogin ? 'register' : 'login'}')">
                        ${isLogin ? "Create Account" : "Back to Login"}
                    </button>
                    <button class="btn btn-primary" type="button" onclick="AuthPage.submit('${mode}')">
                        ${isLogin ? "Login" : "Register"}
                    </button>
                </div>
            </div>
        `);
        document.getElementById("auth-password").addEventListener("keydown", (e) => {
            if (e.key === "Enter") AuthPage.submit(mode);
        });
    },

    showUserMenu() {
        App.showModal(`
            <div class="modal-header">
                <h3>${App.escape(this.user.username)}</h3>
                <button class="modal-close" type="button" onclick="App.closeModal()">&times;</button>
            </div>
            <div class="form-grid">
                <p class="text-muted">Logged in as <strong>${App.escape(this.user.username)}</strong></p>
                <div class="form-actions">
                    <button class="btn btn-danger" type="button" onclick="AuthPage.logout()">Logout</button>
                </div>
            </div>
        `);
    },

    async submit(mode) {
        const username = document.getElementById("auth-username").value.trim();
        const password = document.getElementById("auth-password").value.trim();
        const errorEl = document.getElementById("auth-error");

        if (!username || !password) {
            errorEl.innerHTML = '<span style="color:var(--danger)">Please fill all fields</span>';
            return;
        }

        try {
            const endpoint = mode === "login" ? "/api/auth/login" : "/api/auth/register";
            const data = await API.post(endpoint, { username, password });
            if (data.success) {
                this.user = data.user;
                this.updateUI();
                App.closeModal();
                App.showToast(`${mode === "login" ? "Welcome" : "Registered"}, ${data.user.username}!`);
                App.loadPage(App.currentPage);
            }
        } catch (error) {
            errorEl.innerHTML = `<span style="color:var(--danger)">${App.escape(error.message)}</span>`;
        }
    },

    async logout() {
        try {
            await API.post("/api/auth/logout");
        } catch (error) {}
        this.user = null;
        this.updateUI();
        App.closeModal();
        App.showToast("Logged out");
        App.loadPage(App.currentPage);
    }
};
