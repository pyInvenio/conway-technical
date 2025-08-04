// src/lib/stores/websocket.svelte.ts
import { browser } from '$app/environment';
import { writable, derived } from 'svelte/store';

interface WebSocketMessage {
    type: string;
    [key: string]: any;
}

interface ConnectionStatus {
    connected: boolean;
    connecting: boolean;
    error: string | null;
    lastConnected: Date | null;
    reconnectAttempts: number;
}

// SSR-safe default values
const defaultConnectionStatus: ConnectionStatus = {
    connected: false,
    connecting: false,
    error: null,
    lastConnected: null,
    reconnectAttempts: 0
};

function createWebSocketStore() {
    // Use traditional Svelte stores for SSR compatibility
    const connectionStatus = writable<ConnectionStatus>(defaultConnectionStatus);
    const githubToken = writable<string | null>(null);
    const subscriptions = writable<Set<string>>(new Set());
    
    // Derived stores for convenience
    const isConnected = derived(connectionStatus, ($status) => $status.connected);
    const isConnecting = derived(connectionStatus, ($status) => $status.connecting);
    
    // Only initialize WebSocket in browser environment
    let ws: WebSocket | null = null;
    let messageHandlers = new Map<string, ((data: any) => void)[]>();
    
    // Auto-reconnection settings
    const maxReconnectAttempts = 10;
    const baseReconnectDelay = 1000; // 1 second
    let reconnectTimer: number | null = null;
    let heartbeatTimer: number | null = null;
    
    const store = {
        // Store subscriptions
        connectionStatus: { subscribe: connectionStatus.subscribe },
        isConnected: { subscribe: isConnected.subscribe },
        isConnecting: { subscribe: isConnecting.subscribe },
        subscriptions: { subscribe: subscriptions.subscribe },
        
        // Set GitHub token for authentication
        setToken(token: string) {
            githubToken.set(token);
        },
        
        // Connect to WebSocket
        async connect() {
            if (!browser) {
                console.log('WebSocket connect called on server - skipping');
                return;
            }
            
            if (ws?.readyState === WebSocket.CONNECTING || ws?.readyState === WebSocket.OPEN) {
                console.log('WebSocket already connecting/connected');
                return;
            }
            
            store.disconnect(); // Clean up any existing connection
            
            connectionStatus.update(status => ({
                ...status,
                connecting: true,
                error: null
            }));
            
            try {
                // Connect without token requirement for basic anomaly streaming
                const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`;
                ws = new WebSocket(wsUrl);
                
                ws.onopen = () => {
                    console.log('WebSocket connected');
                    connectionStatus.update(status => ({
                        ...status,
                        connected: true,
                        connecting: false,
                        error: null,
                        lastConnected: new Date(),
                        reconnectAttempts: 0
                    }));
                    
                    // Start heartbeat
                    store.startHeartbeat();
                    
                    // Re-subscribe to channels if we had any
                    let currentSubscriptions: Set<string> = new Set();
                    subscriptions.subscribe(subs => currentSubscriptions = subs)();
                    if (currentSubscriptions.size > 0) {
                        store.send({
                            type: 'subscribe',
                            channels: Array.from(currentSubscriptions)
                        });
                    }
                };
                
                ws.onmessage = (event) => {
                    try {
                        const message: WebSocketMessage = JSON.parse(event.data);
                        store.handleMessage(message);
                    } catch (error) {
                        console.error('Failed to parse WebSocket message:', error);
                    }
                };
                
                ws.onclose = (event) => {
                    console.log('WebSocket disconnected:', event.code, event.reason);
                    connectionStatus.update(status => ({
                        ...status,
                        connected: false,
                        connecting: false
                    }));
                    
                    store.stopHeartbeat();
                    
                    // Auto-reconnect unless it was a clean close
                    let currentStatus: ConnectionStatus = defaultConnectionStatus;
                    connectionStatus.subscribe(status => currentStatus = status)();
                    if (event.code !== 1000 && currentStatus.reconnectAttempts < maxReconnectAttempts) {
                        store.scheduleReconnect();
                    }
                };
                
                ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    connectionStatus.update(status => ({
                        ...status,
                        error: 'Connection error',
                        connecting: false
                    }));
                };
                
            } catch (error) {
                console.error('Failed to create WebSocket connection:', error);
                connectionStatus.update(status => ({
                    ...status,
                    connecting: false,
                    error: 'Failed to connect'
                }));
            }
        },
        
        // Disconnect WebSocket
        disconnect() {
            if (!browser) return;
            
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
            
            store.stopHeartbeat();
            
            if (ws) {
                ws.close(1000, 'Client disconnect');
                ws = null;
            }
            
            connectionStatus.update(status => ({
                ...status,
                connected: false,
                connecting: false,
                reconnectAttempts: 0
            }));
        },
        
        // Send message to server
        send(message: WebSocketMessage) {
            if (!browser) return false;
            
            if (ws?.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify(message));
                return true;
            } else {
                console.warn('Cannot send message: WebSocket not connected');
                return false;
            }
        },
        
        // Subscribe to message type
        subscribe(messageType: string, handler: (data: any) => void) {
            if (!messageHandlers.has(messageType)) {
                messageHandlers.set(messageType, []);
            }
            messageHandlers.get(messageType)!.push(handler);
            
            // Return unsubscribe function
            return () => {
                const handlers = messageHandlers.get(messageType);
                if (handlers) {
                    const index = handlers.indexOf(handler);
                    if (index > -1) {
                        handlers.splice(index, 1);
                    }
                }
            };
        },
        
        // Subscribe to server channels
        subscribeToChannels(channels: string[]) {
            subscriptions.update(subs => {
                channels.forEach(channel => subs.add(channel));
                return subs;
            });
            
            let currentStatus: ConnectionStatus = defaultConnectionStatus;
            connectionStatus.subscribe(status => currentStatus = status)();
            if (currentStatus.connected) {
                store.send({
                    type: 'subscribe',
                    channels: channels
                });
            }
        },

        // Subscribe to severity-based anomaly channels
        subscribeToAnomalyChannels(severityLevels: string[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']) {
            const channels = [
                'anomalies', // General anomaly channel
                ...severityLevels.map(level => `anomalies_${level.toLowerCase()}`)
            ];
            store.subscribeToChannels(channels);
        },

        // Subscribe to user-specific channels
        subscribeToUserChannel(username: string) {
            store.subscribeToChannels([`user_${username}`]);
        },
        
        // Unsubscribe from server channels
        unsubscribeFromChannels(channels: string[]) {
            subscriptions.update(subs => {
                channels.forEach(channel => subs.delete(channel));
                return subs;
            });
            
            let currentStatus: ConnectionStatus = defaultConnectionStatus;
            connectionStatus.subscribe(status => currentStatus = status)();
            if (currentStatus.connected) {
                store.send({
                    type: 'unsubscribe',
                    channels: channels
                });
            }
        },
        
        // Request connection status
        requestStatus() {
            store.send({ type: 'get_status' });
        },
        
        // Handle incoming messages
        handleMessage(message: WebSocketMessage) {
            const { type, ...data } = message;
            
            // Handle system messages
            switch (type) {
                case 'connection':
                    console.log('Connection confirmed:', data);
                    break;
                    
                case 'pong':
                    // Heartbeat response - connection is alive
                    break;
                    
                case 'status':
                    console.log('Connection status:', data);
                    break;
                    
                case 'error':
                    console.error('Server error:', data.message);
                    connectionStatus.update(status => ({
                        ...status,
                        error: data.message
                    }));
                    break;
                    
                default:
                    // Call registered handlers for this message type
                    const handlers = messageHandlers.get(type);
                    if (handlers) {
                        handlers.forEach(handler => {
                            try {
                                handler(data);
                            } catch (error) {
                                console.error(`Error in ${type} handler:`, error);
                            }
                        });
                    }
            }
        },
        
        // Start heartbeat
        startHeartbeat() {
            if (!browser) return;
            
            this.stopHeartbeat(); // Clear any existing timer
            
            heartbeatTimer = window.setInterval(() => {
                let currentStatus: ConnectionStatus = defaultConnectionStatus;
                connectionStatus.subscribe(status => currentStatus = status)();
                if (currentStatus.connected) {
                    store.send({ type: 'ping' });
                }
            }, 30000); // Every 30 seconds
        },
        
        // Stop heartbeat
        stopHeartbeat() {
            if (!browser) return;
            
            if (heartbeatTimer) {
                clearInterval(heartbeatTimer);
                heartbeatTimer = null;
            }
        },
        
        // Schedule reconnection
        scheduleReconnect() {
            if (!browser) return;
            if (reconnectTimer) return; // Already scheduled
            
            let currentStatus: ConnectionStatus = defaultConnectionStatus;
            connectionStatus.subscribe(status => currentStatus = status)();
            
            const newAttempts = currentStatus.reconnectAttempts + 1;
            connectionStatus.update(status => ({
                ...status,
                reconnectAttempts: newAttempts
            }));
            
            const delay = Math.min(
                baseReconnectDelay * Math.pow(2, newAttempts - 1),
                30000 // Max 30 seconds
            );
            
            console.log(`Scheduling reconnect attempt ${newAttempts} in ${delay}ms`);
            
            reconnectTimer = window.setTimeout(() => {
                reconnectTimer = null;
                let status: ConnectionStatus = defaultConnectionStatus;
                connectionStatus.subscribe(s => status = s)();
                
                if (status.reconnectAttempts < maxReconnectAttempts) {
                    console.log(`Reconnect attempt ${status.reconnectAttempts}`);
                    store.connect();
                } else {
                    console.error('Max reconnection attempts reached');
                    connectionStatus.update(status => ({
                        ...status,
                        error: 'Connection failed - max attempts reached'
                    }));
                }
            }, delay);
        }
    };
    
    return store;
}

export const websocketStore = createWebSocketStore();