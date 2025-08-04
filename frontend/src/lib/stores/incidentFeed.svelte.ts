function createIncidentFeedStore() {
    let incidents = $state([]);
    let pagination = $state({ page: 1, limit: 20, total: 0, pages: 0, has_next: false, has_prev: false });
    let loading = $state(false);
    let error = $state(null);
    let isLive = $state(true);
    let initialized = $state(false);
    let retryCount = $state(0);
    
    const MAX_RETRIES = 3;
    const RETRY_DELAY = 1000; // 1 second
    
    async function fetchWithRetry(url, options = {}, attempt = 1) {
        try {
            retryCount = attempt;
            const response = await fetch(url, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            error = null; // Clear error on success
            retryCount = 0;
            return data;
        } catch (err) {
            if (attempt < MAX_RETRIES) {
                console.warn(`Attempt ${attempt} failed, retrying in ${RETRY_DELAY}ms:`, err.message);
                await new Promise(resolve => setTimeout(resolve, RETRY_DELAY * attempt));
                return fetchWithRetry(url, options, attempt + 1);
            } else {
                throw err;
            }
        }
    }
    
    return {
        get incidents() { return incidents; },
        get pagination() { return pagination; },
        get loading() { return loading; },
        get error() { return error; },
        get isLive() { return isLive; },
        get initialized() { return initialized; },
        get retryCount() { return retryCount; },
        
        initializeFromSSR(data) {
            if (data?.incidents) {
                incidents = data.incidents.incidents || [];
                pagination = data.incidents.pagination || pagination;
                initialized = true;
                console.log('IncidentFeed initialized with SSR data:', incidents.length, 'incidents');
            } else if (!initialized) {
                // If no SSR data and not initialized, load data
                this.loadPage(1, 20);
            }
        },
        
        async ensureInitialized() {
            if (!initialized && !loading) {
                await this.loadPage(1, 20);
            }
        },
        
        toggleLive() {
            isLive = !isLive;
        },
        
        setLive(live) {
            isLive = live;
        },
        
        addLiveIncident(incident) {
            if (!isLive || pagination.page !== 1) return;
            
            // Check for duplicates
            const exists = incidents.find(i => i.id === incident.id);
            if (!exists) {
                incidents = [incident, ...incidents].slice(0, pagination.limit);
                // Update pagination total
                pagination = { ...pagination, total: pagination.total + 1 };
                console.log('Live incident added to feed:', incident.title);
            }
        },
        
        async loadPage(page = 1, limit = 20) {
            if (loading) return; // Prevent concurrent requests
            
            loading = true;
            error = null;
            
            try {
                const data = await fetchWithRetry(`http://localhost:8000/incidents?page=${page}&limit=${limit}`);
                
                incidents = data.incidents || [];
                pagination = data.pagination || { page, limit, total: 0, pages: 0, has_next: false, has_prev: false };
                initialized = true;
                
                console.log(`IncidentFeed loaded page ${page}: ${incidents.length} incidents`);
            } catch (err) {
                error = `Failed to load incidents: ${err.message}`;
                console.error('Failed to load incidents:', err);
                
                // If this is first load and failed, set empty state but mark as initialized
                if (!initialized) {
                    incidents = [];
                    pagination = { page: 1, limit: 20, total: 0, pages: 0, has_next: false, has_prev: false };
                    initialized = true;
                }
            } finally {
                loading = false;
            }
        },
        
        async refresh() {
            initialized = false;
            await this.loadPage(pagination.page, pagination.limit);
        },
        
        clearError() {
            error = null;
        }
    };
}

export const incidentFeedStore = createIncidentFeedStore();