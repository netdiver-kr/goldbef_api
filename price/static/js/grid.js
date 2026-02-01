/**
 * KRW Conversion Grid - NauGold Style
 * Percentages as columns, 1g/3.75g as rows
 * Sub-tables: 현재환율 (live rate), 최초고시 (initial rate)
 */
class KRWGrid {
    static TROY_OUNCE_GRAMS = 31.1035;

    // Percentage steps per metal group
    static PCT_GOLD_SILVER = [
        100.00, 100.10, 100.20, 100.25, 100.30, 100.35, 100.40, 100.45,
        100.50, 100.55, 100.60, 100.65, 100.70, 100.75, 100.80, 100.90,
        101.00, 101.10, 101.20, 101.30, 101.40, 101.50, 101.60, 101.70,
        101.80, 101.90, 102.00, 102.20, 102.50, 103.00, 104.00, 105.00,
        107.00, 110.00
    ];

    static PCT_PLAT_PALL = [
        100.00, 101.00, 101.50, 101.80, 102.00, 102.50, 103.00, 104.00
    ];

    static METALS = {
        gold:      { name: '골드',      symbol: 'XAU', pcts: 'PCT_GOLD_SILVER' },
        silver:    { name: '실버',      symbol: 'XAG', pcts: 'PCT_GOLD_SILVER' },
        platinum:  { name: '백금',      symbol: 'XPT', pcts: 'PCT_PLAT_PALL' },
        palladium: { name: '팔라듐',    symbol: 'XPD', pcts: 'PCT_PLAT_PALL' },
    };

    constructor() {
        this.prices = {};       // { gold: 2800, ... }
        this.usdKrw = null;     // live USD/KRW
        this.initialRate = null; // 최초고시환율
        this.cells = {};        // DOM cell references
        this.prevValues = {};   // previous cell values for change detection
    }

    /**
     * Set 최초고시환율
     */
    setInitialRate(rate) {
        if (!rate) return;
        this.initialRate = rate;
        Object.keys(this.prices).forEach(key => this._recalculate(key));
    }

    /**
     * Build all grid tables and insert into container
     */
    buildGrids(container) {
        // Gold and Silver: full-width
        ['gold', 'silver'].forEach(key => {
            const meta = KRWGrid.METALS[key];
            if (!meta) return;
            const pcts = KRWGrid[meta.pcts];
            const card = this._buildMetalGrid(key, meta, pcts);
            container.appendChild(card);
        });

        // Platinum and Palladium: side by side (50:50)
        const pair = document.createElement('div');
        pair.className = 'grid-pair';
        ['platinum', 'palladium'].forEach(key => {
            const meta = KRWGrid.METALS[key];
            if (!meta) return;
            const pcts = KRWGrid[meta.pcts];
            const card = this._buildMetalGrid(key, meta, pcts);
            pair.appendChild(card);
        });
        container.appendChild(pair);
    }

