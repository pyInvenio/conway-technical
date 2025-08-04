<script lang="ts">
  import Icon from "$lib/components/ui/Icon.svelte";
  import Card from "$lib/components/ui/Card.svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import Progress from "$lib/components/ui/Progress.svelte";
  import { repositoryStore } from "$lib/stores/repositories.svelte";
  import { repoMonitorStore } from "$lib/stores/repoMonitor.svelte";
  import { anomalyStore } from "$lib/stores/incidents.svelte";
  import RepositoryDetailModal from "./RepositoryDetailModal.svelte";

  // Use dedicated repo monitor store
  const repositories = $derived(repoMonitorStore.repositories);
  const pagination = $derived(repoMonitorStore.pagination);
  const loading = $derived(repoMonitorStore.loading);
  const anomalies = $derived(anomalyStore.anomalies);

  // Search functionality
  let searchQuery = $state("");

  // Filter repositories based on search query
  const filteredRepositories = $derived(
    repositories.filter((repo) =>
      repo.name.toLowerCase().includes(searchQuery.toLowerCase())
    )
  );

  // Pagination handlers
  async function loadNextPage() {
    if (pagination.has_next && !loading) {
      await repoMonitorStore.loadPage(pagination.page + 1, pagination.limit);
    }
  }

  async function loadPreviousPage() {
    if (pagination.has_prev && !loading) {
      await repoMonitorStore.loadPage(pagination.page - 1, pagination.limit);
    }
  }

  // Modal state
  let selectedRepository = $state(null);
  let showModal = $state(false);

  function openRepositoryDetail(repository) {
    selectedRepository = repository;
    showModal = true;
  }

  function closeModal() {
    showModal = false;
    selectedRepository = null;
  }

  // Update repositories when anomalies change
  $effect(() => {
    if (anomalies.length > 0) {
      repositoryStore.updateFromAnomalies(anomalies);
    }
  });

  function getStatusColor(status) {
    switch (status) {
      case "critical":
        return "error";
      case "warning":
        return "warning";
      default:
        return "success";
    }
  }

  function getRiskColor(score) {
    if (score >= 80) return "from-red-500 to-orange-500";
    if (score >= 60) return "from-orange-500 to-yellow-500";
    return "from-green-500 to-blue-500";
  }

  function timeAgo(dateString) {
    const date = new Date(dateString);
    const minutes = Math.floor((Date.now() - date.getTime()) / (1000 * 60));
    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }
</script>

<Card
  class="p-6 bg-terminal-surface/50 border-terminal-border h-full flex flex-col"
