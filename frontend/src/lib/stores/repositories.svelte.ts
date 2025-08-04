function createRepositoryStore() {
    let repositories = $state([]);
    let pagination = $state({ page: 1, limit: 20, total: 0, pages: 0, has_next: false, has_prev: false });
    let loading = $state(false);
    
    return {
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
        
        // Load paginated repositories
        async loadPage(page = 1, limit = 20) {
            loading = true;
            try {
                const response = await fetch(`/repositories?page=${page}&limit=${limit}`);
                
                if (response.ok) {
                    const data = await response.json();
                    repositories = data.repositories;
                    pagination = data.pagination;
                    console.log('Repositories loaded:', data.repositories.length);
                } else {
                    console.error('Failed to load repositories:', response.status, response.statusText);
                }
            } catch (error) {
                console.error('Failed to load repositories:', error);
            } finally {
                loading = false;
            }
        },
        
        // Generate repository data from anomalies (fallback)
        updateFromAnomalies(anomalies) {
            const repoMap = new Map();
            
            anomalies.forEach(anomaly => {
                const repoName = anomaly.repository_name;
                if (!repoMap.has(repoName)) {
                    repoMap.set(repoName, {
                        name: repoName,
                        events: 0,
                        anomalies: [],
                        riskScore: 0,
                        lastActivity: anomaly.detection_timestamp,
                        status: 'normal'
                    });
                }
                
                const repo = repoMap.get(repoName);
                repo.events += 1;
                repo.anomalies.push(anomaly);
                
                // Calculate risk score based on anomaly scores
                const avgScore = repo.anomalies.reduce((sum, a) => sum + a.final_anomaly_score, 0) / repo.anomalies.length;
                repo.riskScore = Math.round(avgScore * 100);
                
                // Determine status based on severity levels and scores
                const hasCritical = repo.anomalies.some(a => a.severity_level === 'CRITICAL' || a.final_anomaly_score >= 0.8);
                const hasHigh = repo.anomalies.some(a => a.severity_level === 'HIGH' || a.final_anomaly_score >= 0.6);
                
                if (hasCritical || repo.riskScore >= 80) {
                    repo.status = 'critical';
                } else if (hasHigh || repo.riskScore >= 60) {
                    repo.status = 'warning';
                } else {
                    repo.status = 'normal';
                }
                
                // Update last activity
                if (new Date(anomaly.detection_timestamp) > new Date(repo.lastActivity)) {
                    repo.lastActivity = anomaly.detection_timestamp;
                }
            });
            
            repositories = Array.from(repoMap.values())
                .sort((a, b) => b.riskScore - a.riskScore); // Sort by risk score descending
        }
    };
}

export const repositoryStore = createRepositoryStore();