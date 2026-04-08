/**
 * Minimal dashboard: lists jobs, toggles applied state, triggers scan.
 * Same-origin API under /jobs.
 */

const $ = (sel, root = document) => root.querySelector(sel);

const state = {
  highOnly: false,
  canadaOnly: false,
};

/** US state / territory codes when used as "City, ST" (excludes Canadian provinces). */
const US_STATE_CODES = new Set([
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "IA", "ID", "IL", "IN", "KS", "KY",
  "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NM", "NV", "NY",
  "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VA", "VT", "WA", "WI", "WV", "WY", "DC",
]);

const CA_PROV_CODES = new Set(["ON", "BC", "AB", "QC", "MB", "SK", "NS", "NB", "PE", "NL", "YT", "NT", "NU"]);

/** Title/location/description suggest remote or hybrid (US office may still hire Canada). */
function hasRemoteOrHybridSignal(hay) {
  return /\bremote\b|\bhybrid\b|work\s+from\s+home|wfh\b|distributed\s+team/i.test(hay);
}

/**
 * When "Canada" is checked, hide rows that look US-based.
 * Uses full title + description + location (NYC often appears only in the title).
 */
function isExcludedNonCanada(job) {
  const loc = (job.location || "").trim();
  const title = job.title || "";
  const desc = job.description || "";
  const hay = `${loc}\n${title}\n${desc}`.toLowerCase();
  const hayFull = `${loc}\n${title}\n${desc}`;

  const canadaHint =
    /\bcanada\b|\bcanadian\b/i.test(hay) ||
    /toronto|montreal|vancouver|calgary|ottawa|edmonton|winnipeg|mississauga|waterloo|kitchener|hamilton|victoria|halifax|saskatoon|regina|gatineau|laval|burnaby|surrey|kelowna|london\s*,\s*on|markham|oakville|windsor|quebec city|british columbia|\bontario\b|manitoba|saskatchewan|nova scotia|new brunswick|newfoundland|prince edward|northwest territor|yukon|nunavut/i.test(
      hay,
    ) ||
    /,\s*(on|bc|ab|qc|mb|sk|ns|nb|pe|nl|yt|nt|nu)\b/i.test(hay);

  if (canadaHint) return false;

  // README tables often use "SF" / "NYC" with no ", CA" — treat as US site unless remote/hybrid is mentioned.
  if (
    /^\s*sf\s*$/i.test(loc) ||
    /^\s*nyc\s*$/i.test(loc) ||
    /^\s*silicon valley\s*$/i.test(loc) ||
    /^\s*bay area\s*$/i.test(loc)
  ) {
    if (hasRemoteOrHybridSignal(hayFull)) return false;
    return true;
  }

  const tailState = /,\s*([A-Za-z]{2})\s*$/;
  for (const part of [loc, title]) {
    const m = part.match(tailState);
    if (m) {
      const code = m[1].toUpperCase();
      if (CA_PROV_CODES.has(code)) continue;
      if (US_STATE_CODES.has(code)) return true;
    }
  }

  if (
    /\b(nyc\b|new york,\s*ny|manhattan|brooklyn,\s*ny|silicon valley|san francisco,\s*ca|los angeles,\s*ca|chicago,\s*il|boston,\s*ma|seattle,\s*wa|austin,\s*tx|miami,\s*fl|atlanta,\s*ga|denver,\s*co|portland,\s*or|philadelphia,\s*pa|houston,\s*tx)\b/i.test(
      hay,
    )
  ) {
    if (hasRemoteOrHybridSignal(hayFull)) return false;
    return true;
  }

  if (/\b(united states|u\.s\.a\.|usa\b)(?!\s*and canada)/i.test(hay)) return true;

  if (
    /\b(us\s+only|us\s+citizen|authorized\s+to\s+work\s+in\s+the\s+u\.?s\.?|based\s+in\s+the\s+u\.?s\.?|on-?site\s+.*\b(united states|u\.s\.)\b)/i.test(
      hay,
    )
  ) {
    return true;
  }

  return false;
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}

function escAttr(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;");
}

function priorityClass(p) {
  if (p === "HIGH") return "priority priority--high";
  if (p === "MEDIUM") return "priority priority--medium";
  return "priority priority--low";
}

function renderTags(tags) {
  if (!tags || !tags.length) {
    return '<span class="tags">—</span>';
  }
  return `<span class="tags">${tags.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</span>`;
}

const PAGE_SIZE = 200;

