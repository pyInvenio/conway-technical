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
