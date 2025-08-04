import { sequence } from '@sveltejs/kit/hooks';

// Security headers
const securityHeaders = async ({ event, resolve }) => {
    const response = await resolve(event);
    
    response.headers.set('X-Frame-Options', 'DENY');
    response.headers.set('X-Content-Type-Options', 'nosniff');
    response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
    response.headers.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
    
    return response;
};

// Session handling
const handleSession = async ({ event, resolve }) => {
    const sessionId = event.cookies.get('session');
    
    if (sessionId) {
        // In production, validate session from Redis/DB
        event.locals.session = await getSession(sessionId);
    }
    
    return await resolve(event);
};

async function getSession(sessionId) {
    // Implement session retrieval
    return null;
}

export const handle = sequence(securityHeaders, handleSession);

// src/lib/utils/validation.js
export function validateGitHubToken(token) {
    // GitHub personal access tokens start with ghp_
    const pattern = /^ghp_[a-zA-Z0-9]{36}$/;
    return pattern.test(token);
}

export function validateRepoName(name) {
    // owner/repo format
    const pattern = /^[a-zA-Z0-9-_]+\/[a-zA-Z0-9-_.]+$/;
    return pattern.test(name);
}

export function sanitizeInput(input) {
    // Basic XSS prevention
    return input
        .replace(/[<>]/g, '')
        .replace(/javascript:/gi, '')
        .replace(/on\w+=/gi, '');
}

// src/lib/utils/rateLimit.js
export class RateLimiter {
    constructor(maxRequests = 10, windowMs = 60000) {
        this.maxRequests = maxRequests;
        this.windowMs = windowMs;
        this.requests = new Map();
    }
    
    check(key) {
        const now = Date.now();
        const windowStart = now - this.windowMs;
        
        if (!this.requests.has(key)) {
            this.requests.set(key, []);
        }
        
        const userRequests = this.requests.get(key);
        const recentRequests = userRequests.filter(time => time > windowStart);
        
        if (recentRequests.length >= this.maxRequests) {
            return {
                allowed: false,
                remaining: 0,
                resetAt: new Date(recentRequests[0] + this.windowMs)
            };
        }
        
        recentRequests.push(now);
        this.requests.set(key, recentRequests);
        
        return {
            allowed: true,
            remaining: this.maxRequests - recentRequests.length,
            resetAt: new Date(recentRequests[0] + this.windowMs)
        };
    }
    
    // Clean up old entries periodically
    cleanup() {
        const windowStart = Date.now() - this.windowMs;
        
        for (const [key, requests] of this.requests.entries()) {
            const recent = requests.filter(time => time > windowStart);
            if (recent.length === 0) {
                this.requests.delete(key);
            } else {
                this.requests.set(key, recent);
            }
        }
    }
}