/** Fetch every page until a short page or empty page (do not rely on total alone — avoids edge cases). */
async function fetchAllJobs() {
  const base = state.highOnly ? "/jobs/high-priority" : "/jobs";
  let skip = 0;
  let reportedTotal = null;
  const items = [];
  for (;;) {
    const qs = new URLSearchParams({ skip: String(skip), limit: String(PAGE_SIZE) });
    const r = await fetch(`${base}?${qs}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    if (reportedTotal === null && typeof data.total === "number") {
      reportedTotal = data.total;
    }
    const page = data.items || [];
    if (page.length === 0) break;
    items.push(...page);
    if (page.length < PAGE_SIZE) break;
    skip += PAGE_SIZE;
  }
  return { total: reportedTotal ?? items.length, items };
}

function setStatus(msg, kind = "") {
  const el = $("#status-bar");
  el.textContent = msg;
  el.className = "status-bar" + (kind ? ` status-bar--${kind}` : "");
}

async function loadTable() {
  const tbody = $("#jobs-body");
  tbody.innerHTML = `<tr><td colspan="8" class="empty">Loading…</td></tr>`;
  try {
    const { total: apiTotal, items: rawItems } = await fetchAllJobs();
    let items = rawItems;
    if (state.canadaOnly) {
      items = items.filter((j) => !isExcludedNonCanada(j));
    }
    if (!items.length) {
      const msg = state.canadaOnly
        ? "No jobs match the Canada filter. Try unchecking Canada or refresh data."
        : "No jobs yet. Run a scan or check the API.";
      tbody.innerHTML = `<tr><td colspan="8" class="empty">${esc(msg)}</td></tr>`;
      setStatus(msg, "");
      return;
    }
    const shown = items.length;
    const hint =
      state.canadaOnly && shown < apiTotal
        ? `Showing ${shown} of ${apiTotal} jobs (Canada filter on). Scroll the table for the full list.`
        : `Showing ${shown} job${shown === 1 ? "" : "s"}. Scroll the table for the full list.`;
    setStatus(hint, "ok");
    tbody.innerHTML = items.map((j) => rowHtml(j)).join("");
    tbody.querySelectorAll("[data-applied-toggle]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = Number(btn.dataset.id);
        const currentlyApplied = btn.dataset.applied === "1";
        onToggleApplied(id, currentlyApplied);
      });
    });
  } catch (e) {
    console.error(e);
    tbody.innerHTML = `<tr><td colspan="8" class="empty">Failed to load jobs.</td></tr>`;
    setStatus(String(e.message || e), "err");
  }
}

/** Show e.g. "SF · Remote" when location is a US shorthand/metro and copy mentions remote/hybrid. */
function formatLocationCell(j) {
  const raw = (j.location || "").trim();
  const base = raw || "—";
  const hayFull = `${j.location || ""}\n${j.title || ""}\n${j.description || ""}`;
  const hay = hayFull.toLowerCase();
  const shortUs =
    /^\s*sf\s*$/i.test(raw) ||
    /^\s*nyc\s*$/i.test(raw) ||
    /^\s*silicon valley\s*$/i.test(raw) ||
    /^\s*bay area\s*$/i.test(raw);
  if (shortUs && hasRemoteOrHybridSignal(hayFull)) {
    return `${raw} · Remote`;
  }
  if (
    /\b(san francisco,\s*ca|new york,\s*ny|los angeles,\s*ca|seattle,\s*wa|austin,\s*tx)\b/i.test(hay) &&
    hasRemoteOrHybridSignal(hayFull)
  ) {
    return `${raw} · Remote`;
  }
  return base;
}

function rowHtml(j) {
  const applied = Boolean(j.applied_at);
  const location = formatLocationCell(j);
  return `
    <tr data-id="${j.id}">
      <td>
        <button type="button" class="btn btn--small btn--ghost" data-applied-toggle data-id="${j.id}" data-applied="${applied ? "1" : "0"}"
          aria-pressed="${applied}" title="Toggle applied">
          ${applied ? "Applied" : "Mark applied"}
        </button>
      </td>
      <td><span class="${priorityClass(j.priority)}">${esc(j.priority || "—")}</span></td>
      <td>${esc(j.title)}</td>
      <td>${esc(j.company)}</td>
      <td class="cell-location">${esc(location)}</td>
      <td>${renderTags(j.tags)}</td>
      <td>${esc(j.source)}</td>
      <td class="cell-link"><a class="link" href="${escAttr(j.url)}" target="_blank" rel="noopener noreferrer">Open</a></td>
    </tr>
  `;
}

async function onToggleApplied(id, currentlyApplied) {
  const next = !currentlyApplied;
  try {
    const r = await fetch(`/jobs/${id}/applied`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ applied: next }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    await loadTable();
    setStatus(next ? `Marked job #${id} as applied.` : `Cleared applied for job #${id}.`, "ok");
  } catch (e) {
    setStatus(String(e.message || e), "err");
  }
}

async function runScan() {
  setStatus("Scan queued…");
  try {
    const r = await fetch("/run-scan", { method: "POST" });
    const data = await r.json().catch(() => ({}));
    if (data.status === "already_running") {
      setStatus("Scan already running. Polling status…", "ok");
    } else {
      setStatus("Scan started. Waiting for completion…", "ok");
    }
    await pollScanDone();
    await loadTable();
    setStatus("Scan finished. List refreshed.", "ok");
  } catch (e) {
    setStatus(String(e.message || e), "err");
  }
}

function pollScanDone() {
  return new Promise((resolve, reject) => {
    const t0 = Date.now();
    const tick = async () => {
      if (Date.now() - t0 > 120_000) {
        reject(new Error("Scan timeout"));
        return;
      }
      try {
        const r = await fetch("/scan-status");
        const s = await r.json();
        if (s.status !== "running") {
          resolve(s);
          return;
        }
      } catch (e) {
        reject(e);
        return;
      }
      setTimeout(tick, 2000);
    };
    tick();
  });
}

function init() {
  $("#filter-high").addEventListener("change", (e) => {
    state.highOnly = e.target.checked;
    loadTable();
  });
  $("#filter-canada").addEventListener("change", (e) => {
    state.canadaOnly = e.target.checked;
    loadTable();
  });
  $("#btn-refresh").addEventListener("click", () => {
    loadTable();
    setStatus("Refreshed.", "ok");
  });
  $("#btn-scan").addEventListener("click", runScan);
  loadTable();
}

init();
