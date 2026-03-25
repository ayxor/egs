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
  const studioLink = document.getElementById("nav-studio");
  const searchForm = document.getElementById("nav-search-form");
  
  if (!chip || !authLink) {
    return;
  }
  
  if (state.token) {
    if (searchForm) searchForm.classList.remove("hidden");
  } else {
    if (searchForm) searchForm.classList.add("hidden");
  }
  
  if (state.profile) {
    chip.textContent = `${state.profile.name} · ${state.profile.role}`;
    if (uploadLink) {
      uploadLink.classList.toggle("hidden", state.profile.role !== "professor");
    }
    if (studioLink) {
      studioLink.classList.toggle("hidden", state.profile.role !== "professor");
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
    if (studioLink) {
      studioLink.classList.add("hidden");
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
    if (studioLink) {
      studioLink.classList.add("hidden");
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
  const form = document.getElementById("nav-search-form");
  const input = document.getElementById("nav-search-input");
  
  if (!form || !input) {
    return;
  }
  
  // Fill the input if we came from a query param
  const urlParams = new URLSearchParams(window.location.search);
  const q = urlParams.get("q");
  if (q && page === "library") {
    input.value = q;
    state.query = q;
    // We already call loadVideos in bootHomeOrLibrary
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = input.value.trim();
    if (page !== "library") {
      window.location.href = `/library?q=${encodeURIComponent(query)}`;
      return;
    }
    
    // If we're already on the library page, just search in place
    state.query = query;
    // Update the URL to reflect the search without reloading
    const newUrl = new URL(window.location);
    if (query) {
      newUrl.searchParams.set("q", query);
    } else {
      newUrl.searchParams.delete("q");
    }
    window.history.pushState({}, "", newUrl);
    
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
    let recs = pool.filter((v) => v.id !== activeId);
    
    // Sort randomly
    recs.sort(() => 0.5 - Math.random());
    
    // Fill up to 6 videos with dummy data if we don't have enough real videos
    if (recs.length < 6) {
      const dummyTitles = ["Advanced Mathematics", "Physics 101", "Introduction to Biology", "Computer Science Principles", "Modern History", "Philosophy of Science"];
      const dummyProfs = ["Dr. Smith", "Prof. Johnson", "Dr. Williams", "Prof. Brown", "Dr. Davis", "Prof. Miller"];
      const colors = ["#d7623d", "#efb08c", "#4CAF50", "#2196F3", "#9C27B0", "#FF9800", "#e91e63", "#00bcd4"];
      
      const needed = 6 - recs.length;
      for (let i = 0; i < needed; i++) {
        const rIndex = Math.floor(Math.random() * dummyTitles.length);
        recs.push({
          id: "dummy-" + Date.now() + "-" + i,
          title: dummyTitles[rIndex],
          professor: dummyProfs[rIndex],
          course: "General Studies",
          accent: colors[Math.floor(Math.random() * colors.length)]
        });
      }
    }

    recHost.innerHTML = recs
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

  gate.className = "hidden";
  gate.textContent = "";
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
                let msg = `Processing: ${eventData.percent}%`;
                if (eventData.message) {
                  msg += ` - ${eventData.message}`;
                }
                if (statusText) statusText.textContent = msg;
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
  setupSearch();

  // Enforce authentication for protected pages
  if (["library", "watch", "upload", "studio"].includes(page) && !state.token) {
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
  } else if (page === "studio") {
    setupStudioForm();
    await bootStudio();
  }
}

boot();

async function bootStudio() {
  await loadProfile();
  
  const gate = document.getElementById("studio-gate");
  const content = document.getElementById("studio-content");
  
  if (!state.profile || state.profile.role !== "professor") {
    gate.classList.remove("hidden");
    content.classList.add("hidden");
    return;
  }
  
  gate.classList.add("hidden");
  content.classList.remove("hidden");
  
  await loadStudioVideos();
}

async function loadStudioVideos() {
  const tbody = document.getElementById("studio-video-list");
  if (!tbody) return;
  
  try {
    const res = await requestJson("/videos/me", {
      headers: { Authorization: `Bearer ${state.token}` },
    });
    const videos = res.results || [];
    
    if (videos.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="padding: 24px; text-align: center;">No videos found.</td></tr>';
      return;
    }
    
    tbody.innerHTML = videos.map(v => `
      <tr>
        <td style="padding: 12px 16px; border-bottom: 1px solid var(--border);">
          <strong>${escapeHtml(v.title)}</strong><br>
          <small class="muted">${escapeHtml(v.description || 'No description')}</small>
        </td>
        <td style="padding: 12px 16px; border-bottom: 1px solid var(--border);">
          ${escapeHtml(v.course || '—')}<br>
          <small class="muted">${escapeHtml(v.subject || '—')}</small>
        </td>
        <td style="padding: 12px 16px; border-bottom: 1px solid var(--border);">
          <span class="tag ${v.status === 'ready' ? '' : 'warn'}">${escapeHtml(v.status)}</span>
        </td>
        <td style="padding: 12px 16px; border-bottom: 1px solid var(--border); text-align: right;">
          <button class="button small ghost" onclick="openEditModal('${v.video_id}', '${escapeHtml(v.title.replace(/'/g, "\\'"))}', '${escapeHtml((v.description || '').replace(/'/g, "\\'"))}', '${escapeHtml((v.course || '').replace(/'/g, "\\'"))}', '${escapeHtml((v.subject || '').replace(/'/g, "\\'"))}', '${escapeHtml((v.tags || []).join(", ").replace(/'/g, "\\'"))}')">Edit</button>
          <button class="button small error" onclick="deleteStudioVideo('${v.video_id}')">Delete</button>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    console.error(err);
    tbody.innerHTML = `<tr><td colspan="4" style="padding: 24px; text-align: center; color: var(--error);">Error loading videos: ${escapeHtml(err.message)}</td></tr>`;
  }
}

async function deleteStudioVideo(id) {
  if (!confirm("Are you sure you want to delete this video?")) return;
  
  try {
    await requestJson(`/videos/${id}`, { 
      method: "DELETE",
      headers: { Authorization: `Bearer ${state.token}` }
    });
    notify("Video deleted", "success");
    await loadStudioVideos();
  } catch (err) {
    notify(err.message, "error");
  }
}

function openEditModal(id, title, desc, course, subj, tags) {
  document.getElementById("edit-video-id").value = id;
  document.getElementById("edit-title").value = title;
  document.getElementById("edit-description").value = desc;
  document.getElementById("edit-course").value = course;
  document.getElementById("edit-subject").value = subj;
  document.getElementById("edit-tags").value = tags;
  
  document.getElementById("edit-modal").style.display = "flex";
}

function closeEditModal() {
  document.getElementById("edit-modal").style.display = "none";
}

function setupStudioForm() {
  const form = document.getElementById("edit-form");
  if (!form) return;
  
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("edit-video-id").value;
    const updateBtn = form.querySelector('button[type="submit"]');
    updateBtn.disabled = true;
    updateBtn.textContent = "Saving...";
    
    try {
      await requestJson(`/videos/${id}`, {
        method: "PUT",
        headers: { 
          "Authorization": `Bearer ${state.token}`,
          "Content-Type": "application/json" 
        },
        body: JSON.stringify({
          title: document.getElementById("edit-title").value,
          description: document.getElementById("edit-description").value,
          course: document.getElementById("edit-course").value,
          subject: document.getElementById("edit-subject").value,
          tags: document.getElementById("edit-tags").value
        })
      });
      notify("Changes saved successfully", "success");
      closeEditModal();
      await loadStudioVideos();
    } catch (err) {
      notify(err.message, "error");
    } finally {
      updateBtn.disabled = false;
      updateBtn.textContent = "Save Changes";
    }
  });
}
