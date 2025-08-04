<script lang="ts">
  import Modal from '$lib/components/ui/Modal.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Icon from '$lib/components/ui/Icon.svelte';
  
  let { show = false, repository = null, onclose } = $props();
  
  function getSeverityVariant(severity) {
    if (severity >= 0.8) return 'error';
    if (severity >= 0.6) return 'warning';
    return 'info';
  }
  
  function formatDate(dateString) {
    return new Date(dateString).toLocaleString();
  }
  
  function getGitHubRepoUrl(repoName) {
    return `https://github.com/${repoName}`;
  }
  
  function timeAgo(dateString) {
    const date = new Date(dateString);
    const minutes = Math.floor((Date.now() - date.getTime()) / (1000 * 60));
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }
</script>

<Modal {show} title="Repository Details" {onclose}>
  {#snippet children()}
    {#if repository}
      <div class="space-y-6">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center space-x-3 mb-3">
              <Icon name="github" class="h-6 w-6 text-gray-400" />
              <h3 class="text-xl font-semibold text-gray-100 font-mono">{repository.name}</h3>
              <a 
                href={getGitHubRepoUrl(repository.name)} 
                target="_blank" 
                rel="noopener noreferrer"
                class="text-blue-400 hover:text-blue-300"
              >
                <Icon name="external-link" class="h-5 w-5" />
              </a>
            </div>
            <div class="flex items-center space-x-4 text-sm text-gray-400">
              <div class="flex items-center space-x-1">
                <Icon name="clock" class="h-4 w-4" />
                <span>Last activity: {timeAgo(repository.lastActivity)}</span>
              </div>
              <div class="flex items-center space-x-1">
                <Icon name="activity" class="h-4 w-4" />
                <span>{repository.events} events</span>
              </div>
            </div>
          </div>
        </div>

        <div class="p-4 bg-gray-900 rounded-lg border border-gray-600">
          <div class="flex items-center justify-between mb-3">
            <h4 class="text-lg font-semibold text-gray-100">Risk Assessment</h4>
            <Badge variant={repository.riskScore >= 80 ? 'error' : repository.riskScore >= 60 ? 'warning' : 'success'}>
              {repository.status}
            </Badge>
          </div>
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-gray-300">Risk Score</span>
              <span class="text-lg font-mono text-gray-100">{repository.riskScore}/100</span>
            </div>
            <div class="w-full bg-gray-700 rounded-full h-3">
              <div 
                class="h-3 rounded-full bg-gradient-to-r {repository.riskScore >= 80 ? 'from-red-500 to-orange-500' : repository.riskScore >= 60 ? 'from-orange-500 to-yellow-500' : 'from-green-500 to-blue-500'}"
                style="width: {repository.riskScore}%"
              ></div>
            </div>
          </div>
        </div>

        {#if repository.incidents && repository.incidents.length > 0}
          <div class="space-y-3">
            <h4 class="text-lg font-semibold text-gray-100 flex items-center space-x-2">
              <Icon name="alert-triangle" class="h-5 w-5 text-orange-400" />
              <span>Recent Incidents ({repository.incidents.length})</span>
            </h4>
            <div class="space-y-3 max-h-64 overflow-y-auto">
              {#each repository.incidents.slice(0, 10) as incident}
                <div class="p-3 bg-gray-900 rounded-lg border border-gray-600 hover:bg-gray-800 transition-colors cursor-pointer">
                  <div class="flex items-start justify-between mb-2">
                    <h5 class="text-sm font-medium text-gray-100 hover:text-blue-400 transition-colors">{incident.title}</h5>
                    <div class="flex items-center space-x-2">
                      <Badge variant={getSeverityVariant(incident.severity)} class="text-xs">
                        {Math.round(incident.severity * 100)}%
                      </Badge>
                      <button class="text-blue-400 hover:text-blue-300 text-xs">
                        <Icon name="external-link" class="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                  <div class="flex items-center space-x-4 text-xs text-gray-400">
                    <span>{incident.incident_type}</span>
                    <span>•</span>
                    <span>{timeAgo(incident.created_at)}</span>
                    {#if incident.event_ids && incident.event_ids.length > 0}
                      <span>•</span>
                      <span>{incident.event_ids.length} events</span>
                    {/if}
                  </div>
                  {#if incident.root_cause && incident.root_cause[0]}
                    <p class="text-xs text-gray-300 mt-1">{incident.root_cause[0]}</p>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <div class="space-y-3">
          <h4 class="text-lg font-semibold text-gray-100 flex items-center space-x-2">
            <Icon name="trending-up" class="h-5 w-5 text-blue-400" />
            <span>Activity Timeline</span>
          </h4>
          <div class="text-sm text-gray-400">
            Repository has been monitored with {repository.events} total events recorded.
            {#if repository.riskScore > 60}
              This repository shows elevated risk patterns and requires attention.
            {:else}
              This repository shows normal activity patterns.
            {/if}
          </div>
        </div>

        <div class="space-y-3">
          <h4 class="text-lg font-semibold text-gray-100 flex items-center space-x-2">
            <Icon name="lightbulb" class="h-5 w-5 text-yellow-400" />
            <span>Recommendations</span>
          </h4>
          <ul class="space-y-2 text-sm text-gray-300">
            {#if repository.riskScore >= 80}
              <li class="flex items-start space-x-2">
                <Icon name="arrow-right" class="h-4 w-4 text-red-400 mt-0.5 flex-shrink-0" />
                <span>Immediate investigation required - multiple high-severity incidents detected</span>
              </li>
              <li class="flex items-start space-x-2">
                <Icon name="arrow-right" class="h-4 w-4 text-red-400 mt-0.5 flex-shrink-0" />
                <span>Review repository access controls and recent changes</span>
              </li>
            {:else if repository.riskScore >= 60}
              <li class="flex items-start space-x-2">
                <Icon name="arrow-right" class="h-4 w-4 text-orange-400 mt-0.5 flex-shrink-0" />
                <span>Monitor closely for escalating patterns</span>
              </li>
              <li class="flex items-start space-x-2">
                <Icon name="arrow-right" class="h-4 w-4 text-orange-400 mt-0.5 flex-shrink-0" />
                <span>Consider implementing additional security measures</span>
              </li>
            {:else}
              <li class="flex items-start space-x-2">
                <Icon name="arrow-right" class="h-4 w-4 text-green-400 mt-0.5 flex-shrink-0" />
                <span>Repository appears to be operating normally</span>
              </li>
              <li class="flex items-start space-x-2">
                <Icon name="arrow-right" class="h-4 w-4 text-green-400 mt-0.5 flex-shrink-0" />
                <span>Continue regular monitoring</span>
              </li>
            {/if}
          </ul>
        </div>
      </div>
    {/if}
  {/snippet}
</Modal>