>
  <div class="flex items-center justify-between mb-4">
    <div class="flex items-center space-x-2">
      <Icon name="eye" class="h-5 w-5 text-crypto-blue" />
      <h3 class="text-lg font-semibold text-terminal-text font-mono">
        Repository Monitor
      </h3>
    </div>
  </div>

  <!-- Search Input -->
  <div class="relative mb-4">
    <Icon
      name="search"
      class="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400"
    />
    <input
      type="text"
      placeholder="Search repositories..."
      bind:value={searchQuery}
      class="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-600 rounded-lg text-sm text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-crypto-blue focus:border-transparent"
    />
  </div>

  <div class="space-y-3 flex-1 overflow-y-auto">
    {#if filteredRepositories.length > 0}
      {#each filteredRepositories as repo}
        <a
          href="/repository/{encodeURIComponent(repo.name)}"
          class="block p-3 rounded-lg border border-gray-600 bg-gray-800/30 hover:bg-gray-800/50 transition-colors"
        >
          <!-- Header row with name, status, and event count -->
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center space-x-2">
              <h4 class="font-medium text-gray-100 font-mono text-sm">
                {repo.name}
              </h4>
              <Badge
                variant={getStatusColor(repo.status)}
                class="text-xs px-1.5 py-0.5"
              >
                {repo.status}
              </Badge>
            </div>
            <div class="flex items-center space-x-1 text-xs text-gray-400">
              <Icon name="activity" class="h-3 w-3" />
              <span>{repo.events}</span>
            </div>
          </div>

          <!-- Risk score and last activity row -->
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center space-x-2 flex-1">
              <span class="text-xs text-gray-400">Risk:</span>
              <div class="flex-1 max-w-20">
                <div class="h-1 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    class="h-full bg-gradient-to-r {getRiskColor(
                      repo.riskScore
                    )} transition-all duration-500"
                    style="width: {repo.riskScore}%"
                  ></div>
                </div>
              </div>
              <span class="text-xs font-mono text-gray-100"
                >{repo.riskScore}</span
              >
            </div>
            <div class="text-xs text-gray-400 ml-4">
              {timeAgo(repo.lastActivity)}
            </div>
          </div>

          <!-- Status indicator row -->
          <div class="flex items-center justify-between text-xs">
            <div class="flex items-center space-x-1">
              <div
                class="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse"
              ></div>
              <span class="text-gray-400">Monitoring</span>
            </div>

            {#if repo.status === "critical"}
              <div class="flex items-center space-x-1 text-red-400">
                <Icon name="alert-circle" class="h-3 w-3" />
                <span>Attention</span>
              </div>
            {:else if repo.status === "warning"}
              <div class="flex items-center space-x-1 text-orange-400">
                <Icon name="trending-up" class="h-3 w-3" />
                <span>Elevated</span>
              </div>
            {:else}
              <span class="text-green-400">Normal</span>
            {/if}
          </div>
        </a>
      {/each}
    {:else if repositories.length > 0 && filteredRepositories.length === 0}
      <!-- No search results -->
      <div class="text-center py-8 text-gray-400">
        <Icon name="search" class="h-8 w-8 mx-auto mb-2" />
        <p>No repositories found matching "{searchQuery}"</p>
      </div>
    {:else}
      <!-- Skeleton loading state -->
      {#each Array(3) as _, i}
        <div class="p-3 rounded-lg border border-gray-600 bg-gray-800/30">
          <!-- Header row skeleton -->
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center space-x-2">
              <div class="h-4 bg-gray-600 rounded animate-pulse w-24"></div>
              <div class="h-4 bg-gray-600 rounded animate-pulse w-12"></div>
            </div>
            <div class="h-3 bg-gray-600 rounded animate-pulse w-6"></div>
          </div>

          <!-- Risk and activity row skeleton -->
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center space-x-2 flex-1">
              <div class="h-3 bg-gray-600 rounded animate-pulse w-8"></div>
              <div class="flex-1 max-w-20">
                <div class="h-1 bg-gray-600 rounded-full animate-pulse"></div>
              </div>
              <div class="h-3 bg-gray-600 rounded animate-pulse w-6"></div>
            </div>
            <div class="h-3 bg-gray-600 rounded animate-pulse w-12"></div>
          </div>

          <!-- Status row skeleton -->
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-1">
              <div
                class="w-1.5 h-1.5 bg-gray-600 rounded-full animate-pulse"
              ></div>
              <div class="h-3 bg-gray-600 rounded animate-pulse w-16"></div>
            </div>
            <div class="h-3 bg-gray-600 rounded animate-pulse w-12"></div>
          </div>
        </div>
      {/each}
    {/if}
  </div>

  <!-- Pagination Controls -->
  {#if pagination.total > 0}
    <div class="mt-4 pt-4 border-t border-terminal-border">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-4">
          <Button
            variant="ghost"
            size="sm"
            disabled={!pagination.has_prev || loading}
            onclick={loadPreviousPage}
          >
            <Icon name="chevron-left" class="h-4 w-4 mr-1" />
            Previous
          </Button>
          <span class="text-xs text-muted-foreground font-mono">
            Page {pagination.page} of {pagination.pages} ({pagination.total} repos)
          </span>
          <Button
            variant="ghost"
            size="sm"
            disabled={!pagination.has_next || loading}
            onclick={loadNextPage}
          >
            Next
            <Icon name="chevron-right" class="h-4 w-4 ml-1" />
          </Button>
        </div>

        <div class="flex items-center space-x-2 text-xs text-muted-foreground">
          <div class="w-2 h-2 bg-crypto-blue rounded-full animate-pulse"></div>
          <span>Monitoring {filteredRepositories.length} repositories</span>
        </div>
      </div>
    </div>
  {/if}
</Card>

<!-- Repository Detail Modal -->
<RepositoryDetailModal
  show={showModal}
  repository={selectedRepository}
  onclose={closeModal}
/>
