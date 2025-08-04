import type { PageServerLoad } from './$types';
import { error } from '@sveltejs/kit';

const BACKEND_URL = 'http://localhost:8000';

export const load: PageServerLoad = async ({ params, cookies }) => {
  const session_id = cookies.get('session');
  
  if (!session_id) {
    throw error(401, 'Authentication required');
  }

  try {
    // Fetch event details and related anomalies from backend
    const [eventResponse, anomaliesResponse] = await Promise.allSettled([
      fetch(`${BACKEND_URL}/data/event/${params.id}`, {
        headers: { 'Cookie': `session=${session_id}` }
      }),
      fetch(`${BACKEND_URL}/api/v1/anomalies?event_id=${params.id}`, {
        headers: { 'Cookie': `session=${session_id}` }
      })
    ]);
    
    // Process event response
    if (eventResponse.status !== 'fulfilled' || !eventResponse.value.ok) {
      if (eventResponse.status === 'fulfilled' && eventResponse.value.status === 404) {
        throw error(404, 'Event not found');
      }
      throw error(500, 'Failed to fetch event details');
    }
    
    const event = await eventResponse.value.json();
    
    // Process anomalies response
    let relatedAnomalies = [];
    if (anomaliesResponse.status === 'fulfilled' && anomaliesResponse.value.ok) {
      const anomaliesData = await anomaliesResponse.value.json();
      relatedAnomalies = anomaliesData.anomalies || [];
    }
    
    return {
      event,
      relatedAnomalies
    };
  } catch (err) {
    if (err.status) {
      throw err;
    }
    console.error('Error loading event:', err);
    throw error(500, 'Internal server error');
  }
};