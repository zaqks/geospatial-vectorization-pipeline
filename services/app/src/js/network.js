import {
  API_URL,
  FETCH_RETRIES,
  FETCH_TIMEOUT_MS,
  OVERLAY_IMAGE_TIMEOUT_MS,
  RETRY_DELAY_MS,
} from "./config.js";

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export function buildUrl(path) {
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

export async function fetchWithTimeout(url, options = {}, timeoutMs = FETCH_TIMEOUT_MS) {
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

export async function fetchWithRetry(
  url,
  options = {},
  { timeoutMs = FETCH_TIMEOUT_MS, retries = FETCH_RETRIES } = {}
) {
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

export async function loadOverlayImage(url) {
  if (!url) {
    return null;
  }

  try {
    const response = await fetchWithTimeout(url, {}, OVERLAY_IMAGE_TIMEOUT_MS);
    if (!response.ok) {
      throw new Error(`Request failed (${response.status})`);
    }

    const blob = await response.blob();
    return blob;
  } catch {
    return null;
  }
}
