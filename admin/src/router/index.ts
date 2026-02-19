import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import Dashboard from '../views/Dashboard.vue';

const router = createRouter({
    history: createWebHistory('/admin/'), // Base URL for admin
    routes: [
        {
            path: '/',
            name: 'dashboard',
            component: Dashboard,
            meta: { requiresAuth: true, requiresAdmin: true }
        }
    ]
});

router.beforeEach(async (to, from, next) => {
    const authStore = useAuthStore();

    if (to.meta.requiresAuth && !authStore.token) {
        window.location.href = '/login';
        return; // Stop navigation
    }

    if (to.meta.requiresAdmin && authStore.user?.role !== 'admin') {
        window.location.href = '/';
        return;
    }

    next();
});

export default router;
