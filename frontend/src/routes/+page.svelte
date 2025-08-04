<script>
  import { onMount } from "svelte";
  import { anomalyStore } from "$lib/stores/incidents.svelte";
  import { repositoryStore } from "$lib/stores/repositories.svelte";
  import { metricsStore } from "$lib/stores/metrics.svelte";
  import { repoMonitorStore } from "$lib/stores/repoMonitor.svelte";
  import { websocketStore } from "$lib/stores/websocket.svelte";
  import AuthModal from "$lib/components/AuthModal.svelte";
  import Navbar from "$lib/components/dashboard/Navbar.svelte";
  import IncidentFeed from "$lib/components/dashboard/IncidentFeed.svelte";
  import RepoMonitor from "$lib/components/dashboard/RepoMonitor.svelte";
  import DetectionMatrix from "$lib/components/dashboard/DetectionMatrix.svelte";

  let { data } = $props();

  let showAuthModal = $state(!data.authenticated);

  // Get anomalies directly from the anomaly store - use direct access to reactive state
  const anomalies = $derived(anomalyStore.anomalies);
  const anomaliesForBubbleMap = $derived(anomalies);

  // Add debug logging for the derived value
  $effect(() => {
    console.log('Main page anomalies updated:', anomalies?.length);
    console.log('Main page anomaliesForBubbleMap updated:', anomaliesForBubbleMap?.length);
  });

  // Load initial anomalies on page load - this is now handled by the anomaly store
  async function loadInitialAnomalies() {
    console.log('🔄 Loading initial anomalies...');
    // Load page of anomalies from the last 24 hours
    await anomalyStore.loadPage(1, 100);
    console.log(`✅ Loaded ${anomalies.length} anomalies from anomaly store`);
    console.log('🔍 First few anomalies:', anomalies.slice(0, 2));
  }

  onMount(async () => {
    console.log("Page mounted with data:", data);

    if (data.initialData) {
      console.log("Initializing stores with SSR data:", data.initialData);
      anomalyStore.initializeFromSSR(data.initialData);
      repositoryStore.initializeFromSSR(data.initialData);
      metricsStore.initializeFromSSR(data.initialData);
      repoMonitorStore.initializeFromSSR(data.initialData);
    }

    if (data.authenticated) {
      console.log("User is authenticated, connecting to WebSocket...");

      if (data.githubToken) {
        websocketStore.setToken(data.githubToken);
        anomalyStore.setToken(data.githubToken);
      }

      await anomalyStore.connect();

      // Load initial anomalies
      await loadInitialAnomalies();
    }
  });
</script>

{#if data.authenticated}
  <div class="min-h-screen bg-gray-900 text-gray-100">
    <Navbar user={data.user} />

    <main class="container mx-auto px-6 py-8 space-y-8">
      <section class="flex flex-col lg:flex-row gap-4 max-h-[800px] max-w-[70vw] mx-auto">
        <div class="flex-1 lg:max-w-[65%] lg:flex-shrink-0">
          <IncidentFeed />
        </div>
        <div class="flex-1 lg:max-w-[35%] lg:flex-shrink-0">
          <RepoMonitor />
        </div>
      </section>

      <section>
        <DetectionMatrix />
      </section>
      
      <!-- Debug: Show store state -->
      <div class="text-xs text-gray-500 mt-2">
        Debug: Anomaly store has {anomalies?.length || 0} anomalies
      </div>
    </main>
  </div>
{:else}
  <div
    class="min-h-screen bg-gray-900 text-white flex items-center justify-center"
  >
    <div class="text-center space-y-6 p-8">
      <div class="space-y-2">
        <h1 class="text-4xl font-bold">
          GitHub{" "}<span class="text-green-400">Monitor</span>
        </h1>
      </div>
      <p class="text-lg">
        Please authenticate to access the monitoring dashboard
      </p>
      <button
        onclick={() => (showAuthModal = true)}
        class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
      >
        Authenticate
      </button>
    </div>
  </div>
{/if}

<AuthModal show={showAuthModal} onclose={() => (showAuthModal = false)} />
