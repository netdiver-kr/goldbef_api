/**
 * EurasiaMetal Price Dashboard - Main Application
 * SSE connection, price updates, burn-in prevention
 */
class PriceApp {
    static ASSETS = {
        gold:      { name: 'Gold',      symbol: 'XAU/USD', decimals: 2 },
        silver:    { name: 'Silver',    symbol: 'XAG/USD', decimals: 4 },
        platinum:  { name: 'Platinum',  symbol: 'XPT/USD', decimals: 2 },
        palladium: { name: 'Palladium', symbol: 'XPD/USD', decimals: 2 },
        usd_krw:   { name: 'USD/KRW',  symbol: 'USD/KRW', decimals: 2 },
    };

    // Which assets each provider actually sends data for
    // Assets NOT listed here will fall back to accepting from any provider
    static PROVIDER_ASSETS = {
        eodhd:      ['gold', 'silver', 'platinum', 'palladium', 'usd_krw'],
        twelve_data: ['gold', 'silver', 'platinum', 'palladium', 'usd_krw'],
        massive:    ['gold', 'silver', 'platinum', 'palladium', 'usd_krw', 'jpy_krw', 'cny_krw', 'eur_krw', 'hkd_krw'],
    };

    constructor() {
        this.settings = new SettingsManager();
        this.grid = new KRWGrid();
        this.rollers = {};       // { assetKey: RollingNumber }
        this.prevPrices = {};    // { assetKey: price } - last tick for flash direction
        this.refPrices = {};     // { assetKey: price } - reference for change display
        this.allRefPrices = {};  // { assetKey: { today_open, lse_close, nyse_close } }
        this.eventSource = null;
        this.lastGlobalUpdate = 0;      // global throttle timestamp
        this._throttleBatchOpen = false; // batch window flag
        this.fallbackLock = {};  // { assetKey: providerName } - lock fallback to first provider
        this.burnInTimer = null;

        this._init();
    }

    _init() {
        // Build KRW grids
        const gridContainer = document.getElementById('grid-container');
        if (gridContainer) {
            this.grid.buildGrids(gridContainer);
        }

        // Initialize rolling numbers for each asset
        Object.entries(PriceApp.ASSETS).forEach(([key, meta]) => {
            const el = document.querySelector(`[data-asset="${key}"] .price-value`);
            if (el) {
                this.rollers[key] = new RollingNumber(el, { decimals: meta.decimals });
            }
        });

        // Clean up flash classes after animation ends (ensures reliable restart)
        document.querySelectorAll('.price-card').forEach(card => {
            card.addEventListener('animationend', () => {
                card.classList.remove('flash-up', 'flash-down');
            });
        });

        // Settings event listeners
        this.settings.on('provider', () => { this.fallbackLock = {}; this._loadInitialPrices(); this._loadReferencePrices(); });
        this.settings.on('interval', () => {
            // Interval change - throttle is handled in handleUpdate
        });
        this.settings.on('changeRef', () => {
            this._applyReferencePrices();
            this._updateRefPricePanel();
        });

        // Theme toggle button
        const themeBtn = document.getElementById('btn-theme');
        if (themeBtn) {
            const sunIcon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
            const moonIcon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
            themeBtn.addEventListener('click', () => {
                const next = this.settings.toggleTheme();
                themeBtn.innerHTML = next === 'dark' ? sunIcon : moonIcon;
                // Sync drawer theme switch
                const sw = document.getElementById('theme-switch');
                const lbl = document.getElementById('theme-label');
                if (sw) sw.checked = next === 'dark';
                if (lbl) lbl.textContent = next === 'dark' ? '다크 모드' : '라이트 모드';
            });
            themeBtn.innerHTML = this.settings.getTheme() === 'dark' ? sunIcon : moonIcon;
        }

        // Settings drawer
        this._initSettingsDrawer();

        // Connect SSE immediately, load initial data in parallel
        this._connectSSE();
        this._loadInitialPrices();
        this._loadReferencePrices();

        // Burn-in prevention: subtle pixel shift every 10 minutes
        this._startBurnInPrevention();

        // London Fix & Initial Rate (refresh every 30 min for long-running pages)
        this._loadLondonFix();
        this._loadInitialRate();
        this._dailyRefreshTimer = setInterval(() => {
            this._loadLondonFix();
            this._loadInitialRate();
            this._loadReferencePrices(); // Also refresh reference prices
        }, 1800000);

        // Schedule-based refresh for critical times (KST 08:00, 08:05, 08:10)
        // KST = UTC+9, so 08:00 KST = 23:00 UTC previous day
        this._scheduleKSTRefresh();

        // Market hours (update every minute)
        this._updateMarketHours();
        this._marketHoursTimer = setInterval(() => this._updateMarketHours(), 60000);
    }

