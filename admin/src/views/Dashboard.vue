<template>
  <div class="admin-dashboard">
    <h2>Admin Dashboard</h2>
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Email</th>
          <th>Role</th>
          <th>Verified</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="user in users" :key="user.id">
          <td>{{ user.id }}</td>
          <td>{{ user.email }}</td>
          <td>{{ user.role }}</td>
          <td>{{ user.is_verified ? 'Yes' : 'No' }}</td>
          <td>
            <button @click="deleteUser(user.id)" class="delete-btn">Delete</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import axios from 'axios';
// We need to ensure we can import from src/stores/auth or duplicate it.
// Vite allows alias '@' usually pointing to src.
import { useAuthStore } from '../../src/stores/auth'; 

const users = ref([]);
const error = ref('');
const authStore = useAuthStore();

const fetchUsers = async () => {
    try {
        const token = authStore.token;
        const response = await axios.get('http://localhost:3000/api/admin/users', {
            headers: { Authorization: `Bearer ${token}` }
        });
        users.value = response.data;
    } catch (err) {
        error.value = 'Failed to fetch users.';
    }
};

const deleteUser = async (id) => {
    if (!confirm('Are you sure?')) return;
    try {
        const token = authStore.token;
        await axios.delete(`http://localhost:3000/api/admin/users/${id}`, {
             headers: { Authorization: `Bearer ${token}` }
        });
        fetchUsers(); // Refresh list
    } catch (err) {
        alert('Failed to delete user');
    }
};

onMounted(() => {
    fetchUsers();
});
</script>

<style scoped>
.admin-dashboard {
    padding: 20px;
}
table {
    width: 100%;
    border-collapse: collapse;
}
th, td {
    padding: 10px;
    border: 1px solid #ddd;
    text-align: left;
}
.delete-btn {
    background-color: #ff4444;
    color: white;
    padding: 5px 10px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}
</style>
