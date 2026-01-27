/**
 * Real-Time Financial Data Dashboard
 */

class PriceDashboard {
    constructor() {
        this.priceHistory = new Map();
        this.historyPage = 0;
        this.historyPageSize = 50;
        this.isLoadingHistory = false;
        this.hasMoreHistory = true;
        this.eventSource = null;

        // Optimization: Throttle history table updates
        this.historyBuffer = [];
        this.historyFlushInterval = null;
        this.maxHistoryRows = 100;  // Reduced from 200

        this.init();
    }

    init() {
        // Load initial data first, then connect SSE
        this.loadLatestPrices().then(() => {
            this.initSSE();
        });
        this.initHistoryTable();
        this.initFilters();

        // Flush history buffer every 3 seconds (reduces DOM operations)
        this.historyFlushInterval = setInterval(() => this.flushHistoryBuffer(), 3000);
    }

    /**
     * Load latest prices from API on page load
     */
    async loadLatestPrices() {
        try {
            const response = await fetch('api/latest-all');
            const data = await response.json();

            if (data.prices && data.prices.length > 0) {
                data.prices.forEach(price => {
                    // Update price card without flash animation (initial load)
                    this.updatePriceCardInitial(price);
                    // Store in history for change calculation
                    const key = `${price.provider}_${price.asset_type}`;
                    this.priceHistory.set(key, price.price);
                });

                // Update statistics for all assets
                const assets = [...new Set(data.prices.map(p => p.asset_type))];
                assets.forEach(asset => this.updateStatistics(asset));
            }
        } catch (error) {
            console.error('Failed to load initial prices:', error);
        }
    }

    /**
     * Update price card without flash animation (for initial load)
     */
    updatePriceCardInitial(data) {
        const el = document.querySelector(`[data-provider="${data.provider}"][data-asset="${data.asset_type}"]`);
        if (!el) return;

        // Price value
        const valueEl = el.querySelector('.price-value');
        if (valueEl) {
            valueEl.textContent = this.formatNumber(data.price);
        }

        // Bid/Ask
        const bidEl = el.querySelector('.bid strong');
        const askEl = el.querySelector('.ask strong');
        if (bidEl) bidEl.textContent = data.bid ? this.formatNumber(data.bid) : '--';
        if (askEl) askEl.textContent = data.ask ? this.formatNumber(data.ask) : '--';

        // Timestamp
        const tsEl = el.querySelector('.timestamp');
        if (tsEl && data.timestamp) {
            const d = new Date(data.timestamp);
            tsEl.textContent = d.toLocaleTimeString('ko-KR');
        }
    }

    /**
     * Format number with thousand separators
     */
    formatNumber(num, decimals = 2) {
        if (num === null || num === undefined || isNaN(num)) return '--';
        return num.toLocaleString('en-US', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }

    /**
     * Initialize Server-Sent Events connection
     */
    initSSE() {
        this.connectSSE();
    }

    connectSSE() {
        this.updateConnectionStatus('연결 중', 'status-disconnected');

        this.eventSource = new EventSource('https://price-api.goldbef.com:8000/api/stream');

        this.eventSource.onopen = () => {
            this.updateConnectionStatus('연결됨', 'status-connected');
        };

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handlePriceUpdate(data);
            } catch (error) {
                console.error('Parse error:', error);
            }
        };

