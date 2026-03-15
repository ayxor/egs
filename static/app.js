const demoVideos = [
  {
    id: "demo-vhdl-1",
    title: "Introduction to VHDL for Digital Systems",
    professor: "Professor Silva",
    subject: "LSD",
    course: "MIECT",
    description: "Entity/architecture basics, signals, and a first simulation workflow.",
    tags: ["recent", "watermarked", "programming"],
    duration: "42 min",
    views: "214 students",
    accent: "linear-gradient(135deg, #d6603b, #ebb18f)",
  },
  {
    id: "demo-net-1",
    title: "Campus Routing Fundamentals",
    professor: "Professor Almeida",
    subject: "Networks",
    course: "LEI",
    description: "How packet forwarding works from classrooms to core routers.",
    tags: ["recent"],
    duration: "31 min",
    views: "177 students",
    accent: "linear-gradient(135deg, #2a7b77, #7bc6be)",
  },
  {
    id: "demo-db-1",
    title: "Designing Video Metadata Schemas",
    professor: "Professor Costa",
    subject: "Databases",
    course: "LEI",
    description: "Modeling tags, ownership, institution visibility, and search indexes.",
    tags: ["programming"],
    duration: "28 min",
    views: "129 students",
    accent: "linear-gradient(135deg, #654237, #e5af88)",
  },
  {
    id: "demo-rtos-1",
    title: "Real-Time Scheduling in Embedded Systems",
    professor: "Professor Rocha",
    subject: "Embedded",
    course: "MIEEC",
    description: "Deadlines, jitter, and practical scheduling strategies for labs.",
    tags: ["watermarked"],
    duration: "55 min",
    views: "95 students",
    accent: "linear-gradient(135deg, #4f4a82, #8ea0f4)",
  },
];

const state = {
  token: sessionStorage.getItem("ua_access_token") || "",
  refreshToken: sessionStorage.getItem("ua_refresh_token") || "",
  profile: null,
  videos: [...demoVideos],
  query: "",
  filter: "all",
};

const page = (window.UASTREAM_CONFIG && window.UASTREAM_CONFIG.page) || "home";
const selectedVideoId = (window.UASTREAM_CONFIG && window.UASTREAM_CONFIG.selectedVideoId) || "";

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function notify(message, tone = "info") {
  const stack = document.getElementById("toast-stack");
  if (!stack) {
    return;
  }
  const item = document.createElement("article");
  item.className = `toast ${tone}`;
  item.textContent = message;
  stack.prepend(item);
  window.setTimeout(() => item.remove(), 4600);
}

function setSession(access, refresh) {
  state.token = access || "";
  state.refreshToken = refresh || "";
  if (state.token) {
    sessionStorage.setItem("ua_access_token", state.token);
  } else {
    sessionStorage.removeItem("ua_access_token");
  }
  if (state.refreshToken) {
    sessionStorage.setItem("ua_refresh_token", state.refreshToken);
  } else {
    sessionStorage.removeItem("ua_refresh_token");
  }
  updateHeaderSession();
}

function updateHeaderSession() {
  const chip = document.getElementById("session-chip");
  const authLink = document.getElementById("auth-link");
  const uploadLink = document.getElementById("nav-upload");
  if (!chip || !authLink) {
    return;
  }
  if (state.profile) {
    chip.textContent = `${state.profile.name} · ${state.profile.role}`;
    if (uploadLink) {
      uploadLink.classList.toggle("hidden", state.profile.role !== "professor");
    }
    authLink.textContent = "Sign Out";
    authLink.href = "#";
    authLink.onclick = (event) => {
      event.preventDefault();
      const idToken = sessionStorage.getItem("ua_id_token") || "";
      sessionStorage.removeItem("ua_id_token");
      state.profile = null;
      setSession("", "");
      window.location.href = `/auth/logout?id_token_hint=${encodeURIComponent(idToken)}`;
    };
  } else if (state.token) {
    chip.textContent = "Authenticated";
    if (uploadLink) {
      uploadLink.classList.add("hidden");
    }
    authLink.textContent = "Sign Out";
    authLink.href = "#";
    authLink.onclick = (event) => {
      event.preventDefault();
      const idToken = sessionStorage.getItem("ua_id_token") || "";
      sessionStorage.removeItem("ua_id_token");
      state.profile = null;
      setSession("", "");
      window.location.href = `/auth/logout?id_token_hint=${encodeURIComponent(idToken)}`;
    };
  } else {
    chip.textContent = "Guest";
    if (uploadLink) {
      uploadLink.classList.add("hidden");
    }
    authLink.textContent = "Sign In";
    authLink.href = "/auth/login";
    authLink.onclick = null;
  }
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!response.ok) {
    const message = data && typeof data === "object" && data.error ? data.error : response.statusText;
    throw new Error(message || "Request failed");
  }
  return data;
}

