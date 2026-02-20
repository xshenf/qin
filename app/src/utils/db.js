export const DB_NAME = 'QinGuitarAppDB';
export const DB_VERSION = 1;
export const STORE_NAME = 'scores_history';

let dbInstance = null;

export const initDB = () => {
    return new Promise((resolve, reject) => {
        if (dbInstance) {
            resolve(dbInstance);
            return;
        }
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        request.onerror = (event) => reject(event.target.error);
        request.onsuccess = (event) => {
            dbInstance = event.target.result;
            resolve(dbInstance);
        };
        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: 'id' });
            }
        };
    });
};

const getUserPrefix = () => {
    const userStr = localStorage.getItem('user');
    if (userStr) {
        try {
            const user = JSON.parse(userStr);
            return user.email ? `${user.email}_` : 'guest_';
        } catch (e) { }
    }
    return 'guest_';
};

export const saveScore = async (id, name, data, addTime = Date.now()) => {
    const db = await initDB();
    const prefix = getUserPrefix();
    const realId = `${prefix}${id}`;
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        const item = {
            id: realId,
            name,
            data,
            addTime
        };
        const request = store.put(item);
        request.onsuccess = () => resolve({ id, name, addTime }); // Return Original ID
        request.onerror = (e) => reject(e.target.error);
    });
};

export const getScoresList = async () => {
    const db = await initDB();
    const prefix = getUserPrefix();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readonly');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.getAll();
        request.onsuccess = () => {
            const allItems = request.result || [];
            const userItems = allItems.filter(item => String(item.id).startsWith(prefix));
            resolve(userItems.map(item => {
                const originalId = String(item.id).substring(prefix.length);
                return { id: originalId, name: item.name, addTime: item.addTime };
            }).sort((a, b) => b.addTime - a.addTime));
        };
        request.onerror = (e) => reject(e.target.error);
    });
};

export const getScoreData = async (id) => {
    const db = await initDB();
    const prefix = getUserPrefix();
    const realId = `${prefix}${id}`;
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readonly');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.get(realId);
        request.onsuccess = () => {
            const result = request.result;
            if (result) {
                result.id = id; // restore original ID for caller
            }
            resolve(result);
        };
        request.onerror = (e) => reject(e.target.error);
    });
};

export const deleteScore = async (id) => {
    const db = await initDB();
    const prefix = getUserPrefix();
    const realId = `${prefix}${id}`;
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.delete(realId);
        request.onsuccess = () => resolve();
        request.onerror = (e) => reject(e.target.error);
    });
};
