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
          const { data } = await axios.post("/api/v1/auth/refresh", { refresh_token: refresh });
          setStoredToken("access_token", data.access_token);
          setStoredToken("refresh_token", data.refresh_token);
          original.headers.Authorization = `Bearer ${data.access_token}`;
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
