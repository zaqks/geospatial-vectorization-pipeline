const COOKIE_NAME = "upload_uuid";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365;
const FETCH_TIMEOUT_MS = 180 * 1000;
const FETCH_RETRIES = 3;
const RETRY_DELAY_MS = 1000;
const THEME_STORAGE_KEY = "geovec_theme";
const RESULT_RECEIVED_PREFIX = "geovec_result_received_";

const RAW_API_URL = import.meta.env.VITE_API_URL || import.meta.env.API_URL || "";
const API_URL = String(RAW_API_URL).replace(/\/$/, "");

const uploadPanel = document.getElementById("upload-panel");
const statusPanel = document.getElementById("status-panel");
const resultPanel = document.getElementById("result-panel");
const messagePanel = document.getElementById("message-panel");
const heroSection = document.getElementById("hero-section");
const studioOnlyNodes = document.querySelectorAll(".studio-only");

const uploadForm = document.getElementById("upload-form");
const submitBtn = document.getElementById("submit-btn");
const newMapBtn = document.getElementById("new-map-btn");

const fileInput = document.getElementById("map-file");
const uploadPreviewFigure = document.getElementById("upload-preview-figure");
const uploadPreviewImage = document.getElementById("upload-preview-image");
const pointsLineInput = document.getElementById("points-line");

const statusPercent = document.getElementById("status-percent");
const loadingBarFill = document.getElementById("loading-bar-fill");
const statusLabel = statusPanel?.querySelector(".status-label");
const resultMapStack = document.getElementById("result-map-stack");
const resultImage = document.getElementById("result-image");
const resultOverlays = document.getElementById("result-overlays");
const resultFullscreenModal = document.getElementById("result-fullscreen-modal");
const resultFullscreenClose = document.getElementById("result-fullscreen-close");
const resultImageFullscreen = document.getElementById("result-image-fullscreen");
const resultOverlaysFullscreen = document.getElementById("result-overlays-fullscreen");
const overlayListFullscreen = document.getElementById("overlay-list-fullscreen");
const downloadsList = document.getElementById("downloads-list");
const overlayList = document.getElementById("overlay-list");
const messageText = document.getElementById("message-text");
const themeToggle = document.getElementById("theme-toggle");

let activeUuid = null;
let statusEventSource = null;
let previewUrl = null;
let statusMode = "processing";

function resultReceivedKey(uuid) {
  return `${RESULT_RECEIVED_PREFIX}${uuid}`;
}

function setResultReceived(uuid, received) {
  if (!uuid) {
    return;
  }

  window.localStorage.setItem(resultReceivedKey(uuid), received ? "true" : "false");
}

function hasReceivedResult(uuid) {
  if (!uuid) {
    return false;
  }

  return window.localStorage.getItem(resultReceivedKey(uuid)) === "true";
}

function setStatusMode(mode) {
  statusMode = mode === "loading-result" ? "loading-result" : "processing";
  statusPanel.classList.toggle("result-loading", statusMode === "loading-result");

  if (statusLabel) {
    statusLabel.textContent = statusMode === "loading-result" ? "Loading saved result" : "Progress";
  }
}

function applyTheme(theme) {
  const normalizedTheme = theme === "dark" ? "dark" : "light";
  document.body.dataset.theme = normalizedTheme;

  if (themeToggle) {
    themeToggle.checked = normalizedTheme === "dark";
  }
}

function initTheme() {
  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  const initialTheme = storedTheme === "dark" ? "dark" : "light";
  applyTheme(initialTheme);

  if (!themeToggle) {
    return;
  }

  themeToggle.addEventListener("change", () => {
    const nextTheme = themeToggle.checked ? "dark" : "light";
    applyTheme(nextTheme);
    window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
  });
}

function clearPreview() {
  if (previewUrl) {
    URL.revokeObjectURL(previewUrl);
    previewUrl = null;
  }

  uploadPreviewImage.removeAttribute("src");
  uploadPreviewFigure.classList.add("hidden");
}

function updatePreview() {
  clearPreview();

  if (!fileInput.files || fileInput.files.length === 0) {
    return;
  }

  const selectedFile = fileInput.files[0];
  if (!selectedFile.type.startsWith("image/")) {
    return;
  }

  previewUrl = URL.createObjectURL(selectedFile);
  uploadPreviewImage.src = previewUrl;
  uploadPreviewFigure.classList.remove("hidden");
}

function buildUrl(path) {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  if (!API_URL) {
    return path;
  }

  if (path.startsWith("/")) {
    return `${API_URL}${path}`;
  }

  return `${API_URL}/${path}`;
}