    _buildMetalGrid(metalKey, meta, pcts) {
        const card = document.createElement('div');
        card.className = 'grid-card';

        // Title bar: metal name + USD price + live rate + initial rate
        const title = document.createElement('div');
        title.className = 'grid-title';
        title.innerHTML = `
            <span>${meta.name} (${meta.symbol})</span>
            <span class="grid-title-rates">
                <span class="grid-title-usd" id="grid-usd-${metalKey}">--</span>
                <span class="grid-title-sep">|</span>
                <span class="grid-title-rate">현재 <span id="grid-rate-${metalKey}-live">--</span></span>
                <span class="grid-title-sep">|</span>
                <span class="grid-title-rate">최초 <span id="grid-rate-${metalKey}-initial">--</span></span>
            </span>`;
        card.appendChild(title);

        // Scrollable table wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'grid-scroll';

        const table = document.createElement('table');
        table.className = 'grid-table grid-table-horizontal';

        // Header row: percentages
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        headerRow.innerHTML = '<th class="grid-label-col"></th>';
        pcts.forEach(pct => {
            const th = document.createElement('th');
            th.textContent = pct.toFixed(2) + '%';
            if (pct === 100.00) th.classList.add('pct-100');
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        // Body: live rows + initial rows (no section label rows)
        const tbody = document.createElement('tbody');

        this._buildSubSection(tbody, metalKey, '현재', 'live', pcts);
        this._buildSubSection(tbody, metalKey, '최초', 'initial', pcts);

        table.appendChild(tbody);
        wrapper.appendChild(table);
        card.appendChild(wrapper);

        return card;
    }

    _buildSubSection(tbody, metalKey, prefix, rateType, pcts) {
        // Row 1: per-gram (1g)
        const row1g = document.createElement('tr');
        const td1gLabel = document.createElement('td');
        td1gLabel.className = 'grid-label-col';
        td1gLabel.innerHTML = `<small>${prefix}</small> 1g`;
        row1g.appendChild(td1gLabel);

        pcts.forEach(pct => {
            const td = document.createElement('td');
            td.textContent = '--';
            const cellKey = `${metalKey}_${rateType}_1g_${pct}`;
            this.cells[cellKey] = td;
            row1g.appendChild(td);
        });
        tbody.appendChild(row1g);

        // Row 2: per-돈 (3.75g)
        const row375 = document.createElement('tr');
        const td375Label = document.createElement('td');
        td375Label.className = 'grid-label-col';
        td375Label.innerHTML = `<small>${prefix}</small> 3.75g`;
        row375.appendChild(td375Label);

        pcts.forEach(pct => {
            const td = document.createElement('td');
            td.textContent = '--';
            const cellKey = `${metalKey}_${rateType}_375g_${pct}`;
            this.cells[cellKey] = td;
            row375.appendChild(td);
        });
        tbody.appendChild(row375);
    }

    setMetalPrice(metalKey, priceUSD) {
        if (!priceUSD || !KRWGrid.METALS[metalKey]) return;
        this.prices[metalKey] = priceUSD;

        // Update USD display in title bar
        const usdEl = document.getElementById(`grid-usd-${metalKey}`);
        if (usdEl) {
            usdEl.textContent = Number(priceUSD).toLocaleString('en-US', {
                minimumFractionDigits: 2, maximumFractionDigits: 2
            }) + ' USD';
        }

        this._recalculate(metalKey);
    }

    setExchangeRate(rate) {
        if (!rate) return;
        this.usdKrw = rate;

        // Update rate display for all metals
        Object.keys(KRWGrid.METALS).forEach(key => {
            const el = document.getElementById(`grid-rate-${key}-live`);
            if (el) {
                el.textContent = Number(rate).toLocaleString('ko-KR', {
                    minimumFractionDigits: 2, maximumFractionDigits: 2
                });
            }
        });

        Object.keys(this.prices).forEach(key => this._recalculate(key));
    }

    _recalculate(metalKey) {
        const priceUSD = this.prices[metalKey];
        if (!priceUSD) return;

        const meta = KRWGrid.METALS[metalKey];
        if (!meta) return;
        const pcts = KRWGrid[meta.pcts];

        // Calculate for live rate
        if (this.usdKrw) {
            this._calcSection(metalKey, 'live', priceUSD, this.usdKrw, pcts);
        }

        // Calculate for initial rate
        if (this.initialRate) {
            this._calcSection(metalKey, 'initial', priceUSD, this.initialRate, pcts);

            // Update initial rate display
            Object.keys(KRWGrid.METALS).forEach(key => {
                const el = document.getElementById(`grid-rate-${key}-initial`);
                if (el) {
                    el.textContent = Number(this.initialRate).toLocaleString('ko-KR', {
                        minimumFractionDigits: 2, maximumFractionDigits: 2
                    });
                }
            });
        }
    }

    _calcSection(metalKey, rateType, priceUSD, rate, pcts) {
        pcts.forEach(pct => {
            const krwPerGram = (priceUSD * (pct / 100) * rate) / KRWGrid.TROY_OUNCE_GRAMS;
            const krwPer375 = krwPerGram * 3.75;

            this._updateCell(`${metalKey}_${rateType}_1g_${pct}`, Math.round(krwPerGram));
            this._updateCell(`${metalKey}_${rateType}_375g_${pct}`, Math.round(krwPer375));
        });
    }

    _updateCell(cellKey, value) {
        const td = this.cells[cellKey];
        if (!td) return;

        const formatted = value.toLocaleString('ko-KR');
        const prev = this.prevValues[cellKey];

        if (prev !== formatted) {
            td.textContent = formatted;
            this.prevValues[cellKey] = formatted;

            // Batch class toggle via requestAnimationFrame to avoid per-cell forced reflow
            if (!this._pendingCells) {
                this._pendingCells = [];
                requestAnimationFrame(() => {
                    const cells = this._pendingCells;
                    this._pendingCells = null;
                    cells.forEach(c => c.classList.remove('grid-cell-updated'));
                    // Single reflow for entire batch
                    document.body.offsetHeight;
                    cells.forEach(c => c.classList.add('grid-cell-updated'));
                });
            }
            this._pendingCells.push(td);
        }
    }
}
