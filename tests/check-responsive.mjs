import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DIR = join(__dirname, '..', 'e2e-screenshots');
mkdirSync(DIR, { recursive: true });

const BASE = 'http://127.0.0.1:3000';

const VIEWPORTS = [
  { w: 390, h: 844, label: '390' },
  { w: 412, h: 915, label: '412' },
  { w: 768, h: 1024, label: '768' },
  { w: 1440, h: 900, label: '1440' },
];

const PAGES = [
  { label: 'HOME', path: '' },
];

const results = [];

async function ss(page, label) {
  const p = join(DIR, `responsive-${label}.png`);
  await page.screenshot({ path: p, fullPage: true });
  results.push({ type: 'shot', label, path: p });
}

// ═══════════════════════════════════════════════════════════════════
async function login() {
  const r = await fetch(`${BASE}/api/platform/storage`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: '/api/auth/login', method: 'POST',
      body: { email: 'admin@talentmatch.cn', password: 'admin123' } }),
  });
  return r.json();
}

async function injectAuth(page, loginData) {
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.evaluate(({ t, u }) => {
    localStorage.setItem('talentmatch_token', t);
    localStorage.setItem('talentmatch_user', JSON.stringify(u));
  }, { t: loginData.token, u: loginData.user });
}

async function checkWidth(page, label) {
  const m = await page.evaluate(() => ({
    docSW: document.documentElement.scrollWidth,
    docCW: document.documentElement.clientWidth,
    bodySW: document.body.scrollWidth,
    bodyCW: document.body.clientWidth,
    vw: window.innerWidth,
  }));
  const pass = m.docSW <= m.vw + 1 && m.bodySW <= m.vw + 1;
  console.log(`  ${pass ? 'PASS' : 'FAIL'} scrollWidth ${label} | doc ${m.docSW}/${m.vw} body ${m.bodySW}/${m.vw}`);
  results.push({ type: 'check', label: `scroll-${label}`, pass, ...m });
  return pass;
}

async function checkNavDropdown(page, vpLabel) {
  const vw = await page.evaluate(() => window.innerWidth);
  const isMobile = vw <= 900;
  console.log(`  Checking nav dropdown (viewport ${vw}px, ${isMobile ? 'mobile' : 'desktop'})`);

  // Navigate to home first
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(400);

  // Get the trigger button
  const trigger = page.locator('.nav-dropdown > button[aria-haspopup="menu"]');
  const triggerCount = await trigger.count();
  results.push({ type: 'check', label: `${vpLabel}-nav-trigger-exists`, pass: triggerCount > 0 });
  if (triggerCount === 0) return;

  // Close any open menu first
  await page.keyboard.press('Escape');
  await page.waitForTimeout(200);

  if (isMobile) {
    // Mobile: use click (tap) to open
    await trigger.click();
    await page.waitForTimeout(500);
  } else {
    // Desktop: use hover
    await trigger.hover();
    await page.waitForTimeout(500);
  }

  // Assert menu is visible
  const menu = page.locator('.nav-dropdown__menu[role="menu"]');
  const menuCount = await menu.count();
  results.push({ type: 'check', label: `${vpLabel}-nav-menu-exists`, pass: menuCount > 0 });
  if (menuCount === 0) { console.log('  FAIL: nav menu not found in DOM'); return; }

  // Visibility: check boundingBox + opacity
  const menuBox = await menu.boundingBox().catch(() => null);
  const menuVisible = menuBox !== null && menuBox.width > 0 && menuBox.height > 0;
  results.push({ type: 'check', label: `${vpLabel}-nav-menu-visible`, pass: menuVisible });

  // boundingBox checks
  const box = await menu.boundingBox().catch(() => null);
  results.push({ type: 'check', label: `${vpLabel}-nav-menu-bbox-nonnull`, pass: box !== null });
  if (box) {
    results.push({ type: 'check', label: `${vpLabel}-nav-menu-left-ge0`, pass: box.x >= 0, detail: `x=${Math.round(box.x)}` });
    results.push({ type: 'check', label: `${vpLabel}-nav-menu-right-le-vw`, pass: box.x + box.width <= vw + 2,
      detail: `right=${Math.round(box.x + box.width)} vw=${vw}` });
    results.push({ type: 'check', label: `${vpLabel}-nav-menu-top-ge0`, pass: box.y >= 0, detail: `y=${Math.round(box.y)}` });
    console.log(`  Menu bbox: x=${Math.round(box.x)} y=${Math.round(box.y)} w=${Math.round(box.width)} h=${Math.round(box.height)} vw=${vw}`);
  }

  // Check that all 3 menu items are visible
  const items = page.locator('.nav-dropdown__menu[role="menu"] button[role="menuitem"]');
  const itemCount = await items.count();
  results.push({ type: 'check', label: `${vpLabel}-nav-menu-3-items`, pass: itemCount === 3, detail: `found ${itemCount}` });

  for (let i = 0; i < Math.min(itemCount, 3); i++) {
    const itemText = await items.nth(i).textContent();
    const iBox = await items.nth(i).boundingBox().catch(() => null);
    const itemVisible = iBox !== null && iBox.width > 0 && iBox.height > 0;
    results.push({ type: 'check', label: `${vpLabel}-nav-item-${i}-visible`, pass: itemVisible, detail: itemText });
  }

  // Take screenshot
  await ss(page, `${vpLabel}-NAVDROP-visible`);

  // Click "新岗位发现" and verify navigation
  const discItem = page.locator('.nav-dropdown__menu button:has-text("新岗位发现")');
  if (await discItem.count() > 0) {
    await discItem.click();
    await page.waitForTimeout(1500);
    await page.waitForLoadState('networkidle');
    const heading = await page.locator('.comp-discovery h2, .home-section__head-title').first().textContent().catch(() => '');
    const navPass = (heading || '').includes('新岗位发现');
    results.push({ type: 'check', label: `${vpLabel}-click-disc-navigates`, pass: navPass, detail: heading?.slice(0, 40) });
  }

  // Close the menu (via Escape if still open)
  await page.keyboard.press('Escape');
  await page.waitForTimeout(200);

  // Navigate home for the next page check
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(300);

  // Now test "在招岗位" navigation
  if (isMobile) {
    await trigger.click(); await page.waitForTimeout(400);
  } else {
    await trigger.hover(); await page.waitForTimeout(400);
  }
  const jobsItem = page.locator('.nav-dropdown__menu button:has-text("在招岗位")');
  if (await jobsItem.count() > 0) {
    await jobsItem.click();
    await page.waitForTimeout(1200);
    await page.waitForLoadState('networkidle');
    const jobsHeading = await page.locator('#all-jobs-section').count().catch(() => 0);
    results.push({ type: 'check', label: `${vpLabel}-click-jobs-navigates`, pass: jobsHeading > 0,
      detail: `all-jobs-section seen=${jobsHeading > 0}` });
  }
}

