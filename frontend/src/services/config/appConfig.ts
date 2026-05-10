const appName = import.meta.env.VITE_APP_NAME || "DrCT에셋";
const dataSource = (import.meta.env.VITE_DATA_SOURCE || "mock").toLowerCase();
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export const appConfig = {
  appName,
  dataSource,
  apiBaseUrl,
};
