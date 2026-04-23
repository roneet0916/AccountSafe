// src/api/apiClient.ts
import axios from 'axios';
import { forceLogout } from '../utils/logoutEvent';

// API base URL. Set REACT_APP_API_URL at build time (Vercel env var) to the
// Oracle backend, e.g. https://accountsafe.duckdns.org/api/ . Localhost is used
// only for dev; production builds without the env var are considered a
// misconfiguration and fail loudly in the browser console.
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/';
if (!process.env.REACT_APP_API_URL && process.env.NODE_ENV === 'production') {
  // eslint-disable-next-line no-console
  console.error('REACT_APP_API_URL is not set; API calls will fail in production.');
}

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor to add token to headers
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

// Response interceptor to handle 401 errors (revoked sessions)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // If session was revoked (401 Unauthorized), logout immediately
    // But only for session-validated requests, not login/auth endpoints
    if (error.response?.status === 401) {
      const currentPath = window.location.pathname;
      const requestUrl = error.config?.url || '';

      // Don't forceLogout if on auth pages or if the failing request
      // was to an auth endpoint (e.g. wrong password during re-auth)
      const authPages = ['/login', '/register', '/reset-password'];
      const authEndpoints = ['/zk/login/', '/zk/register/', '/zk/salt/', '/auth/login/', '/auth/register/', '/password-reset/'];
      const isAuthPage = authPages.includes(currentPath);
      const isAuthEndpoint = authEndpoints.some(ep => requestUrl.includes(ep));

      if (!isAuthPage && !isAuthEndpoint) {
        forceLogout();
      }
    }
    
    return Promise.reject(error);
  }
);

export default apiClient;

