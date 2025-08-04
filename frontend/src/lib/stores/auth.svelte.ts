export function createAuthStore() {
    let tokens = $state([]);
    let currentIndex = $state(0);
    
    let currentToken = $derived(tokens[currentIndex]);
    let isAuthenticated = $derived(tokens.length > 0);
    
    return {
        get tokens() { return tokens; },
        get currentToken() { return currentToken; },
        get isAuthenticated() { return isAuthenticated; },
        
        addToken(token) {
            tokens = [...tokens, token];
        },
        
        removeToken(index) {
            tokens = tokens.filter((_, i) => i !== index);
            if (currentIndex >= tokens.length) {
                currentIndex = 0;
            }
        }
    };
}