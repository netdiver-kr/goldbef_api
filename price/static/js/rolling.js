/**
 * Toss-style Rolling Number Animation
 * Each digit rolls independently via CSS translateY
 * Uses pixel-snapped heights to prevent sub-pixel misalignment
 */
class RollingNumber {
    /**
     * @param {HTMLElement} element - Container element
     * @param {object} options
     * @param {number} options.decimals - Decimal places (default: 2)
     * @param {number} options.duration - Animation duration ms (default: 600)
     */
    constructor(element, options = {}) {
        this.element = element;
        this.decimals = options.decimals !== undefined ? options.decimals : 2;
        this.duration = options.duration || 600;
        this.currentValue = null;
        this.slots = [];
        this._digitHeight = 0; // measured pixel height (0 = not yet measured)

        this.element.classList.add('rolling-number');
    }

    /**
     * Set new value with rolling animation
     * @param {number} value
     */
    setValue(value) {
        if (value === null || value === undefined || isNaN(value)) return;

        const newStr = this._format(value);
        const oldStr = this.currentValue !== null ? this._format(this.currentValue) : null;

        this._render(newStr, oldStr);
        this.currentValue = value;
    }

    /**
     * Set value without animation (initial load)
     * @param {number} value
     */
    setValueImmediate(value) {
        if (value === null || value === undefined || isNaN(value)) return;

        const str = this._format(value);
        this.element.innerHTML = '';
        this.slots = [];

        for (let i = 0; i < str.length; i++) {
            const char = str[i];
            if (this._isSeparator(char)) {
                const sep = document.createElement('span');
                sep.className = 'digit-separator';
                sep.textContent = char;
                this.element.appendChild(sep);
                this.slots.push({ type: 'sep', el: sep });
            } else {
                const slot = this._createDigitSlot(parseInt(char), false);
                this.element.appendChild(slot.el);
                this.slots.push(slot);
            }
        }

        this.currentValue = value;

        // Measure actual pixel height after DOM render, then snap all transforms
        requestAnimationFrame(() => {
            this._measureAndSnap();
        });
    }

    _format(value) {
        return value.toLocaleString('en-US', {
            minimumFractionDigits: this.decimals,
            maximumFractionDigits: this.decimals
        });
    }

    _isSeparator(char) {
        return char === ',' || char === '.' || char === '-' || char === ' ';
    }

    /** Measure actual rendered slot height and snap all transforms to integer pixels */
    _measureAndSnap() {
        const firstSlot = this.element.querySelector('.digit-slot');
        if (!firstSlot) return;

        this._digitHeight = Math.round(firstSlot.getBoundingClientRect().height);
        if (this._digitHeight <= 0) return;

        // Apply pixel-snapped heights to all slots and spans
        this.element.querySelectorAll('.digit-slot').forEach(el => {
            el.style.height = this._digitHeight + 'px';
        });
        this.element.querySelectorAll('.digit-column span').forEach(el => {
            el.style.height = this._digitHeight + 'px';
            el.style.lineHeight = this._digitHeight + 'px';
        });
        this.element.querySelectorAll('.digit-separator').forEach(el => {
            el.style.height = this._digitHeight + 'px';
            el.style.lineHeight = this._digitHeight + 'px';
        });

        // Re-apply transforms with pixel values
        this.slots.forEach(slot => {
            if (slot.type === 'digit') {
                slot.column.style.transform = `translateY(${-slot.digit * this._digitHeight}px)`;
            }
        });
    }

    _getTransform(digit) {
        if (this._digitHeight > 0) {
            return `translateY(${-digit * this._digitHeight}px)`;
        }
        // Fallback before measurement
        return `translateY(${-digit}em)`;
    }

    _createDigitSlot(digit, animate) {
        const slot = document.createElement('span');
        slot.className = 'digit-slot';

        const column = document.createElement('span');
        column.className = 'digit-column';

        // Disable transition for initial render
        if (!animate) {
            column.style.transition = 'none';
        }

        // Create digits 0-9
        for (let i = 0; i <= 9; i++) {
            const d = document.createElement('span');
            d.textContent = i;
            column.appendChild(d);
        }

        slot.appendChild(column);

        // Position to show target digit
        column.style.transform = this._getTransform(digit);

        // Re-enable transition after render
        if (!animate) {
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    column.style.transition = '';
                });
            });
        }

        return { type: 'digit', el: slot, column: column, digit: digit };
    }

    _render(newStr, oldStr) {
        // If no previous value or length changed, rebuild entirely
        if (!oldStr || oldStr.length !== newStr.length || this.slots.length !== newStr.length) {
            this._rebuild(newStr);
            return;
        }

        // Update each position
        for (let i = 0; i < newStr.length; i++) {
            const newChar = newStr[i];
            const oldChar = oldStr[i];
            const slot = this.slots[i];

            if (newChar === oldChar) continue;

            if (this._isSeparator(newChar)) {
                if (slot.type === 'sep') {
                    slot.el.textContent = newChar;
                }
            } else {
                if (slot.type === 'digit') {
                    const digit = parseInt(newChar);
                    slot.digit = digit;
                    slot.column.style.transform = this._getTransform(digit);
                }
            }
        }
    }

    _rebuild(str) {
        this.element.innerHTML = '';
        this.slots = [];

        for (let i = 0; i < str.length; i++) {
            const char = str[i];
            if (this._isSeparator(char)) {
                const sep = document.createElement('span');
                sep.className = 'digit-separator';
                sep.textContent = char;
                this.element.appendChild(sep);
                this.slots.push({ type: 'sep', el: sep });
            } else {
                const slot = this._createDigitSlot(parseInt(char), true);
                this.element.appendChild(slot.el);
                this.slots.push(slot);
            }
        }

        // Measure and snap after rebuild
        requestAnimationFrame(() => {
            this._measureAndSnap();
        });
    }
}
