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
  const registerLink = document.getElementById("nav-register-link");
  
  if (!chip || !authLink) {
    return;
  }
  
  if (state.token) {
    if (searchForm) searchForm.classList.remove("hidden");
    if (registerLink) registerLink.classList.add("hidden");
  } else {
    if (searchForm) searchForm.classList.add("hidden");
    if (registerLink) registerLink.classList.remove("hidden");
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
    professor: video.uploader_name || "Institution Lecturer",
    course: video.channel_name || video.course || "General Lecture",
    description: video.description || "No description provided.",
    tags: [...(video.tags || []), "recent"],
    duration: "Lecture",
    views: video.views !== undefined ? `${video.views} views` : "0 views",
    thumbnail_url: video.thumbnail_url,
    accent: idx % 2
      ? "linear-gradient(135deg, #2a7b77, #7bc6be)"
      : "linear-gradient(135deg, #d6603b, #ebb18f)",
  }));
}

function filteredVideos() {
  if (state.filter === "classes") {
    return [];
  }
  return state.videos.filter((video) => {
    const haystack = [video.title, video.description, video.subject, video.course, ...(video.tags || [])]
      .join(" ")
      .toLowerCase();
    const queryOk = !state.query || haystack.includes(state.query.toLowerCase());
    return queryOk;
  });
}