async function loadProfile() {
  if (!state.token) {
    state.profile = null;
    updateHeaderSession();
    return;
  }
  try {
    state.profile = await requestJson("/users/me", {
      headers: { Authorization: `Bearer ${state.token}` },
    });
    updateHeaderSession();
  } catch {
    state.profile = null;
    updateHeaderSession();
    notify("Could not load user profile yet. Retaining session.", "warn");
  }
}

function mapApiVideos(results = []) {
  return results.map((video, idx) => ({
    id: video.video_id,
    title: video.title,
    professor: "Institution Lecturer",
    subject: video.subject || "Subject",
    course: video.course || "Course",
    description: video.description || "No description provided.",
    tags: [...(video.tags || []), "recent"],
    duration: "Lecture",
    views: "Scoped access",
    accent: idx % 2
      ? "linear-gradient(135deg, #2a7b77, #7bc6be)"
      : "linear-gradient(135deg, #d6603b, #ebb18f)",
  }));
}

function filteredVideos() {
  return state.videos.filter((video) => {
    const haystack = [video.title, video.description, video.subject, video.course, ...(video.tags || [])]
      .join(" ")
      .toLowerCase();
    const queryOk = !state.query || haystack.includes(state.query.toLowerCase());
    const filterOk = state.filter === "all" || (video.tags || []).includes(state.filter);
    return queryOk && filterOk;
  });
}

async function loadVideos() {
  if (!state.token) {
    state.videos = [...demoVideos];
    return;
  }
  const qs = new URLSearchParams();
  if (state.query) {
    qs.set("q", state.query);
  }
  try {
    const data = await requestJson(`/videos?${qs.toString()}`, {
      headers: { Authorization: `Bearer ${state.token}` },
    });
    const mapped = mapApiVideos(data.results || []);
    state.videos = mapped.length ? mapped : [...demoVideos];
  } catch {
    state.videos = [...demoVideos];
    notify("Live catalog unavailable. Showing demo feed.", "warn");
  }
}

function renderVideoCards(targetId) {
  const host = document.getElementById(targetId);
  if (!host) {
    return;
  }
  const videos = filteredVideos();
  host.innerHTML = videos
    .map((video) => `
      <article class="video-card card">
        <a class="video-thumb" href="/watch/${encodeURIComponent(video.id)}" style="background: ${video.accent};">
          <span class="badge">${escapeHtml(video.subject)}</span>
          <span class="duration">${escapeHtml(video.duration)}</span>
        </a>
        <div class="video-body">
          <h3><a href="/watch/${encodeURIComponent(video.id)}">${escapeHtml(video.title)}</a></h3>
          <p>${escapeHtml(video.description)}</p>
          <div class="video-meta">
            <span>${escapeHtml(video.professor)}</span>
            <span>${escapeHtml(video.course)}</span>
            <span>${escapeHtml(video.views)}</span>
          </div>
        </div>
      </article>
    `)
    .join("");

  if (!videos.length) {
    host.innerHTML = '<article class="card empty">No videos matched your search.</article>';
  }
}

function setupSearch() {
  const form = document.getElementById("search-form");
  const input = document.getElementById("search-input");
  if (!form || !input) {
    return;
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    state.query = input.value.trim();
    await loadVideos();
    renderVideoCards("video-grid");
  });
}

function setupFilters() {
  const bar = document.getElementById("filter-bar");
  if (!bar) {
    return;
  }
  bar.addEventListener("click", async (event) => {
    const chip = event.target.closest("[data-filter]");
    if (!chip) {
      return;
    }
    state.filter = chip.dataset.filter;
    bar.querySelectorAll("[data-filter]").forEach((node) => node.classList.toggle("active", node === chip));
    await loadVideos();
    renderVideoCards("video-grid");
  });
}

async function setupWatchPage() {
  await loadVideos();
  const pool = filteredVideos();
  const current = pool.find((v) => v.id === selectedVideoId) || pool[0] || demoVideos[0];

  const frame = document.getElementById("player-frame");
  const title = document.getElementById("watch-title");
  const meta = document.getElementById("watch-meta");
  const title2 = document.getElementById("watch-title-secondary");
  const description = document.getElementById("watch-description");
  if (frame && title && meta && title2 && description && current) {
    frame.style.background = current.accent;
    title.textContent = current.title;
    meta.textContent = `${current.professor} · ${current.subject} · ${current.course}`;
    title2.textContent = current.title;
    description.textContent = current.description;
  }

  const recHost = document.getElementById("recommendations");
  if (recHost) {
    recHost.innerHTML = pool
      .filter((v) => v.id !== current.id)
      .slice(0, 8)
      .map((video) => `
        <a class="recommend-item" href="/watch/${encodeURIComponent(video.id)}">
          <span class="rec-thumb" style="background:${video.accent};"></span>
          <span>
            <strong>${escapeHtml(video.title)}</strong>
            <small>${escapeHtml(video.professor)} · ${escapeHtml(video.course)}</small>
          </span>
        </a>
      `)
      .join("");
  }
}