function showOnly(panel) {
  [uploadPanel, statusPanel, resultPanel, messagePanel].forEach((el) => {
    if (!el) {
      return;
    }

    el.classList.toggle("hidden", el !== panel);
  });

  const showHomeDecor = panel === uploadPanel;
  if (heroSection) {
    heroSection.classList.toggle("hidden", !showHomeDecor);
  }

  studioOnlyNodes.forEach((node) => {
    node.classList.toggle("hidden", !showHomeDecor);
  });

  if (panel !== resultPanel) {
    closeFullscreenPreview();
  }
}

function showMessage(message) {
  messageText.textContent = message;
  showOnly(messagePanel);
}

function setProgress(percent) {
  if (statusMode === "loading-result") {
    return;
  }

  const safePercent = Number.isFinite(percent) ? Math.max(0, Math.min(100, percent)) : 0;
  statusPercent.textContent = String(safePercent);
  if (loadingBarFill) {
    loadingBarFill.style.width = `${safePercent}%`;
  }
}

function clearMessage() {
  messageText.textContent = "";
}

function setCookie(name, value, maxAgeSec) {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${maxAgeSec}; SameSite=Lax`;
}

function getCookie(name) {
  const cookies = document.cookie ? document.cookie.split("; ") : [];
  for (const cookie of cookies) {
    const [rawName, ...rest] = cookie.split("=");
    if (rawName === name) {
      return decodeURIComponent(rest.join("="));
    }
  }
  return null;
}

function clearCookie(name) {
  document.cookie = `${name}=; path=/; max-age=0; SameSite=Lax`;
}

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

async function fetchWithTimeout(url, options = {}, timeoutMs = FETCH_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

async function fetchWithRetry(url, options = {}, { timeoutMs = FETCH_TIMEOUT_MS, retries = FETCH_RETRIES } = {}) {
  let attempt = 0;

  while (true) {
    try {
      const response = await fetchWithTimeout(url, options, timeoutMs);
      if (response.ok) {
        return response;
      }

      const isRetryableStatus = response.status === 429 || response.status >= 500;
      if (attempt < retries && isRetryableStatus) {
        attempt += 1;
        await wait(RETRY_DELAY_MS * attempt);
        continue;
      }

      throw new Error(`Request failed (${response.status})`);
    } catch (error) {
      const isAbortError = error instanceof DOMException && error.name === "AbortError";
      const isNetworkError = error instanceof TypeError || isAbortError;

      if (attempt < retries && isNetworkError) {
        attempt += 1;
        await wait(RETRY_DELAY_MS * attempt);
        continue;
      }

      if (isAbortError) {
        throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s`);
      }

      throw error;
    }
  }
}

function stopStatusStream() {
  if (statusEventSource) {
    statusEventSource.close();
    statusEventSource = null;
  }
}

function setInputsDisabled(disabled) {
  fileInput.disabled = disabled;
  pointsLineInput.disabled = disabled;
  submitBtn.disabled = disabled || !isUploadReady();
  const isProcessing = uploadForm.dataset.processing === "true";
  submitBtn.classList.toggle("is-loading", isProcessing);
  submitBtn.setAttribute("aria-busy", isProcessing ? "true" : "false");
}

function hasSelectedImage() {
  return Boolean(fileInput.files && fileInput.files.length > 0);
}

function arePointFieldsFilled() {
  return pointsLineInput.value.trim() !== "";
}

function parseCoordinateLine(rawLine) {
  const parts = rawLine
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part !== "");

  if (parts.length !== 4) {
    return null;
  }

  const [lat1, lng1, lat2, lng2] = parts.map((part) => Number(part));
  if (![lat1, lng1, lat2, lng2].every(Number.isFinite)) {
    return null;
  }

  return { lat1, lng1, lat2, lng2 };
}

function isUploadReady() {
  return hasSelectedImage() && arePointFieldsFilled();
}

function updateSubmitState() {
  if (!submitBtn || submitBtn.disabled && submitBtn.form?.dataset.processing === "true") {
    return;
  }

  submitBtn.disabled = !isUploadReady();
}

function extractOverlayId(name) {
  const normalized = String(name || "");
  const match = /^(?:id_)?(\d+)(?:_|\.|$)/i.exec(normalized);
  if (!match) {
    return Number.MAX_SAFE_INTEGER;
  }
  const parsed = Number.parseInt(match[1], 10);
  return Number.isFinite(parsed) ? parsed : Number.MAX_SAFE_INTEGER;
}

function openFullscreenPreview() {
  if (!resultFullscreenModal) {
    return;
  }

  resultFullscreenModal.classList.remove("hidden");
  resultFullscreenModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("fullscreen-open");
}

function closeFullscreenPreview() {
  if (!resultFullscreenModal) {
    return;
  }

  resultFullscreenModal.classList.add("hidden");
  resultFullscreenModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("fullscreen-open");
}

