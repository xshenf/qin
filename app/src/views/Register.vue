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
      <div class="form-group">
        <label>验证码</label>
        <div class="captcha-container">
          <input type="text" v-model="captcha" placeholder="输入验证码" required />
          <div class="captcha-image" v-html="captchaSvg" @click="refreshCaptcha" title="点击刷新验证码"></div>
        </div>
      </div>
      <button type="submit">Register</button>
    </form>
    <p v-if="message" class="success">{{ message }}</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p>Already have an account? <router-link to="/login">Login</router-link></p>
    <div class="home-link">
      <router-link to="/">返回主页</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useAuthStore } from '../stores/auth';

const email = ref('');
const password = ref('');
const captcha = ref('');
const captchaSvg = ref('');
const message = ref('');
const error = ref('');
const authStore = useAuthStore();
const router = useRouter();

const refreshCaptcha = async () => {
    try {
        const response = await fetch('/api/auth/captcha');
        captchaSvg.value = await response.text();
    } catch (err) {
        console.error('Failed to fetch captcha:', err);
    }
};

import { onMounted } from 'vue';
import { useRouter } from 'vue-router';

onMounted(() => {
    refreshCaptcha();
});

const handleRegister = async () => {
    try {
        await authStore.register(email.value, password.value, captcha.value);
        message.value = '注册成功！现在您可以直接登录了。';
        error.value = '';
    } catch (err) {
        error.value = err;
        message.value = '';
        refreshCaptcha(); // Refresh captcha on failure
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
.captcha-container {
    display: flex;
    gap: 10px;
}
.captcha-container input {
    flex: 1;
}
.captcha-image {
    cursor: pointer;
    height: 40px;
    background: #f0f0f0;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}
.captcha-image :deep(svg) {
    height: 100%;
}
.home-link {
    margin-top: 20px;
    text-align: center;
    border-top: 1px solid #eee;
    padding-top: 15px;
}
.home-link a {
    color: #666;
    text-decoration: none;
    font-size: 0.9em;
}
.home-link a:hover {
    color: #42b983;
}
</style>
