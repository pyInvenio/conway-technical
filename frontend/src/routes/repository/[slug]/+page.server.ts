import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:8000';

export const load: PageServerLoad = async ({ params, cookies }) => {
  const { slug } = params;
  const sessionId = cookies.get('session');
  
  try {
    // Decode repository name (e.g., microsoft%2Fvscode -> microsoft/vscode)
    const repoName = decodeURIComponent(slug);
    
    if (sessionId) {
      // Fetch repository details, anomalies, and statistics
      const [repoResponse, anomaliesResponse, statsResponse] = await Promise.allSettled([
        fetch(`${BACKEND_URL}/repository/${encodeURIComponent(repoName)}`, {
          headers: { 'Cookie': `session=${sessionId}` }
        }),
        fetch(`${BACKEND_URL}/anomalies?repo=${encodeURIComponent(repoName)}&limit=50`, {
          headers: { 'Cookie': `session=${sessionId}` }
        }),
        fetch(`${BACKEND_URL}/api/v1/anomalies/stats/summary?days=30`, {
          headers: { 'Cookie': `session=${sessionId}` }
        })
      ]);

      const repository = repoResponse.status === 'fulfilled' && repoResponse.value.ok 
        ? await repoResponse.value.json() 
        : null;

      const anomalies = anomaliesResponse.status === 'fulfilled' && anomaliesResponse.value.ok 
        ? await anomaliesResponse.value.json() 
        : { anomalies: [], pagination: { page: 1, limit: 50, total: 0, pages: 0, has_next: false, has_prev: false } };

      const stats = statsResponse.status === 'fulfilled' && statsResponse.value.ok 
        ? await statsResponse.value.json() 
        : null;

      if (!repository) {
        throw error(404, 'Repository not found');
      }

      return {
        repository: {
          ...repository,
          anomalies: anomalies.anomalies
        },
        anomaliesPagination: anomalies.pagination,
        globalStats: stats
      };
    }

    throw error(401, 'Authentication required');
  } catch (err) {
    console.error('Failed to fetch repository data:', err);
    throw error(500, 'Failed to load repository');
  }
};