import { ref } from 'vue';

// Default remote URL
const DEFAULT_SOUND_FONT_URL = 'https://unpkg.com/@coderline/alphatab@1.8.1/dist/soundfont/sonivox.sf2';

// Reactive URL - starts with default, updates to blob URL when loaded
export const soundFontUrl = ref(DEFAULT_SOUND_FONT_URL);

let isLoading = false;

export const initSoundFontLoader = () => {
    if (isLoading || soundFontUrl.value.startsWith('blob:')) return;

    isLoading = true;
    console.log("Starting background SoundFont download...");

    fetch(DEFAULT_SOUND_FONT_URL)
        .then(response => {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.blob();
        })
        .then(blob => {
            const localUrl = URL.createObjectURL(blob);
            soundFontUrl.value = localUrl;
            console.log("SoundFont downloaded and cached at:", localUrl);
        })
        .catch(error => {
            console.warn("Failed to preload SoundFont:", error);
            // Fallback is already set (DEFAULT_SOUND_FONT_URL)
        })
        .finally(() => {
            isLoading = false;
        });
};
