(function () {
  const STORE = "ownex-notes-v1";
  const FEEL_STORE = "ownex-feelings-v1";
  const FEEL_BACKUP = "ownex-feelings-backup-v1";
  const TOKEN_STORE = "ownex-family-token";
  const LOCAL_FAMILY = "ownex-family-local-v1";
  let familyMe = null;
  let familyBackend = "unknown";
  const MONTHS = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"];
  const ICONS = {
    exhibition:
      '<svg class="icon" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16"/><path d="M7 16l3.2-4 2.3 3 2-2.4L17 16"/><circle cx="9" cy="9" r="1.1"/></svg>',
    music:
      '<svg class="icon" viewBox="0 0 24 24"><path d="M9 18V6l10-2v12"/><circle cx="7" cy="18" r="2.2"/><circle cx="17" cy="16" r="2.2"/></svg>',
    stage:
      '<svg class="icon" viewBox="0 0 24 24"><path d="M4 18c2-4 4.5-6 8-6s6 2 8 6"/><circle cx="9" cy="9" r="2"/><circle cx="15" cy="9" r="2"/></svg>',
  };

  const data = window.OWNEX || { exhibitions: [], google: {} };

  try {
    applySeason();
  } catch (err) {}
  const notes = loadNotes();
  const feels = loadFeels();
  try {
    mergeSaved();
  } catch (err) {}
  const state = {
    field: "exhibition",
    year: "",
    month: "",
    initial: "",
    selected: null,
    artIndex: 0,
    space: "",
    reviewId: "",
    stickerYear: String(Math.max(2026, new Date().getFullYear())),
    stickerPage: 0,
    frontExtra: 0,
  };
  const FRONT_REVIEWS = 3;

  function isPhoneLayout() {
    try {
      return Boolean(navigator.standalone) ||
        window.matchMedia("(display-mode: standalone)").matches ||
        window.matchMedia("(max-width: 800px)").matches;
    } catch (err) {
      return false;
    }
  }

  function frontReviewBase() {
    return isPhoneLayout() ? 2 : FRONT_REVIEWS;
  }

  function frontReviewCount() {
    return frontReviewBase() + (Number(state.frontExtra) || 0);
  }

  function syncPhoneClass() {
    document.body.classList.toggle("phone", isPhoneLayout());
  }

  syncPhoneClass();
  window.addEventListener("resize", syncPhoneClass);

  const yearEl = document.getElementById("year");
  const yearAll = document.getElementById("year-all");
  const monthEl = document.getElementById("month");
  const monthWrap = document.getElementById("month-wrap");
  const monthList = document.getElementById("month-list");
  const ownCal = document.getElementById("own-cal");
  const artwork = document.getElementById("artwork");
  const frontRow = document.getElementById("front-row");
  const feelings = document.getElementById("feelings");
  const reviewPage = document.getElementById("review-page");
  const praiseBoard = document.getElementById("praise-board");
  const gcalIcon = document.getElementById("gcal-icon");

  if (gcalIcon && data.google && data.google.open_url) gcalIcon.href = data.google.open_url;

  try {
    fillYears();
  } catch (err) {}
  document.querySelectorAll(".field").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.disabled) return;
      state.field = btn.getAttribute("data-field");
      document.querySelectorAll(".field").forEach((el) => el.classList.toggle("on", el === btn));
      state.month = "";
      state.selected = null;
      if (monthEl) monthEl.value = "";
      draw();
    });
  });
  let pickLock = false;
  function syncPicks(fromUser) {
    if (pickLock || !yearEl || !monthEl) return;
    const y = String(yearEl.value || "");
    const m = String(monthEl.value || "");
    if (y === state.year && m === state.month) return;
    state.year = y;
    state.month = m;
    if (y && y !== "all") {
      state.stickerYear = y;
      state.stickerPage = 0;
    }
    if (fromUser) {
      state.selected = null;
      state.space = "";
      state.initial = "";
    }
    draw();
  }
  window.ownexSyncPicks = function () {
    syncPicks(true);
    return false;
  };
  if (yearEl) yearEl.addEventListener("change", function () { syncPicks(true); });
  if (yearAll) yearAll.addEventListener("click", () => {
    if (yearEl) yearEl.value = "all";
    syncPicks(true);
  });
  if (monthEl) monthEl.addEventListener("change", function () { syncPicks(true); });
  document.addEventListener("click", function (event) {
    const nameBtn = event.target.closest("#month-list .name");
    if (!nameBtn) return;
    const row =
      showById(nameBtn.getAttribute("data-id") || "") ||
      monthRows()[Number(nameBtn.getAttribute("data-index"))];
    if (!row) return;
    event.preventDefault();
    openShow(row);
  });

  function applySeason() {
    const month = new Date().getMonth() + 1;
    const season = month === 12 || month <= 2 ? "winter" : month <= 5 ? "spring" : month <= 8 ? "summer" : "fall";
    document.body.dataset.season = season;
    const colors = { winter: "#1b2a33", spring: "#24382e", summer: "#2a2e12", fall: "#351e28" };
    const theme = document.querySelector('meta[name="theme-color"]');
    if (theme) theme.setAttribute("content", colors[season]);
  }

  function notesKey() {
    return familyMe && familyMe.id ? STORE + ":" + familyMe.id : STORE;
  }

  function readNotesStore(key) {
    try {
      const raw = JSON.parse(localStorage.getItem(key) || "{}");
      return raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};
    } catch (err) {
      return {};
    }
  }

  function fillNotes(source) {
    Object.keys(notes).forEach((key) => delete notes[key]);
    Object.keys(source || {}).forEach((key) => {
      notes[key] = source[key];
    });
  }

  function persistNotes() {
    localStorage.setItem(notesKey(), JSON.stringify(notes));
  }

  function switchNotesToUser(user) {
    familyMe = user && user.id ? user : null;
    if (user && user.owner) {
      try {
        if (!localStorage.getItem("ownex-notes-moved")) {
          const destKey = STORE + ":" + user.id;
          const dest = readNotesStore(destKey);
          const guest = readNotesStore(STORE);
          if (!Object.keys(dest).length && Object.keys(guest).length) {
            localStorage.setItem(destKey, JSON.stringify(guest));
            localStorage.setItem("ownex-notes-moved", "1");
          }
        }
      } catch (err) {}
    }
    fillNotes(readNotesStore(notesKey()));
    mergeSaved();
  }

  function loadNotes() {
    return readNotesStore(STORE);
  }

  const SHARE_URL = "shared-state.json";
  let shareAt = "";
  let shareQuiet = false;

  function isStaticHost() {
    try {
      return /github\.io$/i.test(location.hostname);
    } catch (err) {
      return false;
    }
  }

  function saveNotes() {
    persistNotes();
    paintGlance();
    pushState();
  }

  function readFeelStore(key, storage) {
    try {
      const raw = JSON.parse((storage && storage.getItem(key)) || "[]");
      return Array.isArray(raw) ? raw : [];
    } catch (err) {
      return [];
    }
  }

  function writeFeelStore(list) {
    const text = JSON.stringify(list);
    try {
      localStorage.setItem(FEEL_STORE, text);
    } catch (err) {}
    try {
      sessionStorage.setItem(FEEL_BACKUP, text);
    } catch (err) {}
  }

  function loadFeels() {
    const bag = [];
    const seen = {};
    []
      .concat(readFeelStore(FEEL_STORE, localStorage), readFeelStore(FEEL_BACKUP, sessionStorage))
      .forEach((item) => {
        if (!item) return;
        const key = [item.id || "", item.title || "", item.body || "", item.at || "", item.by || ""].join("|");
        if (seen[key]) return;
        seen[key] = true;
        bag.push(item);
      });
    return bag;
  }

  function mergeSaved() {
    const seed = data.saved;
    if (!seed || typeof seed !== "object") return;
    const seedNotes = seed.notes && typeof seed.notes === "object" ? seed.notes : {};
    const rev = String(seed.rev || "reviews-20260907k");
    let applied = "";
    try { applied = localStorage.getItem("ownex-seed-rev") || ""; } catch (err) {}
    Object.keys(seedNotes).forEach((key) => {
      const local = notes[key] && typeof notes[key] === "object" ? notes[key] : {};
      const seedNote = seedNotes[key] && typeof seedNotes[key] === "object" ? seedNotes[key] : {};
      if (!notes[key] || applied !== rev) {
        notes[key] = Object.assign({}, seedNote, local);
        notes[key].visited = Boolean(local.visited) || Boolean(seedNote.visited);
      }
    });
    try { localStorage.setItem("ownex-seed-rev", rev); } catch (err) {}
    const seen = {};
    feels.forEach((item) => {
      seen[[item.id || "", item.title || "", item.body || "", item.at || ""].join("|")] = true;
    });
    (Array.isArray(seed.feels) ? seed.feels : []).forEach((item) => {
      if (!item) return;
      const key = [item.id || "", item.title || "", item.body || "", item.at || ""].join("|");
      if (seen[key]) return;
      seen[key] = true;
      feels.push(item);
    });
    try {
      persistNotes();
      writeFeelStore(feels);
    } catch (err) {}
  }

  function saveFeels() {
    writeFeelStore(feels);
    paintGlance();
    pushState();
    pushShared();
  }

  function feelKey(item) {
    return [item.id || "", item.title || "", item.body || "", item.at || "", item.by || ""].join("|");
  }

  function mergeFeelsList(list) {
    const seen = {};
    let added = 0;
    feels.forEach((item) => {
      seen[feelKey(item)] = true;
    });
    (Array.isArray(list) ? list : []).forEach((item) => {
      if (!item) return;
      const key = feelKey(item);
      if (seen[key]) return;
      seen[key] = true;
      feels.push(item);
      added += 1;
    });
    writeFeelStore(feels);
    return added;
  }

  function sharePack() {
    return { feels: feels, at: new Date().toISOString() };
  }

  function pullShared() {
    if (!SHARE_URL || isStaticHost()) return Promise.resolve(false);
    return fetch(SHARE_URL + "?" + Date.now(), { cache: "no-store", headers: { Accept: "application/json" } })
      .then(function (res) { return res.json(); })
      .then(function (remote) {
        if (!remote || !Array.isArray(remote.feels)) return false;
        if (remote.at && shareAt && remote.at === shareAt) return false;
        shareQuiet = true;
        const added = mergeFeelsList(remote.feels);
        shareQuiet = false;
        if (remote.at && (!shareAt || remote.at > shareAt)) shareAt = remote.at;
        return added > 0;
      })
      .catch(function () { return false; });
  }

  function pushShared() {
    if (shareQuiet || isStaticHost()) return Promise.resolve();
    if (!SHARE_URL) return Promise.resolve();
    const body = sharePack();
    shareAt = body.at;
    return fetch(SHARE_URL, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    }).catch(function () {});
  }

  function familyToken() {
    try {
      return localStorage.getItem(TOKEN_STORE) || "";
    } catch (err) {
      return "";
    }
  }

  function setFamilyToken(token) {
    try {
      if (token) localStorage.setItem(TOKEN_STORE, token);
      else localStorage.removeItem(TOKEN_STORE);
    } catch (err) {}
  }

  function localHash(pin, salt) {
    let h = 2166136261;
    const s = String(salt) + String(pin);
    for (let i = 0; i < s.length; i += 1) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return (h >>> 0).toString(16);
  }

  function readLocalFamily() {
    try {
      const data = JSON.parse(localStorage.getItem(LOCAL_FAMILY) || "{}");
      if (!data || typeof data !== "object") return { users: [], sessions: {} };
      return {
        users: Array.isArray(data.users) ? data.users : [],
        sessions: data.sessions && typeof data.sessions === "object" ? data.sessions : {},
      };
    } catch (err) {
      return { users: [], sessions: {} };
    }
  }

  function writeLocalFamily(data) {
    try {
      localStorage.setItem(LOCAL_FAMILY, JSON.stringify(data));
    } catch (err) {}
  }

  function publicLocalUser(user) {
    if (!user) return { id: "", name: "", owner: false, approved: false };
    return {
      id: user.id,
      name: user.name,
      owner: Boolean(user.owner),
      approved: Boolean(user.approved),
    };
  }

  function localMe() {
    const token = familyToken();
    const data = readLocalFamily();
    const info = data.sessions[token];
    if (!info) return { id: "", name: "", owner: false, approved: false };
    const user = data.users.find((item) => item.id === info.user_id);
    return publicLocalUser(user);
  }

  function localFamilyApi(path, body) {
    const data = readLocalFamily();
    if (path === "/api/family/me") return Promise.resolve(localMe());
    if (path === "/api/family/people") {
      if (!localMe().id) return Promise.resolve({ error: "목록을 볼 수 없습니다." });
      return Promise.resolve({
        people: data.users.map((user) => publicLocalUser(user)),
      });
    }
    if (path === "/api/family/logout") {
      delete data.sessions[familyToken()];
      writeLocalFamily(data);
      return Promise.resolve({ ok: true });
    }
    if (path === "/api/family/signup" || path === "/api/family/login" || path === "/api/family/enter") {
      let name = String((body && body.name) || "").trim();
      const pin = String((body && body.pin) || "");
      if (!name || name.length > 64) return Promise.resolve({ error: "이름 또는 이메일은 1~64자로 해 주세요." });
      if (pin.length < 4) return Promise.resolve({ error: "비밀번호는 4자 이상으로 해 주세요." });
      if (name.indexOf("@") >= 0) name = name.toLowerCase();
      const existing = data.users.find((item) => item.name === name);
      if (path === "/api/family/enter") {
        path = existing ? "/api/family/login" : "/api/family/signup";
      }
      if (path === "/api/family/signup") {
        if (existing) return Promise.resolve({ error: "이미 있는 이름입니다." });
        const salt = String(Date.now());
        const isOwner = !data.users.some((user) => user.owner);
        const user = {
          id: "l" + Date.now().toString(16),
          name: name,
          salt: salt,
          pinHash: localHash(pin, salt),
          owner: isOwner,
          approved: true,
        };
        data.users.push(user);
        const token = "t" + Date.now().toString(16) + Math.random().toString(16).slice(2);
        data.sessions[token] = { user_id: user.id };
        writeLocalFamily(data);
        return Promise.resolve(Object.assign(publicLocalUser(user), { token: token }));
      }
      const user = existing;
      if (!user || user.pinHash !== localHash(pin, user.salt)) {
        return Promise.resolve({ error: "이름 또는 비밀번호가 다릅니다." });
      }
      if (!user.approved) return Promise.resolve({ error: "아직 승인을 기다리고 있습니다." });
      const token = "t" + Date.now().toString(16) + Math.random().toString(16).slice(2);
      data.sessions[token] = { user_id: user.id };
      writeLocalFamily(data);
      return Promise.resolve(Object.assign(publicLocalUser(user), { token: token }));
    }
    if (path === "/api/family/approve") {
      const me = localMe();
      if (!me.owner) return Promise.resolve({ error: "승인할 수 없습니다." });
      const user = data.users.find((item) => item.id === (body && body.id));
      if (!user) return Promise.resolve({ error: "그 이름을 찾을 수 없습니다." });
      user.approved = true;
      writeLocalFamily(data);
      return Promise.resolve(publicLocalUser(user));
    }
    if (path === "/api/family/state") {
      const me = localMe();
      if (!me.id) return Promise.resolve({ notes: {}, feels: feels });
      if (body) {
        const nextNotes = body.notes && typeof body.notes === "object" ? body.notes : notes;
        localStorage.setItem(STORE + ":" + me.id, JSON.stringify(nextNotes));
        if (Array.isArray(body.feels)) mergeFeelsList(body.feels);
        return Promise.resolve({ notes: nextNotes, feels: feels });
      }
      return Promise.resolve({ notes: readNotesStore(STORE + ":" + me.id), feels: feels });
    }
    return Promise.resolve({ error: "없는 주소입니다." });
  }

  function api(path, body) {
    if (familyBackend === "local" && path.indexOf("/api/family/") === 0) {
      return localFamilyApi(path, body);
    }
    const headers = { Accept: "application/json" };
    const token = familyToken();
    if (token) headers.Authorization = "Bearer " + token;
    const opt = { method: body ? "POST" : "GET", headers, credentials: "same-origin" };
    if (body) {
      headers["Content-Type"] = "application/json";
      opt.body = JSON.stringify(body);
    }
    return fetch(path, opt).then((res) => res.json().catch(() => ({})));
  }

  function probeFamily() {
    if (isStaticHost()) {
      familyBackend = "local";
      const me = localMe();
      if (me.id) switchNotesToUser(me);
      return Promise.resolve(me);
    }
    return fetch("/api/family/me", {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
      cache: "no-store",
    })
      .then((res) => {
        const ct = res.headers.get("content-type") || "";
        if (!res.ok || ct.indexOf("json") < 0) {
          familyBackend = "local";
          const me = localMe();
          if (me.id) switchNotesToUser(me);
          return me;
        }
        familyBackend = "api";
        return res.json().then((user) => {
          if (user && user.id) switchNotesToUser(user);
          return user;
        });
      })
      .catch(() => {
        familyBackend = "local";
        const me = localMe();
        if (me.id) switchNotesToUser(me);
        return me;
      });
  }

  function applyNotes(nextNotes) {
    fillNotes(nextNotes && typeof nextNotes === "object" ? nextNotes : {});
    persistNotes();
  }

  function pushState() {
    const body = { feels: feels };
    if (familyMe && familyMe.id) body.notes = notes;
    return api("/api/family/state", body).then((payload) => {
      if (!payload || payload.error) return;
      if (familyMe && familyMe.id && payload.notes && typeof payload.notes === "object") applyNotes(payload.notes);
      if (Array.isArray(payload.feels)) mergeFeelsList(payload.feels);
    }).catch(() => {});
  }

  function pullState() {
    return api("/api/family/state").then((shared) => {
      if (shared && !shared.error && Array.isArray(shared.feels)) mergeFeelsList(shared.feels);
      return api("/api/family/me").then((user) => {
      if (!(user && user.id)) return;
      switchNotesToUser(user);
      return api("/api/family/state").then((payload) => {
        if (!payload || payload.error) return;
        mergeFeelsList(payload.feels || []);
        const remoteNotes = payload.notes && typeof payload.notes === "object" ? payload.notes : {};
        const mergedNotes = {};
        Object.keys(Object.assign({}, remoteNotes, notes)).forEach((key) => {
          const a = notes[key] || {};
          const b = remoteNotes[key] || {};
          const visited = Object.prototype.hasOwnProperty.call(a, "visited")
            ? Boolean(a.visited)
            : Boolean(b.visited);
          mergedNotes[key] = Object.assign({}, b, a, { visited: visited });
        });
        applyNotes(mergedNotes);
        return api("/api/family/state", { notes: notes, feels: feels }).then((saved) => {
          if (!saved || saved.error) return;
          if (saved.notes && typeof saved.notes === "object") applyNotes(saved.notes);
          if (Array.isArray(saved.feels)) mergeFeelsList(saved.feels);
        });
      });
      });
    }).catch(() => {});
  }

  const PRAISE_STAMPS = ["잘했어요", "참 잘했어요", "우수해요", "멋져요", "훌륭해요", "최고예요", "잘 보았어요", "열심히 보았어요", "대단해요", "참 훌륭해요"];
  const PRAISE_COUNT = 25;
  const PRAISE_FILLS = ["#e39a86", "#d4a05c", "#c9849a", "#6faf8e", "#d9b15a", "#c87868", "#7ea4b8", "#c4a06a"];

  function yearChoices() {
    const now = new Date().getFullYear();
    const last = Math.max(2028, now);
    const years = [];
    for (let y = 2026; y <= last; y += 1) years.push(String(y));
    return years;
  }

  function showById(id) {
    const want = String(id || "");
    if (!want) return null;
    return (data.exhibitions || []).find((row) => row && itemId(row) === want) || null;
  }

  function visitYearOf(id, note) {
    if (note && note.at) return String(note.at).slice(0, 4);
    const row = showById(id);
    return ((row && row.start_date) || String(new Date().getFullYear())).slice(0, 4);
  }

  function allVisits() {
    const bag = notes && typeof notes === "object" && !Array.isArray(notes) ? notes : {};
    const seen = {};
    return Object.keys(bag)
      .filter((id) => id && bag[id] && (bag[id].visited === true || bag[id].visited === "true"))
      .filter((id) => {
        const pair = id.split("|").slice(0, 2).join("|");
        if (seen[pair]) return false;
        seen[pair] = true;
        return true;
      })
      .sort((a, b) => String(bag[a].at || "").localeCompare(String(bag[b].at || "")));
  }

  function visitsForYear(year) {
    const y = String(year || new Date().getFullYear());
    return allVisits()
      .filter((id) => visitYearOf(id, notes[id]) === y)
      .map((id) => ({ id, note: notes[id], row: showById(id) }));
  }

  function visitsForScope(year) {
    if (String(year) === "all") {
      return allVisits().map((id) => ({ id, note: notes[id], row: showById(id) }));
    }
    return visitsForYear(year);
  }

  function praiseFor(count, allTime) {
    if (count >= 25) return { word: "대단해요", line: allTime ? "전시를 깊이 따라가고 있습니다." : "올해 전시를 깊이 따라가고 있습니다." };
    if (count >= 20) return { word: "최고예요", line: "보는 눈이 꽤 단단해졌습니다." };
    if (count >= 10) return { word: "우수해요", line: allTime ? "열 번을 채웠습니다." : "열 번을 채웠습니다. 올해의 그림이 완성되었습니다." };
    if (count >= 5) return { word: "참 잘했어요", line: "작품 앞에 머무는 시간이 늘고 있습니다." };
    if (count >= 1) return { word: "잘했어요", line: allTime ? "전시장에 발을 들인 기록입니다." : "전시장에 발을 들인 해입니다." };
    return { word: "함께 보아요", line: "방문함을 누르면 칭찬 스티커가 붙습니다." };
  }

  function seedCubistFeel() {
    if (feels.some((item) => item.title === "큐비스트 감상")) return;
    const show = matchShow("큐비스트 감상");
    feels.unshift({
      id: "seed-cubist",
      title: "큐비스트 감상",
      body: "유럽의 거장 큐비스트들을 통해 한국의 나헤석, 김환기 작가 등 한국 근현대 미술가들이 오버랩되어 한국의 큐비즘의 태동을 만난 것 같았다.",
      at: new Date().toISOString().slice(0, 10),
      showId: show ? itemId(show) : "",
    });
    saveFeels();
  }

  function matchShow(text) {
    const cleaned = String(text || "")
      .replace(/[〈〉《》\(\)·•]/g, " ")
      .replace(/감상|소감|방문|후기|느낌/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const tokens = cleaned.split(" ").filter((part) => part.length >= 2);
    let best = null;
    let score = 0;
    events().forEach((row) => {
      const title = row.title || "";
      let next = 0;
      if (cleaned && title.includes(cleaned)) next += 8;
      tokens.forEach((token) => {
        if (title.includes(token)) next += 4;
        if ((row.venue || "").includes(token)) next += 1;
      });
      if (next > score) {
        score = next;
        best = row;
      }
    });
    return score >= 4 ? best : null;
  }

  function showArtwork(row) {
    if (!row || !artwork) return;
    state.selected = row;
    state.space = "";
    if (frontRow) {
      frontRow.hidden = true;
      frontRow.setAttribute("hidden", "");
    }
    if (ownCal) ownCal.hidden = true;
    if (monthList) monthList.hidden = true;
    if (reviewPage) reviewPage.hidden = true;
    artwork.hidden = false;
    artwork.removeAttribute("hidden");
    document.body.classList.add("open");
    document.body.classList.remove("reviews");
    try {
      renderArtwork();
    } catch (err) {}
    try {
      artwork.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {}
  }

  function openShow(row) {
    if (!row) return;
    const year = (row.start_date || "").slice(0, 4);
    const month = (row.start_date || "").slice(5, 7);
    pickLock = true;
    state.year = year || state.year || "all";
    state.month = month || state.month;
    state.selected = row;
    state.space = "";
    if (yearEl && state.year) yearEl.value = state.year;
    if (monthEl && state.month) monthEl.value = state.month;
    try {
      draw();
    } catch (err) {}
    showArtwork(row);
    setTimeout(function () {
      pickLock = false;
      if (state.selected === row) showArtwork(row);
    }, 500);
  }

  function events() {
    const rows = (data.exhibitions || []).map((row) => Object.assign({ kind: row.kind || "exhibition" }, row));
    return rows.filter((row) => row.kind === state.field);
  }

  function itemId(row) {
    if (!row) return "";
    return [row.title || "", row.venue || "", row.start_date || "", row.end_date || ""].join("|");
  }

  function showPair(row) {
    return [row && row.title ? row.title : "", row && row.venue ? row.venue : ""].join("|");
  }

  function showEnded(row) {
    const end = (row && (row.end_date || row.start_date)) || "";
    if (!end) return false;
    return end < new Date().toISOString().slice(0, 10);
  }

  function endedTag(row) {
    return showEnded(row) ? '<span class="ended-tag">종료</span>' : "";
  }

  function relatedNoteKeys(row) {
    const id = itemId(row);
    const pair = showPair(row) + "|";
    const keys = Object.keys(notes).filter((key) => key === id || (pair !== "|" && key.indexOf(pair) === 0));
    if (keys.indexOf(id) < 0) keys.push(id);
    return keys;
  }

  function isVisited(row) {
    return relatedNoteKeys(row).some((key) => notes[key] && (notes[key].visited === true || notes[key].visited === "true"));
  }

  function titleBits(text) {
    return String(text || "")
      .replace(/[〈〉《》()·•,.]/g, " ")
      .replace(/\d{4}/g, " ")
      .split(/\s+/)
      .filter((part) => part.length >= 2);
  }

  function looseTitle(a, b) {
    const left = titleBits(a);
    const right = titleBits(b);
    if (!left.length || !right.length) return false;
    const short = left.length <= right.length ? left : right;
    const long = left.length <= right.length ? right : left;
    return short.every((tok) => long.some((item) => item.indexOf(tok) >= 0 || tok.indexOf(item) >= 0));
  }

  function choseong(text) {
    const ch = String(text || "").trim().charAt(0);
    const code = ch.charCodeAt(0);
    if (code >= 0xac00 && code <= 0xd7a3) {
      return "ㄱㄱㄴㄷㄷㄹㅁㅂㅂㅅㅅㅇㅈㅈㅊㅋㅌㅍㅎ".charAt(Math.floor((code - 0xac00) / 588));
    }
    return /[A-Za-z]/.test(ch) ? "A-Z" : "기타";
  }

  function overlapsMonth(row, year, month) {
    const start = row.start_date || row.collected_date || "";
    const end = row.end_date || start;
    if (!start || !month) return false;
    const from = start.slice(0, 7);
    const to = (end || start).slice(0, 7);
    if (!year || year === "all") {
      const first = Number(from.slice(0, 4));
      const last = Number(to.slice(0, 4));
      for (let y = first; y <= last; y += 1) {
        const key = y + "-" + month;
        if (from <= key && to >= key) return true;
      }
      return false;
    }
    const key = year + "-" + month;
    return from <= key && to >= key;
  }

  function googleMonthSrc(year, month) {
    const base = (data.google && data.google.embed_src) || "";
    if (!base) return "";
    const useYear = year === "all" ? String(new Date().getFullYear()) : year;
    const start = useYear + month + "01";
    const next = new Date(Number(useYear), Number(month), 1);
    const end = String(next.getFullYear()) + String(next.getMonth() + 1).padStart(2, "0") + "01";
    return base.replace(/&dates=[^&]*/g, "") + "&mode=MONTH&dates=" + start + "/" + end;
  }

  function fillYears() {
    if (!yearEl || !monthEl) return;
    const years = yearChoices();
    yearEl.innerHTML =
      '<option value="">연도를 고르세요</option><option value="all">전체</option>' +
      years.map((y) => `<option value="${y}">${y}</option>`).join("");
    monthEl.innerHTML = '<option value="">월을 고르세요</option>' + MONTHS.map((name, i) => {
      const value = String(i + 1).padStart(2, "0");
      return `<option value="${value}">${name}</option>`;
    }).join("");
  }

  function monthRows() {
    return events().filter((row) => overlapsMonth(row, state.year, state.month));
  }

  function paintGlance() {
    const home = document.getElementById("glance-home");
    if (home) {
      const onHome = !state.selected && state.space !== "reviews" && !(state.year && state.month);
      home.hidden = onHome;
    }
  }

  function paintGuests(total) {
    const el = document.getElementById("glance-visitor-num");
    if (!el) return;
    const n = Number(total);
    if (!Number.isFinite(n) || n < 1) return;
    el.textContent = String(n);
    try {
      localStorage.setItem("ownex-guest-total", String(n));
    } catch (err) {}
  }

  function guestDay() {
    return new Date().toISOString().slice(0, 10);
  }

  function alreadyCountedOpen() {
    try {
      return sessionStorage.getItem("ownex-open-hit") === "1";
    } catch (err) {
      return false;
    }
  }

  function markCountedOpen() {
    try {
      sessionStorage.setItem("ownex-open-hit", "1");
    } catch (err) {}
  }

  function readCachedGuests() {
    try {
      const n = Number(localStorage.getItem("ownex-guest-total") || "");
      return Number.isFinite(n) && n > 0 ? n : 0;
    } catch (err) {
      return 0;
    }
  }

  function countFrom(res) {
    if (!res || typeof res !== "object") return 0;
    const n = Number(res.total || res.value || res.count || 0);
    return Number.isFinite(n) ? n : 0;
  }

  function bumpSharedGuests(doHit) {
    const hosts = ["https://abacus.jsn.cam/", "https://abacus.jasoncameron.dev/"];
    const path = (doHit ? "hit" : "get") + "/ownex-yinxiakr/opens";
    return hosts.reduce(function (wait, host) {
      return wait.then(function (n) {
        if (n) return n;
        return fetch(host + path + "?" + Date.now(), { cache: "no-store" })
          .then((res) => res.json())
          .then((payload) => countFrom(payload))
          .catch(() => 0);
      });
    }, Promise.resolve(0));
  }

  function bumpLocalGuests(doHit) {
    return fetch("/api/visitors", {
      method: doHit ? "POST" : "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
    })
      .then((res) => {
        const ct = res.headers.get("content-type") || "";
        if (!res.ok || ct.indexOf("json") < 0) return 0;
        return res.json();
      })
      .then((payload) => countFrom(payload))
      .catch(() => 0);
  }

  function countSiteGuests() {
    const cached = readCachedGuests();
    const doHit = !alreadyCountedOpen();
    let local = cached;
    if (doHit) {
      local = cached + 1;
      markCountedOpen();
    }
    paintGuests(local);
    return Promise.all([bumpLocalGuests(doHit), bumpSharedGuests(doHit)]).then((pair) => {
      const total = Math.max(pair[1] || 0, pair[0] || 0, local || 0);
      paintGuests(total);
      return total;
    });
  }

  function goHomeApp() {
    state.space = "";
    state.selected = null;
    state.year = "";
    state.month = "";
    state.initial = "";
    if (yearEl) yearEl.value = "";
    if (monthEl) monthEl.value = "";
    if (location.hash === "#reviews") {
      history.replaceState(null, "", location.pathname + location.search);
    }
    draw();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function bindGlance() {
    const home = document.getElementById("glance-home");
    if (home) home.addEventListener("click", goHomeApp);
    document.addEventListener("click", (event) => {
      const all = event.target.closest("[data-reviews='all']");
      const more = event.target.closest("[data-reviews='more']");
      if (all) {
        event.preventDefault();
        openReviews();
      } else if (more) {
        event.preventDefault();
        showMoreReviews();
      }
    });
  }

  function reviewDraftOpen() {
    const box = document.getElementById("art-review-body");
    if (!box) return false;
    if (document.activeElement === box) return true;
    return Boolean(String(box.value || "").trim());
  }

  function draw() {
    paintGlance();
    const reviewOnly = state.space === "reviews";
    const browsing = Boolean(state.year && state.month);
    const showFeel = !reviewOnly && !state.selected && (state.space === "feel" || !browsing);
    document.body.classList.toggle("reviews", reviewOnly);
    document.body.classList.toggle("open", !reviewOnly && browsing && state.space !== "feel");
    if (monthWrap) monthWrap.hidden = false;
    if (yearAll) yearAll.classList.toggle("on", state.year === "all");
    const showMonth = !reviewOnly && browsing && !state.selected && state.space !== "feel";
    if (frontRow) {
      frontRow.hidden = !showFeel;
      if (showFeel) frontRow.removeAttribute("hidden");
    }
    if (reviewPage) reviewPage.hidden = !reviewOnly;
    if (ownCal) ownCal.hidden = !showMonth;
    if (monthList) monthList.hidden = !showMonth;
    artwork.hidden = reviewOnly || !state.selected;
    if (reviewOnly) {
      renderFeelings(reviewPage, "full");
      return;
    }
    if (showFeel) {
      try {
        renderFeelings(feelings, "preview");
      } catch (err) {}
      try {
        renderPraise();
      } catch (err) {
        renderPraiseFallback();
      }
    }
    if (showMonth) {
      try {
        renderOwnCalendar();
      } catch (err) {}
      try {
        renderNames();
      } catch (err) {}
    }
    if (state.selected) {
      try {
        renderArtwork();
      } catch (err) {
        artwork.hidden = false;
        artwork.innerHTML =
          '<div class="art-head"><button type="button" class="back" data-back="names">목록으로</button></div>' +
          (state.selected
            ? "<h3>" + escapeHtml(state.selected.title || "") + "</h3><p class='quiet'>전시를 여는 중 문제가 생겼습니다.</p>"
            : "");
        const back = artwork.querySelector("[data-back]");
        if (back) {
          back.addEventListener("click", () => {
            state.selected = null;
            draw();
          });
        }
      }
    }
  }

  function showMoreReviews() {
    const shown = frontReviewCount();
    if (shown >= feels.length) {
      openReviews();
      return;
    }
    state.frontExtra = (Number(state.frontExtra) || 0) + frontReviewBase();
    draw();
  }

  function openReviews() {
    state.space = "reviews";
    state.selected = null;
    try {
      draw();
    } catch (err) {}
    if (frontRow) frontRow.hidden = true;
    if (reviewPage) {
      reviewPage.hidden = false;
      reviewPage.removeAttribute("hidden");
      try {
        renderFeelings(reviewPage, "full");
      } catch (err) {}
      reviewPage.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (location.hash !== "#reviews") {
      try {
        location.hash = "reviews";
      } catch (err) {}
    }
  }

  function closeReviews() {
    state.space = "";
    if (location.hash === "#reviews") {
      history.replaceState(null, "", location.pathname + location.search);
    }
    draw();
  }

  function renderFeelings(root, mode) {
    const preview = mode !== "full";
    const box = root || (preview ? feelings : reviewPage);
    if (!box) return;
    const limit = preview ? frontReviewCount() : feels.length;
    const start = preview ? Math.max(0, feels.length - limit) : 0;
    const items = feels.slice(start);
    const rows = items.map((item, offset) => {
      const index = start + offset;
      const no = index + 1;
      const open = state.reviewId === item.id;
      const bodyText = String((item && item.body) || "");
      const snippet = bodyText.length > 28 ? bodyText.slice(0, 28) + "…" : bodyText;
      const show = (data.exhibitions || []).find((row) => itemId(row) === item.showId) || matchShow(item.title);
      return `<div class="review-item ${open ? "on" : ""}">
        <div class="review-last-row">
        <button type="button" class="review-line" data-id="${escapeHtml(item.id)}" data-title="${escapeHtml(item.title)}" data-show="${escapeHtml(item.showId || "")}" onclick="ownexGoReview(this)">
          <span class="review-no">${no}</span>
          <span class="review-date">${escapeHtml(item.at || "")}${item.by ? `<span class="review-by">${escapeHtml(item.by)}</span>` : ""}</span>
          <span class="review-name">${escapeHtml(item.title)}</span>
          <span class="review-snip">${escapeHtml(open ? "접기" : snippet)}</span>
        </button>
        </div>
        ${
          open
            ? `<div class="review-open">
                <p>${escapeHtml(item.body)}</p>
                <div class="review-actions">
                  ${
                    show
                      ? `<button type="button" class="review-go" data-show="${encodeURIComponent(item.showId || "")}" data-title="${encodeURIComponent(item.title)}">${escapeHtml(show.title)}</button>`
                      : ""
                  }
                  <button type="button" class="review-note" data-id="${escapeHtml(item.id)}">메모로 보내기</button>
                </div>
              </div>`
            : ""
        }
      </div>`;
    }).join("");
    const moreOutside = preview
      ? '<div class="review-foot">' +
        '<button type="button" class="review-more-btn" data-reviews="more" onclick="ownexMore()">계속</button>' +
        '<button type="button" class="review-all-btn" data-reviews="all" onclick="ownexReviews()">전체보기</button>' +
        "</div>"
      : "";
    const empty = [1, 2, 3].map(function (no) {
      return '<div class="review-item empty-row"><div class="review-last-row"><div class="review-line"><span class="review-no">' +
        no +
        '</span><span class="review-date"></span><span class="review-name"></span><span class="review-snip"></span></div></div></div>';
    }).join("");
    const head = preview
      ? `<div class="feel-head"><h2>Review</h2></div>`
      : `<div class="feel-head"><h2>Review</h2><button type="button" class="back" data-reviews="home" onclick="ownexHome()">앞페이지</button></div>`;
    const writeForm = preview
      ? ""
      : `<form class="feel-form" id="feel-form">
        <div class="feel-row">
          <input id="feel-title" name="title" maxlength="80" placeholder="제목" autocomplete="off" required />
          <button type="submit" class="save">남기기</button>
        </div>
        <textarea id="feel-body" name="body" placeholder="소감" required></textarea>
      </form>`;
    box.innerHTML =
      head +
      writeForm +
      `<div class="review-table">
        <div class="review-cols" aria-hidden="true">
          <span class="review-no">순번</span>
          <span class="review-date">날짜</span>
          <span class="review-name">제목</span>
          <span class="review-snip">소감</span>
        </div>
        ${rows || empty}
      </div>` +
      moreOutside;
    const form = box.querySelector("#feel-form");
    if (form) {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const title = box.querySelector("#feel-title").value.trim();
        const body = box.querySelector("#feel-body").value.trim();
        if (!title || !body) return;
        const show = matchShow(title);
        addReview(title, body, show);
        renderFeelings(box, mode);
      });
    }
    box.querySelectorAll(".review-line").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (btn.closest(".empty-row")) return;
        const showId = btn.getAttribute("data-show") || "";
        const title = btn.getAttribute("data-title") || "";
        const show =
          (showId && (data.exhibitions || []).find((row) => itemId(row) === showId)) ||
          matchShow(title);
        if (show) {
          openShow(show);
          return;
        }
        const id = btn.getAttribute("data-id");
        state.reviewId = state.reviewId === id ? "" : id;
        renderFeelings(box, mode);
      });
    });
    box.querySelectorAll(".review-go").forEach((btn) => {
      btn.addEventListener("click", () => {
        const showId = decodeURIComponent(btn.getAttribute("data-show") || "");
        const title = decodeURIComponent(btn.getAttribute("data-title") || "");
        const show = (data.exhibitions || []).find((row) => itemId(row) === showId) || matchShow(title);
        if (location.hash === "#reviews") history.replaceState(null, "", location.pathname + location.search);
        openShow(show);
      });
    });
    box.querySelectorAll(".review-note").forEach((btn) => {
      btn.addEventListener("click", () => {
        const item = feels.find((row) => row.id === btn.getAttribute("data-id"));
        if (item) sendToNotes(item);
      });
    });
    box.querySelectorAll("[data-reviews='all']").forEach((btn) => {
      btn.addEventListener("click", function (event) {
        event.preventDefault();
        openReviews();
      });
    });
    const homeBtn = box.querySelector("[data-reviews='home']");
    if (homeBtn) homeBtn.addEventListener("click", closeReviews);
  }

  function renderPraise() {
    if (!praiseBoard) return;
    praiseBoard.innerHTML = praiseBoardHtml();
    bindPraiseBoard(praiseBoard);
  }

  function renderPraiseFallback() {
    if (!praiseBoard) return;
    praiseBoard.innerHTML = praiseBoardHtml();
  }

  function praiseMark(visit) {
    if (!visit) return "";
    const current = state.selected && itemId(state.selected) === visit.id ? " current" : "";
    return (
      ' class="praise-sticker on' +
      current +
      '" data-show="' +
      escapeHtml(visit.id) +
      '" title="' +
      escapeHtml((visit.row && visit.row.title) || "방문") +
      '"'
    );
  }

  function praiseScoreText(count, allTime, page, pages) {
    if (!count) return allTime ? "전체 기간 방문이 모입니다" : "방문할 때마다 스티커가 붙습니다";
    const scope = allTime ? " · 전체" : "";
    if (pages > 1) return count + scope + " · " + (page + 1) + "/" + pages;
    if (count < PRAISE_COUNT) return count + " / " + PRAISE_COUNT + scope;
    if (count === PRAISE_COUNT) return PRAISE_COUNT + " / " + PRAISE_COUNT + scope;
    return count + "번 다녀왔어요" + scope;
  }

  function praiseSheetHtml(visits, page) {
    const rows = visits || [];
    const start = Math.max(0, (Number(page) || 0) * PRAISE_COUNT);
    let tiles = "";
    for (let i = 0; i < PRAISE_COUNT; i += 1) {
      const visit = rows[start + i];
      if (!visit) {
        tiles += '<span class="praise-sticker empty"></span>';
        continue;
      }
      const fill = PRAISE_FILLS[i % PRAISE_FILLS.length];
      tiles +=
        '<button type="button" style="background:' +
        fill +
        '"' +
        praiseMark(visit) +
        "></button>";
    }
    return '<div class="praise-sheet">' + tiles + "</div>";
  }

  function praiseBoardHtml() {
    const year = state.stickerYear || String(new Date().getFullYear());
    const allTime = year === "all";
    const visits = visitsForScope(year);
    const count = visits.length;
    const pages = Math.max(1, Math.ceil(count / PRAISE_COUNT) || 1);
    if (state.stickerPage > pages - 1) state.stickerPage = pages - 1;
    if (state.stickerPage < 0) state.stickerPage = 0;
    const page = state.stickerPage;
    const done = count >= PRAISE_COUNT && page === pages - 1;
    let years = '<button type="button" class="praise-year' + (allTime ? " on" : "") + '" data-sticker-year="all">전체</button>';
    yearChoices().forEach((y) => {
      years += '<button type="button" class="praise-year' + (y === year ? " on" : "") + '" data-sticker-year="' + y + '">' + y + "</button>";
    });
    const nav =
      pages > 1
        ? '<div class="praise-nav">' +
          '<button type="button" class="praise-arrow" data-sticker-page="-1"' +
          (page <= 0 ? " disabled" : "") +
          ">‹</button>" +
          '<span class="praise-page">' +
          (page + 1) +
          " / " +
          pages +
          "</span>" +
          '<button type="button" class="praise-arrow" data-sticker-page="1"' +
          (page >= pages - 1 ? " disabled" : "") +
          ">›</button>" +
          "</div>"
        : "";
    return (
      '<div class="praise-head"><h2 class="praise-title">Achievement</h2><div class="praise-years">' +
      years +
      "</div></div>" +
      '<p class="praise-total"><span class="praise-num">' +
      allVisits().length +
      "</span><span class="praise-total-label">다녀온 전시</span></p>" +
      '<p class="praise-score">' +
      praiseScoreText(count, allTime, page, pages) +
      "</p>" +
      '<div class="praise-art sheet' +
      (done ? " open" : "") +
      '">' +
      praiseSheetHtml(visits, page) +
      (done ? '<span class="praise-done">완성</span>' : "") +
      "</div>" +
      nav
    );
  }

  function bindPraiseBoard(root) {
    const box = root || praiseBoard;
    if (!box) return;
    box.querySelectorAll("[data-sticker-year]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.stickerYear = btn.getAttribute("data-sticker-year");
        state.stickerPage = 0;
        if (state.selected) renderArtwork();
        else renderPraise();
      });
    });
    box.querySelectorAll("[data-sticker-page]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.stickerPage += Number(btn.getAttribute("data-sticker-page") || 0);
        if (state.selected) renderArtwork();
        else renderPraise();
      });
    });
    box.querySelectorAll("[data-show]").forEach((el) => {
      el.addEventListener("click", () => {
        const show = showById(el.getAttribute("data-show") || "");
        if (show) openShow(show);
      });
    });
  }

  function sendToNotes(item) {
    const text = [item.title, item.at || "", "", item.body].filter((part, i) => i < 2 || part).join("\n");
    if (navigator.share) {
      navigator.share({ title: item.title, text }).catch(() => copyNote(text));
      return;
    }
    copyNote(text);
  }

  function copyNote(text) {
    const done = () => {
      window.alert("메모에 붙여넣을 글을 복사했습니다.");
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
      return;
    }
    fallbackCopy(text, done);
  }

  function fallbackCopy(text, done) {
    const box = document.createElement("textarea");
    box.value = text;
    document.body.appendChild(box);
    box.select();
    try {
      document.execCommand("copy");
      done();
    } catch (err) {
      window.alert(text);
    }
    box.remove();
  }

  function renderOwnCalendar() {
    const src = googleMonthSrc(state.year, state.month);
    if (src) {
      ownCal.innerHTML = `<iframe src="${src}" title="Ownex 달력" loading="lazy"></iframe>`;
    } else {
      ownCal.innerHTML = "<p class='quiet'>구글 Ownex 달력이 아직 연결되지 않았습니다. 구글달력연결.bat 을 실행해 주세요.</p>";
    }
  }

  function renderNames() {
    const initials = ["", "ㄱ", "ㄴ", "ㄷ", "ㄹ", "ㅁ", "ㅂ", "ㅅ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"];
    let rows = monthRows();
    if (state.initial) rows = rows.filter((row) => choseong(row.title) === state.initial);
    monthList.innerHTML = `
      <div class="month-head">
        <h2>${state.year === "all" ? "전체" : state.year} ${MONTHS[Number(state.month) - 1]}</h2>
        <button type="button" class="back" data-back="cal">월 다시 고르기</button>
      </div>
      <div class="chips">
        ${initials
          .map((ch) => `<button type="button" class="chip ${ch ? "" : "wide"} ${state.initial === ch ? "on" : ""}" data-initial="${ch}">${ch || "전체"}</button>`)
          .join("")}
      </div>
      <div class="names">
        ${
          rows.length
            ? rows
                .map((row, i) => {
                  const src = coverOf(row);
                  const art = src
                    ? `<img class="name-art" src="${escapeHtml(src)}" alt="">`
                    : `<span class="name-art"></span>`;
                  return `<button type="button" class="name ${src ? "has-art" : ""}" data-index="${i}" data-id="${escapeHtml(itemId(row))}" onclick="ownexOpenId(this.getAttribute('data-id'))">
              ${art}
              <span><strong>${escapeHtml(row.title)}</strong><small>${escapeHtml(row.venue || "")} · ${escapeHtml([row.start_date, row.end_date].filter(Boolean).join(" ~ "))}${endedTag(row)}</small></span>
            </button>`;
                })
                .join("")
            : `<p class="quiet">이 달에는 아직 기록이 없습니다.</p>`
        }
      </div>`;
    monthList.querySelector("[data-back]").addEventListener("click", () => {
      state.month = "";
      state.selected = null;
      monthEl.value = "";
      draw();
    });
    monthList.querySelectorAll("[data-initial]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.initial = btn.getAttribute("data-initial");
        renderNames();
      });
    });
    monthList.querySelectorAll(".name").forEach((btn) => {
      btn.addEventListener("click", (event) => {
        event.preventDefault();
        const row = showById(btn.getAttribute("data-id") || "") || rows[Number(btn.getAttribute("data-index"))];
        if (row) openShow(row);
      });
    });
  }

  function coverOf(row) {
    return row.poster || "";
  }

  function imagesOf(row) {
    return row.poster ? [row.poster] : [];
  }

  function searchUrl(kind, row) {
    const q = encodeURIComponent((row.title || "") + " " + (state.field === "exhibition" ? "전시" : "공연") + " " + (row.venue || ""));
    if (kind === "naver") return "https://search.naver.com/search.naver?query=" + q;
    if (kind === "google") return "https://www.google.com/search?q=" + q;
    return "https://www.youtube.com/results?search_query=" + encodeURIComponent((row.title || "") + " 작가 작품");
  }

  function reviewsForShow(showId, title) {
    const wantId = String(showId || "");
    const wantTitle = String(title || "").trim();
    const wantPair = wantId.split("|").slice(0, 2).join("|");
    return feels.filter((item) => {
      if (!item) return false;
      if (wantId && item.showId === wantId) return true;
      const haveId = String(item.showId || "");
      const havePair = haveId.split("|").slice(0, 2).join("|");
      if (wantPair && havePair && wantPair === havePair) return true;
      const have = String(item.title || "").trim();
      if (wantTitle && have === wantTitle) return true;
      if (wantTitle && have && (have.indexOf(wantTitle) >= 0 || wantTitle.indexOf(have) >= 0)) return true;
      if (looseTitle(have, wantTitle)) return true;
      return false;
    });
  }

  function addReview(title, body, show) {
    const item = {
      id: String(Date.now()),
      title,
      body,
      at: new Date().toISOString().slice(0, 10),
      showId: show ? itemId(show) : "",
      by: (familyMe && familyMe.name) || "",
    };
    feels.push(item);
    writeFeelStore(feels);
    state.reviewId = item.id;
    saveFeels();
    return item;
  }

  function renderArtwork() {
    const row = state.selected;
    if (!row) return;
    const id = itemId(row);
    const visited = isVisited(row);
    const imgs = imagesOf(row);
    const current = imgs[state.artIndex] || "";
    const poster = current
      ? `<img class="poster" src="${escapeHtml(current)}" alt="${escapeHtml(row.title || "")}">`
      : `<div class="poster typed"><p>${escapeHtml(row.title || "")}</p></div>`;
    const draft = (artwork.querySelector("#art-review-body") || {}).value || "";
    const mine = reviewsForShow(id, row.title || "");
    const shown = mine.slice(-FRONT_REVIEWS);
    const mineHtml = shown.length
      ? shown
          .map(
            (item) =>
              `<div class="art-review-item"><p class="art-review-date">${escapeHtml(item.at || "")}${item.by ? " · " + escapeHtml(item.by) : ""}</p><p>${escapeHtml(item.body)}</p></div>`
          )
          .join("")
      : '<p class="quiet">아직 이 작품에 남긴 감상평이 없습니다.</p>';
    const moreBtn =
      mine.length > FRONT_REVIEWS
        ? '<button type="button" class="review-all" data-reviews="all">전체 보기</button>'
        : "";
    artwork.innerHTML =
      '<div class="art-head"><button type="button" class="back" data-back="names">목록으로</button></div>' +
      '<div class="artwork">' +
      poster +
      '<div class="art-copy"><h3>' +
      escapeHtml(row.title || "") +
      "</h3><p class='meta'>" +
      escapeHtml(row.venue || "") +
      "<br>" +
      escapeHtml(row.venue_address || "") +
      "<br>" +
      escapeHtml([row.start_date, row.end_date].filter(Boolean).join(" ~ ")) +
      endedTag(row) +
      "</p><p class='meta'>" +
      escapeHtml(row.summary || "") +
      "</p><div class='links'>" +
      (row.reservation_url ? '<a href="' + escapeHtml(row.reservation_url) + '" target="_blank" rel="noopener">공식</a>' : "") +
      '<a href="' +
      searchUrl("naver", row) +
      '" target="_blank" rel="noopener">네이버</a>' +
      '<a href="' +
      searchUrl("google", row) +
      '" target="_blank" rel="noopener">구글</a>' +
      '<a href="' +
      searchUrl("youtube", row) +
      '" target="_blank" rel="noopener">유튜브</a>' +
      '<button type="button" class="mark' +
      (visited ? " on" : "") +
      '" data-act="visit" title="다녀온 전시면 눌러 주세요. 끝난 전시도 기록됩니다.">방문함</button></div>' +
      (imgs.length > 1
        ? '<div class="art-nav"><button type="button" class="nav-art" data-dir="-1">이전 장면</button><button type="button" class="nav-art" data-dir="1">다음 장면</button></div>'
        : "") +
      '<form class="art-review" id="art-review-form">' +
      "<h4>Review</h4>" +
      '<textarea id="art-review-body" name="body" placeholder="이 작품을 보고 느낀 점을 적어 주세요." required></textarea>' +
      '<button type="button" class="save" id="art-review-save">남기기</button>' +
      '<div class="art-review-list">' +
      mineHtml +
      moreBtn +
      "</div></form>" +
      "</div></div>";
    const reviewForm = artwork.querySelector("#art-review-form");
    const reviewBody = artwork.querySelector("#art-review-body");
    const reviewSave = artwork.querySelector("#art-review-save");
    if (reviewBody && draft) reviewBody.value = draft;
    const keepReview = function () {
      const text = String((reviewBody || {}).value || "").trim();
      if (!text) return;
      addReview(row.title || "감상", text, row);
      renderArtwork();
      paintGlance();
      if (feelings) renderFeelings(feelings, "preview");
    };
    if (reviewForm) {
      reviewForm.addEventListener("submit", (event) => {
        event.preventDefault();
        keepReview();
      });
    }
    if (reviewSave) reviewSave.addEventListener("click", keepReview);
    const stage = artwork.querySelector(".artwork");
    try {
      const hold = document.createElement("div");
      hold.className = "art-praise";
      hold.innerHTML = praiseBoardHtml();
      if (stage) stage.appendChild(hold);
      bindPraiseBoard(hold);
    } catch (err) {}
    const back = artwork.querySelector("[data-back]");
    if (back) {
      back.addEventListener("click", () => {
        state.selected = null;
        draw();
      });
    }
    artwork.querySelectorAll("[data-act]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (btn.getAttribute("data-act") === "visit") {
          const on = !isVisited(row);
          const at = new Date().toISOString().slice(0, 10);
          relatedNoteKeys(row).forEach((key) => {
            notes[key] = notes[key] || {};
            notes[key].visited = on;
            notes[key].at = at;
          });
          if (on) state.stickerYear = at.slice(0, 4);
        }
        saveNotes();
        renderArtwork();
        renderPraise();
      });
    });
    artwork.querySelectorAll("[data-dir]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const dir = Number(btn.getAttribute("data-dir"));
        state.artIndex = (state.artIndex + dir + imgs.length) % imgs.length;
        renderArtwork();
      });
    });
    const more = artwork.querySelector("[data-reviews='all']");
    if (more) more.addEventListener("click", openReviews);
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  window.ownexOpenReviews = openReviews;
  window.ownexMoreReviews = showMoreReviews;
  window.ownexHome = closeReviews;
  window.ownexOpenId = function (id) {
    const show = showById(id) || matchShow(id);
    if (show) openShow(show);
    return false;
  };
  window.ownexOpenByTitle = function (title) {
    const want = String(title || "").trim();
    const show =
      showById(want) ||
      (data.exhibitions || []).find((row) => row && String(row.title || "").trim() === want) ||
      matchShow(want);
    if (show) openShow(show);
  };

  try {
    seedCubistFeel();
  } catch (err) {}
  if (location.hash === "#reviews") state.space = "reviews";
  window.addEventListener("hashchange", () => {
    const want = location.hash === "#reviews";
    if (want && state.space !== "reviews") {
      state.space = "reviews";
      state.selected = null;
      draw();
    } else if (!want && state.space === "reviews") {
      state.space = "";
      draw();
    }
  });
  try {
    bindGlance();
    paintGuests(readCachedGuests());
    countSiteGuests();
    bindFamilyBar();
    draw();
    paintFamilyBar();
  } catch (err) {}
  probeFamily()
    .then(function () {
      return pullShared();
    })
    .then(function () {
      return pullState();
    })
    .then(function () {
      draw();
      paintFamilyBar();
      pushShared();
    });
  if (!isStaticHost()) {
    setInterval(function () {
      pullShared().then(function (changed) {
        if (!changed) return;
        paintGlance();
        if (reviewDraftOpen() || state.selected) return;
        draw();
      });
    }, 3000);
  }

  function bindFamilyBar() {
    const form = document.getElementById("family-form");
    const enterBtn = document.getElementById("family-enter");
    const out = document.getElementById("family-out");
    if (form) {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        enterFamily();
      });
    }
    if (enterBtn) enterBtn.addEventListener("click", enterFamily);
    if (out) {
      out.addEventListener("click", (event) => {
        event.preventDefault();
        if (window.ownexLeave) window.ownexLeave();
      });
    }
    document.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-approve]");
      if (!btn) return;
      api("/api/family/approve", { id: btn.getAttribute("data-approve") }).then(() => paintFamilyBar());
    });
  }

  window.ownexAfterEnter = function (user) {
    familyBackend = "local";
    try {
      if (user && user.id) switchNotesToUser(user);
    } catch (err) {}
    try {
      draw();
    } catch (err) {}
    paintFamilyBar();
  };

  window.ownexAfterLeave = function () {
    setFamilyToken("");
    try {
      switchNotesToUser(null);
    } catch (err) {}
    try {
      draw();
    } catch (err) {}
    paintFamilyBar();
  };

  function enterFamily() {
    if (window.ownexEnter) window.ownexEnter();
  }

  function greetName(user) {
    const raw = String((user && user.name) || "").trim();
    if (!raw) return "";
    return raw.indexOf("@") >= 0 ? raw.split("@")[0] : raw;
  }

  function paintFamilyBar() {
    const form = document.getElementById("family-form");
    const meBox = document.getElementById("family-me");
    const who = document.getElementById("family-who");
    const people = document.getElementById("family-people");
    const msg = document.getElementById("family-msg");
    const user = familyMe && familyMe.id ? familyMe : localMe();
    const inNow = Boolean(user && user.id);
    const bar = document.querySelector(".family-bar");
    if (bar) bar.classList.toggle("is-in", inNow);
    if (form) form.hidden = inNow;
    if (meBox) meBox.hidden = !inNow;
    if (who) who.textContent = inNow ? greetName(user) + "의 방문을 환영합니다." : "";
    if (msg) {
      msg.textContent = inNow && user.approved === false ? "관리자가 승인한 뒤에 Review를 같이 모읍니다." : "";
    }
    if (!people) return;
    people.innerHTML = "";
  }
})();
