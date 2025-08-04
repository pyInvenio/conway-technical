// API configuration
export const API_BASE_URL = import.meta.env.SSR 
  ? 'http://localhost:8000'  // Server-side rendering (internal container communication)
  : '';  // Client-side (use relative URLs that go through Caddy)

export const WS_URL = import.meta.env.SSR
  ? 'ws://localhost:8000/ws'
  : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}://${window.location.host}/ws`;