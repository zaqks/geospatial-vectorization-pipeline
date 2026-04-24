import { RESULT_RECEIVED_PREFIX } from "./config.js";

const MAP_DB_NAME = "geovec_maps";
const MAP_DB_VERSION = 2;
const MAP_STORE_NAME = "maps";
const OVERLAY_STORE_NAME = "overlays";
const MAP_BLOB_CACHE_PREFIX = "geovec_map_blob_";
const OVERLAY_BLOB_CACHE_PREFIX = "geovec_overlay_blob_";

let mapDbPromise = null;

function resultReceivedKey(uuid) {
  return `${RESULT_RECEIVED_PREFIX}${uuid}`;
}

function mapBlobCacheKey(uuid) {
  return `${MAP_BLOB_CACHE_PREFIX}${uuid}`;
}

function overlayBlobCacheKey(cacheKey) {
  return `${OVERLAY_BLOB_CACHE_PREFIX}${cacheKey}`;
}

function dataUrlToBlob(dataUrl) {
  if (!dataUrl || typeof dataUrl !== "string" || !dataUrl.startsWith("data:")) {
    return null;
  }

  const commaIndex = dataUrl.indexOf(",");
  if (commaIndex === -1) {
    return null;
  }

  const header = dataUrl.slice(5, commaIndex);
  const payload = dataUrl.slice(commaIndex + 1);
  const isBase64 = /;base64/i.test(header);
  const mimeType = header.split(";")[0] || "application/octet-stream";

  try {
    if (isBase64) {
      const binary = window.atob(payload);
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
      }
      return new Blob([bytes], { type: mimeType });
    }

    return new Blob([decodeURIComponent(payload)], { type: mimeType });
  } catch {
    return null;
  }
}

async function blobToDataUrl(blob) {
  if (!(blob instanceof Blob)) {
    return null;
  }

  return await new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => {
      resolve(typeof reader.result === "string" ? reader.result : null);
    };
    reader.onerror = () => resolve(null);
    reader.readAsDataURL(blob);
  });
}

function readCachedBlob(cacheKey) {
  if (!cacheKey) {
    return null;
  }

  const cachedDataUrl = window.localStorage.getItem(cacheKey);
  return dataUrlToBlob(cachedDataUrl);
}

async function writeCachedBlob(cacheKey, blob) {
  if (!cacheKey || !(blob instanceof Blob)) {
    return;
  }

  const dataUrl = await blobToDataUrl(blob);
  if (!dataUrl) {
    return;
  }

  try {
    window.localStorage.setItem(cacheKey, dataUrl);
  } catch {
    // Ignore storage quota failures and keep the IndexedDB copy.
  }
}

export function setResultReceived(uuid, received) {
  if (!uuid) {
    return;
  }

  window.localStorage.setItem(resultReceivedKey(uuid), received ? "true" : "false");
}

export function hasReceivedResult(uuid) {
  if (!uuid) {
    return false;
  }

  return window.localStorage.getItem(resultReceivedKey(uuid)) === "true";
}

