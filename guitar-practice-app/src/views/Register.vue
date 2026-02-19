<template>
  <div class="auth-container">
    <h2>Register</h2>
    <form @submit.prevent="handleRegister">
      <div class="form-group">
        <label>Email</label>
        <input type="email" v-model="email" required />
      </div>
      <div class="form-group">
        <label>Password</label>
        <input type="password" v-model="password" required />
      </div>
      <button type="submit">Register</button>
    </form>
    <p v-if="message" class="success">{{ message }}</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p>Already have an account? <router-link to="/login">Login</router-link></p>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useAuthStore } from '../stores/auth';

const email = ref('');
const password = ref('');
const message = ref('');
const error = ref('');
const authStore = useAuthStore();

const handleRegister = async () => {
    try {
        await authStore.register(email.value, password.value);
        message.value = 'Registration successful! Please check the backend console for verification link.';
        error.value = '';
    } catch (err) {
        error.value = err;
        message.value = '';
    }
};
</script>

<style scoped>
/* Same styles as Login.vue */
.auth-container {
    max-width: 400px;
    margin: 50px auto;
    padding: 20px;
    border: 1px solid #ccc;
    border-radius: 8px;
}
.form-group {
    margin-bottom: 15px;
}
label {
    display: block;
    margin-bottom: 5px;
}
input {
    width: 100%;
    padding: 8px;
    box-sizing: border-box;
}
button {
    width: 100%;
    padding: 10px;
    background-color: #42b983;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}
button:hover {
    background-color: #3aa876;
}
.error {
    color: red;
}
.success {
    color: green;
}
</style>
