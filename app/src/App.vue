<template>
  <div class="app-layout">
    <!-- <nav class="main-nav">
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
    </nav> -->
    
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

import { onMounted } from 'vue';
import { initSoundFontLoader } from './utils/soundFont';

onMounted(() => {
    initSoundFontLoader();
});
</script>

<style>
/* Global styles */
body {
  margin: 0;
  padding: 0;
  font-family: 'Inter', sans-serif;
  background-color: #f8fafc;
  color: #1e293b;
}

.app-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.main-nav {
  background-color: #ffffff;
  padding: 10px 20px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
}

.nav-links a {
  color: #475569;
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
  color: #94a3b8;
}
</style>
