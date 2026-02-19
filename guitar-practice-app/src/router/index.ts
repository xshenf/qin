import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import Home from '../views/Home.vue';

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes: [
        {
            path: '/',
            name: 'home',
            component: Home
        },
        {
            path: '/login',
            name: 'login',
            component: () => import('../views/Login.vue')
        },
        {
            path: '/register',
            name: 'register',
            component: () => import('../views/Register.vue')
        }
    ]
});

router.beforeEach(async (to, from, next) => {
    // Client-side protection (optional, maybe specific features)
    // For now, allow public access to Home, but protect if needed.
    next();
});

export default router;