        this.eventSource.onerror = () => {
            this.updateConnectionStatus('연결 끊김', 'status-disconnected');
            setTimeout(() => {
                if (this.eventSource.readyState === EventSource.CLOSED) {
                    this.eventSource.close();
                    this.connectSSE();
                }
            }, 5000);
        };
    }

    updateConnectionStatus(text, className) {
        const el = document.getElementById('connection-status');
        if (el) {
            el.textContent = text;
            el.className = `status-badge ${className}`;
        }
    }

    handlePriceUpdate(data) {
        const key = `${data.provider}_${data.asset_type}`;
        const prevPrice = this.priceHistory.get(key);

        this.updatePriceCard(data, prevPrice);
        this.updateStatistics(data.asset_type);
        this.priceHistory.set(key, data.price);

        // Add to history table in real-time
        this.addToHistoryTable(data);
    }

    /**
     * Add new price data to history buffer (batched for performance)
     */
    addToHistoryTable(data) {
        // Check if current filter matches
        const assetFilter = document.getElementById('asset-filter')?.value || '';
        const providerFilter = document.getElementById('provider-filter')?.value || '';

        if (assetFilter && assetFilter !== data.asset_type) return;
        if (providerFilter && providerFilter !== data.provider) return;

        // Add to buffer instead of immediate DOM update
        this.historyBuffer.push(data);

        // Keep buffer size reasonable
        if (this.historyBuffer.length > 50) {
            this.historyBuffer.shift();
        }
    }

    /**
     * Flush history buffer to DOM (called periodically)
     */
    flushHistoryBuffer() {
        if (this.historyBuffer.length === 0) return;

        const tbody = document.getElementById('history-tbody');
        if (!tbody) return;

        // Use DocumentFragment for batch DOM insertion
        const fragment = document.createDocumentFragment();

        this.historyBuffer.forEach(data => {
            const row = document.createElement('tr');
            const ts = new Date(data.timestamp).toLocaleString('ko-KR');

            row.innerHTML = `
                <td>${ts}</td>
                <td>${this.fmtProvider(data.provider)}</td>
                <td>${this.fmtAsset(data.asset_type)}</td>
                <td>${this.formatNumber(data.price)}</td>
                <td>${data.bid ? this.formatNumber(data.bid) : '--'}</td>
                <td>${data.ask ? this.formatNumber(data.ask) : '--'}</td>
            `;
            row.classList.add('new-row');
            fragment.appendChild(row);
        });

        // Insert all at once
        tbody.insertBefore(fragment, tbody.firstChild);

        // Clear buffer
        this.historyBuffer = [];

        // Remove highlight after animation
        setTimeout(() => {
            tbody.querySelectorAll('.new-row').forEach(row => row.classList.remove('new-row'));
        }, 1000);

        // Limit table rows
        while (tbody.children.length > this.maxHistoryRows) {
            tbody.removeChild(tbody.lastChild);
        }
    }

    updatePriceCard(data, prevPrice) {
        const el = document.querySelector(`[data-provider="${data.provider}"][data-asset="${data.asset_type}"]`);
        if (!el) return;

        // Price value
        const valueEl = el.querySelector('.price-value');
        if (valueEl) {
            valueEl.textContent = this.formatNumber(data.price);
        }

        // Bid/Ask
        const bidEl = el.querySelector('.bid strong');
        const askEl = el.querySelector('.ask strong');
        if (bidEl) bidEl.textContent = data.bid ? this.formatNumber(data.bid) : '--';
        if (askEl) askEl.textContent = data.ask ? this.formatNumber(data.ask) : '--';

        // Change
        if (prevPrice) {
            const change = data.price - prevPrice;
            const pct = (change / prevPrice * 100).toFixed(2);

            const changeEl = el.querySelector('.price-change');
            if (changeEl) {
                const sign = change >= 0 ? '+' : '';
                changeEl.textContent = `${sign}${this.formatNumber(change)} (${sign}${pct}%)`;
                changeEl.className = `price-change ${change >= 0 ? 'positive' : 'negative'}`;
            }

            // Flash
            el.classList.remove('flash-up', 'flash-down');
            void el.offsetWidth;
            el.classList.add(change >= 0 ? 'flash-up' : 'flash-down');
        }

        // Timestamp
        const tsEl = el.querySelector('.timestamp');
        if (tsEl && data.timestamp) {
            const d = new Date(data.timestamp);
            tsEl.textContent = d.toLocaleTimeString('ko-KR');
        }
    }

    updateStatistics(asset) {
        const providers = ['eodhd', 'twelve_data', 'massive'];
        const prices = [];

        providers.forEach(p => {
            const price = this.priceHistory.get(`${p}_${asset}`);
            if (price !== undefined && price !== null) prices.push(price);
        });

        if (prices.length === 0) return;

        const avg = prices.reduce((a, b) => a + b, 0) / prices.length;
        const max = Math.max(...prices);
        const min = Math.min(...prices);
        const spread = max - min;

        this.setStatText(`${asset}-avg`, this.formatNumber(avg));
        this.setStatText(`${asset}-max`, this.formatNumber(max));
        this.setStatText(`${asset}-min`, this.formatNumber(min));
        this.setStatText(`${asset}-spread`, this.formatNumber(spread));
    }

    setStatText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    initHistoryTable() {
        this.loadHistoryPage();

        const container = document.getElementById('history-container');
        if (container) {
            container.addEventListener('scroll', () => {
                const pos = container.scrollTop + container.clientHeight;
                if (pos >= container.scrollHeight - 100 && !this.isLoadingHistory && this.hasMoreHistory) {
                    this.loadHistoryPage();
                }
            });
        }
    }

    initFilters() {
        const btn = document.getElementById('apply-filter');
        if (btn) {
            btn.addEventListener('click', () => {
                this.resetHistory();
                this.loadHistoryPage();
            });
        }
    }

    resetHistory() {
        this.historyPage = 0;
        this.hasMoreHistory = true;
        const tbody = document.getElementById('history-tbody');
        if (tbody) tbody.innerHTML = '';
    }

    async loadHistoryPage() {
        if (this.isLoadingHistory || !this.hasMoreHistory) return;

        this.isLoadingHistory = true;
        this.showLoading(true);

        try {
            const asset = document.getElementById('asset-filter')?.value || '';
            const provider = document.getElementById('provider-filter')?.value || '';

            const params = new URLSearchParams({
                page: this.historyPage,
                page_size: this.historyPageSize,
                ...(asset && { asset }),
                ...(provider && { provider })
            });

            const response = await fetch(`api/history?${params}`);
            const data = await response.json();

            if (data.records && data.records.length > 0) {
                this.renderHistoryRecords(data.records);
                this.historyPage++;
                if (data.records.length < this.historyPageSize) this.hasMoreHistory = false;
            } else {
                this.hasMoreHistory = false;
            }

        } catch (error) {
            console.error('Load history failed:', error);
        } finally {
            this.isLoadingHistory = false;
            this.showLoading(false);
        }
    }

    renderHistoryRecords(records) {
        const tbody = document.getElementById('history-tbody');
        if (!tbody) return;

        records.forEach(r => {
            const row = document.createElement('tr');
            const ts = new Date(r.timestamp).toLocaleString('ko-KR');

            row.innerHTML = `
                <td>${ts}</td>
                <td>${this.fmtProvider(r.provider)}</td>
                <td>${this.fmtAsset(r.asset_type)}</td>
                <td>${this.formatNumber(r.price)}</td>
                <td>${r.bid ? this.formatNumber(r.bid) : '--'}</td>
                <td>${r.ask ? this.formatNumber(r.ask) : '--'}</td>
            `;

            tbody.appendChild(row);
        });
    }

    fmtProvider(p) {
        return { 'eodhd': 'EODHD', 'twelve_data': 'Twelve Data', 'massive': 'Massive' }[p] || p;
    }

    fmtAsset(a) {
        return { 'gold': 'Gold', 'silver': 'Silver', 'usd_krw': 'USD/KRW', 'platinum': 'Platinum', 'palladium': 'Palladium', 'jpy_krw': 'JPY/KRW', 'cny_krw': 'CNY/KRW', 'eur_krw': 'EUR/KRW' }[a] || a;
    }

    showLoading(show) {
        const el = document.getElementById('loading');
        if (el) el.style.display = show ? 'flex' : 'none';
    }

    destroy() {
        if (this.eventSource) this.eventSource.close();
        if (this.historyFlushInterval) clearInterval(this.historyFlushInterval);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new PriceDashboard();
    window.addEventListener('beforeunload', () => dashboard.destroy());
});