function setupAuthTabs() {
  document.querySelectorAll("[data-auth-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.authTab;
      document.querySelectorAll("[data-auth-tab]").forEach((node) => node.classList.toggle("active", node === tab));
      document.querySelectorAll("[data-auth-panel]").forEach((panel) => panel.classList.toggle("hidden", panel.dataset.authPanel !== target));
    });
  });
}

function setupAuthForms() {
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const status = document.getElementById("auth-status");

  if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const body = Object.fromEntries(new FormData(loginForm).entries());
      try {
        const data = await requestJson("/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        setSession(data.access_token, data.refresh_token);
        await loadProfile();
        notify("Login successful.", "success");
        if (status) {
          status.textContent = "Signed in successfully. Redirecting to library...";
        }
        window.setTimeout(() => {
          window.location.href = "/library";
        }, 700);
      } catch (error) {
        if (status) {
          status.textContent = error.message;
        }
        notify(`Login failed: ${error.message}`, "error");
      }
    });
  }

  if (registerForm) {
    registerForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const body = Object.fromEntries(new FormData(registerForm).entries());
      try {
        await requestJson("/users", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (status) {
          status.textContent = "Account created. You can now log in.";
        }
        notify("Account created successfully.", "success");
      } catch (error) {
        if (status) {
          status.textContent = error.message;
        }
        notify(`Registration failed: ${error.message}`, "error");
      }
    });
  }
}

function updateUploadGate() {
  const gate = document.getElementById("upload-gate");
  const form = document.getElementById("upload-form");
  const submit = document.getElementById("upload-submit");
  if (!gate || !form || !submit) {
    return;
  }

  if (!state.token || !state.profile) {
    gate.className = "gate-message warn";
    gate.textContent = "Sign in first to unlock upload features.";
    form.querySelectorAll("input, textarea, select, button").forEach((el) => {
      el.disabled = true;
    });
    return;
  }

  if (state.profile.role !== "professor") {
    gate.className = "gate-message error";
    gate.textContent = "Only professor accounts can upload videos.";
    form.querySelectorAll("input, textarea, select, button").forEach((el) => {
      el.disabled = true;
    });
    return;
  }

  gate.className = "gate-message success";
  gate.textContent = `Upload unlocked for ${state.profile.name} (${state.profile.role}).`;
  form.querySelectorAll("input, textarea, select, button").forEach((el) => {
    el.disabled = false;
  });
}

function parseSseEvents(text) {
  const events = text.split("\n\n").filter(Boolean);
  const parsed = [];
  for (const event of events) {
    const line = event.split("\n").find((v) => v.startsWith("data:"));
    if (!line) {
      continue;
    }
    try {
      parsed.push(JSON.parse(line.slice(5).trim()));
    } catch {
      continue;
    }
  }
  return parsed;
}

function setupUploadForm() {
  const form = document.getElementById("upload-form");
  if (!form) {
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.profile || state.profile.role !== "professor") {
      notify("Only professors can upload.", "error");
      return;
    }

    const formData = new FormData(form);
    const mode = formData.get("upload_mode");
    formData.delete("upload_mode");

    const tags = String(formData.get("tags") || "")
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
    formData.delete("tags");
    tags.forEach((tag) => formData.append("tags", tag));

    if (mode === "process") {
      formData.append("operations", JSON.stringify([
        {
          type: "watermark",
          params: { text: "UAStream", position: "bottom-right", opacity: 0.85 },
        },
      ]));
    }

    const endpoint = mode === "process" ? "/videos/process" : "/videos";

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { Authorization: `Bearer ${state.token}` },
        body: formData,
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(body || "Upload failed");
      }

      if (mode === "process") {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let complete = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }
          complete += decoder.decode(value, { stream: true });
        }
        const events = parseSseEvents(complete);
        const done = events.find((e) => e.status === "done");
        if (done) {
          notify(`Lecture processed. Video id: ${done.video_id || done.job_id}`, "success");
        } else {
          notify("Processing started. Check notifications later.", "info");
        }
      } else {
        const payload = await response.json();
        notify(`Video uploaded: ${payload.video_id}`, "success");
      }

      form.reset();
    } catch (error) {
      notify(`Upload failed: ${error.message}`, "error");
    }
  });
}

async function bootHomeOrLibrary() {
  await loadVideos();
  renderVideoCards("video-grid");
  setupSearch();
  setupFilters();
}

async function bootUpload() {
  await loadProfile();
  updateUploadGate();
  setupUploadForm();
}

async function boot() {
  updateHeaderSession();
  await loadProfile();
  updateHeaderSession();

  if (page === "home" || page === "library") {
    await bootHomeOrLibrary();
  } else if (page === "watch") {
    await setupWatchPage();
  } else if (page === "auth") {
    setupAuthTabs();
    setupAuthForms();
  } else if (page === "upload") {
    await bootUpload();
  }
}

boot();