// ═══════════════════════════════════════════════════════════════════
(async () => {
  const browser = await chromium.launch({ headless: true });
  const loginData = await login();

  for (const vp of VIEWPORTS) {
    console.log(`\n═══ ${vp.w}×${vp.h} ═══`);
    const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h } });
    const page = await ctx.newPage();

    await injectAuth(page, loginData);

    // Homepage scrollWidth check
    await page.goto(BASE, { waitUntil: 'networkidle' });
    await page.waitForTimeout(600);
    await checkWidth(page, `${vp.label}-HOME`);

    // Job management scrollWidth check
    const nav = page.locator('.nav-dropdown > button[aria-haspopup="menu"]');
    if (await nav.count() > 0) {
      if (vp.w <= 900) { await nav.click(); } else { await nav.hover(); }
      await page.waitForTimeout(500);
      const jobsItem = page.locator('.nav-dropdown__menu button:has-text("在招岗位")');
      if (await jobsItem.count() > 0) {
        await jobsItem.click();
        await page.waitForTimeout(1500);
        await page.waitForLoadState('networkidle');
      }
    }
    await checkWidth(page, `${vp.label}-JOB-MGMT`);

    // Discovery scrollWidth check
    await page.goto(BASE, { waitUntil: 'networkidle' });
    await page.waitForTimeout(300);
    if (await nav.count() > 0) {
      if (vp.w <= 900) { await nav.click(); } else { await nav.hover(); }
      await page.waitForTimeout(500);
      const discItem = page.locator('.nav-dropdown__menu button:has-text("新岗位发现")');
      if (await discItem.count() > 0) {
        await discItem.click();
        await page.waitForTimeout(1500);
        await page.waitForLoadState('networkidle');
      }
    }
    await checkWidth(page, `${vp.label}-DISCOVERY`);

    // Discovery dialog scrollWidth check
    const addBtn = page.locator('.comp-discovery .add-job-button');
    if (await addBtn.count() > 0) {
      await addBtn.first().click();
      await page.waitForTimeout(500);
    }
    await checkWidth(page, `${vp.label}-DIALOG`);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);

    // HOME screenshot
    await page.goto(BASE, { waitUntil: 'networkidle' });
    await page.waitForTimeout(400);
    await ss(page, `${vp.label}-HOME`);

    // Nav dropdown check
    await checkNavDropdown(page, vp.label);

    await ctx.close();
  }

  await browser.close();

  // Summary
  const passes = results.filter(r => r.type === 'check' && r.pass).length;
  const fails = results.filter(r => r.type === 'check' && !r.pass).length;
  const shots = results.filter(r => r.type === 'shot').length;

  console.log('\n═══════════════════════════════════════');
   for (const r of results) {
    if (r.type === 'check') {
      const label = r.label.padEnd(40);
      const detail = r.detail ? ` [${r.detail}]` : '';
      console.log(`  ${r.pass ? 'PASS' : 'FAIL'} ${label}${detail}`);
    }
  }
  console.log(`\n${passes} passed, ${fails} failed, ${shots} screenshots → ${DIR}`);

  writeFileSync(join(DIR, 'responsive-report.json'), JSON.stringify({ results, passes, fails, shots }, null, 2));
  process.exit(fails > 0 ? 1 : 0);
})();
