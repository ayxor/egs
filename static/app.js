const demoVideos = [];

const state = {
  token: sessionStorage.getItem("ua_access_token") || "",
  refreshToken: sessionStorage.getItem("ua_refresh_token") || "",
  profile: null,
  videos: [],
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
    state.videos = [];
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
    state.videos = mapped.length ? mapped : [];
  } catch {
    state.videos = [];
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
  
  const frame = document.getElementById("player-frame");
  const title = document.getElementById("watch-title");
  const meta = document.getElementById("watch-meta");
  const title2 = document.getElementById("watch-title-secondary");
  const description = document.getElementById("watch-description");
  const videoEl = document.getElementById("watch-video");
  const overlay = document.getElementById("player-overlay");

  const activeId = selectedVideoId || (pool[0] && pool[0].id);

  if (activeId && state.token) {
    try {
      const videoData = await requestJson(`/videos/${encodeURIComponent(activeId)}`, {
        headers: { Authorization: `Bearer ${state.token}` },
      });
      
      console.log("Fetched Video Data:", videoData);

      if (title) title.textContent = videoData.title || "Unknown Title";
      if (title2) title2.textContent = videoData.title || "Unknown Title";
      if (description) description.textContent = videoData.description || "No description.";
      if (meta) meta.textContent = `${videoData.uploader_id || 'Professor'} · ${videoData.subject || 'Subject'} · ${videoData.course || 'Course'}`;
      
      if (videoEl && videoData.stream_url) {
        videoEl.src = videoData.stream_url;
        videoEl.style.display = "block";
        if (overlay) overlay.style.display = "none";
        if (frame) frame.style.background = "black";
      } else if (videoEl) {
         // Show it anyway so at least the player is there
         videoEl.style.display = "block";
         if (overlay) overlay.style.display = "none";
      }
    } catch (err) {
      console.error("Failed to fetch stream URL:", err);
      // Force display video so the user knows it's an empty player at least
      if (videoEl) {
        videoEl.style.display = "block";
      }
      if (overlay) {
        overlay.style.display = "none";
      }
      if (title) title.textContent = "Error Loading Video";
      if (description) description.textContent = err.message;
    }
  } else {
    // If we reach here, we are missing state.token or activeId!
    console.error("Missing activeId or state.token", { activeId, token: state.token });
    if (overlay) overlay.style.display = "none";
    if (title) title.textContent = "Authentication Required";
    if (description) description.textContent = "Please sign in to watch videos.";
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
  if (!form) return;

  const uploadStatus = document.getElementById("upload-status");
  const statusText = document.getElementById("status-text");
  const progressFill = document.getElementById("progress-fill");
  const submitBtn = document.getElementById("upload-submit");

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

    if (uploadStatus) {
      uploadStatus.classList.remove("hidden");
      // reset colors
      if (progressFill) {
          progressFill.style.background = "#0066cc";
          progressFill.style.width = "0%";
      }
    }
    
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Uploading...";
    }

    try {
      if (mode !== "process") {
        // --- XHR strictly to get actual upload percentage ---
        const xhr = new XMLHttpRequest();
        xhr.open("POST", endpoint, true);
        xhr.setRequestHeader("Authorization", `Bearer ${state.token}`);

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 100);
            if (progressFill) progressFill.style.width = `${percent}%`;
            if (statusText) statusText.textContent = `Uploading: ${percent}%`;
          }
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            const payload = JSON.parse(xhr.responseText);
            if (statusText) statusText.textContent = "Upload complete!";
            if (progressFill) progressFill.style.width = "100%";
            notify("Video uploaded successfully!", "success");
            window.setTimeout(() => window.location.href = `/watch/${payload.video_id}`, 1000);
          } else {
             if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = "Publish Lecture"; }
             if (statusText) statusText.textContent = `Error: ${xhr.status} ${xhr.statusText}`;
             if (progressFill) progressFill.style.background = "#d32f2f";
             notify("Upload failed: " + xhr.responseText, "error");
          }
        };

        xhr.onerror = () => {
          if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = "Publish Lecture"; }
          if (progressFill) progressFill.style.background = "#d32f2f";
          if (statusText) statusText.textContent = "Upload failed - Network error";
          notify("Network Error during upload", "error");
        };

        xhr.send(formData);

      } else {
        // --- Fetch is required to sequentially stream Server-Sent Events after upload ---
        // For 'process' mode, we upload then immediately tail the EventStream for watermarking %
        if (statusText) statusText.textContent = "Uploading (waiting for engine)...";
        if (progressFill) progressFill.style.width = "25%";
        
        const response = await fetch(endpoint, {
          method: "POST",
          headers: { Authorization: `Bearer ${state.token}` },
          body: formData,
        });

        if (!response.ok) {
          if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = "Publish Lecture"; }
          const body = await response.text();
          throw new Error(body || "Upload failed");
        }

        if (statusText) statusText.textContent = "Processing video...";
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop();

          for (const part of parts) {
            const line = part.split("\n").find(l => l.startsWith("data:"));
            if (!line) continue;
            try {
              const eventData = JSON.parse(line.slice(5).trim());
              if (eventData.percent !== undefined) {
                if (progressFill) progressFill.style.width = `${eventData.percent}%`;
                if (statusText) statusText.textContent = `Processing: ${eventData.percent}%`;
              }
              if (eventData.status === "done") {
                if (statusText) statusText.textContent = "Processing complete!";
                notify("Video processed and ready.", "success");
                window.setTimeout(() => {
                   window.location.href = `/watch/${eventData.video_id}`;
                }, 1500);
              } else if (eventData.status === "failed") {
                throw new Error(eventData.error || "Processing failed");
              }
            } catch (e) {
              console.error("SSE Parse Error", e);
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
      if (statusText) statusText.textContent = `Error: ${err.message}`;
      if (progressFill) progressFill.style.background = "#d32f2f";
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Publish Lecture";
      }
      notify(err.message, "error");
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

  // Enforce authentication for protected pages
  if (["library", "watch", "upload"].includes(page) && !state.token) {
    window.location.href = "/auth/login";
    return;
  }

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
