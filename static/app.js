document.addEventListener('DOMContentLoaded', () => {
    const page = document.body.dataset.page;

    if (page === 'login') {
        initLoginPage();
        return;
    }

    if (page === 'dashboard') {
        initDashboardPage();
    }
});

function initHelpModal() {
    const modal = document.getElementById('help-modal');
    const openButton = document.querySelector('[data-help-open]');
    const closeButton = document.querySelector('[data-help-close]');

    if (!modal || !openButton) {
        return;
    }

    const openModal = (event) => {
        if (event) {
            event.preventDefault();
        }
        modal.classList.remove('hidden');
        modal.setAttribute('aria-hidden', 'false');
    };

    const closeModal = () => {
        modal.classList.add('hidden');
        modal.setAttribute('aria-hidden', 'true');
    };

    openButton.addEventListener('click', openModal);

    if (closeButton) {
        closeButton.addEventListener('click', closeModal);
    }

    modal.addEventListener('click', (event) => {
        if (event.target === modal) {
            closeModal();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !modal.classList.contains('hidden')) {
            closeModal();
        }
    });
}

function initLoginPage() {
    const loginForm = document.getElementById('loginForm');
    const errorBox = document.getElementById('error-msg');
    const demoButton = document.querySelector('[data-demo-login]');

    if (!loginForm) {
        return;
    }

    if (demoButton) {
        demoButton.addEventListener('click', () => {
            localStorage.removeItem('inventory_token');
            localStorage.removeItem('location_id');
            localStorage.removeItem('role');
            window.location.href = '/dashboard';
        });
    }

    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault();

        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;

        try {
            const response = await fetch('/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            if (!response.ok) {
                errorBox.textContent = 'INVALID CREDENTIALS.';
                errorBox.classList.remove('hidden');
                return;
            }

            const data = await response.json();
            localStorage.setItem('inventory_token', data.access_token);
            localStorage.setItem('location_id', data.location_id);
            localStorage.setItem('role', data.role);
            window.location.href = '/dashboard';
        } catch (error) {
            console.error('Login connection failed', error);
            errorBox.textContent = 'SERVER CONNECTION FAILED.';
            errorBox.classList.remove('hidden');
        }
    });
}

function formatNumber(value) {
    if (value === null || value === undefined || value === '') {
        return '0';
    }
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) {
        return '0';
    }
    return numericValue % 1 === 0 ? String(numericValue) : numericValue.toFixed(2).replace(/\.00$/, '');
}

function getAuditBadge(flag) {
    if (!flag) {
        return { label: '', className: 'audit-chip hidden' };
    }

    if (flag === 'SHRINKAGE_ALERT') {
        return { label: 'SHRINKAGE', className: 'audit-chip audit-shrinkage' };
    }

    if (flag === 'SURPLUS_WASTE_ALERT') {
        return { label: 'SURPLUS', className: 'audit-chip audit-surplus' };
    }

    return { label: 'REVIEW', className: 'audit-chip' };
}

function recalcOrderNeeded(row) {
    const parValue = Number.parseFloat(row.querySelector('[data-field="par"]').value || 0);
    const currentValue = Number.parseFloat(row.querySelector('[data-field="current_inv"]').value || 0);
    const salesValue = Number.parseFloat(row.querySelector('[data-field="sales_proj"]').value || 0);
    const previousValue = Number.parseFloat(row.dataset.previousCurrentInv || 0);

    const expectedEnding = previousValue - salesValue + Math.max(0, currentValue - previousValue + salesValue);
    const discrepancy = expectedEnding - currentValue;

    let alertFlag = null;
    if (discrepancy < -2) {
        alertFlag = 'SHRINKAGE_ALERT';
        row.classList.add('audit-shrinkage');
        row.classList.remove('audit-surplus');
    } else if (discrepancy > 2 && salesValue <= 2) {
        alertFlag = 'SURPLUS_WASTE_ALERT';
        row.classList.add('audit-surplus');
        row.classList.remove('audit-shrinkage');
    } else {
        row.classList.remove('audit-shrinkage', 'audit-surplus');
    }

    const baseOrder = Math.max(0, parValue + salesValue - currentValue);
    const unaccountedBuffer = alertFlag ? Math.min(baseOrder, Math.max(0, Math.abs(discrepancy) * 0.5)) : 0;
    const orderValue = Math.max(0, baseOrder - unaccountedBuffer);
    const orderField = row.querySelector('[data-field="order_needed"]');
    const badge = row.querySelector('[data-field="audit_flag"]');
    const badgeData = getAuditBadge(alertFlag);

    orderField.value = formatNumber(orderValue);
    if (badge) {
        badge.textContent = badgeData.label;
        badge.className = badgeData.className;
    }

    if (alertFlag) {
        row.setAttribute('data-audit-flag', alertFlag);
    } else {
        row.removeAttribute('data-audit-flag');
    }
}