    // --- SSE Connection ---
    _connectSSE() {
        this._updateConnectionStatus('연결 중', false);

        this.eventSource = new EventSource('/api/stream');

        this.eventSource.onopen = () => {
            this._updateConnectionStatus('연결됨', true);
        };

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this._handleUpdate(data);
            } catch (e) {
                // ignore parse errors
            }
        };

        this.eventSource.onerror = () => {
            this._updateConnectionStatus('연결 끊김', false);
            setTimeout(() => {
                if (this.eventSource && this.eventSource.readyState === EventSource.CLOSED) {
                    this.eventSource.close();
                    this._connectSSE();
                }
            }, 5000);
        };
    }

    _updateConnectionStatus(text, connected) {
        const el = document.getElementById('connection-status');
        if (el) {
            el.textContent = text;
            el.className = `status-badge ${connected ? 'status-connected' : 'status-disconnected'}`;
        }
    }

    // --- Price Updates ---
    _handleUpdate(data) {
        const provider = data.provider;
        const asset = data.asset_type;
        const selectedProvider = this.settings.getProvider();

        // Check if the selected provider supports this asset
        const supported = PriceApp.PROVIDER_ASSETS[selectedProvider] || [];
        if (supported.includes(asset)) {
            // Supported asset - only accept from selected provider
            if (provider !== selectedProvider) return;
        } else {
            // Unsupported asset (e.g. XPT on EODHD) - lock to first provider that delivers
            if (!this.fallbackLock[asset]) this.fallbackLock[asset] = provider;
            if (provider !== this.fallbackLock[asset]) return;
        }

        // Global throttle - all assets update together
        const interval = this.settings.getInterval();
        const now = Date.now();
        if (!this._throttleBatchOpen) {
            if (now - this.lastGlobalUpdate < interval) return;
            this._throttleBatchOpen = true;
            this.lastGlobalUpdate = now;
            setTimeout(() => { this._throttleBatchOpen = false; }, 500);
        }

        // Update price card
        this._updatePriceCard(asset, data);

        // Update KRW grid
        if (asset === 'usd_krw') {
            this.grid.setExchangeRate(data.price);
        } else if (KRWGrid.METALS[asset]) {
            this.grid.setMetalPrice(asset, data.price);
        }
    }

    _updatePriceCard(asset, data) {
        const card = document.querySelector(`.price-card[data-asset="${asset}"]`);
        if (!card) return;

        const meta = PriceApp.ASSETS[asset];
        if (!meta) return;

        // Rolling number animation
        const roller = this.rollers[asset];
        if (roller) {
            roller.setValue(data.price);
        }

        // Flash animation based on tick-to-tick change
        const prevPrice = this.prevPrices[asset];
        if (prevPrice && data.price !== prevPrice) {
            const cls = data.price > prevPrice ? 'flash-up' : 'flash-down';
            card.classList.remove('flash-up', 'flash-down');
            // Double rAF ensures browser processes the removal before re-adding
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    card.classList.add(cls);
                });
            });
        }
        this.prevPrices[asset] = data.price;

        // Change display based on reference price
        this._updateChangeDisplay(asset, data.price);

        // Bid / Ask
        const bidEl = card.querySelector('.bid-value');
        const askEl = card.querySelector('.ask-value');
        if (bidEl) bidEl.textContent = data.bid ? this._fmt(data.bid, meta.decimals) : '--';
        if (askEl) askEl.textContent = data.ask ? this._fmt(data.ask, meta.decimals) : '--';
    }

    _updateChangeDisplay(asset, currentPrice) {
        const card = document.querySelector(`.price-card[data-asset="${asset}"]`);
        if (!card) return;

        const ref = this.refPrices[asset];
        if (!ref) return;

        const meta = PriceApp.ASSETS[asset];
        if (!meta) return;

        const change = currentPrice - ref;
        const pct = (change / ref * 100);
        const sign = change >= 0 ? '+' : '';

        const changeEl = card.querySelector('.price-change');
        if (changeEl) {
            changeEl.textContent = `${sign}${this._fmt(change, meta.decimals)} (${sign}${pct.toFixed(2)}%)`;
            changeEl.className = `price-change ${change >= 0 ? 'up' : 'down'}`;
        }
    }

    // --- Initial Load ---
    async _loadInitialPrices() {
        try {
            const response = await fetch('/api/latest-all');
            const data = await response.json();

            if (!data.prices || data.prices.length === 0) return;

            const selectedProvider = this.settings.getProvider();
            const supported = PriceApp.PROVIDER_ASSETS[selectedProvider] || [];
            const loaded = new Set(); // track which assets we already loaded
            this.fallbackLock = {};   // reset fallback locks on load

            data.prices.forEach(p => {
                // For supported assets, only accept from selected provider
                // For unsupported assets (e.g. XPT on EODHD), lock to first provider in response
                if (supported.includes(p.asset_type)) {
                    if (p.provider !== selectedProvider) return;
                } else {
                    if (loaded.has(p.asset_type)) return;
                    // Lock fallback provider for SSE consistency
                    if (!this.fallbackLock[p.asset_type]) this.fallbackLock[p.asset_type] = p.provider;
                }
                loaded.add(p.asset_type);

                const meta = PriceApp.ASSETS[p.asset_type];
                if (!meta) return;

                // Set rolling number without animation
                const roller = this.rollers[p.asset_type];
                if (roller) {
                    roller.setValueImmediate(p.price);
                }

                // Bid/Ask
                const card = document.querySelector(`.price-card[data-asset="${p.asset_type}"]`);
                if (card) {
                    const bidEl = card.querySelector('.bid-value');
                    const askEl = card.querySelector('.ask-value');
                    if (bidEl) bidEl.textContent = p.bid ? this._fmt(p.bid, meta.decimals) : '--';
                    if (askEl) askEl.textContent = p.ask ? this._fmt(p.ask, meta.decimals) : '--';

                    const provBadge = card.querySelector('.provider-badge');
                    if (provBadge) {
                        provBadge.textContent = this._providerLabel(p.provider);
                    }
                }

                this.prevPrices[p.asset_type] = p.price;

                // Update grid
                if (p.asset_type === 'usd_krw') {
                    this.grid.setExchangeRate(p.price);
                } else if (KRWGrid.METALS[p.asset_type]) {
                    this.grid.setMetalPrice(p.asset_type, p.price);
                }
            });
        } catch (e) {
            console.error('Failed to load initial prices:', e);
        }
    }

    // --- Reference Prices ---
    async _loadReferencePrices() {
        try {
            const provider = this.settings.getProvider();
            const response = await fetch(`/api/reference-prices?provider=${provider}`);
            if (!response.ok) return;
            const data = await response.json();
            this.allRefPrices = data;
            this._applyReferencePrices();
            this._updateRefPricePanel();
        } catch (e) {
            // Reference prices API not available yet
        }
    }

    _applyReferencePrices() {
        const refType = this.settings.getChangeRef();
        Object.entries(this.allRefPrices).forEach(([asset, refs]) => {
            const ref = refs[refType];
            if (ref != null) {
                this.refPrices[asset] = ref;
            }
        });

        // Re-apply change display for all assets with current prices
        Object.entries(this.prevPrices).forEach(([asset, price]) => {
            this._updateChangeDisplay(asset, price);
        });
    }

    // --- London Fix ---
    async _loadLondonFix() {
        try {
            const response = await fetch('/api/london-fix');
            if (!response.ok) return;
            const data = await response.json();

            if (data.gold_am != null) this._setText('london-gold-am', this._fmt(data.gold_am, 2));
            if (data.gold_pm != null) this._setText('london-gold-pm', this._fmt(data.gold_pm, 2));
            if (data.silver != null) this._setText('london-silver', this._fmt(data.silver, 4));
            if (data.platinum_am != null) this._setText('london-platinum-am', this._fmt(data.platinum_am, 2));
            if (data.platinum_pm != null) this._setText('london-platinum-pm', this._fmt(data.platinum_pm, 2));
            if (data.palladium_am != null) this._setText('london-palladium-am', this._fmt(data.palladium_am, 2));
            if (data.palladium_pm != null) this._setText('london-palladium-pm', this._fmt(data.palladium_pm, 2));
            if (data.date) this._setText('london-fix-date', data.date);
        } catch (e) {
            // London Fix not available yet
        }
    }

    // --- Initial Exchange Rate ---
    async _loadInitialRate() {
        try {
            const response = await fetch('/api/initial-rate');
            if (!response.ok) return;
            const data = await response.json();

            if (data.rate != null) {
                this._setText('initial-rate-value', this._fmt(data.rate, 2));
                // Feed initial rate to grid for 최초고시 calculation
                this.grid.setInitialRate(data.rate);
            }
            if (data.date) {
                this._setText('initial-rate-date', data.date);
            }
        } catch (e) {
            // Initial rate API not available yet
        }
    }

    // --- Market Hours ---
    static MARKETS = [
        { id: 'london',   name: 'London (LSE)',    tz: 'Europe/London',    openH: 8, closeH: 16, closeM: 30 },
        { id: 'newyork',  name: 'New York (NYSE)', tz: 'America/New_York', openH: 9, openM: 30, closeH: 16 },
        { id: 'seoul',    name: 'Seoul (KRX)',     tz: 'Asia/Seoul',       openH: 9, closeH: 15, closeM: 30 },
        { id: 'shanghai', name: 'Shanghai (SSE)',   tz: 'Asia/Shanghai',   openH: 9, openM: 30, closeH: 15 },
        { id: 'sydney',   name: 'Sydney (ASX)',    tz: 'Australia/Sydney', openH: 10, closeH: 16 },
    ];

    _updateMarketHours() {
        const now = new Date();
        PriceApp.MARKETS.forEach(m => {
            const local = new Date(now.toLocaleString('en-US', { timeZone: m.tz }));
            const h = local.getHours();
            const min = local.getMinutes();
            const current = h * 60 + min;
            const open = m.openH * 60 + (m.openM || 0);
            const close = m.closeH * 60 + (m.closeM || 0);
            const day = local.getDay(); // 0=Sun, 6=Sat
            const isWeekday = day >= 1 && day <= 5;
            const isOpen = isWeekday && current >= open && current < close;

            const dot = document.getElementById(`dot-${m.id}`);
            if (dot) {
                dot.classList.toggle('open', isOpen);
            }

            const timeEl = document.getElementById(`time-${m.id}`);
            if (timeEl) {
                const hh = String(local.getHours()).padStart(2, '0');
                const mm = String(local.getMinutes()).padStart(2, '0');
                timeEl.textContent = `${hh}:${mm}`;
            }
        });
    }

    // --- Reference Price Display ---
    _updateRefPricePanel() {
        const refType = this.settings.getChangeRef();
        const labels = {
            today_open: '당일 시작가',
            nyse_close: 'NYSE 마감',
            lse_close: 'LSE 마감'
        };
        const labelEl = document.getElementById('ref-type-label');
        if (labelEl) labelEl.textContent = labels[refType] || refType;

        const assets = ['gold', 'silver', 'platinum', 'palladium', 'usd_krw'];
        const decimalsMap = { gold: 2, silver: 4, platinum: 2, palladium: 2, usd_krw: 2 };

        assets.forEach(asset => {
            const el = document.getElementById(`ref-${asset}`);
            if (!el) return;
            const refs = this.allRefPrices[asset];
            const val = refs ? refs[refType] : null;
            if (val != null) {
                el.textContent = this._fmt(val, decimalsMap[asset]);
                el.classList.remove('placeholder');
            } else {
                el.textContent = '--';
            }
        });
    }

    // --- Schedule-based Refresh for KST 08:00 ---
    _scheduleKSTRefresh() {
        // Critical refresh times (KST hours)
        const KST_REFRESH_HOURS = [8]; // 08:00 KST - today_open update
        const KST_REFRESH_MINUTES = [0, 5, 10, 15]; // Retry at :00, :05, :10, :15

        const checkAndRefresh = () => {
            const now = new Date();
            // Convert to KST (UTC+9)
            const kst = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Seoul' }));
            const hour = kst.getHours();
            const minute = kst.getMinutes();

            // Check if we're at a critical refresh time
            if (KST_REFRESH_HOURS.includes(hour) && KST_REFRESH_MINUTES.includes(minute)) {
                console.log(`[KST Refresh] Triggered at KST ${hour}:${String(minute).padStart(2, '0')}`);
                this._loadReferencePrices();
                this._loadLondonFix();
                this._loadInitialRate();
            }
        };

        // Check every minute
        this._kstRefreshTimer = setInterval(checkAndRefresh, 60000);

        // Also check immediately on load
        checkAndRefresh();
    }

    // --- Burn-in Prevention ---
    _startBurnInPrevention() {
        const container = document.querySelector('.main-container');
        if (!container) return;

        container.classList.add('burn-in-shift');

        this.burnInTimer = setInterval(() => {
            const x = (Math.random() * 2 - 1).toFixed(1); // -1 ~ 1px
            const y = (Math.random() * 2 - 1).toFixed(1);
            container.style.transform = `translate(${x}px, ${y}px)`;
        }, 600000); // 10 minutes
    }

    // --- Utilities ---
    _fmt(num, decimals) {
        if (num == null || isNaN(num)) return '--';
        return Number(num).toLocaleString('en-US', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }

    _providerLabel(provider) {
        const map = { eodhd: 'EODHD', twelve_data: 'TwelveData', massive: 'Massive' };
        return map[provider] || provider;
    }

    _setText(id, text) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = text;
            el.classList.remove('placeholder');
        }
    }

    // --- Settings Drawer ---
    _initSettingsDrawer() {
        const drawer = document.getElementById('settings-drawer');
        const backdrop = document.getElementById('settings-backdrop');
        const openBtn = document.getElementById('btn-settings');
        const closeBtn = document.getElementById('drawer-close');

        if (!drawer || !backdrop) return;

        const open = () => {
            drawer.classList.add('open');
            backdrop.classList.add('open');
        };
        const close = () => {
            drawer.classList.remove('open');
            backdrop.classList.remove('open');
        };

        if (openBtn) openBtn.addEventListener('click', open);
        if (closeBtn) closeBtn.addEventListener('click', close);
        backdrop.addEventListener('click', close);

        // Reset button
        const resetBtn = document.getElementById('btn-reset-settings');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                const D = SettingsManager.DEFAULTS;
                // Theme
                this.settings.setTheme(D.theme);
                const sw = document.getElementById('theme-switch');
                const lbl = document.getElementById('theme-label');
                if (sw) sw.checked = D.theme === 'dark';
                if (lbl) lbl.textContent = D.theme === 'dark' ? '다크 모드' : '라이트 모드';
                const themeBtn = document.getElementById('btn-theme');
                if (themeBtn) {
                    const sunIcon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
                    const moonIcon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
                    themeBtn.innerHTML = D.theme === 'dark' ? sunIcon : moonIcon;
                }
                // Provider
                this.settings.setProvider(D.provider);
                const pr = document.querySelector(`input[name="provider"][value="${D.provider}"]`);
                if (pr) pr.checked = true;
                // Change Reference
                this.settings.setChangeRef(D.changeRef);
                const cr = document.querySelector(`input[name="changeref"][value="${D.changeRef}"]`);
                if (cr) cr.checked = true;
                // Interval
                this.settings.setInterval(D.interval);
                const ir = document.querySelector(`input[name="interval"][value="${D.interval}"]`);
                if (ir) ir.checked = true;
            });
        }

        // Theme toggle
        const themeSwitch = document.getElementById('theme-switch');
        const themeLabel = document.getElementById('theme-label');
        if (themeSwitch && themeLabel) {
            const currentTheme = this.settings.getTheme();
            themeSwitch.checked = currentTheme === 'dark';
            themeLabel.textContent = currentTheme === 'dark' ? '다크 모드' : '라이트 모드';

            themeSwitch.addEventListener('change', () => {
                const next = themeSwitch.checked ? 'dark' : 'light';
                this.settings.setTheme(next);
                themeLabel.textContent = next === 'dark' ? '다크 모드' : '라이트 모드';
                // Update header theme button icon
                const themeBtn = document.getElementById('btn-theme');
                if (themeBtn) {
                    const sunIcon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
                    const moonIcon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
                    themeBtn.innerHTML = next === 'dark' ? sunIcon : moonIcon;
                }
            });
        }

        // Provider radios
        const currentProvider = this.settings.getProvider();
        const provRadio = document.querySelector(`input[name="provider"][value="${currentProvider}"]`);
        if (provRadio) provRadio.checked = true;

        document.querySelectorAll('input[name="provider"]').forEach(radio => {
            radio.addEventListener('change', () => {
                this.settings.setProvider(radio.value);
            });
        });

        // Change Reference radios
        const currentRef = this.settings.getChangeRef();
        const refRadio = document.querySelector(`input[name="changeref"][value="${currentRef}"]`);
        if (refRadio) refRadio.checked = true;

        document.querySelectorAll('input[name="changeref"]').forEach(radio => {
            radio.addEventListener('change', () => {
                this.settings.setChangeRef(radio.value);
            });
        });

        // Interval radios
        const currentInterval = this.settings.getInterval().toString();
        const intRadio = document.querySelector(`input[name="interval"][value="${currentInterval}"]`);
        if (intRadio) intRadio.checked = true;

        document.querySelectorAll('input[name="interval"]').forEach(radio => {
            radio.addEventListener('change', () => {
                this.settings.setInterval(parseInt(radio.value, 10));
            });
        });
    }

    destroy() {
        if (this.eventSource) this.eventSource.close();
        if (this.burnInTimer) clearInterval(this.burnInTimer);
        if (this._dailyRefreshTimer) clearInterval(this._dailyRefreshTimer);
        if (this._marketHoursTimer) clearInterval(this._marketHoursTimer);
        if (this._kstRefreshTimer) clearInterval(this._kstRefreshTimer);
    }
}

// --- Boot ---
document.addEventListener('DOMContentLoaded', () => {
    const app = new PriceApp();
    window.addEventListener('beforeunload', () => app.destroy());
});
