import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ url, fetch }) => {
    const userId = url.searchParams.get('id');
    
    if (!userId) {
        return json({ error: 'User ID required' }, { status: 400 });
    }

    try {
        // For now, return basic user context
        // In a real implementation, you might fetch from GitHub API or your backend
        const userContext = {
            login: userId,
            profileUrl: `https://github.com/${userId}`,
            avatarUrl: `https://avatars.githubusercontent.com/${userId}`,
            // Add risk assessment or historical data here
            riskLevel: 'normal',
            recentActivity: {
                commits: 0,
                pullRequests: 0,
                issues: 0
            }
        };
        
        return json({
            user: userContext,
            additionalContext: {
                isKnownContributor: false,
                lastActivity: new Date().toISOString()
            }
        });
    } catch (error) {
        console.error('Error fetching user context:', error);
        return json({ error: 'Failed to fetch user context' }, { status: 500 });
    }
};