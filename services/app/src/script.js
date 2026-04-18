const COOKIE_NAME = "upload_uuid";
const COOKIE_MAX_AGE = 60 * 60 * 24;
const POLL_INTERVAL_MS = 5000;

const RAW_API_URL = import.meta.env.VITE_API_URL || import.meta.env.API_URL || "";
const API_URL = String(RAW_API_URL).replace(/\/$/, "");

const uploadPanel = document.getElementById("upload-panel");
const statusPanel = document.getElementById("status-panel");
const resultPanel = document.getElementById("result-panel");
const messagePanel = document.getElementById("message-panel");

const uploadForm = document.getElementById("upload-form");
const submitBtn = document.getElementById("submit-btn");
const newMapBtn = document.getElementById("new-map-btn");

const fileInput = document.getElementById("map-file");
const lat1Input = document.getElementById("lat-1");
const lng1Input = document.getElementById("lng-1");
const lat2Input = document.getElementById("lat-2");
const lng2Input = document.getElementById("lng-2");

const statusPercent = document.getElementById("status-percent");
const resultImage = document.getElementById("result-image");
const downloadsList = document.getElementById("downloads-list");
const messageText = document.getElementById("message-text");

let activeUuid = null;
let pollTimer = null;

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
}

function showMessage(message) {
  messageText.textContent = message;
  showOnly(messagePanel);
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

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

function setInputsDisabled(disabled) {
  fileInput.disabled = disabled;
  lat1Input.disabled = disabled;
  lng1Input.disabled = disabled;
  lat2Input.disabled = disabled;
  lng2Input.disabled = disabled;
  submitBtn.disabled = disabled;
}

function renderResult(data) {
  const imageUrl = buildUrl(data.img_url || "");
  resultImage.src = imageUrl;

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

  showOnly(resultPanel);
}

async function pollOnce() {
  if (!activeUuid) {
    return;
  }

  try {
    const response = await fetch(buildUrl(`/api/result/${activeUuid}`));
    if (!response.ok) {
      throw new Error(`Polling failed (${response.status})`);
    }

    const data = await response.json();
    const percent = Number(data.status_percent ?? 0);
    statusPercent.textContent = Number.isFinite(percent) ? String(percent) : "0";

    if (percent >= 100 && data.img_url) {
      stopPolling();
      renderResult(data);
    } else {
      showOnly(statusPanel);
    }
  } catch (error) {
    stopPolling();
    showMessage(error instanceof Error ? error.message : "Polling failed.");
  }
}

function startPolling() {
  stopPolling();
  showOnly(statusPanel);
  pollOnce();
  pollTimer = window.setInterval(pollOnce, POLL_INTERVAL_MS);
}

async function handleUpload(event) {
  event.preventDefault();
  clearMessage();

  if (!fileInput.files || fileInput.files.length === 0) {
    showMessage("Please select an image file.");
    return;
  }

  const lat1 = Number(lat1Input.value);
  const lng1 = Number(lng1Input.value);
  const lat2 = Number(lat2Input.value);
  const lng2 = Number(lng2Input.value);

  if (![lat1, lng1, lat2, lng2].every(Number.isFinite)) {
    showMessage("Please enter valid latitude and longitude values.");
    return;
  }

  const bbox = [
    [lat1, lng1],
    [lat2, lng2],
  ];

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("bounding_box", JSON.stringify(bbox));

  setInputsDisabled(true);

  try {
    const response = await fetch(buildUrl("/api/upload"), {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Upload failed (${response.status})`);
    }

    const data = await response.json();
    if (!data.uuid) {
      throw new Error("Upload did not return a UUID.");
    }

    activeUuid = String(data.uuid);
    setCookie(COOKIE_NAME, activeUuid, COOKIE_MAX_AGE);
    statusPercent.textContent = "0";
    startPolling();
  } catch (error) {
    setInputsDisabled(false);
    showMessage(error instanceof Error ? error.message : "Upload failed.");
  }
}

function resetForNewMap() {
  stopPolling();
  activeUuid = null;
  clearCookie(COOKIE_NAME);
  clearMessage();

  uploadForm.reset();
  downloadsList.innerHTML = "";
  resultImage.removeAttribute("src");
  statusPercent.textContent = "0";

  setInputsDisabled(false);
  showOnly(uploadPanel);
}

function init() {
  if (!API_URL) {
    showMessage("Missing VITE_API_URL Vite environment variable.");
    setInputsDisabled(true);
    return;
  }

  uploadForm.addEventListener("submit", handleUpload);
  newMapBtn.addEventListener("click", resetForNewMap);

  const rememberedUuid = getCookie(COOKIE_NAME);
  if (rememberedUuid) {
    activeUuid = rememberedUuid;
    setInputsDisabled(true);
    startPolling();
    return;
  }

  showOnly(uploadPanel);
}

init();
