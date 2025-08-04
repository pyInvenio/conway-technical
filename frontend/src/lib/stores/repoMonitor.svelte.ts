// Dedicated store for RepoMonitor component
function createRepoMonitorStore() {
    let repositories = $state([]);
    let pagination = $state({ page: 1, limit: 20, total: 0, pages: 0, has_next: false, has_prev: false });
    let loading = $state(false);
    
    return {
        // Getters
        get repositories() { return repositories; },
        get pagination() { return pagination; },
        get loading() { return loading; },
        
        // Initialize with SSR data
        initializeFromSSR(data) {
            if (data?.repositories) {
                repositories = data.repositories.repositories || [];
                pagination = data.repositories.pagination || pagination;
            }
        },
        
        // Update repository risk when new incident arrives
        updateRepositoryFromIncident(incident) {
            const existingRepo = repositories.find(r => r.name === incident.repo_name);
            if (existingRepo) {
                // Update existing repository
                existingRepo.events += 1;
                existingRepo.lastActivity = incident.created_at;
                // Trigger reactivity
                repositories = [...repositories];
            } else if (pagination.page === 1) {
                // Add new repository to first page only
                const newRepo = {
                    name: incident.repo_name,
                    events: 1,
                    lastActivity: incident.created_at,
                    riskScore: Math.round(incident.severity * 100),
                    status: incident.severity >= 0.8 ? 'critical' : incident.severity >= 0.6 ? 'warning' : 'normal'
                };
                repositories = [newRepo, ...repositories].slice(0, pagination.limit);
                pagination = { ...pagination, total: pagination.total + 1 };
            }
        },
        
        // Load paginated repositories
        async loadPage(page = 1, limit = 20) {
            loading = true;
            try {
                const response = await fetch(`http://localhost:8000/repositories?page=${page}&limit=${limit}`);
                
                if (response.ok) {
                    const data = await response.json();
                    repositories = data.repositories;
                    pagination = data.pagination;
                    console.log(`RepoMonitor loaded page ${page}: ${data.repositories.length} repositories`);
                } else {
                    console.error('Failed to load repositories:', response.status, response.statusText);
                }
            } catch (error) {
                console.error('Failed to load repositories:', error);
            } finally {
                loading = false;
            }
        }
    };
}

export const repoMonitorStore = createRepoMonitorStore();