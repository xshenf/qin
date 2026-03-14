import { ref } from 'vue';
import { SOUND_FONT_URL } from '../config/alphaTabConfig';

export const soundFontUrl = ref(SOUND_FONT_URL);

// 空的初始化函数，向后兼容调用处
export const initSoundFontLoader = () => {};
