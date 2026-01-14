export type ApiSettings = {
  apiUrl: string;
};

const resolveApiUrlFromWindow = () => {
  if (typeof window === 'undefined') return '';

  const win = window as unknown as { __API_BASE_URL__?: string };
  if (win.__API_BASE_URL__) return win.__API_BASE_URL__;

  // Vite-style env var support (if available)
  const meta = (import.meta as unknown as { env?: Record<string, string> });
  const envUrl = meta?.env?.VITE_API_URL;
  if (envUrl) return envUrl;

  if (window.location?.hostname) {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }

  return '';
};

export const getApiSettings = (): ApiSettings => {
  const apiUrl = resolveApiUrlFromWindow() || 'http://localhost:8000';
  return { apiUrl };
};

export const buildApiUrl = (path: string): string => {
  const { apiUrl } = getApiSettings();
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${apiUrl}${normalizedPath}`;
};
