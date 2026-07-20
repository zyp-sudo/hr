/**
 * DOM overflow diagnostic — 390px viewport.
 * Outputs every element whose right edge exceeds the viewport width.
 */

import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:3000';

// ── Helpers ──────────────────────────────────────────────────────────
async function diagnose(page, label) {
  console.log(`\n══════ ${label} ══════`);
  const result = await page.evaluate(() => {
    const vw = window.innerWidth;
    const offenders = [];
    const all = document.querySelectorAll('*');
    for (const el of all) {
      const r = el.getBoundingClientRect();
      if (r.right > vw + 1) {
        const cs = getComputedStyle(el);
        // Walk up to 4 levels of parents
        const parents = [];
        let p = el.parentElement;
        for (let i = 0; i < 4 && p; i++) {
          const pr = p.getBoundingClientRect();
          const pcs = getComputedStyle(p);
          const pcls = (typeof p.className === 'string' ? p.className : '') || '';
          parents.push({
            tag: p.tagName,
            cls: pcls.slice(0, 120),
            left: Math.round(pr.left), right: Math.round(pr.right), width: Math.round(pr.width),
            minW: pcs.minWidth, maxW: pcs.maxWidth, w: pcs.width, overflow: pcs.overflowX,
          });
          p = p.parentElement;
        }
        const cls = (typeof el.className === 'string' ? el.className : '') || '';
        offenders.push({
          tag: el.tagName,
          cls,
          id: el.id || '',
          left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width),
          sw: el.scrollWidth, cw: el.clientWidth,
          minW: cs.minWidth, maxW: cs.maxWidth, w: cs.width, overflow: cs.overflowX,
          display: cs.display, flexShrink: cs.flexShrink, flexWrap: cs.flexWrap,
          position: cs.position,
          parents,
        });
      }
    }
    return { vw, count: offenders.length, offenders };
  });

  console.log(`  viewport=${result.vw}  overflowing-elements=${result.count}`);

  // Dedup: group by tag+cls, show one example per group
  const seen = new Set();
  const unique = [];
  for (const o of result.offenders) {
    const key = `${o.tag} ${o.cls.slice(0, 80)}`;
    if (!seen.has(key)) { seen.add(key); unique.push(o); }
  }
  console.log(`  unique offenders: ${unique.length}`);
  for (const o of unique) {
    console.log(`  ──────────────────────────────────────────`);
    console.log(`  <${o.tag}${o.id ? '#' + o.id : ''} class="${o.cls.slice(0, 100)}">`);
    console.log(`    rect: left=${o.left} right=${o.right} width=${o.width}  scrollWidth=${o.sw} clientWidth=${o.cw}`);
    console.log(`    CSS:  min-width=${o.minW} width=${o.w} max-width=${o.maxW} display=${o.display} flex-shrink=${o.flexShrink} flex-wrap=${o.flexWrap} overflow-x=${o.overflow} position=${o.position}`);
    if (o.parents.length > 0) {
      const p0 = o.parents[0];
      console.log(`    parent[0]: <${p0.tag} class="${p0.cls}"> rect:${p0.left}/${p0.right}/${p0.width} minW:${p0.minW} w:${p0.w} overflow:${p0.overflow}`);
    }
    if (o.parents.length > 1) {
      const p1 = o.parents[1];
      console.log(`    parent[1]: <${p1.tag} class="${p1.cls}"> rect:${p1.left}/${p1.right}/${p1.width} minW:${p1.minW} w:${p1.w} overflow:${p1.overflow}`);
    }
    if (o.parents.length > 2) {
      const p2 = o.parents[2];
      console.log(`    parent[2]: <${p2.tag} class="${p2.cls}"> rect:${p2.left}/${p2.right}/${p2.width} minW:${p2.minW} w:${p2.w} overflow:${p2.overflow}`);
    }
  }
}

// ═══════════════════════════════════════════════════════════════════
(async () => {
  const browser = await chromium.launch({ headless: true });

  // Login
  const loginBody = JSON.stringify({
    url: '/api/auth/login', method: 'POST',
    body: { email: 'admin@talentmatch.cn', password: 'admin123' },
  });
  const lr = await fetch(`${BASE}/api/platform/storage`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: loginBody,
  });
  const loginData = await lr.json();

  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();

  // Inject auth
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.evaluate(({ t, u }) => {
    localStorage.setItem('talentmatch_token', t);
    localStorage.setItem('talentmatch_user', JSON.stringify(u));
  }, { t: loginData.token, u: loginData.user });

  // ── 1. Homepage ─────────────────────────────────────────────────
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(600);
  await diagnose(page, 'HOME');

  // ── 2. Job Management — 在招岗位 ───────────────────────────────
  const nav = page.locator('.nav-dropdown > button:has-text("岗位管理")');
  await nav.hover(); await page.waitForTimeout(300);
  const jobsItem = page.locator('.nav-dropdown__menu button:has-text("在招岗位")');
  if (await jobsItem.count() > 0) {
    await jobsItem.click();
    await page.waitForTimeout(1500);
    await page.waitForLoadState('networkidle');
  }
  await diagnose(page, 'JOB-MANAGEMENT');

  // ── 3. Competition Discovery ───────────────────────────────────
  const nav2 = page.locator('.nav-dropdown > button:has-text("岗位管理")');
  await nav2.hover(); await page.waitForTimeout(300);
  const discItem = page.locator('.nav-dropdown__menu button:has-text("新岗位发现")');
  if (await discItem.count() > 0) {
    await discItem.click();
    await page.waitForTimeout(1500);
    await page.waitForLoadState('networkidle');
  }
  await diagnose(page, 'DISCOVERY');

  // ── 4. Discovery dialog open ───────────────────────────────────
  const addBtn = page.locator('.comp-discovery .add-job-button');
  if (await addBtn.count() > 0) {
    await addBtn.click();
    await page.waitForTimeout(500);
    await diagnose(page, 'DISCOVERY-DIALOG-OPEN');
  }

  await browser.close();
  console.log('\n═══ Diagnostic complete ═══');
})();
