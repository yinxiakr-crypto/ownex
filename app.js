(function () {
  const STORE = "ownex-notes-v1";
  const FEEL_STORE = "ownex-feelings-v1";
  const TOKEN_STORE = "ownex-family-token";
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

  applySeason();
  const notes = loadNotes();
  const feels = loadFeels();
  mergeSaved();
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
  };
  const FRONT_REVIEWS = 3;

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

  if (data.google && data.google.open_url) gcalIcon.href = data.google.open_url;

  fillYears();
  document.querySelectorAll(".field").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.disabled) return;
      state.field = btn.getAttribute("data-field");
      document.querySelectorAll(".field").forEach((el) => el.classList.toggle("on", el === btn));
      state.month = "";
      state.selected = null;
      monthEl.value = "";
      draw();
    });
  });
  yearEl.addEventListener("change", () => {
    state.year = yearEl.value;
    if (state.year && state.year !== "all") state.stickerYear = state.year;
    state.month = "";
    state.selected = null;
    state.space = "";
    monthEl.value = "";
    draw();
  });
  yearAll.addEventListener("click", () => {
    state.year = "all";
    yearEl.value = "all";
    state.month = "";
    state.selected = null;
    state.space = "";
    monthEl.value = "";
    draw();
  });
  monthEl.addEventListener("change", () => {
    state.month = monthEl.value;
    state.selected = null;
    state.initial = "";
    state.space = "";
    draw();
  });

  function applySeason() {
    const month = new Date().getMonth() + 1;
    const season = month === 12 || month <= 2 ? "winter" : month <= 5 ? "spring" : month <= 8 ? "summer" : "fall";
    document.body.dataset.season = season;
    const colors = { winter: "#1b2a33", spring: "#24382e", summer: "#2a2e12", fall: "#351e28" };
    const theme = document.querySelector('meta[name="theme-color"]');
    if (theme) theme.setAttribute("content", colors[season]);
  }

  function loadNotes() {
    try {
      return JSON.parse(localStorage.getItem(STORE) || "{}");
    } catch (err) {
      return {};
    }
  }

  function saveNotes() {
    localStorage.setItem(STORE, JSON.stringify(notes));
    pushState();
  }

  function loadFeels() {
    try {
      const raw = JSON.parse(localStorage.getItem(FEEL_STORE) || "[]");
      return Array.isArray(raw) ? raw : [];
    } catch (err) {
      return [];
    }
  }

  function mergeSaved() {
    const seed = data.saved;
    if (!seed || typeof seed !== "object") return;
    const seedNotes = seed.notes && typeof seed.notes === "object" ? seed.notes : {};
    Object.keys(seedNotes).forEach((key) => {
      const a = notes[key] || {};
      const b = seedNotes[key] || {};
      notes[key] = Object.assign({}, b, a, { visited: Boolean(a.visited) || Boolean(b.visited) });
    });
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
      localStorage.setItem(STORE, JSON.stringify(notes));
      localStorage.setItem(FEEL_STORE, JSON.stringify(feels));
    } catch (err) {}
  }

  function saveFeels() {
    localStorage.setItem(FEEL_STORE, JSON.stringify(feels));
    pushState();
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

  function api(path, body) {
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

  function applyState(payload) {
    if (!payload || typeof payload !== "object") return;
    const nextNotes = payload.notes && typeof payload.notes === "object" ? payload.notes : {};
    Object.keys(notes).forEach((key) => delete notes[key]);
    Object.keys(nextNotes).forEach((key) => {
      notes[key] = nextNotes[key];
    });
    localStorage.setItem(STORE, JSON.stringify(notes));
    feels.splice(0, feels.length);
    (Array.isArray(payload.feels) ? payload.feels : []).forEach((item) => feels.push(item));
    localStorage.setItem(FEEL_STORE, JSON.stringify(feels));
  }

  function pushState() {
    api("/api/family/state", { notes: notes, feels: feels }).then((payload) => {
      if (payload && payload.notes) applyState(payload);
    }).catch(() => {});
  }

  function pullState() {
    return api("/api/family/state").then((payload) => {
      const remote = payload && !payload.error ? payload : { notes: {}, feels: [] };
      const mergedNotes = Object.assign({}, remote.notes || {}, notes);
      Object.keys(Object.assign({}, remote.notes || {}, notes)).forEach((key) => {
        const a = notes[key] || {};
        const b = (remote.notes || {})[key] || {};
        mergedNotes[key] = Object.assign({}, b, a, { visited: Boolean(a.visited) || Boolean(b.visited) });
      });
      const bag = [];
      const seen = {};
      []
        .concat(remote.feels || [], feels)
        .forEach((item) => {
          if (!item) return;
          const key = [item.id || "", item.title || "", item.body || "", item.at || ""].join("|");
          const loose = [item.title || "", item.body || "", item.at || ""].join("|");
          if (seen[key] || seen[loose]) return;
          seen[key] = true;
          seen[loose] = true;
          bag.push(item);
        });
      applyState({ notes: mergedNotes, feels: bag });
      return api("/api/family/state", { notes: notes, feels: feels }).then((saved) => {
        if (saved && saved.notes && !saved.error) applyState(saved);
      });
    }).catch(() => {});
  }

  const PRAISE_STAMPS = ["잘했어요", "참 잘했어요", "우수해요", "멋져요", "훌륭해요", "최고예요", "잘 보았어요", "열심히 보았어요", "대단해요", "참 훌륭해요"];
  const PRAISE_COUNT = 30;
  const PRAISE_FILLS = ["#f6e4dc", "#f3c4b5", "#fde8df", "#ead4c8", "#e8c8c4", "#f7ece4", "#dcc4bc", "#c9d4c0"];

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
    return Object.keys(bag)
      .filter((id) => bag[id] && (bag[id].visited === true || bag[id].visited === "true"))
      .sort((a, b) => String(bag[a].at || "").localeCompare(String(bag[b].at || "")));
  }

  function visitsForYear(year) {
    const y = String(year || new Date().getFullYear());
    return allVisits()
      .filter((id) => visitYearOf(id, notes[id]) === y)
      .map((id) => ({ id, note: notes[id], row: showById(id) }));
  }

  function praiseFor(count) {
    if (count >= 30) return { word: "대단해요", line: "올해 전시를 깊이 따라가고 있습니다." };
    if (count >= 20) return { word: "최고예요", line: "보는 눈이 꽤 단단해졌습니다." };
    if (count >= 10) return { word: "우수해요", line: "열 번을 채웠습니다. 올해의 그림이 완성되었습니다." };
    if (count >= 5) return { word: "참 잘했어요", line: "작품 앞에 머무는 시간이 늘고 있습니다." };
    if (count >= 1) return { word: "잘했어요", line: "전시장에 발을 들인 해입니다." };
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
      .replace(/[〈〉《》\(\)]/g, " ")
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

  function openShow(row) {
    if (!row) return;
    const year = (row.start_date || "").slice(0, 4);
    const month = (row.start_date || "").slice(5, 7);
    state.year = year || state.year || "all";
    state.month = month || state.month;
    state.selected = row;
    state.space = "";
    yearEl.value = state.year;
    if (state.month) monthEl.value = state.month;
    draw();
    artwork.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function events() {
    const rows = (data.exhibitions || []).map((row) => Object.assign({ kind: row.kind || "exhibition" }, row));
    return rows.filter((row) => row.kind === state.field);
  }

  function itemId(row) {
    if (!row) return "";
    return [row.title || "", row.venue || "", row.start_date || "", row.end_date || ""].join("|");
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

  function draw() {
    const reviewOnly = state.space === "reviews";
    const browsing = Boolean(state.year && state.month);
    const showFeel = !reviewOnly && !state.selected && (state.space === "feel" || !browsing);
    document.body.classList.toggle("reviews", reviewOnly);
    document.body.classList.toggle("open", !reviewOnly && browsing && state.space !== "feel");
    monthWrap.hidden = reviewOnly || !state.year;
    yearAll.classList.toggle("on", state.year === "all");
    const showMonth = !reviewOnly && browsing && !state.selected && state.space !== "feel";
    frontRow.hidden = !showFeel;
    if (frontRow) {
      frontRow.style.display = showFeel ? "grid" : "none";
      if (showFeel) {
        frontRow.style.gridTemplateColumns = "minmax(18rem, 40rem) minmax(16rem, 1fr)";
        frontRow.style.gap = "1.5rem 2rem";
        frontRow.style.alignItems = "start";
      }
    }
    if (reviewPage) reviewPage.hidden = !reviewOnly;
    ownCal.hidden = !showMonth;
    monthList.hidden = !showMonth;
    artwork.hidden = reviewOnly || !state.selected;
    if (reviewOnly) {
      renderFeelings(reviewPage, "full");
      return;
    }
    if (showFeel) {
      renderFeelings(feelings, "preview");
      try {
        renderPraise();
      } catch (err) {
        renderPraiseFallback();
      }
    }
    if (showMonth) {
      renderOwnCalendar();
      renderNames();
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

  function openReviews() {
    state.space = "reviews";
    state.selected = null;
    if (location.hash !== "#reviews") location.hash = "reviews";
    draw();
    if (reviewPage) reviewPage.scrollIntoView({ behavior: "smooth", block: "start" });
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
    const start = preview ? Math.max(0, feels.length - FRONT_REVIEWS) : 0;
    const items = feels.slice(start);
    const rows = items.map((item, offset) => {
      const index = start + offset;
      const no = index + 1;
      const open = state.reviewId === item.id;
      const snippet = item.body.length > 28 ? item.body.slice(0, 28) + "…" : item.body;
      const show = (data.exhibitions || []).find((row) => itemId(row) === item.showId) || matchShow(item.title);
      const last = preview && offset === items.length - 1;
      return `<div class="review-item ${open ? "on" : ""} ${last ? "is-last" : ""}">
        <div class="review-last-row">
        <button type="button" class="review-line" data-id="${escapeHtml(item.id)}">
          <span class="review-no">${no}</span>
          <span class="review-date">${escapeHtml(item.at || "")}</span>
          <span class="review-name">${escapeHtml(item.title)}</span>
          <span class="review-snip">${escapeHtml(open ? "접기" : snippet)}</span>
        </button>
        ${last ? '<button type="button" class="review-all-btn" data-reviews="all">전체 보기</button>' : ""}
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
    const empty = preview
      ? `<p class="quiet">아직 남긴 감상평이 없습니다.</p><button type="button" class="review-all-btn" data-reviews="all">전체 보기</button>`
      : '<p class="quiet">아직 남긴 감상평이 없습니다.</p>';
    const head = preview
      ? `<div class="feel-head"><h2>Review</h2></div>`
      : `<div class="feel-head"><h2>Review</h2><button type="button" class="back" data-reviews="home">앞페이지</button></div>`;
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
      </div>`;
    const form = box.querySelector("#feel-form");
    if (form) {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const title = box.querySelector("#feel-title").value.trim();
        const body = box.querySelector("#feel-body").value.trim();
        if (!title || !body) return;
        const show = matchShow(title);
        addReview(title, body, show);
        if (show) {
          const id = itemId(show);
          notes[id] = notes[id] || {};
          notes[id].visited = true;
          notes[id].at = new Date().toISOString().slice(0, 10);
          state.stickerYear = notes[id].at.slice(0, 4);
          saveNotes();
        }
        saveFeels();
        renderFeelings(box, mode);
      });
    }
    box.querySelectorAll(".review-line").forEach((btn) => {
      btn.addEventListener("click", () => {
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
    const allBtn = box.querySelector("[data-reviews='all']");
    if (allBtn) allBtn.addEventListener("click", openReviews);
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
    return (
      ' data-show="' +
      escapeHtml(visit.id) +
      '" title="' +
      escapeHtml((visit.row && visit.row.title) || "방문") +
      '"'
    );
  }

  function praiseScoreText(count) {
    if (!count) return "방문할 때마다 스티커가 붙습니다";
    if (count < PRAISE_COUNT) return count + " / " + PRAISE_COUNT;
    if (count === PRAISE_COUNT) return PRAISE_COUNT + " / " + PRAISE_COUNT + " · 완성";
    return "완성 · " + count + "번 다녀왔어요";
  }

  function praiseSheetHtml(count, visits) {
    const n = Math.max(0, Math.min(Number(count) || 0, PRAISE_COUNT));
    const rows = visits || [];
    let tiles = "";
    for (let i = 0; i < PRAISE_COUNT; i += 1) {
      if (i >= n) {
        tiles += '<span class="praise-sticker empty"></span>';
        continue;
      }
      const fill = PRAISE_FILLS[i % PRAISE_FILLS.length];
      tiles +=
        '<button type="button" class="praise-sticker on" style="background:' +
        fill +
        '"' +
        praiseMark(rows[i]) +
        "></button>";
    }
    return '<div class="praise-sheet">' + tiles + "</div>";
  }

  function praiseBoardHtml() {
    const year = state.stickerYear || String(new Date().getFullYear());
    const visits = visitsForYear(year);
    const count = visits.length;
    const done = count >= PRAISE_COUNT;
    let years = "";
    yearChoices().forEach((y) => {
      years += '<button type="button" class="praise-year' + (y === year ? " on" : "") + '" data-sticker-year="' + y + '">' + y + "</button>";
    });
    return (
      '<div class="praise-head"><h2 class="praise-title">Achievement</h2><div class="praise-years">' +
      years +
      "</div></div>" +
      '<p class="praise-score">' +
      praiseScoreText(count) +
      "</p>" +
      '<div class="praise-art sheet' +
      (done ? " open" : "") +
      '">' +
      praiseSheetHtml(count, visits) +
      (done ? '<span class="praise-done">완성</span>' : "") +
      "</div>"
    );
  }

  function bindPraiseBoard(root) {
    const box = root || praiseBoard;
    if (!box) return;
    box.querySelectorAll("[data-sticker-year]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.stickerYear = btn.getAttribute("data-sticker-year");
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
                .map((row) => {
                  const src = coverOf(row);
                  const art = src
                    ? `<img class="name-art" src="${escapeHtml(src)}" alt="">`
                    : `<span class="name-art"></span>`;
                  return `<button type="button" class="name ${src ? "has-art" : ""}" data-id="${encodeURIComponent(itemId(row))}">
              ${art}
              <span><strong>${escapeHtml(row.title)}</strong><small>${escapeHtml(row.venue || "")} · ${escapeHtml([row.start_date, row.end_date].filter(Boolean).join(" ~ "))}</small></span>
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
      btn.addEventListener("click", () => {
        let id = btn.getAttribute("data-id") || "";
        try {
          id = decodeURIComponent(id);
        } catch (err) {}
        state.selected =
          events().find((row) => itemId(row) === id) ||
          events().find((row) => encodeURIComponent(itemId(row)) === btn.getAttribute("data-id")) ||
          null;
        state.artIndex = 0;
        draw();
        if (state.selected && artwork && !artwork.hidden) {
          artwork.scrollIntoView({ behavior: "smooth", block: "start" });
        }
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
    return feels.filter((item) => item.showId === showId || item.title === title);
  }

  function addReview(title, body, show) {
    const item = {
      id: String(Date.now()),
      title,
      body,
      at: new Date().toISOString().slice(0, 10),
      showId: show ? itemId(show) : "",
    };
    feels.push(item);
    state.reviewId = item.id;
    if (show) {
      const showId = itemId(show);
      notes[showId] = notes[showId] || {};
      notes[showId].visited = true;
      notes[showId].at = item.at;
      state.stickerYear = item.at.slice(0, 4);
      localStorage.setItem(STORE, JSON.stringify(notes));
    }
    saveFeels();
    return item;
  }

  function renderArtwork() {
    const row = state.selected;
    if (!row) return;
    const id = itemId(row);
    const saved = notes[id] || {};
    const imgs = imagesOf(row);
    const current = imgs[state.artIndex] || "";
    const poster = current
      ? `<img class="poster" src="${escapeHtml(current)}" alt="${escapeHtml(row.title || "")}">`
      : `<div class="poster typed"><p>${escapeHtml(row.title || "")}</p></div>`;
    const mine = reviewsForShow(id, row.title || "");
    const shown = mine.slice(-FRONT_REVIEWS);
    const mineHtml = shown.length
      ? shown
          .map(
            (item) =>
              `<div class="art-review-item"><p class="art-review-date">${escapeHtml(item.at || "")}</p><p>${escapeHtml(item.body)}</p></div>`
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
      (saved.visited ? " on" : "") +
      '" data-act="visit">방문함</button></div>' +
      (imgs.length > 1
        ? '<div class="art-nav"><button type="button" class="nav-art" data-dir="-1">이전 장면</button><button type="button" class="nav-art" data-dir="1">다음 장면</button></div>'
        : "") +
      '<form class="art-review" id="art-review-form">' +
      "<h4>Review</h4>" +
      '<textarea id="art-review-body" name="body" placeholder="이 작품을 보고 느낀 점을 적어 주세요." required></textarea>' +
      '<button type="submit" class="save">남기기</button>' +
      '<div class="art-review-list">' +
      mineHtml +
      moreBtn +
      "</div></form>" +
      "</div></div>";
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
        notes[id] = notes[id] || {};
        if (btn.getAttribute("data-act") === "visit") notes[id].visited = !notes[id].visited;
        notes[id].at = new Date().toISOString().slice(0, 10);
        if (notes[id].visited) state.stickerYear = notes[id].at.slice(0, 4);
        saveNotes();
        renderArtwork();
      });
    });
    artwork.querySelectorAll("[data-dir]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const dir = Number(btn.getAttribute("data-dir"));
        state.artIndex = (state.artIndex + dir + imgs.length) % imgs.length;
        renderArtwork();
      });
    });
    const reviewForm = artwork.querySelector("#art-review-form");
    if (reviewForm) {
      reviewForm.addEventListener("submit", (event) => {
        event.preventDefault();
        const body = (artwork.querySelector("#art-review-body") || {}).value || "";
        const text = String(body).trim();
        if (!text) return;
        addReview(row.title || "감상", text, row);
        renderArtwork();
        if (feelings) renderFeelings(feelings, "preview");
      });
    }
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

  seedCubistFeel();
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
  bindFamilyBar();
  pullState().then(() => {
    draw();
    paintFamilyBar();
  });

  function bindFamilyBar() {
    const form = document.getElementById("family-form");
    const out = document.getElementById("family-out");
    const signupBtn = document.getElementById("family-signup");
    if (form) {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        enterFamily("/api/family/login");
      });
    }
    if (signupBtn) {
      signupBtn.addEventListener("click", () => enterFamily("/api/family/signup"));
    }
    if (out) {
      out.addEventListener("click", () => {
        api("/api/family/logout", {}).finally(() => {
          setFamilyToken("");
          paintFamilyBar();
        });
      });
    }
    document.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-approve]");
      if (!btn) return;
      api("/api/family/approve", { id: btn.getAttribute("data-approve") }).then(() => paintFamilyBar());
    });
  }

  function enterFamily(path) {
    const name = (document.getElementById("family-name") || {}).value || "";
    const pin = (document.getElementById("family-pin") || {}).value || "";
    const msg = document.getElementById("family-msg");
    api(path, { name: String(name).trim(), pin: String(pin) }).then((res) => {
      if (res.error) {
        if (msg) msg.textContent = res.error;
        return;
      }
      if (res.id) setFamilyToken(familyToken());
      pullState().then(() => {
        draw();
        paintFamilyBar();
      });
    });
  }

  function paintFamilyBar() {
    const form = document.getElementById("family-form");
    const me = document.getElementById("family-me");
    const who = document.getElementById("family-who");
    const people = document.getElementById("family-people");
    const msg = document.getElementById("family-msg");
    api("/api/family/me").then((user) => {
      const inNow = Boolean(user && user.id);
      if (form) form.hidden = inNow;
      if (me) me.hidden = !inNow;
      if (who) who.textContent = inNow ? user.name + (user.owner ? " · 관리" : "") : "";
      if (msg) msg.textContent = "";
      if (!people) return;
      people.innerHTML = "";
      if (!(user && user.owner)) return;
      api("/api/family/people").then((res) => {
        (res.people || []).forEach((person) => {
          if (person.owner) return;
          const line = document.createElement("p");
          line.className = "family-person";
          line.textContent = person.name + (person.approved ? " · 승인됨" : " · 기다림 ");
          if (!person.approved) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "save";
            btn.setAttribute("data-approve", person.id);
            btn.textContent = "승인";
            line.appendChild(btn);
          }
          people.appendChild(line);
        });
      });
    });
  }
})();
