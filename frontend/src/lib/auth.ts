export const AUTH_COOKIE_NAME = "alphalens_access_token";
export const AUTH_STORAGE_KEY = "alphalens.access_token";
export const AUTH_REFRESH_COOKIE_NAME = "alphalens_refresh_token";

export const AUTH_ROUTES = new Set(["/login", "/register"]);

export function isProtectedPath(pathname: string): boolean {
  if (pathname.startsWith("/api") || pathname.startsWith("/_next")) {
    return false;
  }
  return !AUTH_ROUTES.has(pathname);
}

export function setStoredToken(token: string) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(AUTH_STORAGE_KEY, token);
  document.cookie = `${AUTH_COOKIE_NAME}=${encodeURIComponent(token)}; Path=/; SameSite=Lax; Max-Age=${60 * 60 * 24 * 7}`;
}

export function setRefreshToken(token: string) {
  if (typeof window === "undefined") return;
  document.cookie = `${AUTH_REFRESH_COOKIE_NAME}=${encodeURIComponent(token)}; Path=/; SameSite=Lax; Max-Age=${60 * 60 * 24 * 14}`;
}

export function clearStoredToken() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  document.cookie = `${AUTH_COOKIE_NAME}=; Path=/; SameSite=Lax; Max-Age=0`;
  document.cookie = `${AUTH_REFRESH_COOKIE_NAME}=; Path=/; SameSite=Lax; Max-Age=0`;
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  const localValue = window.localStorage.getItem(AUTH_STORAGE_KEY);
  if (localValue) {
    return localValue;
  }
  const cookie = document.cookie
    .split("; ")
    .find((entry) => entry.startsWith(`${AUTH_COOKIE_NAME}=`));
  if (!cookie) {
    return null;
  }
  return decodeURIComponent(cookie.split("=")[1] ?? "");
}
