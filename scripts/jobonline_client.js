const fs = require("fs");
const path = require("path");
const vm = require("vm");
const crypto = require("crypto");

const ROOT = path.resolve(__dirname, "..");
const RAW_DIR = path.resolve(process.env.JOBONLINE_RAW_DIR || path.join(ROOT, "data", "raw", "china_jobs", "jobonline"));
const APP_CACHE = path.join(ROOT, "tmp", "cn_js", "jobonline_app.js");
const OUTPUT_PATH = path.resolve(process.env.JOBONLINE_OUTPUT || path.join(RAW_DIR, "jobonline_batch.json"));
const API_URL = "https://api.jobonline.cn/jobtbao-es-api/elastic/api/position/queryPositionByCon";
const API_PATH = "/jobtbao-es-api/elastic/api/position/queryPositionByCon";
const PUBLIC_KEY = "043f4a9673db98fd52a87e087da75ca8d4978748188e29373acc131887d7b78ee89b07364f644352e4cb4029d8330509368b27b10638345c8afd41149626d917aa";

const DEFAULT_PROVINCES = [
  "110000", "120000", "130000", "140000", "150000", "210000", "220000", "230000",
  "310000", "320000", "330000", "340000", "350000", "360000", "370000", "410000",
  "420000", "430000", "440000", "450000", "460000", "500000", "510000", "520000",
  "530000", "540000", "610000", "620000", "630000", "640000", "650000",
];

function envBool(name, defaultValue) {
  const value = process.env[name];
  if (value == null) return defaultValue;
  return !["0", "false", "no", "off"].includes(value.trim().toLowerCase());
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function ensureAppBundle() {
  if (fs.existsSync(APP_CACHE)) return fs.readFileSync(APP_CACHE, "utf8");
  fs.mkdirSync(path.dirname(APP_CACHE), { recursive: true });
  const home = await (await fetch("https://www.jobonline.cn/", {
    headers: { "User-Agent": "Mozilla/5.0", "Accept": "text/html,*/*" },
  })).text();
  const match = home.match(/<script\s+src=(https:\/\/js\.e-sscard\.com\/[^>"]+app\.[^>"]+\.js)>/);
  if (!match) throw new Error("jobonline app bundle URL not found");
  const source = await (await fetch(match[1], {
    headers: { "User-Agent": "Mozilla/5.0", "Referer": "https://www.jobonline.cn/" },
  })).text();
  fs.writeFileSync(APP_CACHE, source, "utf8");
  return source;
}

function createEncryptor(source) {
  const patched = source.replace("a(a.s=0)}", "globalThis.__jobonline_require=a;}");
  const sandbox = {
    window: { webpackJsonp: [], crypto: crypto.webcrypto },
    document: {},
    console,
    setTimeout,
    clearTimeout,
    navigator: { userAgent: "Mozilla/5.0" },
    location: { href: "https://www.jobonline.cn/" },
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(patched, sandbox, { timeout: 10000 });
  return sandbox.__jobonline_require("sbn1").default;
}

function encryptedRequest(encryptor, payload) {
  const config = { url: API_PATH, headers: {}, data: payload };
  encryptor.UpEncry(config, { type: "sm", publicKey: PUBLIC_KEY });
  return config;
}

async function requestPage(encryptor, shard, page, pageSize, useCache) {
  const shardName = shard ? `province_${shard}` : "all";
  const cachePath = path.join(RAW_DIR, `${shardName}_page_${page}.json`);
  if (useCache && fs.existsSync(cachePath)) {
    return JSON.parse(fs.readFileSync(cachePath, "utf8"));
  }
  const provinceCodes = shard ? [Number(shard)] : [];
  const payload = {
    page,
    pagesize: pageSize,
    positionName3: "",
    provinceCodes,
    cityCodes: [],
    areaCodes: [],
    sortType: "0",
  };
  const config = encryptedRequest(encryptor, payload);
  const headers = {
    ...config.headers,
    "User-Agent": "Mozilla/5.0",
    "Origin": "https://www.jobonline.cn",
    "Referer": "https://www.jobonline.cn/",
    "Accept": "application/json, text/plain, */*",
    "msha": "1",
  };
  let lastError;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers,
        body: JSON.stringify(config.data),
      });
      const data = await response.json();
      if (response.status !== 200 || data.code !== "200") {
        throw new Error(`status=${response.status} code=${data.code || ""} message=${data.message || ""}`);
      }
      fs.mkdirSync(path.dirname(cachePath), { recursive: true });
      fs.writeFileSync(cachePath, JSON.stringify(data, null, 2), "utf8");
      return data;
    } catch (error) {
      lastError = error;
      await sleep(500 * attempt);
    }
  }
  if (fs.existsSync(cachePath)) return JSON.parse(fs.readFileSync(cachePath, "utf8"));
  throw lastError;
}

async function main() {
  const target = Number(process.env.JOBONLINE_TARGET || "50000");
  const pageSize = Math.min(40, Math.max(1, Number(process.env.JOBONLINE_PAGE_SIZE || "40")));
  const maxPagesPerShard = Math.max(1, Number(process.env.JOBONLINE_MAX_PAGES_PER_SHARD || "250"));
  const sleepMs = Math.max(0, Number(process.env.JOBONLINE_SLEEP_MS || "40"));
  const useCache = envBool("USE_RAW_CACHE", false);
  const shards = (process.env.JOBONLINE_PROVINCE_CODES || DEFAULT_PROVINCES.join(","))
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

  fs.mkdirSync(RAW_DIR, { recursive: true });
  const encryptor = createEncryptor(await ensureAppBundle());
  const rows = [];
  const seen = new Set();
  const summary = [];

  for (const shard of shards) {
    let shardRows = 0;
    let total = 0;
    for (let page = 1; page <= maxPagesPerShard; page += 1) {
      if (rows.length >= target) break;
      const data = await requestPage(encryptor, shard, page, pageSize, useCache);
      const object = data.object || {};
      const list = Array.isArray(object.rows) ? object.rows : [];
      total = Number(object.total || total || 0);
      for (const item of list) {
        const id = item && item.id ? String(item.id) : "";
        if (!id || seen.has(id)) continue;
        seen.add(id);
        rows.push(item);
        shardRows += 1;
        if (rows.length >= target) break;
      }
      if (!list.length || list.length < pageSize) break;
      if (total > 0 && page >= Math.ceil(total / pageSize)) break;
      if (sleepMs > 0) await sleep(sleepMs);
    }
    summary.push({ shard, total, records: shardRows });
    console.log(JSON.stringify({ stage: "jobonline_shard_done", shard, records: shardRows, total_records: rows.length }));
    if (rows.length >= target) break;
  }

  fs.writeFileSync(OUTPUT_PATH, JSON.stringify({
    generatedAt: new Date().toISOString(),
    target,
    records: rows.length,
    summary,
    rows,
  }, null, 2), "utf8");
  console.log(JSON.stringify({ stage: "jobonline_done", output: OUTPUT_PATH, records: rows.length }));
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
});