function createOverlayToggleItem(label, checked, onChange) {
  const li = document.createElement("li");
  li.className = "overlay-item";

  const toggleLabel = document.createElement("label");
  toggleLabel.className = "overlay-toggle";

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = checked;
  checkbox.addEventListener("change", () => onChange(checkbox.checked));

  const text = document.createElement("span");
  text.textContent = label;

  toggleLabel.appendChild(checkbox);
  toggleLabel.appendChild(text);
  li.appendChild(toggleLabel);

  return { li, checkbox };
}

function renderResult(data) {
  const imageUrl = buildUrl(data.img_url || "");
  resultImage.src = imageUrl;
  if (resultImageFullscreen) {
    resultImageFullscreen.src = imageUrl;
  }
  resultOverlays.innerHTML = "";
  if (resultOverlaysFullscreen) {
    resultOverlaysFullscreen.innerHTML = "";
  }
  overlayList.innerHTML = "";
  if (overlayListFullscreen) {
    overlayListFullscreen.innerHTML = "";
  }

  const overlays = (Array.isArray(data.overlays) ? data.overlays : [])
    .filter((entry) => Array.isArray(entry) && entry.length >= 2)
    .map((entry, index) => {
      const [name, link] = entry;
      return {
        name: String(name || `overlay-${index + 1}`),
        link: String(link || ""),
        overlayId: extractOverlayId(name),
      };
    })
    .sort((a, b) => a.overlayId - b.overlayId);

  overlays.forEach((entry, index) => {
    const label = entry.name;
    const overlayUrl = buildUrl(entry.link);
    const overlayId = `overlay-${index}`;

    const inlineOverlayImg = document.createElement("img");
    inlineOverlayImg.src = overlayUrl;
    inlineOverlayImg.alt = label;
    inlineOverlayImg.className = "result-overlay-image";
    inlineOverlayImg.dataset.overlayId = overlayId;

    const fullscreenOverlayImg = document.createElement("img");
    fullscreenOverlayImg.src = overlayUrl;
    fullscreenOverlayImg.alt = label;
    fullscreenOverlayImg.className = "result-overlay-image";
    fullscreenOverlayImg.dataset.overlayId = overlayId;

    if (Number.isFinite(entry.overlayId)) {
      inlineOverlayImg.style.zIndex = String(entry.overlayId);
      fullscreenOverlayImg.style.zIndex = String(entry.overlayId);
    }
    resultOverlays.appendChild(inlineOverlayImg);
    if (resultOverlaysFullscreen) {
      resultOverlaysFullscreen.appendChild(fullscreenOverlayImg);
    }

    const applyOverlayVisibility = (visible) => {
      inlineOverlayImg.classList.toggle("hidden", !visible);
      fullscreenOverlayImg.classList.toggle("hidden", !visible);
      inlineToggle.checkbox.checked = visible;
      fullscreenToggle.checkbox.checked = visible;
    };

    const inlineToggle = createOverlayToggleItem(label, true, applyOverlayVisibility);
    const fullscreenToggle = createOverlayToggleItem(label, true, applyOverlayVisibility);

    overlayList.appendChild(inlineToggle.li);
    if (overlayListFullscreen) {
      overlayListFullscreen.appendChild(fullscreenToggle.li);
    }
  });

  downloadsList.innerHTML = "";
  const files = Array.isArray(data.files) ? data.files : [];

  files.forEach((entry, index) => {
    if (!Array.isArray(entry) || entry.length < 2) {
      return;
    }

    const [name, link] = entry;
    const li = document.createElement("li");
    const anchor = document.createElement("a");
    anchor.href = buildUrl(String(link));
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    anchor.textContent = String(name || `file-${index + 1}`);
    li.appendChild(anchor);
    downloadsList.appendChild(li);
  });

  closeFullscreenPreview();
  showOnly(resultPanel);
}

async function fetchResultForActiveUpload() {
  if (!activeUuid) {
    return;
  }

  const response = await fetchWithRetry(buildUrl(`/api/result/${activeUuid}`));
  const data = await response.json();
  const percent = Number(data.status_percent ?? 0);
  setProgress(percent);

  if (percent >= 100 && data.img_url) {
    setResultReceived(activeUuid, true);
    renderResult(data);
    return;
  }

  showOnly(statusPanel);
}

async function handleStatusEventPayload(data) {
  const percentValue = data?.status_percent;
  const hasPercent = Number.isFinite(Number(percentValue));
  const percent = hasPercent ? Number(percentValue) : null;

  if (percent !== null) {
    setProgress(percent);
  }

  const shouldLoadResult = Boolean(data?.result_ready) || (percent !== null && percent >= 100);
  if (!shouldLoadResult) {
    showOnly(statusPanel);
    return;
  }

  try {
    await fetchResultForActiveUpload();
    if (hasReceivedResult(activeUuid)) {
      stopStatusStream();
    }
  } catch (error) {
    showMessage(error instanceof Error ? error.message : "Failed to load result.");
  }
}