function renderAuditSummary(items) {
    const summaryHost = document.getElementById('delta-summary');
    if (!summaryHost) {
        return;
    }

    const safeItems = Array.isArray(items) ? items : [];
    const previousInvTotal = safeItems.reduce((total, item) => total + Number(item.previous_current_inv || 0), 0);
    const currentInvTotal = safeItems.reduce((total, item) => total + Number(item.current_inv || 0), 0);
    const impliedSalesTotal = safeItems.reduce((total, item) => total + Number(item.sales_proj || 0), 0);
    const varianceTotal = safeItems.reduce((total, item) => total + Number(item.actual_discrepancy || 0), 0);

    const varianceTone = varianceTotal < 0 ? 'negative' : varianceTotal > 0 ? 'positive' : 'neutral';

    summaryHost.innerHTML = `
        <div class="delta-card">
            <span class="delta-label">PREV INV</span>
            <strong>${formatNumber(previousInvTotal)}</strong>
        </div>
        <div class="delta-card">
            <span class="delta-label">CURRENT INV</span>
            <strong>${formatNumber(currentInvTotal)}</strong>
        </div>
        <div class="delta-card">
            <span class="delta-label">IMPLIED SALES</span>
            <strong>${formatNumber(impliedSalesTotal)}</strong>
        </div>
        <div class="delta-card ${varianceTone}">
            <span class="delta-label">VARIANCE</span>
            <strong>${formatNumber(varianceTotal)}</strong>
        </div>
    `;
}

function searchInventory() {
    const query = document.getElementById('searchInput').value.trim().toLowerCase();
    const rows = document.querySelectorAll('.inventory-item-row');
    let visibleCount = 0;

    rows.forEach((row) => {
        const itemName = (row.dataset.item || '').toLowerCase();
        const unit = (row.dataset.unit || '').toLowerCase();
        const matches = !query || itemName.includes(query) || unit.includes(query);
        row.classList.toggle('hidden', !matches);
        if (matches) visibleCount += 1;
    });

    const emptyState = document.getElementById('empty-state');
    if (emptyState) {
        emptyState.classList.toggle('hidden', visibleCount > 0);
    }
}

