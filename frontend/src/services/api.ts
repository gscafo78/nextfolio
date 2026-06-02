import axios from "axios";

export const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

function getStoredToken(key: string): string | null {
  return localStorage.getItem(key) ?? sessionStorage.getItem(key);
}

function setStoredToken(key: string, value: string) {
  const remember = localStorage.getItem("nf-remember") !== "0";
  (remember ? localStorage : sessionStorage).setItem(key, value);
}

// Single in-flight refresh promise shared across all concurrent 401 interceptors.
// Without this, N simultaneous expired-token requests each fire a refresh call;
// the first succeeds and rotates the token, the rest fail with the old token.
let refreshPromise: Promise<void> | null = null;

api.interceptors.request.use((config) => {
  const token = getStoredToken("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const refresh = getStoredToken("refresh_token");
      if (refresh) {
        try {
          if (!refreshPromise) {
            refreshPromise = axios
              .post("/api/v1/auth/refresh", { refresh_token: refresh })
              .then(({ data }) => {
                setStoredToken("access_token", data.access_token);
                setStoredToken("refresh_token", data.refresh_token);
              })
              .finally(() => {
                refreshPromise = null;
              });
          }
          await refreshPromise;
          original.headers.Authorization = `Bearer ${getStoredToken("access_token")}`;
          return api(original);
        } catch {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          sessionStorage.removeItem("access_token");
          sessionStorage.removeItem("refresh_token");
          window.location.href = "/login";
        }
      }
    }
    return Promise.reject(error);
  }
);
