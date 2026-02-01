/**
 * Settings Manager
 * Manages user preferences via localStorage
 */
class SettingsManager {
    static KEYS = {
        THEME: 'em_theme',
        PROVIDER: 'em_provider',
        INTERVAL: 'em_interval',
        CHANGE_REF: 'em_change_ref'
    };

    static DEFAULTS = {
        theme: 'light',
        provider: 'eodhd',
        interval: 3000,
        changeRef: 'today_open'
    };

    constructor() {
        this.listeners = new Map();
        this._applyTheme(this.getTheme());
    }

    // --- Getters ---
    getTheme() {
        return localStorage.getItem(SettingsManager.KEYS.THEME) || SettingsManager.DEFAULTS.theme;
    }

    getProvider() {
        return localStorage.getItem(SettingsManager.KEYS.PROVIDER) || SettingsManager.DEFAULTS.provider;
    }

    getInterval() {
        const val = localStorage.getItem(SettingsManager.KEYS.INTERVAL);
        return val ? parseInt(val, 10) : SettingsManager.DEFAULTS.interval;
    }

    getChangeRef() {
        return localStorage.getItem(SettingsManager.KEYS.CHANGE_REF) || SettingsManager.DEFAULTS.changeRef;
    }

    // --- Setters ---
    setTheme(theme) {
        localStorage.setItem(SettingsManager.KEYS.THEME, theme);
        this._applyTheme(theme);
        this._emit('theme', theme);
    }

    setProvider(provider) {
        localStorage.setItem(SettingsManager.KEYS.PROVIDER, provider);
        this._emit('provider', provider);
    }

    setInterval(ms) {
        localStorage.setItem(SettingsManager.KEYS.INTERVAL, ms.toString());
        this._emit('interval', ms);
    }

    setChangeRef(ref) {
        localStorage.setItem(SettingsManager.KEYS.CHANGE_REF, ref);
        this._emit('changeRef', ref);
    }

    // --- Theme ---
    _applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
    }

    toggleTheme() {
        const current = this.getTheme();
        const next = current === 'dark' ? 'light' : 'dark';
        this.setTheme(next);
        return next;
    }

    // --- Event System ---
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event).push(callback);
    }

    _emit(event, data) {
        const cbs = this.listeners.get(event);
        if (cbs) {
            cbs.forEach(cb => cb(data));
        }
    }
}
