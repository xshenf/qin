<template>
  <div class="app-layout">
    <nav class="main-nav">
      <div class="nav-links">
        <router-link to="/">Home</router-link> |
        <template v-if="!authStore.isAuthenticated">
          <router-link to="/login">Login</router-link> |
          <router-link to="/register">Register</router-link>
        </template>
        <template v-else>
          <span class="user-info">Welcome, {{ authStore.user?.email }}</span>
          <a href="#" @click.prevent="logout">Logout</a>
          <span v-if="authStore.isAdmin"> | <router-link to="/admin">Admin</router-link></span>
        </template>
      </div>
    </nav>
    
    <router-view />
  </div>
</template>

<script setup>
import { useAuthStore } from './stores/auth';
import { useRouter } from 'vue-router';

const authStore = useAuthStore();
const router = useRouter();

const logout = () => {
    authStore.logout();
    router.push('/login');
};
</script>

<style>
/* Global styles */
body {
  margin: 0;
  padding: 0;
  font-family: 'Inter', sans-serif;
  background-color: #1a1a2e;
  color: #e0e0e0;
}

.app-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.main-nav {
  background-color: #16213e;
  padding: 10px 20px;
  border-bottom: 1px solid #2a2a4a;
  display: flex;
  justify-content: flex-end;
}

.nav-links a {
  color: #e0e0e0;
  text-decoration: none;
  margin: 0 5px;
}

.nav-links a:hover {
  text-decoration: underline;
  color: #42b883;
}

.nav-links a.router-link-active {
  color: #42b883;
  font-weight: bold;
}

.user-info {
  margin-right: 10px;
  color: #888;
}
</style>
