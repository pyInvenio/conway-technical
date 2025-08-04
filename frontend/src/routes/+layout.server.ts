import { getSession } from '$lib/server/auth';

export async function load({ cookies }) {
  const sessionId = cookies.get("session");

  if (!sessionId) {
    return { user: null, githubToken: null };
  }

  try {
    const session = await getSession(sessionId);
    
    if (session) {
      return { 
        user: session.user,
        githubToken: session.token // Pass token to client for SSE connection
      };
    }
  } catch (error) {
    console.error("Session validation failed:", error);
  }

  return { user: null, githubToken: null };
}
