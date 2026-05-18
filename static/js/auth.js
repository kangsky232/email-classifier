const AuthPage = {
    user: null,

    async init() {
        try {
            const data = await API.get("/api/auth/me");
            if (data.authenticated && data.user) {
                this.user = data.user;
                this.updateUI();
                this.showMainApp();
            } else {
                this.showLoginWall();
            }
        } catch (error) {
            console.error('Failed to check auth status:', error);
            this.showLoginWall();
        }
    },

    showLoginWall() {
        document.querySelector('.app-shell').style.display = 'none';
        const wall = document.getElementById('login-wall') || this.createLoginWall();
        wall.style.display = 'flex';
        this.showLogin('login');
    },

    showMainApp() {
        document.querySelector('.app-shell').style.display = '';
        const wall = document.getElementById('login-wall');
        if (wall) wall.style.display = 'none';
        App.loadPage(App.currentPage);
    },

    createLoginWall() {
        const wall = document.createElement('div');
        wall.id = 'login-wall';
        wall.style.cssText = 'display:flex;align-items:center;justify-content:center;position:fixed;top:0;left:0;width:100%;height:100%;background:var(--bg,#f5f5f5);z-index:9999;';
        wall.innerHTML = `<div id="login-wall-content" style="width:380px;max-width:90vw;"></div>`;
        document.body.appendChild(wall);
        return wall;
    },

    updateUI() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const btn = document.getElementById("user-btn-text");
        if (this.user) {
            btn.textContent = this.user.username;
            document.getElementById("user-btn").onclick = () => this.showUserMenu();
        } else {
            btn.textContent = t("auth.login");
            document.getElementById("user-btn").onclick = () => this.showLogin();
        }
    },

    showLogin(mode = "login") {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const isLogin = mode === "login";
        const html = `
            <div style="background:var(--card,#fff);border-radius:12px;padding:32px;box-shadow:0 4px 24px rgba(0,0,0,.12);">
                <h2 style="margin:0 0 8px;font-size:24px;text-align:center;">${t("auth.app_title")}</h2>
                <p style="margin:0 0 24px;text-align:center;color:var(--muted,#888);">${t("auth.app_desc")}</p>
                <div class="form-grid">
                    <div class="form-group">
                        <label>${t("auth.username")}</label>
                        <input id="auth-username" type="text" autocomplete="username" placeholder="${t("auth.username")}" maxlength="30" style="width:100%;">
                    </div>
                    <div class="form-group">
                        <label>${t("auth.password")}</label>
                        <input id="auth-password" type="password" autocomplete="${isLogin ? 'current-password' : 'new-password'}" placeholder="${t("auth.password")}" maxlength="50" style="width:100%;">
                    </div>
                    <div id="auth-error" class="text-muted"></div>
                    <div class="form-actions" style="display:flex;gap:8px;">
                        <button class="btn" type="button" onclick="AuthPage.showLogin('${isLogin ? 'register' : 'login'}')" style="flex:1;">
                            ${isLogin ? t("auth.register") : t("common.back")}
                        </button>
                        <button class="btn btn-primary" type="button" onclick="AuthPage.submit('${mode}')" style="flex:1;">
                            ${isLogin ? t("auth.login") : t("auth.register")}
                        </button>
                    </div>
                </div>
            </div>
        `;
        const wallContent = document.getElementById('login-wall-content');
        const modalContent = document.getElementById('modal-content');
        if (wallContent && wallContent.parentElement.style.display !== 'none') {
            wallContent.innerHTML = html;
        } else {
            App.showModal(html);
        }
        setTimeout(() => {
            const pw = document.getElementById("auth-password");
            if (pw) pw.addEventListener("keydown", (e) => {
                if (e.key === "Enter") AuthPage.submit(mode);
            });
        }, 50);
    },

    showUserMenu() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        App.showModal(`
            <div class="modal-header">
                <h3>${App.escape(this.user.username)}</h3>
                <button class="modal-close" type="button" onclick="App.closeModal()">&times;</button>
            </div>
            <div class="form-grid">
                <p class="text-muted">${t("auth.username")}: <strong>${App.escape(this.user.username)}</strong></p>
                <div class="form-actions">
                    <button class="btn btn-danger" type="button" onclick="AuthPage.logout()">${t("auth.logout")}</button>
                </div>
            </div>
        `);
    },

    async submit(mode) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const username = document.getElementById("auth-username").value.trim();
        const password = document.getElementById("auth-password").value.trim();
        const errorEl = document.getElementById("auth-error");
        const submitBtn = document.querySelector('.btn-primary');

        if (!username || !password) {
            errorEl.innerHTML = `<span style="color:var(--danger)">${t("auth.fill_all")}</span>`;
            return;
        }

        if (submitBtn) submitBtn.disabled = true;
        try {
            const endpoint = mode === "login" ? "/api/auth/login" : "/api/auth/register";
            const data = await API.post(endpoint, { username, password });
            if (data.success) {
                this.user = data.user;
                this.updateUI();
                App.closeModal();
                this.showMainApp();
                App.showToast(`${mode === "login" ? t("auth.welcome") : t("auth.registered")}, ${data.user.username}!`);
            }
        } catch (error) {
            console.error('Auth submit failed:', error);
            errorEl.innerHTML = `<span style="color:var(--danger)">${App.escape(error.message)}</span>`;
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    },

    async logout() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        try {
            await API.post("/api/auth/logout");
        } catch (error) {
            console.error('Logout request failed:', error);
        }
        this.user = null;
        this.updateUI();
        App.closeModal();
        this.showLoginWall();
        App.showToast(t("auth.logged_out"));
    }
};