function openMapDb() {
  if (mapDbPromise) {
    return mapDbPromise;
  }

  if (!("indexedDB" in window)) {
    return Promise.resolve(null);
  }

  mapDbPromise = new Promise((resolve) => {
    const request = window.indexedDB.open(MAP_DB_NAME, MAP_DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(MAP_STORE_NAME)) {
        db.createObjectStore(MAP_STORE_NAME, { keyPath: "uuid" });
      }
      if (!db.objectStoreNames.contains(OVERLAY_STORE_NAME)) {
        db.createObjectStore(OVERLAY_STORE_NAME, { keyPath: "key" });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => resolve(null);
  });

  return mapDbPromise;
}

export async function saveMapBlob(uuid, blob) {
  if (!uuid || !(blob instanceof Blob)) {
    return;
  }

  await writeCachedBlob(mapBlobCacheKey(uuid), blob);

  const db = await openMapDb();
  if (!db) {
    return;
  }

  await new Promise((resolve) => {
    const tx = db.transaction(MAP_STORE_NAME, "readwrite");
    tx.objectStore(MAP_STORE_NAME).put({ uuid, blob, savedAt: Date.now() });
    tx.oncomplete = () => resolve();
    tx.onerror = () => resolve();
    tx.onabort = () => resolve();
  });
}

export async function getMapBlob(uuid) {
  if (!uuid) {
    return null;
  }

  const cachedBlob = readCachedBlob(mapBlobCacheKey(uuid));
  if (cachedBlob) {
    return cachedBlob;
  }

  const db = await openMapDb();
  if (!db) {
    return null;
  }

  return new Promise((resolve) => {
    const tx = db.transaction(MAP_STORE_NAME, "readonly");
    const request = tx.objectStore(MAP_STORE_NAME).get(uuid);
    request.onsuccess = () => {
      const record = request.result;
      resolve(record?.blob instanceof Blob ? record.blob : null);
    };
    request.onerror = () => resolve(null);
  });
}

export async function deleteMapBlob(uuid) {
  if (!uuid) {
    return;
  }

  const db = await openMapDb();
  if (!db) {
    return;
  }

  await new Promise((resolve) => {
    const tx = db.transaction(MAP_STORE_NAME, "readwrite");
    tx.objectStore(MAP_STORE_NAME).delete(uuid);
    tx.oncomplete = () => resolve();
    tx.onerror = () => resolve();
    tx.onabort = () => resolve();
  });
}

export function buildOverlayCacheKey(uuid, overlayName, index) {
  return `${uuid}::${index}::${overlayName}`;
}

export async function saveOverlayBlob(cacheKey, uuid, blob) {
  if (!cacheKey || !uuid || !(blob instanceof Blob)) {
    return;
  }

  await writeCachedBlob(overlayBlobCacheKey(cacheKey), blob);

  const db = await openMapDb();
  if (!db) {
    return;
  }

  await new Promise((resolve) => {
    const tx = db.transaction(OVERLAY_STORE_NAME, "readwrite");
    tx.objectStore(OVERLAY_STORE_NAME).put({ key: cacheKey, uuid, blob, savedAt: Date.now() });
    tx.oncomplete = () => resolve();
    tx.onerror = () => resolve();
    tx.onabort = () => resolve();
  });
}

export async function getOverlayBlob(cacheKey) {
  if (!cacheKey) {
    return null;
  }

  const cachedBlob = readCachedBlob(overlayBlobCacheKey(cacheKey));
  if (cachedBlob) {
    return cachedBlob;
  }

  const db = await openMapDb();
  if (!db) {
    return null;
  }

  return new Promise((resolve) => {
    const tx = db.transaction(OVERLAY_STORE_NAME, "readonly");
    const request = tx.objectStore(OVERLAY_STORE_NAME).get(cacheKey);
    request.onsuccess = () => {
      const record = request.result;
      resolve(record?.blob instanceof Blob ? record.blob : null);
    };
    request.onerror = () => resolve(null);
  });
}

export async function deleteOverlayBlobs(uuid) {
  if (!uuid) {
    return;
  }

  const db = await openMapDb();
  if (!db) {
    return;
  }

  await new Promise((resolve) => {
    const tx = db.transaction(OVERLAY_STORE_NAME, "readwrite");
    const store = tx.objectStore(OVERLAY_STORE_NAME);
    const cursorRequest = store.openCursor();

    cursorRequest.onsuccess = () => {
      const cursor = cursorRequest.result;
      if (!cursor) {
        return;
      }

      const record = cursor.value;
      if (record?.uuid === uuid) {
        cursor.delete();
      }

      cursor.continue();
    };

    tx.oncomplete = () => resolve();
    tx.onerror = () => resolve();
    tx.onabort = () => resolve();
  });
}

export function clearLegacyResultImageCache() {
  const keysToDelete = [];

  for (let i = 0; i < window.localStorage.length; i += 1) {
    const key = window.localStorage.key(i);
    if (!key || !key.startsWith("geovec_result_image_")) {
      continue;
    }

    const value = window.localStorage.getItem(key) || "";
    if (value.startsWith("data:")) {
      keysToDelete.push(key);
    }
  }

  keysToDelete.forEach((key) => {
    window.localStorage.removeItem(key);
  });
}
