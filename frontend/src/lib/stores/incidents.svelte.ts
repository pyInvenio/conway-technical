// src/lib/stores/anomalies.svelte.ts - Pure anomaly detection store
import { websocketStore } from './websocket.svelte';

function createAnomalyStore() {
    let anomalies = $state([]);
    let pagination = $state({ page: 1, limit: 20, total: 0, pages: 0, has_next: false, has_prev: false });
    let loading = $state(false);
    let githubToken = $state(null);
    let wsUnsubscribe: (() => void) | null = null;
    let processingStats = $state({ events_processed: 0, anomalies_detected: 0, batch_size: 0 });
    let liveUpdatesEnabled = $state(true);
    
    return {
        // Reactive getters
        get anomalies() { return anomalies; },
        get pagination() { return pagination; },
        get loading() { return loading; },
        get processingStats() { return processingStats; },
        get liveUpdatesEnabled() { return liveUpdatesEnabled; },
        get isConnected() { 
            if (typeof websocketStore?.isConnected?.subscribe === 'function') {
                let connected = false;
                websocketStore.isConnected.subscribe(value => connected = value)();
                return connected;
            }
            return false;
        },
        
        // Computed values for severity filtering
        get criticalAnomalies() {
            return anomalies.filter(a => 
                a.severity_level === 'CRITICAL' || 
                a.severity_level === 'HIGH' || 
                a.final_anomaly_score >= 0.65
            );
        },
        
        get anomaliesBySeverity() {
            const severityGroups = {
                CRITICAL: [],
                HIGH: [],
                MEDIUM: [],
                LOW: [],
                INFO: []
            };
            
            anomalies.forEach(anomaly => {
                const severity = anomaly.severity_level || 
                    (anomaly.final_anomaly_score >= 0.85 ? 'CRITICAL' :
                     anomaly.final_anomaly_score >= 0.65 ? 'HIGH' :
                     anomaly.final_anomaly_score >= 0.35 ? 'MEDIUM' :
                     anomaly.final_anomaly_score >= 0.15 ? 'LOW' : 'INFO');
                
                severityGroups[severity].push(anomaly);
            });
            
            return severityGroups;
        },
        
        get anomaliesByRepo() {
            const grouped = {};
            anomalies.forEach(anomaly => {
                const repoName = anomaly.repository_name;
                if (!grouped[repoName]) {
                    grouped[repoName] = [];
                }
                grouped[repoName].push(anomaly);
            });
            return grouped;
        },
        
        // Initialize with SSR data
        initializeFromSSR(data) {
            if (data?.anomalies) {
                anomalies = data.anomalies.anomalies || [];
                pagination = data.anomalies.pagination || pagination;
            }
        },
        
        // Set GitHub token for authentication
        setToken(token) {
            githubToken = token;
            if (websocketStore?.setToken) {
                websocketStore.setToken(token);
            }
        },
        
        // Load paginated anomalies
        async loadPage(page = 1, limit = 20) {
            console.log('🔄 AnomalyStore: loadPage called with', page, limit);
            loading = true;
            try {
                const url = `http://localhost:8000/api/v1/anomalies?page=${page}&limit=${limit}`;
                console.log('🌐 AnomalyStore: fetching from', url);
                const response = await fetch(url);
                
                console.log('📡 AnomalyStore: response status', response.status);
                
                if (response.ok) {
                    const data = await response.json();
                    console.log('📦 AnomalyStore: received data with', data.anomalies?.length || 0, 'anomalies');
                    anomalies = data.anomalies;
                    pagination = data.pagination;
                    console.log('✅ AnomalyStore: stored', anomalies.length, 'anomalies in state');
                    console.log(`Loaded page ${page}: ${data.anomalies.length} anomalies`);
                } else {
                    console.error('Failed to load anomalies:', response.status, response.statusText);
                }
            } catch (error) {
                console.error('Failed to load anomalies:', error);
            } finally {
                loading = false;
            }
        },
        
        // Connect to WebSocket for real-time anomaly updates
        async connect() {
            if (!githubToken) {
                console.error('No GitHub token available for WebSocket connection');
                return;
            }
            
            // Subscribe to real-time anomaly messages
            if (websocketStore?.subscribe) {
                // Subscribe to anomaly detection messages - correct channel name
                const unsubscribeAnomaly = websocketStore.subscribe('anomalies', (data) => {
                    const anomalyData = data.data || data;
                    this.handleNewAnomaly(anomalyData);
                });

                // Subscribe to processing statistics
                const unsubscribeStats = websocketStore.subscribe('processing_stats', (data) => {
                    const statsData = data.data || data;
                    this.handleProcessingStats(statsData);
                });

                // Subscribe to events processed feed
                const unsubscribeEvents = websocketStore.subscribe('events_processed', (data) => {
                    const eventData = data.data || data;
                    this.handleEventsProcessed(eventData);
                });

                // Store all unsubscribe functions
                wsUnsubscribe = () => {
                    unsubscribeAnomaly();
                    unsubscribeStats();
                    unsubscribeEvents();
                };
            }
            
            // Connect to WebSocket
            if (websocketStore?.connect) {
                await websocketStore.connect();
            }
        },

        // Control live updates
        setLiveUpdates(enabled) {
            liveUpdatesEnabled = enabled;
            console.log('Live updates:', enabled ? 'enabled' : 'disabled');
        },

        // Handle new anomaly from WebSocket
        handleNewAnomaly(anomalyData) {
            // Only add real-time updates if live mode is enabled and we're on the first page
            if (liveUpdatesEnabled && pagination.page === 1) {
                const exists = anomalies.find(a => a.id === anomalyData.id);
                if (!exists) {
                    anomalies = [anomalyData, ...anomalies].slice(0, pagination.limit);
                    // Update total count in pagination
                    pagination = {
                        ...pagination,
                        total: pagination.total + 1
                    };
                    console.log('New anomaly received via WebSocket:', anomalyData);
                }
            } else if (!liveUpdatesEnabled) {
                console.log('New anomaly received but live updates are paused');
            }
        },

        // Handle processing statistics
        handleProcessingStats(statsData) {
            processingStats = statsData;
            console.log('Processing stats updated:', statsData);
        },

        // Handle events processed updates  
        handleEventsProcessed(eventData) {
            console.log('Events processed:', eventData);
        },
        
        // Disconnect from WebSocket
        disconnect() {
            if (wsUnsubscribe) {
                wsUnsubscribe();
                wsUnsubscribe = null;
            }
            if (websocketStore?.disconnect) {
                websocketStore.disconnect();
            }
        }
    };
}

// Export the pure anomaly store - 100x faster than incidents
export const anomalyStore = createAnomalyStore();