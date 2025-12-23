const API_BASE = window.location.origin + '/api';

const api = {
    async request(endpoint, options = {}) {
        const token = localStorage.getItem('token');
        const headers = {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            ...options.headers
        };

        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers
        });

        if (response.status === 401 || response.status === 403) {
            localStorage.removeItem('token');
            if (!window.location.pathname.includes('auth.html')) {
                window.location.href = 'auth.html';
            }
        }

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Something went wrong');
        }
        return data;
    },

    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async get(endpoint) {
        return this.request(endpoint, {
            method: 'GET'
        });
    },

    async delete(endpoint) {
        return this.request(endpoint, {
            method: 'DELETE'
        });
    },

    async patch(endpoint, data) {
        return this.request(endpoint, {
            method: 'PATCH',
            body: JSON.stringify(data)
        });
    },

    async upload(endpoint, formData) {
        const token = localStorage.getItem('token');
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: {
                ...(token ? { 'Authorization': `Bearer ${token}` } : {})
            },
            body: formData
        });

        if (response.status === 403) {
            localStorage.removeItem('token');
            window.location.href = 'auth.html';
        }

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Upload failed');
        }
        return data;
    }
};