async function loadVideos() {
  state.searchedChannels = []; // Reset searched channels on every load
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
    state.searchedChannels = data.channels || [];
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

  let channelsHtml = "";
  if (state.filter !== "videos" && state.searchedChannels && state.searchedChannels.length > 0) {
    const heading = state.query ? "Matched Channels" : "Course Channels";
    channelsHtml = `
      <div style="grid-column: 1 / -1; margin-bottom: 8px;">
        <h3 style="font-family: 'Space Grotesk', sans-serif; margin-bottom: 12px; color: var(--text);">${escapeHtml(heading)}</h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px;">
          ${state.searchedChannels.map(c => `
            <a href="/channel/${c.id}" class="card" style="padding: 16px; border: 1px solid var(--line); display: flex; flex-direction: column; gap: 6px; text-decoration: none; color: inherit; transition: all 0.2s; position: relative;" onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--line)'">
              <span class="badge-pill ${c.visibility || 'public'}" style="position: absolute; top: 12px; right: 12px; font-size: 0.65rem; padding: 2px 6px;">
                ${(c.visibility || 'public') === 'private' ? '🔒 Private' : (c.visibility || 'public') === 'unlisted' ? '🔗 Unlisted' : '🌐 Public'}
              </span>
              <p class="eyebrow" style="margin: 0; font-size: 0.72rem;">${escapeHtml(c.course_code || 'Class Channel')}</p>
              <h4 style="margin: 4px 0 2px 0; font-family: 'Space Grotesk', sans-serif; font-size: 1.1rem; color: var(--text);">${escapeHtml(c.name)}</h4>
              <p class="muted" style="font-size: 0.82rem; margin: 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.4; height: 34px;">${escapeHtml(c.description || 'No class description.')}</p>
              <div style="margin-top: 8px; font-size: 0.78rem; color: var(--muted); border-top: 1px solid var(--line); padding-top: 8px;">Lecturer: <strong style="color: var(--text);">${escapeHtml(c.owner_name || 'Institution Lecturer')}</strong></div>
            </a>
          `).join("")}
        </div>
        ${state.filter === "all" ? '<hr style="border: 0; border-top: 1px solid var(--line); margin: 24px 0 16px 0;">' : ''}
      </div>
    `;
  }

  const videos = filteredVideos();
  let videosHtml = "";
  if (state.filter !== "classes") {
    videosHtml = videos
      .map((video) => `
        <article class="video-card card">
          <a class="video-thumb" href="/watch/${encodeURIComponent(video.id)}" style="background: ${video.thumbnail_url ? `url('${video.thumbnail_url}') center/cover no-repeat, ` : ''}${video.accent}; border: 1px solid var(--border);">
            <span class="badge">${escapeHtml(video.subject)}</span>
            <span class="duration">${escapeHtml(video.duration)}</span>
          </a>
          <div class="video-body">
            <h3><a href="/watch/${encodeURIComponent(video.id)}">${escapeHtml(video.title)}</a></h3>
            <div class="video-meta">
              <span>By: <strong>${escapeHtml(video.professor)}</strong></span>
              <span>Class: <strong>${escapeHtml(video.course)}</strong></span>
              <span>Views: <strong>${escapeHtml(video.views)}</strong></span>
            </div>
          </div>
        </article>
      `)
      .join("");
  }

  host.innerHTML = channelsHtml + videosHtml;

  const hasChannels = state.filter !== "videos" && state.searchedChannels && state.searchedChannels.length > 0;
  const hasVideos = state.filter !== "classes" && videos.length > 0;

  if (!hasChannels && !hasVideos) {
    if (state.filter === "classes") {
      host.innerHTML = '<article class="card empty">No course channels matched your search.</article>';
    } else if (state.filter === "videos") {
      host.innerHTML = '<article class="card empty">No lectures matched your search.</article>';
    } else {
      host.innerHTML = '<article class="card empty">No videos or channels matched your search.</article>';
    }
  } else if (!hasVideos && state.filter === "all") {
    host.innerHTML = channelsHtml + '<article class="card empty" style="grid-column: 1 / -1;">No matching videos found in this catalog.</article>';
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
  const viewsEl = document.getElementById("watch-views");
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
      if (viewsEl) viewsEl.textContent = `${videoData.views !== undefined ? videoData.views : 0} views`;
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
    // if (recs.length < 6) {
    //   const dummyTitles = ["Advanced Mathematics", "Physics 101", "Introduction to Biology", "Computer Science Principles", "Modern History", "Philosophy of Science"];
    //   const dummyProfs = ["Dr. Smith", "Prof. Johnson", "Dr. Williams", "Prof. Brown", "Dr. Davis", "Prof. Miller"];
    //   const colors = ["#d7623d", "#efb08c", "#4CAF50", "#2196F3", "#9C27B0", "#FF9800", "#e91e63", "#00bcd4"];
    //   
    //   const needed = 6 - recs.length;
    //   for (let i = 0; i < needed; i++) {
    //     const rIndex = Math.floor(Math.random() * dummyTitles.length);
    //     recs.push({
    //       id: "dummy-" + Date.now() + "-" + i,
    //       title: dummyTitles[rIndex],
    //       professor: dummyProfs[rIndex],
    //       course: "General Studies",
    //       accent: colors[Math.floor(Math.random() * colors.length)]
    //     });
    //   }
    // }

    recHost.innerHTML = recs
      .slice(0, 8)
      .map((video) => `
        <a class="recommend-item" href="/watch/${encodeURIComponent(video.id)}">
          <span class="rec-thumb" style="background: ${video.thumbnail_url ? `url('${video.thumbnail_url}') center/cover no-repeat, ` : ''}${video.accent}; border: 1px solid var(--border);"></span>
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
      window.location.hash = target;
    });
  });

  if (window.location.hash === "#register") {
    const registerTab = document.querySelector('[data-auth-tab="register"]');
    if (registerTab) registerTab.click();
  }
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
        
        // Hide form and status
        registerForm.classList.add("hidden");
        if (status) status.classList.add("hidden");
        
        // Change title
        const authTitle = document.getElementById("auth-title");
        if (authTitle) authTitle.textContent = "Registration Complete";
        
        // Show success div
        const successBlock = document.getElementById("register-success");
        if (successBlock) successBlock.classList.remove("hidden");
        
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
  if (!state.token) {
    const grid = document.getElementById("video-grid");
    if (grid) grid.innerHTML = "";
    
    // Also remove the "Trending Lectures" section on home page if not logged in
    if (page === "home") {
        const trendingTitle = document.querySelector(".section-head");
        if (trendingTitle) trendingTitle.style.display = "none";
    }
    return;
  }
  await loadVideos();
  renderVideoCards("video-grid");
  setupFilters();
}

async function bootUpload() {
  await loadProfile();
  updateUploadGate();
  setupUploadForm();
  await populateChannelSelects();
}

async function boot() {
  updateHeaderSession();
  await loadProfile();
  updateHeaderSession();
  setupSearch();
  setupCreateChannelForm();

  // Enforce authentication for protected pages
  if (["library", "watch", "upload", "studio", "channel"].includes(page) && !state.token) {
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
    setupEditChannelForm();
    await bootStudio();
  } else if (page === "channel") {
    await bootChannel();
  }
}

boot();

async function bootStudio() {
  await loadProfile();
  await populateChannelSelects();
  
  const gate = document.getElementById("studio-gate");
  const content = document.getElementById("studio-content");
  
  if (!state.profile || state.profile.role !== "professor") {
    gate.classList.remove("hidden");
    content.classList.add("hidden");
    return;
  }
  
  gate.classList.add("hidden");
  content.classList.remove("hidden");
  
  await loadStudioChannels();
}

async function loadStudioChannels() {
  const grid = document.getElementById("studio-channels-grid");
  if (!grid) return;

  try {
    const res = await requestJson("/channels", {
      headers: { Authorization: `Bearer ${state.token}` },
    });
    const channels = res.results || [];
    const profId = state.profile.id || state.profile.user_id;
    const owned = channels.filter(c => String(c.owner_id) === String(profId));

    if (owned.length === 0) {
      grid.innerHTML = `
        <article class="card empty" style="padding: 30px; grid-column: 1 / -1; border: 1px dashed var(--line);">
          <h3>No course channels created yet</h3>
          <p class="muted" style="margin-bottom: 12px;">Create a class channel to upload and organize lectures.</p>
          <button class="button primary" onclick="openCreateChannelModal()">➕ Create Channel</button>
        </article>
      `;
      document.getElementById("studio-videos-wrapper").classList.add("hidden");
      document.getElementById("studio-videos-placeholder").classList.remove("hidden");
      return;
    }

    grid.innerHTML = owned.map(c => `
      <article class="card channel-select-card" 
               onclick="selectStudioChannel(this)" 
               data-id="${c.id}" 
               data-name="${escapeHtml(c.name)}" 
               data-description="${escapeHtml(c.description || '')}" 
               data-course-code="${escapeHtml(c.course_code || '')}" 
               data-visibility="${c.visibility}"
               style="cursor: pointer; padding: 20px; position: relative; border: 1px solid var(--line); transition: all 0.2s; display: flex; flex-direction: column; gap: 8px;" 
               id="studio-chan-${c.id}">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="badge-pill ${c.visibility}">${c.visibility}</span>
          <div style="display: flex; gap: 6px; align-items: center;">
            ${c.course_code ? `<span class="tag" style="margin:0; font-size: 0.72rem; padding: 2px 8px; background: rgba(31,122,114,0.08);">${escapeHtml(c.course_code)}</span>` : ''}
            <button class="button small ghost" style="padding: 2px 8px; font-size: 0.75rem; margin: 0;" onclick="event.stopPropagation(); triggerEditChannel(this)">Edit</button>
          </div>
        </div>
        <h3 style="margin-top: 4px; font-family: 'Space Grotesk', sans-serif;">${escapeHtml(c.name)}</h3>
        <p class="muted" style="font-size: 0.88rem; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; margin: 0; line-height: 1.5; height: 38px;">${escapeHtml(c.description || 'No class description.')}</p>
        <div style="margin-top: 8px; font-size: 0.8rem; color: var(--accent); font-weight: 700;">Click to view videos ➔</div>
      </article>
    `).join("");

    // Auto-select the first channel or preserve current selection if still valid
    const activeId = window.selectedStudioChannelId;
    const stillExists = owned.find(c => String(c.id) === String(activeId));
    if (activeId && stillExists) {
      selectStudioChannel(stillExists.id, stillExists.name, stillExists.visibility);
    } else if (owned.length > 0) {
      const firstChan = owned[0];
      selectStudioChannel(firstChan.id, firstChan.name, firstChan.visibility);
    }

  } catch (err) {
    console.error(err);
    grid.innerHTML = `<article class="card empty error">Failed to load channels: ${escapeHtml(err.message)}</article>`;
  }
}

window.selectStudioChannel = function(elOrId, optName, optVisibility) {
  let id, name, visibility;
  if (elOrId && typeof elOrId === 'object') {
    id = elOrId.getAttribute('data-id');
    name = elOrId.getAttribute('data-name');
    visibility = elOrId.getAttribute('data-visibility');
  } else {
    id = elOrId;
    name = optName;
    visibility = optVisibility;
  }

  if (!id) return;

  // Track selection state
  window.selectedStudioChannelId = id;

  // Highlight active channel card
  document.querySelectorAll(".channel-select-card").forEach(el => {
    el.style.borderColor = "var(--line)";
    el.style.background = "var(--surface)";
  });
  const activeCard = document.getElementById(`studio-chan-${id}`);
  if (activeCard) {
    activeCard.style.borderColor = "var(--accent)";
    activeCard.style.background = "linear-gradient(135deg, rgba(31, 122, 114, 0.03) 0%, rgba(215, 98, 61, 0.03) 100%)";
  }

  // Toggle wrappers
  document.getElementById("studio-videos-placeholder").classList.add("hidden");
  document.getElementById("studio-videos-wrapper").classList.remove("hidden");

  // Update headers
  document.getElementById("selected-channel-header").textContent = `Lectures inside: ${name}`;
  const pill = document.getElementById("selected-channel-visibility-pill");
  if (pill) {
    pill.className = `tag badge-pill ${visibility}`;
    pill.textContent = visibility;
  }

  // Fetch lectures for this channel
  loadStudioChannelVideos(id);
};

async function loadStudioChannelVideos(channelId) {
  const tbody = document.getElementById("studio-video-list");
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="4" style="padding: 24px; text-align: center;">Loading lectures...</td></tr>';
  
  try {
    const res = await requestJson(`/channels/${channelId}`, {
      headers: { Authorization: `Bearer ${state.token}` },
    });
    const videos = res.results || [];
    
    if (videos.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="padding: 24px; text-align: center;">No lectures uploaded to this channel yet.</td></tr>';
      return;
    }
    
    tbody.innerHTML = videos.map(v => `
      <tr>
        <td style="padding: 14px 16px; border-bottom: 1px solid var(--border);">
          ${v.status === 'ready' ? `<a href="/watch/${v.video_id}" style="color: var(--accent); font-weight: 700; font-size: 0.98rem; text-decoration: none; transition: color 0.15s;" onmouseover="this.style.color='var(--accent-hover)'" onmouseout="this.style.color='var(--accent)'">${escapeHtml(v.title)}</a>` : `<strong style="font-size: 0.98rem; color: var(--muted);">${escapeHtml(v.title)}</strong>`}
          <br>
          <small class="muted" style="margin-top: 4px; display: inline-block;">${escapeHtml(v.description || 'No description provided')}</small>
        </td>
        <td style="padding: 14px 16px; border-bottom: 1px solid var(--border); text-align: left;">
          <span style="font-weight: 500; color: var(--text);">${v.views !== undefined ? v.views : 0} views</span>
        </td>
        <td style="padding: 14px 16px; border-bottom: 1px solid var(--border); text-align: center;">
          <span class="tag ${v.status === 'ready' ? '' : 'warn'}" style="margin: 0;">${escapeHtml(v.status)}</span>
        </td>
        <td style="padding: 14px 16px; border-bottom: 1px solid var(--border); text-align: right; white-space: nowrap;">
          <button class="button small ghost" style="padding: 6px 12px; font-size: 0.8rem; margin-right: 4px;" onclick="openEditModal('${v.video_id}', '${escapeHtml(v.title.replace(/'/g, "\\'"))}', '${escapeHtml((v.description || '').replace(/'/g, "\\'"))}', '${escapeHtml((v.tags || []).join(", ").replace(/'/g, "\\'"))}', '${channelId}')">Edit</button>
          <button class="button small error" style="padding: 6px 12px; font-size: 0.8rem;" onclick="deleteStudioVideo('${v.video_id}', '${channelId}')">Delete</button>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    console.error(err);
    tbody.innerHTML = `<tr><td colspan="4" style="padding: 24px; text-align: center; color: var(--error);">Error loading videos: ${escapeHtml(err.message)}</td></tr>`;
  }
}

async function deleteStudioVideo(id, channelId) {
  if (!confirm("Are you sure you want to delete this lecture?")) return;
  
  try {
    await requestJson(`/videos/${id}`, { 
      method: "DELETE",
      headers: { Authorization: `Bearer ${state.token}` }
    });
    notify("Lecture deleted successfully.", "success");
    await loadStudioChannelVideos(channelId);
  } catch (err) {
    notify(err.message, "error");
  }
}

function openEditModal(id, title, desc, tags, channel_id) {
  document.getElementById("edit-video-id").value = id;
  document.getElementById("edit-title").value = title;
  document.getElementById("edit-description").value = desc;
  document.getElementById("edit-tags").value = tags;
  
  const select = document.getElementById("edit-channel-select");
  if (select) select.value = channel_id || "";
  
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
    
    const targetChannelId = document.getElementById("edit-channel-select").value || null;
    
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
          tags: document.getElementById("edit-tags").value,
          channel_id: targetChannelId
        })
      });
      notify("Changes saved successfully", "success");
      closeEditModal();
      
      // Reload studio selections
      await loadStudioChannels();
    } catch (err) {
      notify(err.message, "error");
    } finally {
      updateBtn.disabled = false;
      updateBtn.textContent = "Save Changes";
    }
  });
}

