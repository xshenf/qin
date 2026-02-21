import axios from 'axios';

const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || '/api',
    timeout: 10000,
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export const login = async (username, password) => {
    const res = await api.post('/auth/login', { username, password });
    if (res.data.token) {
        localStorage.setItem('token', res.data.token);
        localStorage.setItem('user', JSON.stringify(res.data.user || { username }));
    }
    return res.data;
};

export const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
};

import { getScoreData } from './db.js';

export const syncHistoryToBackend = async (historyList, syncDataId = null) => {
    if (!localStorage.getItem('token')) return;

    try {
        const syncData = await Promise.all(historyList.map(async (item) => {
            let base64Data = null;

            // Only fetch full data if this is the currently loading score
            if (syncDataId === item.id) {
                const row = await getScoreData(item.id);
                if (row && row.data) {
                    // If the data is a File/Blob, read it as base64
                    if (row.data instanceof Blob) {
                        base64Data = await new Promise((resolve) => {
                            const reader = new FileReader();
                            reader.onloadend = () => {
                                // Extract just the base64 part, split out the data URL prefix
                                const text = reader.result.split(',')[1];
                                resolve(text);
                            };
                            reader.readAsDataURL(row.data);
                        });
                    }
                }
            }

            return {
                id: item.id,
                name: item.name,
                addTime: item.addTime,
                data: base64Data
            };
        }));

        return api.post('/user/history/sync', { history: syncData });
    } catch (e) {
        console.error("Sync data error", e);
    }
};

export const fetchHistoryFromBackend = async () => {
    if (!localStorage.getItem('token')) return [];
    try {
        const res = await api.get('/user/history');
        return res.data;
    } catch (e) {
        console.error("Fetch history error", e);
        return [];
    }
};

export const fetchScoreDataFromBackend = async (localId) => {
    if (!localStorage.getItem('token')) return null;
    try {
        const res = await api.get(`/user/history/${localId}/data`);
        if (res.data && res.data.data) {
            // Convert base64 back to Blob
            const byteCharacters = atob(res.data.data);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            return new Blob([byteArray]);
        }
    } catch (e) {
        console.error("Fetch score data error", e);
    }
    return null;
};

export default api;
