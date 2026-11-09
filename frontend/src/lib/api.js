import axios from "axios";
import { useAuth } from "@clerk/react";
import { useCallback, useEffect, useState } from "react";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function useApi() {
  const { getToken } = useAuth();
  return useCallback(
    async (method, url, data, cfg = {}) => {
      const token = await getToken();
      const r = await axios({ method, url: `${API}${url}`, data, ...cfg, headers: { Authorization: `Bearer ${token}`, ...(cfg.headers || {}) } });
      return r.data;
    },
    [getToken]
  );
}

export function useFetch(url) {
  const api = useApi();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const reload = useCallback(async () => {
    if (!url) return;
    setLoading(true);
    try {
      setData(await api("get", url));
      setError(null);
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, [api, url]);
  useEffect(() => {
    reload();
  }, [reload]);
  return { data, loading, error, reload, setData };
}

export const errMsg = (e) => {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg).join("; ");
  return e?.message || "Erro inesperado";
};

export const qs = (obj) => {
  const p = new URLSearchParams();
  Object.entries(obj || {}).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && p.set(k, v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export async function downloadFile(api, url, filename, mode = "download") {
  const blob = await api("get", url, null, { responseType: "blob" });
  const href = URL.createObjectURL(blob);
  if (mode === "print") {
    const w = window.open(href, "_blank");
    if (w) w.onload = () => w.print();
    return;
  }
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(href), 4000);
}

export const fmt = (v) => (v === null || v === undefined ? "—" : typeof v === "number" ? v.toLocaleString("pt-BR") : v);
export const fmtDate = (iso) => (iso ? new Date(iso).toLocaleString("pt-BR") : "—");
