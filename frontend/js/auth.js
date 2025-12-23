document.addEventListener('DOMContentLoaded', () => {
    const authForm = document.getElementById('auth-form');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const submitBtn = document.getElementById('submit-btn');
    const toggleText = document.getElementById('toggle-text');
    const authTitle = document.getElementById('auth-title');
    const errorMsg = document.getElementById('error-msg');

    let isLogin = true;

    const toggleAuthMode = () => {
        isLogin = !isLogin;
        authTitle.innerText = isLogin ? 'Login to Account' : 'Create New Account';
        submitBtn.innerText = isLogin ? 'Sign In' : 'Register';
        toggleText.innerHTML = isLogin
            ? `Don't have an account? <button id="toggle-btn" class="text-blue-400 font-medium hover:underline">Register now</button>`
            : `Already have an account? <button id="toggle-btn" class="text-blue-400 font-medium hover:underline">Sign in</button>`;
        errorMsg.classList.add('hidden');
    };

    toggleText.addEventListener('click', (e) => {
        if (e.target.id === 'toggle-btn') {
            e.preventDefault();
            toggleAuthMode();
        }
    });

    authForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        errorMsg.classList.add('hidden');
        submitBtn.disabled = true;
        submitBtn.innerText = isLogin ? 'Signing In...' : 'Registering...';

        try {
            if (isLogin) {
                // OAuth2 form data for login
                const formData = new FormData();
                formData.append('username', emailInput.value);
                formData.append('password', passwordInput.value);

                const response = await fetch('http://localhost:8000/api/auth/login', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();
                if (!response.ok) throw new Error(data.detail || 'Login failed');

                localStorage.setItem('token', data.access_token);
                window.location.href = 'dashboard.html';
            } else {
                await api.post('/auth/register', {
                    email: emailInput.value,
                    password: passwordInput.value
                });

                // Switch to login after registration
                toggleAuthMode();
                errorMsg.innerText = 'Account created! Please sign in.';
                errorMsg.classList.remove('hidden');
                errorMsg.className = 'mt-4 p-3 bg-green-900/30 border border-green-500/50 text-green-400 text-sm rounded-xl';
            }
        } catch (error) {
            errorMsg.innerText = error.message;
            errorMsg.classList.remove('hidden');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerText = isLogin ? 'Sign In' : 'Register';
        }
    });
});
