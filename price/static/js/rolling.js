/**
 * Toss-style Rolling Number Animation
 * Each digit rolls independently via CSS translateY
 */
class RollingNumber {
    /**
     * @param {HTMLElement} element - Container element
     * @param {object} options
     * @param {number} options.decimals - Decimal places (default: 2)
     * @param {number} options.duration - Animation duration ms (default: 400)
     */
    constructor(element, options = {}) {
        this.element = element;
        this.decimals = options.decimals !== undefined ? options.decimals : 2;
        this.duration = options.duration || 400;
        this.currentValue = null;
        this.slots = [];

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
        const offset = -(digit * 10);
        column.style.transform = `translateY(${offset}%)`;

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
                    const offset = -(digit * 10);
                    slot.column.style.transform = `translateY(${offset}%)`;
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
    }
}
