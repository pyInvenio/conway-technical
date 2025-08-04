import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:8000';

export const GET: RequestHandler = async ({ url, fetch }) => {
    const repoId = url.searchParams.get('id');
    
    if (!repoId) {
        return json({ error: 'Repository ID required' }, { status: 400 });
    }

    try {
        // Fetch repository context from backend
        const backendUrl = `${BACKEND_URL}/data/repository/${encodeURIComponent(repoId)}`;
        const response = await fetch(backendUrl);
        
        if (!response.ok) {
            throw new Error(`Backend returned ${response.status}`);
        }
        
        const data = await response.json();
        
        // Add any additional context or processing here
        return json({
            repository: data,
            additionalContext: {
                // Add any frontend-specific context here
                isMonitored: true,
                lastChecked: new Date().toISOString()
            }
        });
    } catch (error) {
        console.error('Error fetching repository context:', error);
        return json({ error: 'Failed to fetch repository context' }, { status: 500 });
    }
};