function renderLedgerRows(items) {
    const inventoryBody = document.getElementById('inventory-body');
    const emptyState = document.getElementById('empty-state');

    if (!inventoryBody) {
        return;
    }

    inventoryBody.innerHTML = '';

    if (!items || items.length === 0) {
        if (emptyState) {
            emptyState.classList.remove('hidden');
        }
        return;
    }

    if (emptyState) {
        emptyState.classList.add('hidden');
    }

    items.forEach((item) => {
        const row = document.createElement('tr');
        row.className = 'inventory-item-row';
        row.dataset.item = item.item || '';
        row.dataset.unit = item.unit || '';
        row.dataset.previousCurrentInv = Number(item.previous_current_inv || 0);
        row.innerHTML = `
            <td class="cell-item"><input type="text" value="${(item.item || '').replace(/"/g, '&quot;')}" readonly></td>
            <td><input type="text" value="${(item.unit || '').replace(/"/g, '&quot;')}" data-field="unit"></td>
            <td><input type="number" value="${formatNumber(item.par)}" data-field="par"></td>
            <td><input type="number" value="${formatNumber(item.current_inv)}" data-field="current_inv"></td>
            <td><input type="number" value="${formatNumber(item.sales_proj)}" data-field="sales_proj"></td>
            <td class="order-cell">
                <div class="order-stack">
                    <input type="text" value="${formatNumber(item.order_needed)}" data-field="order_needed" readonly>
                    <span class="audit-chip hidden" data-field="audit_flag">${getAuditBadge(item.audit_flag).label}</span>
                </div>
            </td>
        `;

        const currentInvInput = row.querySelector('[data-field="current_inv"]');
        const salesProjInput = row.querySelector('[data-field="sales_proj"]');
        const parInput = row.querySelector('[data-field="par"]');

        [currentInvInput, salesProjInput, parInput].forEach((input) => {
            input.addEventListener('input', () => recalcOrderNeeded(row));
        });

        recalcOrderNeeded(row);
        inventoryBody.appendChild(row);
    });

    renderAuditSummary(items);
    searchInventory();
}

function showGuestNotice() {
    const modal = document.getElementById('guest-modal');
    if (!modal) {
        return;
    }
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
}

function hideGuestNotice() {
    const modal = document.getElementById('guest-modal');
    if (!modal) {
        return;
    }
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
}

function renderDemoCatalog(items) {
    const inventoryBody = document.getElementById('inventory-body');
    const emptyState = document.getElementById('empty-state');
    const banner = document.getElementById('demo-banner');
    const deltaSummary = document.getElementById('delta-summary');
    if (banner) {
        banner.classList.remove('hidden');
    }
    if (deltaSummary) {
        deltaSummary.innerHTML = `
            <div class="delta-card">
                <span class="delta-label">CATALOG</span>
                <strong>${items.length}</strong>
            </div>
            <div class="delta-card">
                <span class="delta-label">ARTISTS</span>
                <strong>${new Set(items.map((item) => item.artist)).size}</strong>
            </div>
            <div class="delta-card">
                <span class="delta-label">GENRES</span>
                <strong>${new Set(items.flatMap((item) => item.genre || [])).size}</strong>
            </div>
            <div class="delta-card positive">
                <span class="delta-label">STATUS</span>
                <strong>READ ONLY</strong>
            </div>
        `;
    }

    if (!inventoryBody) {
        return;
    }
    inventoryBody.innerHTML = '';

    if (!items || items.length === 0) {
        if (emptyState) {
            emptyState.classList.remove('hidden');
        }
        return;
    }

    if (emptyState) {
        emptyState.classList.add('hidden');
    }

    items.forEach((item) => {
        const row = document.createElement('tr');
        row.className = 'inventory-item-row';
        row.dataset.item = item.title || '';
        row.dataset.unit = item.artist || '';
        row.innerHTML = `
            <td class="cell-item"><input type="text" value="${(item.title || '').replace(/"/g, '&quot;')}" readonly></td>
            <td><input type="text" value="${(item.artist || '').replace(/"/g, '&quot;')}" readonly></td>
            <td><input type="text" value="${(item.release_year || '').replace(/"/g, '&quot;')}" readonly></td>
            <td><input type="text" value="${(item.genre || []).join(', ')}" readonly></td>
            <td><input type="text" value="${(item.review_summary || '').replace(/"/g, '&quot;')}" readonly></td>
            <td class="order-cell">
                <div class="order-stack">
                    <button type="button" class="ghost-button demo-action" data-demo-action="review">VIEW REVIEW</button>
                    <button type="button" class="ghost-button demo-action" data-demo-action="write">ADD REVIEW</button>
                </div>
            </td>
        `;

        const reviewButton = row.querySelector('[data-demo-action="review"]');
        const writeButton = row.querySelector('[data-demo-action="write"]');

        reviewButton.addEventListener('click', () => { showGuestNotice(); });
        writeButton.addEventListener('click', () => { showGuestNotice(); });

        inventoryBody.appendChild(row);
    });

    searchInventory();
}

