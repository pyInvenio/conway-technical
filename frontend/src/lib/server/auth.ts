// Simple in-memory session store (use Redis in production!)
const tokenSessions = new Map();

// Helper to get session
export async function getSession(sessionId: string) {
    const session = tokenSessions.get(sessionId);
    
    // Check if session exists and isn't expired
    if (session && Date.now() - session.createdAt < 7 * 24 * 60 * 60 * 1000) {
        return session;
    }
    
    return null;
}

// Helper to store session
export function setSession(sessionId: string, sessionData: any) {
    tokenSessions.set(sessionId, sessionData);
}

// Helper to remove session (logout)
export function removeSession(sessionId: string) {
    return tokenSessions.delete(sessionId);
}

export { tokenSessions };