// ---------------------------------------------------------------------------
// Channels Global Actions
// ---------------------------------------------------------------------------

window.openCreateChannelModal = function() {
  const modal = document.getElementById("channel-create-modal");
  if (modal) modal.style.display = "flex";
};

window.closeCreateChannelModal = function() {
  const modal = document.getElementById("channel-create-modal");
  if (modal) modal.style.display = "none";
};

function setupCreateChannelForm() {
  const form = document.getElementById("create-channel-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = "Creating...";

    const body = {
      name: document.getElementById("new-channel-name").value.trim(),
      description: document.getElementById("new-channel-description").value.trim(),
      course_code: document.getElementById("new-channel-code").value.trim(),
      visibility: document.getElementById("new-channel-visibility").value,
      channel_type: "class"
    };

    try {
      const channel = await requestJson("/channels", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${state.token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify(body)
      });

      notify("Class Channel created successfully!", "success");
      closeCreateChannelModal();
      form.reset();
      
      // Refresh channels selector populators and view
      await populateChannelSelects();
      if (page === "studio") {
        await loadStudioChannels();
        selectStudioChannel(channel.id, channel.name, channel.visibility);
      } else {
        window.location.href = `/channel/${channel.id}`;
      }
    } catch (err) {
      notify(err.message, "error");
      btn.disabled = false;
      btn.textContent = "Create Channel";
    }
  });
}

