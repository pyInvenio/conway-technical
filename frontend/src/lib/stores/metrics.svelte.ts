function createMetricsStore() {
    let metrics = $state({
        totalEvents: 0,
        criticalAlerts: 0,
        repositories: 0,
        threatScore: 0.0
    });
    
    let loading = $state(false);
    
    return {
        get metrics() { return metrics; },
        get loading() { return loading; },
        
        initializeFromSSR(data) {
            if (data?.metrics) {
                metrics = data.metrics;
            }
        },
        
        async fetchMetrics() {
            loading = true;
            try {
                const response = await fetch('/metrics');
                
                if (response.ok) {
                    const data = await response.json();
                    metrics = data;
                    console.log('Metrics loaded:', data);
                } else {
                    console.error('Failed to fetch metrics:', response.status);
                }
            } catch (error) {
                console.error('Failed to fetch metrics:', error);
            } finally {
                loading = false;
            }
        },
        
        updateFromAnomalies(anomalies) {
            const criticalAnomalies = anomalies.filter(a => 
                a.severity_level === 'CRITICAL' || 
                a.severity_level === 'HIGH' || 
                a.final_anomaly_score >= 0.8
            );
            const repositories = new Set(anomalies.map(a => a.repository_name)).size;
            const avgThreatScore = anomalies.length > 0 
                ? anomalies.reduce((sum, a) => sum + a.final_anomaly_score, 0) / anomalies.length 
                : 0;
            
            metrics = {
                totalEvents: anomalies.length,
                criticalAlerts: criticalAnomalies.length,
                repositories: repositories,
                threatScore: avgThreatScore
            };
        },
        
        async fetchHealthMetrics() {
            loading = true;
            try {
                const response = await fetch('/health', {
                    credentials: 'include'
                });
                
                if (response.ok) {
                    const health = await response.json();
                    console.log('Health metrics:', health);
                } else {
                    console.error('Failed to fetch health metrics:', response.status);
                }
            } catch (error) {
                console.error('Failed to fetch health metrics:', error);
            } finally {
                loading = false;
            }
        }
    };
}

export const metricsStore = createMetricsStore();