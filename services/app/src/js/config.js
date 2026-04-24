export const COOKIE_NAME = "upload_uuid";
export const COOKIE_MAX_AGE = 60 * 60 * 24 * 365;
export const FETCH_TIMEOUT_MS = 180 * 1000;
export const FETCH_RETRIES = 3;
export const RETRY_DELAY_MS = 1000;
export const THEME_STORAGE_KEY = "geovec_theme";
export const RESULT_RECEIVED_PREFIX = "geovec_result_received_";
export const OVERLAY_IMAGE_TIMEOUT_MS = 60 * 1000;

const RAW_API_URL = import.meta.env.VITE_API_URL || import.meta.env.API_URL || "";
export const API_URL = String(RAW_API_URL).replace(/\/$/, "");