window.triggerEditChannel = function(btnEl) {
  const card = btnEl.closest('.channel-select-card');
  if (!card) return;
  const id = card.getAttribute('data-id');
  const name = card.getAttribute('data-name');
  const description = card.getAttribute('data-description');
  const code = card.getAttribute('data-course-code');
  const visibility = card.getAttribute('data-visibility');
  openEditChannelModal(id, name, description, code, visibility);
};

window.openEditChannelModal = function(id, name, description, code, visibility) {
  document.getElementById("edit-channel-id").value = id;
  document.getElementById("edit-channel-name").value = name;
  document.getElementById("edit-channel-description").value = description;
  document.getElementById("edit-channel-code").value = code;
  document.getElementById("edit-channel-visibility").value = visibility;
  
  const modal = document.getElementById("channel-edit-modal");
  if (modal) modal.style.display = "flex";
};

window.closeEditChannelModal = function() {
  const modal = document.getElementById("channel-edit-modal");
  if (modal) modal.style.display = "none";
};

function setupEditChannelForm() {
  const form = document.getElementById("edit-channel-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("edit-channel-id").value;
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = "Saving...";

    const body = {
      name: document.getElementById("edit-channel-name").value.trim(),
      description: document.getElementById("edit-channel-description").value.trim(),
      course_code: document.getElementById("edit-channel-code").value.trim(),
      visibility: document.getElementById("edit-channel-visibility").value
    };

    try {
      await requestJson(`/channels/${id}`, {
        method: "PUT",
        headers: {
          "Authorization": `Bearer ${state.token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify(body)
      });

      notify("Channel updated successfully!", "success");
      closeEditChannelModal();
      
      // Refresh channels selector populators and view
      await populateChannelSelects();
      await loadStudioChannels();
    } catch (err) {
      notify(err.message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Save Changes";
    }
  });
}

async function bootChannel() {
  const channelId = window.UASTREAM_SELECTED_CHANNEL_ID;
  if (!channelId || !state.token) return;

  await loadProfile();
  
  const typeEye = document.getElementById("channel-type-eyebrow");
  const nameTitle = document.getElementById("channel-name-title");
  const visBadge = document.getElementById("channel-visibility-badge");
  const ownerChip = document.getElementById("channel-owner-chip");
  const codeChip = document.getElementById("channel-code-chip");
  const descText = document.getElementById("channel-desc");
  const subBtn = document.getElementById("channel-subscribe-btn");
  const videoGrid = document.getElementById("channel-video-grid");

  try {
    const data = await requestJson(`/channels/${channelId}`, {
      headers: { Authorization: `Bearer ${state.token}` },
    });
    
    const channel = data.channel;
    const isSubscribed = data.is_subscribed;
    const videos = data.results || [];

    // Render metadata
    if (typeEye) typeEye.textContent = channel.channel_type === "personal" ? "Professor Personal Channel" : "Class Channel";
    if (nameTitle) nameTitle.textContent = channel.name;
    if (descText) descText.textContent = channel.description || "No class description provided.";
    
    if (visBadge) {
      visBadge.className = `badge-pill ${channel.visibility}`;
      visBadge.textContent = channel.visibility;
    }

    if (ownerChip) ownerChip.textContent = `Lecturer: ${channel.owner_name || 'Professor'}`;
    
    if (codeChip && channel.course_code) {
      codeChip.textContent = channel.course_code;
      codeChip.classList.remove("hidden");
    } else if (codeChip) {
      codeChip.classList.add("hidden");
    }

    // Subscribe button logic (only show if current user is not the owner)
    if (subBtn) {
      const isOwner = String(channel.owner_id) === String(state.profile.id || state.profile.user_id);
      if (isOwner) {
        subBtn.classList.add("hidden");
      } else {
        subBtn.classList.remove("hidden");
        subBtn.textContent = isSubscribed ? "Leave Class" : "Join Class";
        subBtn.className = isSubscribed ? "button ghost" : "button primary";
        
        // Remove old event listeners
        const newBtn = subBtn.cloneNode(true);
        subBtn.parentNode.replaceChild(newBtn, subBtn);
        
        newBtn.addEventListener("click", async () => {
          newBtn.disabled = true;
          newBtn.textContent = isSubscribed ? "Leaving..." : "Joining...";
          try {
            await requestJson(`/channels/${channelId}/subscribe`, {
              method: "POST",
              headers: {
                "Authorization": `Bearer ${state.token}`,
                "Content-Type": "application/json"
              },
              body: JSON.stringify({ action: isSubscribed ? "unsubscribe" : "subscribe" })
            });
            notify(isSubscribed ? "Unsubscribed from class" : "Joined class successfully!", "success");
            await bootChannel();
          } catch (err) {
            notify(err.message, "error");
            newBtn.disabled = false;
            newBtn.textContent = isSubscribed ? "Leave Class" : "Join Class";
          }
        });
      }
    }

    // Render lectures
    if (videoGrid) {
      if (videos.length === 0) {
        videoGrid.innerHTML = '<article class="card empty">No lectures published in this channel yet.</article>';
        return;
      }

      const mapped = mapApiVideos(videos);
      videoGrid.innerHTML = mapped.map(video => `
        <article class="video-card card">
          <a class="video-thumb" href="/watch/${encodeURIComponent(video.id)}" style="background: ${video.thumbnail_url ? `url('${video.thumbnail_url}') center/cover no-repeat, ` : ''}${video.accent}; border: 1px solid var(--border);">
            <span class="badge">${escapeHtml(video.subject)}</span>
            <span class="duration">${escapeHtml(video.duration)}</span>
          </a>
          <div class="video-body">
            <h3><a href="/watch/${encodeURIComponent(video.id)}">${escapeHtml(video.title)}</a></h3>
            <p>${escapeHtml(video.description)}</p>
            <div class="video-meta">
              <span>By: <strong>${escapeHtml(video.professor)}</strong></span>
              <span>Class: <strong>${escapeHtml(video.course)}</strong></span>
            </div>
          </div>
        </article>
      `).join("");
    }

  } catch (err) {
    console.error(err);
    notify(err.message, "error");
    if (videoGrid) videoGrid.innerHTML = `<article class="card empty error">Error loading channel: ${escapeHtml(err.message)}</article>`;
  }
}

async function loadSidebarChannels() {
  // Sidebar removed, kept as safe no-op
}

async function populateChannelSelects() {
  const uploadSelect = document.getElementById("upload-channel-select");
  const editSelect = document.getElementById("edit-channel-select");

  if (!uploadSelect && !editSelect) return;

  try {
    const res = await requestJson("/channels", {
      headers: { Authorization: `Bearer ${state.token}` },
    });
    const channels = res.results || [];
    const profId = state.profile.id || state.profile.user_id;
    const owned = channels.filter(c => String(c.owner_id) === String(profId));

    const optionsHtml = owned.map(c => `
      <option value="${c.id}">${c.visibility === 'private' ? '🔒' : c.visibility === 'unlisted' ? '🔗' : '🌐'} ${escapeHtml(c.name)} (${c.visibility})</option>
    `).join("");

    if (uploadSelect) {
      if (owned.length === 0) {
        uploadSelect.innerHTML = '<option value="">⚠️ Create a Class Channel first! --</option>';
      } else {
        uploadSelect.innerHTML = optionsHtml;
      }
    }

    if (editSelect) {
      editSelect.innerHTML = '<option value="">-- No Channel --</option>' + owned.map(c => `
        <option value="${c.id}">${escapeHtml(c.name)}</option>
      `).join("");
    }
  } catch (err) {
    console.error("Failed to populate channels selector:", err);
  }
}

window.showChannelSubscribers = async function() {
  const channelId = window.selectedStudioChannelId;
  if (!channelId) return;

  const modal = document.getElementById("subscribers-modal");
  const tbody = document.getElementById("subscribers-list-tbody");
  if (!modal || !tbody) return;

  tbody.innerHTML = '<tr><td colspan="2" style="padding: 20px; text-align: center;">Loading subscribers...</td></tr>';
  modal.style.display = "flex";

  try {
    const res = await requestJson(`/channels/${channelId}/subscribers`, {
      headers: { Authorization: `Bearer ${state.token}` },
    });
    const subs = res.results || [];

    if (subs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="2" style="padding: 20px; text-align: center;" class="muted">No subscribers yet for this class channel.</td></tr>';
      return;
    }

    tbody.innerHTML = subs.map(s => `
      <tr style="border-bottom: 1px solid var(--border);">
        <td style="padding: 10px 12px; font-weight: 500; border-bottom: 1px solid var(--border);">${escapeHtml(s.name)}</td>
        <td style="padding: 10px 12px; color: var(--muted); border-bottom: 1px solid var(--border);">${escapeHtml(s.email)}</td>
      </tr>
    `).join("");

  } catch (err) {
    console.error(err);
    tbody.innerHTML = `<tr><td colspan="2" style="padding: 20px; text-align: center; color: var(--error);">Error loading subscribers: ${escapeHtml(err.message)}</td></tr>`;
  }
};

window.closeSubscribersModal = function() {
  const modal = document.getElementById("subscribers-modal");
  if (modal) modal.style.display = "none";
};


