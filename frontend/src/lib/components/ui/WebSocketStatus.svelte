<script lang="ts">
  import { websocketStore } from '$lib/stores/websocket.svelte';
  import { browser } from '$app/environment';
  import Icon from './Icon.svelte';
  
  // Import derived for reactive values
  import { derived } from 'svelte/store';
  
  // Default values for SSR
  const defaultConnectionStatus = {
    connected: false,
    connecting: false,
    error: null,
    lastConnected: null,
    reconnectAttempts: 0
  };
  
  // Create SSR-safe mock stores
  const createMockStore = (value) => ({
    subscribe: (fn) => {
      fn(value);
      return { unsubscribe: () => {} };
    }
  });

  // Create derived stores that are SSR-safe
  const connectionStatus = browser && websocketStore?.connectionStatus 
    ? websocketStore.connectionStatus 
    : createMockStore(defaultConnectionStatus);
    
  const isConnected = browser && websocketStore?.isConnected 
    ? websocketStore.isConnected 
    : createMockStore(false);
    
  const isConnecting = browser && websocketStore?.isConnecting 
    ? websocketStore.isConnecting 
    : createMockStore(false);
  
  // Get status color and text using derived store
  const statusInfo = derived(
    [connectionStatus, isConnected, isConnecting],
    ([$connectionStatus, $isConnected, $isConnecting]) => {
      if ($isConnected) {
        return {
          color: 'text-green-400',
          bgColor: 'bg-green-400',
          icon: 'wifi',
          text: 'Connected',
          description: 'Real-time updates active'
        };
      } else if ($isConnecting) {
        return {
          color: 'text-yellow-400',
          bgColor: 'bg-yellow-400',
          icon: 'loader',
          text: 'Connecting...',
          description: 'Establishing connection'
        };
      } else if ($connectionStatus.error) {
        return {
          color: 'text-red-400',
          bgColor: 'bg-red-400',
          icon: 'wifi-off',
          text: 'Error',
          description: $connectionStatus.error
        };
      } else {
        return {
          color: 'text-gray-400',
          bgColor: 'bg-gray-400',
          icon: 'wifi-off',
          text: 'Disconnected',
          description: 'No real-time updates'
        };
      }
    }
  );
  
  function handleClick() {
    if (!browser || !websocketStore) return;
    
    // Get current values by subscribing and immediately unsubscribing
    let currentConnected = false;
    let currentConnecting = false;
    
    // Use a simpler approach - get values through the stores
    try {
      const unsubConnected = isConnected.subscribe(value => currentConnected = value);
      const unsubConnecting = isConnecting.subscribe(value => currentConnecting = value);
      
      // Call unsubscribe if it exists
      if (unsubConnected?.unsubscribe) unsubConnected.unsubscribe();
      if (unsubConnecting?.unsubscribe) unsubConnecting.unsubscribe();
    } catch (error) {
      console.warn('Error accessing store values:', error);
    }
    
    if (!currentConnected && !currentConnecting) {
      websocketStore.connect();
    } else {
      websocketStore.requestStatus();
    }
  }
</script>

<button 
  class="flex items-center space-x-2 px-3 py-1 rounded-lg border border-gray-600 bg-gray-800/50 hover:bg-gray-800/70 transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-crypto-blue"
  onclick={handleClick}
  title={$statusInfo.description}
  aria-label="WebSocket connection status: {$statusInfo.text}"
>
  <!-- Status indicator dot -->
  <div class="relative">
    <div class="w-2 h-2 rounded-full {$statusInfo.bgColor}"></div>
    {#if $isConnected}
      <div class="absolute inset-0 w-2 h-2 rounded-full {$statusInfo.bgColor} animate-ping opacity-75"></div>
    {/if}
  </div>
  
  <!-- Status icon -->
  <Icon 
    name={$statusInfo.icon} 
    class="h-3 w-3 {$statusInfo.color} {$isConnecting ? 'animate-spin' : ''}" 
  />
  
  <!-- Status text -->
  <span class="text-xs font-medium {$statusInfo.color}">
    {$statusInfo.text}
  </span>
  
  <!-- Connection details (on hover/expanded) -->
  {#if $connectionStatus.reconnectAttempts > 0}
    <span class="text-xs text-gray-500">
      (Attempt {$connectionStatus.reconnectAttempts})
    </span>
  {/if}
</button>

<!-- Optional: Detailed status tooltip or dropdown -->
{#if $connectionStatus.lastConnected || $connectionStatus.reconnectAttempts > 0}
  <div class="mt-1 text-xs text-gray-500 hidden group-hover:block">
    {#if $connectionStatus.lastConnected}
      Last connected: {$connectionStatus.lastConnected.toLocaleTimeString()}
    {/if}
    {#if $connectionStatus.reconnectAttempts > 0}
      <br>Reconnection attempts: {$connectionStatus.reconnectAttempts}
    {/if}
  </div>
{/if}