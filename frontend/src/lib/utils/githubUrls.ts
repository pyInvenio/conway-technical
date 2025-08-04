/**
 * GitHub URL Generator - Creates specific GitHub URLs based on event type and payload
 */

export interface GitHubEventPayload {
  // PushEvent specific
  head?: string;
  before?: string;
  commits?: Array<{
    sha: string;
    message: string;
    url: string;
  }>;
  
  // DeleteEvent specific  
  ref?: string;
  ref_type?: 'branch' | 'tag';
  pusher_type?: string;
  
  // PullRequestEvent specific
  pull_request?: {
    number: number;
    html_url: string;
  };
  
  // IssuesEvent specific
  issue?: {
    number: number;
    html_url: string;
  };
  
  // WorkflowRunEvent specific
  workflow_run?: {
    id: number;
    html_url: string;
  };
  
  // ForkEvent specific
  forkee?: {
    html_url: string;
  };
}

/**
 * Generate specific GitHub URL based on event type and payload
 */
export function generateGitHubEventUrl(
  eventType: string,
  repositoryName: string,
  payload: GitHubEventPayload | null,
  fallbackToRepo: boolean = true
): string {
  const baseRepoUrl = `https://github.com/${repositoryName}`;
  
  if (!payload) {
    return fallbackToRepo ? baseRepoUrl : '';
  }

  try {
    switch (eventType) {
      case 'PushEvent':
        return generatePushEventUrl(baseRepoUrl, payload);
      
      case 'DeleteEvent':
        return generateDeleteEventUrl(baseRepoUrl, payload);
      
      case 'PullRequestEvent':
        if (payload.pull_request?.html_url) {
          return payload.pull_request.html_url;
        }
        break;
      
      case 'IssuesEvent':
        if (payload.issue?.html_url) {
          return payload.issue.html_url;
        }
        break;
      
      case 'WorkflowRunEvent':
        if (payload.workflow_run?.html_url) {
          return payload.workflow_run.html_url;
        }
        return `${baseRepoUrl}/actions`;
      
      case 'ForkEvent':
        if (payload.forkee?.html_url) {
          return payload.forkee.html_url;
        }
        return `${baseRepoUrl}/forks`;
      
      case 'MemberEvent':
        return `${baseRepoUrl}/settings/access`;
      
      case 'ReleaseEvent':
        return `${baseRepoUrl}/releases`;
      
      default:
        // For other event types, try to find a relevant URL in payload
        if (payload && typeof payload === 'object') {
          // Check for common URL fields
          const urlFields = ['html_url', 'url', 'compare'];
          for (const field of urlFields) {
            const url = (payload as any)[field];
            if (url && typeof url === 'string' && url.includes('github.com')) {
              return url;
            }
          }
        }
        break;
    }
  } catch (error) {
    console.warn('Error generating GitHub URL:', error);
  }

  return fallbackToRepo ? baseRepoUrl : '';
}

/**
 * Generate URL for PushEvent - links to commit or compare view
 */
function generatePushEventUrl(baseRepoUrl: string, payload: GitHubEventPayload): string {
  // If there's a compare URL in the payload, use it
  if ((payload as any).compare) {
    return (payload as any).compare;
  }
  
  // If there are commits, link to the latest commit
  if (payload.commits && payload.commits.length > 0) {
    const latestCommit = payload.commits[payload.commits.length - 1];
    if (latestCommit.sha) {
      return `${baseRepoUrl}/commit/${latestCommit.sha}`;
    }
  }
  
  // If there's a head commit SHA, link to it
  if (payload.head) {
    return `${baseRepoUrl}/commit/${payload.head}`;
  }
  
  // Fallback to commits page
  return `${baseRepoUrl}/commits`;
}

/**
 * Generate URL for DeleteEvent - links to branches/tags page with context
 */
function generateDeleteEventUrl(baseRepoUrl: string, payload: GitHubEventPayload): string {
  const refType = payload.ref_type || 'branch';
  const refName = payload.ref;
  
  if (refType === 'branch') {
    // Link to branches page since the branch no longer exists
    return `${baseRepoUrl}/branches`;
  } else if (refType === 'tag') {
    // Link to tags/releases page since the tag no longer exists  
    return `${baseRepoUrl}/tags`;
  }
  
  // Generic fallback
  return `${baseRepoUrl}/branches`;
}

/**
 * Generate commit-specific URLs for detailed analysis
 */
export function generateCommitUrls(
  repositoryName: string,
  payload: GitHubEventPayload | null
): Array<{sha: string, url: string, message: string}> {
  if (!payload || !payload.commits) {
    return [];
  }
  
  const baseRepoUrl = `https://github.com/${repositoryName}`;
  
  return payload.commits.map(commit => ({
    sha: commit.sha,
    url: commit.url || `${baseRepoUrl}/commit/${commit.sha}`,
    message: commit.message || 'No commit message'
  }));
}

/**
 * Get a human-readable description of what the event URL shows
 */
export function getEventUrlDescription(eventType: string, payload: GitHubEventPayload | null): string {
  switch (eventType) {
    case 'PushEvent':
      if (payload?.commits && payload.commits.length > 0) {
        const count = payload.commits.length;
        return count === 1 ? 'View commit' : `View ${count} commits`;
      }
      return 'View push details';
    
    case 'DeleteEvent':
      const refType = payload?.ref_type || 'branch';
      const refName = payload?.ref;
      return refName ? `View deleted ${refType}: ${refName}` : `View deleted ${refType}`;
    
    case 'PullRequestEvent':
      return 'View pull request';
    
    case 'IssuesEvent':
      return 'View issue';
    
    case 'WorkflowRunEvent':
      return 'View workflow run';
    
    case 'ForkEvent':
      return 'View forked repository';
    
    case 'MemberEvent':
      return 'View repository access';
    
    case 'ReleaseEvent':
      return 'View release';
    
    default:
      return 'View on GitHub';
  }
}

/**
 * Generate URLs for the pattern analysis recommendations
 */
export function generateInvestigationUrls(
  repositoryName: string,
  eventType: string,
  userLogin: string,
  payload: GitHubEventPayload | null
) {
  const baseRepoUrl = `https://github.com/${repositoryName}`;
  
  return {
    // User's recent activity on this repo
    userActivity: `${baseRepoUrl}/commits?author=${userLogin}`,
    
    // Repository's recent activity
    repoActivity: `${baseRepoUrl}/commits`,
    
    // Repository security settings
    securitySettings: `${baseRepoUrl}/settings/security_analysis`,
    
    // Repository access settings
    accessSettings: `${baseRepoUrl}/settings/access`,
    
    // Specific event URL
    eventUrl: generateGitHubEventUrl(eventType, repositoryName, payload),
    
    // User profile
    userProfile: `https://github.com/${userLogin}`,
    
    // Repository insights
    insights: `${baseRepoUrl}/pulse`
  };
}