import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:8000';

async function fetchWithFallback(url: string, options: RequestInit = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    }
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  
  return response.json();
}

async function fetchInitialData(sessionId?: string) {
  const headers = sessionId ? { 'Cookie': `session=${sessionId}` } : {};
  
  try {
    // Try to fetch from SSR endpoint first
    return await fetchWithFallback(`${BACKEND_URL}/ssr/initial-data`, { headers });
  } catch (error) {
    console.warn('SSR endpoint failed, falling back to individual API calls:', error);
    
    // Fallback: fetch data from individual endpoints
    try {
      const [anomalies, metrics] = await Promise.allSettled([
        fetchWithFallback(`${BACKEND_URL}/api/v1/anomalies?page=1&limit=20`, { headers }),
        fetchWithFallback(`${BACKEND_URL}/metrics`, { headers })
      ]);
      
      const anomaliesData = anomalies.status === 'fulfilled' ? anomalies.value : {
        anomalies: [],
        pagination: { page: 1, limit: 20, total: 0, pages: 0, has_next: false, has_prev: false }
      };
      
      const metricsData = metrics.status === 'fulfilled' ? metrics.value : {
        totalEvents: 0,
        criticalAlerts: 0,
        repositories: 0,
        threatScore: 0.0
      };
      
      // Try to fetch repositories data if possible
      let repositoriesData = {
        repositories: [],
        pagination: { page: 1, limit: 20, total: 0, pages: 0, has_next: false, has_prev: false }
      };
      
      try {
        repositoriesData = await fetchWithFallback(`${BACKEND_URL}/repositories?page=1&limit=20`, { headers });
      } catch (repoError) {
        console.warn('Failed to fetch repositories data:', repoError);
      }
      
      return {
        anomalies: anomaliesData,
        metrics: metricsData,
        repositories: repositoriesData
      };
    } catch (fallbackError) {
      console.error('All fallback attempts failed:', fallbackError);
      return null;
    }
  }
}

export const load: PageServerLoad = async ({ cookies, url, parent }) => {
  const sessionId = cookies.get('session');
  
  // Get user and token from parent layout
  const { user, githubToken } = await parent();
  
  if (!user) {
    return {
      authenticated: false,
      user: null,
      githubToken: null,
      initialData: null
    };
  }
  
  // Fetch initial data for authenticated users
  const initialData = await fetchInitialData(sessionId);
  
  return {
    authenticated: true,
    user,
    githubToken,
    initialData
  };
};