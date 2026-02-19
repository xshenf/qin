<template>
  <div class="admin-layout">
    <nav class="admin-nav">
      <h1>Admin Portal</h1>
      <div class="nav-links">
        <a href="/">Back to App</a>
        <span class="divider">|</span>
        <span>{{ authStore.user?.email }}</span>
        <button @click="logout" class="logout-btn">Logout</button>
      </div>
    </nav>
    <router-view />
  </div>
</template>

<script setup>
import { useAuthStore } from '../src/stores/auth';

const authStore = useAuthStore();

const logout = () => {
    authStore.logout();
    window.location.href = '/login';
};
</script>

<style>
body {
  margin: 0;
  padding: 0;
  font-family: 'Inter', sans-serif;
  background-color: #f4f4f9;
  color: #333;
}

.admin-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.admin-nav {
  background-color: #2c3e50;
  color: white;
  padding: 15px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.admin-nav h1 {
  margin: 0;
  font-size: 1.2rem;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 15px;
}

.nav-links a {
  color: #ccc;
  text-decoration: none;
}

.nav-links a:hover {
  color: white;
}

.logout-btn {
  background: #e74c3c;
  border: none;
  color: white;
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
}
</style>
