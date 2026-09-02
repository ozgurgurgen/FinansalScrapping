/**
 * Finance Pipeline API Client (JavaScript / Node.js)
 * 
 * Kullanım:
 *   import { FinanceClient } from './api_client.js';
 *   // veya
 *   const { FinanceClient } = require('./api_client.js');
 * 
 *   const client = new FinanceClient(); // default: http://localhost:3000
 * 
 *   const companies = await client.getCompanies();
 *   const thyao = await client.getAll('THYAO');
 *   const funds = await client.getFunds(500);
 */

class FinanceClient {
    constructor(baseUrl = 'http://localhost:3000') {
        this.baseUrl = baseUrl.replace(/\/$/, '');
    }

    async _get(path, params = {}) {
        const url = new URL(`${this.baseUrl}${path}`);
        Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
        const r = await fetch(url.toString());
        if (!r.ok) throw new Error(`API Error ${r.status}: ${await r.text()}`);
        return r.json();
    }

    async _getRaw(path) {
        const r = await fetch(`${this.baseUrl}${path}`);
        if (!r.ok) throw new Error(`API Error ${r.status}`);
        return r;
    }

    // ─── Schema ───────────────────────────────────────────────
    async getSchema() {
        return this._get('/api/export/schema');
    }

    // ─── Şirketler ───────────────────────────────────────────
    async getCompanies() {
        return this._get('/api/export/companies');
    }

    async search(query, limit = 20) {
        return this._get('/api/export/search', { q: query, limit });
    }

    // ─── Finansal ─────────────────────────────────────────────
    async getFinancials(ticker) {
        return this._get(`/api/export/financials/${ticker.toUpperCase()}`);
    }

    async getAll(ticker) {
        return this._get(`/api/export/all/${ticker.toUpperCase()}`);
    }

    // ─── TEFAS ────────────────────────────────────────────────
    async getFunds(limit = 100) {
        return this._get('/api/export/funds', { limit });
    }

    async getFund(code) {
        return this._get(`/api/export/fund/${code.toUpperCase()}`);
    }

    // ─── CSV ──────────────────────────────────────────────────
    async downloadCsv(table, savePath) {
        const r = await this._getRaw(`/api/export/csv/${table}`);
        const text = await r.text();
        if (savePath && typeof require !== 'undefined') {
            require('fs').writeFileSync(savePath, text);
            return savePath;
        }
        return text;
    }
}

// Node.js require desteği
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { FinanceClient };
}

// ─── Kullanım Örneği ──────────────────────────────────────────
if (require.main === module) {
    (async () => {
        const client = new FinanceClient();
        
        const companies = await client.getCompanies();
        console.log(`Toplam ${companies.length} şirket`);
        
        const thyao = await client.getAll('THYAO');
        console.log(`\nTHYAO:`);
        console.log(`  Finansal: ${thyao.financials.length} dönem`);
        console.log(`  Bildirim: ${thyao.disclosures.length}`);
        console.log(`  Ortak: ${thyao.shareholders.length}`);
        
        const funds = await client.getFunds(10);
        console.log(`\nİlk 10 fon:`);
        funds.forEach(f => console.log(`  ${f.code}: ${f.title} (${f.kind})`));
    })();
}
