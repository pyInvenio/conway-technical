import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:8000';

export const load: PageServerLoad = async ({ params, cookies, setHeaders }) => {
  const { slug } = params;
  const sessionId = cookies.get('session');
  
  try {
    const repoName = decodeURIComponent(slug);
    
    if (sessionId) {
      const overviewResponse = await fetch(
        `${BACKEND_URL}/repository/${encodeURIComponent(repoName)}/overview?limit=20`, 
        {
          headers: { 'Cookie': `session=${sessionId}` }
        }
      );

      if (!overviewResponse.ok) {
        if (overviewResponse.status === 404) {
          throw error(404, 'Repository not found');
        }
        throw error(overviewResponse.status, 'Failed to fetch repository data');
      }

      const overviewData = await overviewResponse.json();
      
      // Optional: Fetch global stats in background (non-blocking)
      let globalStats = null;
      try {
        const statsResponse = await fetch(
          `${BACKEND_URL}/api/v1/anomalies/stats/summary?days=7`, // Reduced from 30 to 7 days
          {
            headers: { 'Cookie': `session=${sessionId}` },
            signal: AbortSignal.timeout(2000) // 2 second timeout
          }
        );
        if (statsResponse.ok) {
          globalStats = await statsResponse.json();
        }
      } catch (statsError) {
      }

      setHeaders({
        'cache-control': 'private, max-age=30'
      });

      return {
        repository: {
          ...overviewData.repository,
          anomalies: overviewData.anomalies
        },
        anomaliesPagination: overviewData.pagination,
        globalStats
      };
    }

    throw error(401, 'Authentication required');
  } catch (err) {
    if (err.status) {
      throw err; // Re-throw SvelteKit errors
    }
    throw error(500, 'Failed to load repository');
  }
};