import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:3000';
const VW = 390;

async function login() {
  const r = await fetch(`${BASE}/api/platform/storage`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: '/api/auth/login', method: 'POST',
      body: { email: 'admin@talentmatch.cn', password: 'admin123' } }),
  });
  return r.json();
}

async function inject(page, loginData) {
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.evaluate(({ t, u }) => {
    localStorage.setItem('talentmatch_token', t);
    localStorage.setItem('talentmatch_user', JSON.stringify(u));
  }, { t: loginData.token, u: loginData.user });
}

async function check(page, label) {
  const m = await page.evaluate(() => ({
    docSW: document.documentElement.scrollWidth,
    docCW: document.documentElement.clientWidth,
    bodySW: document.body.scrollWidth,
    bodyCW: document.body.clientWidth,
    vw: window.innerWidth,
  }));
  const pass = m.docSW <= m.vw + 1 && m.bodySW <= m.vw + 1;
  console.log(`  ${pass ? 'PASS' : 'FAIL'} ${label} | doc ${m.docSW}/${m.vw} body ${m.bodySW}/${m.vw}`);
  return pass;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: VW, height: 844 } });
  const page = await ctx.newPage();
  const loginData = await login();
  await inject(page, loginData);
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(800);

  let allPass = true;
  allPass = (await check(page, 'HOME')) && allPass;

  // Job management
  const nav = page.locator('.nav-dropdown > button:has-text("岗位管理")');
  await nav.hover(); await page.waitForTimeout(400);
  await page.locator('.nav-dropdown__menu button:has-text("在招岗位")').click();
  await page.waitForTimeout(1500); await page.waitForLoadState('networkidle');
  allPass = (await check(page, 'JOB-MGMT')) && allPass;

  // Discovery
  const nav2 = page.locator('.nav-dropdown > button:has-text("岗位管理")');
  await nav2.hover(); await page.waitForTimeout(400);
  await page.locator('.nav-dropdown__menu button:has-text("新岗位发现")').click();
  await page.waitForTimeout(1500); await page.waitForLoadState('networkidle');
  allPass = (await check(page, 'DISCOVERY')) && allPass;

  // Dialog open
  const addBtn = page.locator('.comp-discovery .add-job-button');
  await addBtn.click(); await page.waitForTimeout(600);
  allPass = (await check(page, 'DIALOG')) && allPass;

  // Nav dropdown
  await page.keyboard.press('Escape'); await page.waitForTimeout(300);
  const nav3 = page.locator('.nav-dropdown > button:has-text("岗位管理")');
  await nav3.hover(); await page.waitForTimeout(600);
  allPass = (await check(page, 'NAV-DROPDOWN')) && allPass;

  console.log(allPass ? '\nALL PASS' : '\nSOME FAILED');
  await browser.close();
  process.exit(allPass ? 0 : 1);
})();
