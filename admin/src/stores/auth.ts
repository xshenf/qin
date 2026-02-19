import { defineStore } from 'pinia';
import axios from 'axios';
import { ref, computed } from 'vue';

const API_URL = 'http://localhost:3000/api/auth';

export const useAuthStore = defineStore('auth', () => {
    const user = ref(JSON.parse(localStorage.getItem('user') || 'null'));
    const token = ref(localStorage.getItem('token') || null);

    const isAuthenticated = computed(() => !!token.value);
    const isAdmin = computed(() => user.value?.role === 'admin');

    async function login(email, password) {
        try {
            const response = await axios.post(`${API_URL}/login`, { email, password });
            token.value = response.data.token;
            user.value = response.data.user;

            localStorage.setItem('token', token.value);
            localStorage.setItem('user', JSON.stringify(user.value));
            return true;
        } catch (error) {
            throw error.response?.data?.message || 'Login failed';
        }
    }

    async function register(email, password) {
        try {
            await axios.post(`${API_URL}/register`, { email, password });
            return true;
        } catch (error) {
            throw error.response?.data?.message || 'Registration failed';
        }
    }

    function logout() {
        token.value = null;
        user.value = null;
        localStorage.removeItem('token');
        localStorage.removeItem('user');
    }

    return { user, token, isAuthenticated, isAdmin, login, register, logout };
});