function startStatusStream(mode = "processing") {
  stopStatusStream();
  setStatusMode(mode);
  showOnly(statusPanel);

  if (!activeUuid) {
    return;
  }

  const stream = new EventSource(buildUrl(`/api/events/${activeUuid}`));
  statusEventSource = stream;

  stream.onmessage = (event) => {
    if (!event?.data) {
      return;
    }

    try {
      const payload = JSON.parse(event.data);
      void handleStatusEventPayload(payload);
    } catch (error) {
      showMessage(error instanceof Error ? error.message : "Invalid stream payload.");
    }
  };

  stream.onerror = async () => {
    if (!activeUuid) {
      return;
    }

    // EventSource auto-reconnects; this one-off fetch keeps UI fresh when stream blips.
    try {
      await fetchResultForActiveUpload();
    } catch {
      // Ignore transient failures; EventSource will retry.
    }
  };
}

async function handleUpload(event) {
  event.preventDefault();
  clearMessage();

  if (!hasSelectedImage()) {
    showMessage("Please select an image file.");
    return;
  }

  if (!arePointFieldsFilled()) {
    showMessage("Please fill in all point coordinates before uploading.");
    return;
  }

  const parsedCoords = parseCoordinateLine(pointsLineInput.value);
  if (!parsedCoords) {
    showMessage(
      "Please enter valid comma-separated coordinates: latA, lngA, latB, lngB."
    );
    return;
  }

  const { lat1, lng1, lat2, lng2 } = parsedCoords;

  const bbox = {
    points: [
      { lat: lat1, lng: lng1 },
      { lat: lat2, lng: lng2 },
    ],
  };

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("bounding_box", JSON.stringify(bbox));

  uploadForm.dataset.processing = "true";
  setInputsDisabled(true);

  try {
    const response = await fetchWithRetry(buildUrl("/api/upload"), {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!data.uuid) {
      throw new Error("Upload did not return a UUID.");
    }

    activeUuid = String(data.uuid);
    setCookie(COOKIE_NAME, activeUuid, COOKIE_MAX_AGE);
    setResultReceived(activeUuid, false);
    setProgress(0);
    startStatusStream("processing");
  } catch (error) {
    uploadForm.dataset.processing = "false";
    setInputsDisabled(false);
    showMessage(error instanceof Error ? error.message : "Upload failed.");
  }
}

function resetForNewMap() {
  stopStatusStream();
  activeUuid = null;
  clearCookie(COOKIE_NAME);
  clearMessage();

  uploadForm.reset();
  clearPreview();
  closeFullscreenPreview();
  resultOverlays.innerHTML = "";
  if (resultOverlaysFullscreen) {
    resultOverlaysFullscreen.innerHTML = "";
  }
  overlayList.innerHTML = "";
  if (overlayListFullscreen) {
    overlayListFullscreen.innerHTML = "";
  }
  downloadsList.innerHTML = "";
  resultImage.removeAttribute("src");
  if (resultImageFullscreen) {
    resultImageFullscreen.removeAttribute("src");
  }
  setStatusMode("processing");
  setProgress(0);

  uploadForm.dataset.processing = "false";
  setInputsDisabled(false);
  updateSubmitState();
  showOnly(uploadPanel);
}

function init() {
  initTheme();

  if (!API_URL) {
    showMessage("Missing VITE_API_URL Vite environment variable.");
    setInputsDisabled(true);
    return;
  }

  uploadForm.addEventListener("submit", handleUpload);
  fileInput.addEventListener("change", () => {
    updatePreview();
    updateSubmitState();
  });
  pointsLineInput.addEventListener("input", updateSubmitState);
  newMapBtn.addEventListener("click", resetForNewMap);
  if (resultMapStack) {
    resultMapStack.addEventListener("click", openFullscreenPreview);
  }
  if (resultFullscreenClose) {
    resultFullscreenClose.addEventListener("click", closeFullscreenPreview);
  }
  if (resultFullscreenModal) {
    resultFullscreenModal.addEventListener("click", (event) => {
      const target = event.target;
      if (target instanceof HTMLElement && target.dataset.closeFullscreen === "true") {
        closeFullscreenPreview();
      }
    });
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeFullscreenPreview();
    }
  });

  const rememberedUuid = getCookie(COOKIE_NAME);
  if (rememberedUuid) {
    activeUuid = rememberedUuid;
    setInputsDisabled(true);
    if (hasReceivedResult(activeUuid)) {
      startStatusStream("loading-result");
    } else {
      setProgress(0);
      startStatusStream("processing");
    }
    return;
  }

  showOnly(uploadPanel);
  updateSubmitState();
}

init();
