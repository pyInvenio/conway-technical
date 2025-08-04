import { json } from '@sveltejs/kit';
import { removeSession } from '$lib/server/auth';

export async function POST({ cookies }) {
    const sessionId = cookies.get('session');
    
    if (sessionId) {
        // Remove session from server store
        removeSession(sessionId);
        
        // Clear the session cookie
        cookies.delete('session', { path: '/' });
    }
    
    return json({ success: true });
}