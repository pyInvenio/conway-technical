// src/routes/api/auth/validate/+server.js
import { json } from '@sveltejs/kit';
import { setSession } from '$lib/server/auth';

export async function POST({ request, cookies }) {
    try {
        // Get token from request body
        const { token } = await request.json();
        
        if (!token || typeof token !== 'string') {
            return json({ message: 'Invalid token format' }, { status: 400 });
        }
        
        // Validate token with GitHub API
        const response = await fetch('https://api.github.com/user', {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28'
            }
        });
        
        if (!response.ok) {
            return json({ message: 'Invalid GitHub token' }, { status: 401 });
        }
        
        // Get user data and rate limit info
        const user = await response.json();
        const rateLimit = {
            remaining: parseInt(response.headers.get('X-RateLimit-Remaining') || '0'),
            reset: parseInt(response.headers.get('X-RateLimit-Reset') || '0')
        };
        
        // Create a session ID
        const sessionId = crypto.randomUUID();
        
        // In production, store token in Redis/DB with this sessionId
        // For now, we'll use a simple in-memory store
        setSession(sessionId, {
            token,
            user: {
                login: user.login,
                avatar_url: user.avatar_url,
                name: user.name
            },
            createdAt: Date.now()
        });
        
        // Set secure session cookie
        cookies.set('session', sessionId, {
            path: '/',
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'strict',
            maxAge: 60 * 60 * 24 * 7 // 1 week
        });
        
        // Return user info (never return the token to client!)
        return json({ 
            user: {
                login: user.login,
                avatar_url: user.avatar_url,
                name: user.name
            },
            rateLimit
        });
        
    } catch (error) {
        console.error('Token validation error:', error);
        return json({ message: 'Failed to validate token' }, { status: 500 });
    }
}