async function loadAuthenticatedInventory() {
    const token = localStorage.getItem('inventory_token');
    if (!token) {
        return;
    }

    try {
        const response = await fetch('/inventory', {
            headers: { Authorization: `Bearer ${token}` },
        });

        const result = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(result.detail || 'Failed to load inventory');
        }

        const items = Array.isArray(result.inventory) ? result.inventory : [];
        const transformed = items.map((item) => {
            const currentInv = Number(item.current_stock || 0);
            const salesProj = Number(item.weeks_of_supply || 0) * 4;
            return {
                item: item.name || item.sku || 'UNKNOWN ITEM',
                unit: item.unit || 'UNIT',
                par: 0,
                current_inv: currentInv,
                sales_proj: salesProj,
                previous_current_inv: currentInv,
                actual_discrepancy: 0,
                order_needed: Math.max(0, 0 + salesProj - currentInv),
            };
        });

        renderLedgerRows(transformed);
    } catch (error) {
        console.error('Inventory load error', error);
        const statusBox = document.getElementById('upload-status');
        if (statusBox) {
            statusBox.textContent = `INVENTORY LOAD FAILED: ${error.message}`;
            statusBox.className = 'upload-status visible status-error';
        }
    }
}

async function uploadLedger() {
    const fileInput = document.getElementById('ledgerFileInput');
    const statusBox = document.getElementById('upload-status');
    const file = fileInput && fileInput.files[0];

    if (!file) {
        statusBox.textContent = 'SELECT A LEDGER FILE FIRST.';
        statusBox.className = 'upload-status visible status-error';
        return;
    }

    const token = localStorage.getItem('inventory_token');
    const formData = new FormData();
    formData.append('file', file);

    statusBox.textContent = 'UPLOADING LEDGER...';
    statusBox.className = 'upload-status visible status-info';

    try {
        const response = await fetch('/api/upload-ledger', {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
            body: formData
        });

        const result = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(result.detail || 'UPLOAD FAILED');
        }

        renderLedgerRows(result.items || []);
        statusBox.textContent = `${result.message || 'LEDGER PROCESSED'} | ROWS: ${result.rows_processed || 0}`;
        statusBox.className = 'upload-status visible status-success';
    } catch (error) {
        console.error('Ledger upload error', error);
        statusBox.textContent = `UPLOAD FAILED: ${error.message}`;
        statusBox.className = 'upload-status visible status-error';
    } finally {
        if (fileInput) {
            fileInput.value = '';
        }
    }
}

function initDashboardPage() {
    const token = localStorage.getItem('inventory_token');

    if (!token) {
        window.location.href = '/';
        return;
    }

    window.logout = function logout() {
        localStorage.removeItem('inventory_token');
        localStorage.removeItem('location_id');
        localStorage.removeItem('role');
        window.location.href = '/';
    };

    window.uploadLedger = uploadLedger;
    window.searchInventory = searchInventory;

    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', searchInventory);
    }

    const locationBadge = document.getElementById('location-badge');
    const locationId = Number(localStorage.getItem('location_id') || 1);
    if (locationBadge) {
        locationBadge.textContent = `LOCATION ${locationId}`;
    }

    initHelpModal();

    const guestClose = document.querySelector('[data-guest-close]');
    if (guestClose) {
        guestClose.addEventListener('click', hideGuestNotice);
    }

    const guestModal = document.getElementById('guest-modal');
    if (guestModal) {
        guestModal.addEventListener('click', (event) => {
            if (event.target === guestModal) {
                hideGuestNotice();
            }
        });
    }

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            hideGuestNotice();
        }
    });

    if (!localStorage.getItem('inventory_token')) {
        const banner = document.getElementById('demo-banner');
        if (banner) {
            banner.classList.remove('hidden');
        }
        fetch('/api/demo-catalog')
            .then((response) => response.json())
            .then((result) => renderDemoCatalog(result.items || []))
            .catch(() => renderDemoCatalog([]));
        return;
    }

    loadAuthenticatedInventory();
}
