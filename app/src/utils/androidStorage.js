import { Preferences } from '@capacitor/preferences';
import { Filesystem, Directory } from '@capacitor/filesystem';
import { Capacitor } from '@capacitor/core';

const isNative = Capacitor.isNativePlatform();

/**
 * 将 Blob/File 转换为 Base64 字符串
 */
const blobToBase64 = (blob) => {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = reject;
        reader.onload = () => {
            const base64String = reader.result.split(',')[1];
            resolve(base64String);
        };
        reader.readAsDataURL(blob);
    });
};

/**
 * 将 Base64 字符串转换为 Blob
 */
const base64ToBlob = (base64, type = 'application/octet-stream') => {
    const byteCharacters = atob(base64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    return new Blob([byteArray], { type });
};

export const saveScoreNative = async (id, name, data, addTime) => {
    // 1. 保存元数据到 Preferences
    const metadata = { id, name, addTime };
    const { value: existingHistoryStr } = await Preferences.get({ key: 'scores_history' });
    let history = [];
    try {
        history = existingHistoryStr ? JSON.parse(existingHistoryStr) : [];
    } catch (e) {
        history = [];
    }

    // 更新或添加
    const index = history.findIndex(item => item.id === id);
    if (index >= 0) {
        history[index] = metadata;
    } else {
        history.push(metadata);
    }

    await Preferences.set({
        key: 'scores_history',
        value: JSON.stringify(history)
    });

    // 2. 如果有文件内容，保存到 Filesystem
    if (data && (data instanceof Blob || data instanceof File)) {
        const base64Data = await blobToBase64(data);
        const fileName = `score_${id}.gp`; // 统一后缀或根据实际情况

        await Filesystem.writeFile({
            path: `scores/${fileName}`,
            data: base64Data,
            directory: Directory.Data,
            recursive: true
        });
    }
};

export const getScoresListNative = async () => {
    const { value } = await Preferences.get({ key: 'scores_history' });
    if (!value) return [];
    try {
        return JSON.parse(value);
    } catch (e) {
        return [];
    }
};

export const getScoreDataNative = async (id) => {
    const fileName = `score_${id}.gp`;
    try {
        const file = await Filesystem.readFile({
            path: `scores/${fileName}`,
            directory: Directory.Data
        });

        // 我们需要找到元数据
        const list = await getScoresListNative();
        const meta = list.find(item => item.id === id);

        if (meta) {
            return {
                ...meta,
                data: base64ToBlob(file.data)
            };
        }
    } catch (e) {
        console.error("Native file read error", e);
    }
    return null;
};

export const deleteScoreNative = async (id) => {
    // 1. 删除元数据
    const list = await getScoresListNative();
    const newList = list.filter(item => item.id !== id);
    await Preferences.set({
        key: 'scores_history',
        value: JSON.stringify(newList)
    });

    // 2. 删除文件
    const fileName = `score_${id}.gp`;
    try {
        await Filesystem.deleteFile({
            path: `scores/${fileName}`,
            directory: Directory.Data
        });
    } catch (e) {
        // 文件可能不存在
    }
};

export { isNative };
