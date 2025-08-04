<script lang="ts">
  import Icon from '$lib/components/ui/Icon.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { anomalyStore } from '$lib/stores/incidents.svelte';
  import IncidentDetailModal from './IncidentDetailModal.svelte';
  import { 
    parseAISummary, 
    parseRiskIndicators, 
    getIncidentTypeDisplay, 
    getSeverityColor,
    getPrimaryDetectionMethod,
    generateFallbackSummary,
    type ComponentScores 
  } from '$lib/utils/summaryParser';
  
  const anomalies = $derived(anomalyStore.anomalies);
  const pagination = $derived(anomalyStore.pagination);
  const loading = $derived(anomalyStore.loading);
  const processingStats = $derived(anomalyStore.processingStats);
  const isConnected = $derived(anomalyStore.isConnected);
  
  // Debug what IncidentFeed is actually getting
  $effect(() => {
    console.log('🔍 IncidentFeed: anomalies updated to', anomalies?.length || 0);
  });
  
  let isLive = $state(true);
  
  async function loadNextPage() {
    if (pagination.has_next && !loading) {
      await anomalyStore.loadPage(pagination.page + 1, pagination.limit);
    }
  }
  
  async function loadPreviousPage() {
    if (pagination.has_prev && !loading) {
      await anomalyStore.loadPage(pagination.page - 1, pagination.limit);
    }
  }
  
  function toggleLive() {
    isLive = !isLive;
    
    anomalyStore.setLiveUpdates(isLive);
    
    if (isLive) {
      anomalyStore.loadPage(1, pagination.limit);
      console.log('Live mode enabled');
    } else {
      console.log('Live mode paused');
    }
  }
  
  let selectedAnomaly = $state(null);
  let showModal = $state(false);
  
  function openAnomalyDetail(anomaly) {
    selectedAnomaly = anomaly;
    showModal = true;
  }
  
  function closeModal() {
    showModal = false;
    selectedAnomaly = null;
  }
  

  function getSeverityVariant(severityLevel, score) {
    if (severityLevel === 'CRITICAL' || score >= 0.8) return 'error';
    if (severityLevel === 'HIGH' || score >= 0.6) return 'warning';
    if (severityLevel === 'MEDIUM' || score >= 0.4) return 'warning';
    return 'info';
  }

  function getEventTypeIcon(eventType) {
    switch (eventType) {
      case 'PushEvent': return 'git-branch';
      case 'WorkflowRunEvent': return 'alert-triangle';
      case 'DeleteEvent': return 'trash-2';
      case 'MemberEvent': return 'users';
      case 'ReleaseEvent': return 'tag';
      case 'ForkEvent': return 'git-fork';
      case 'IssuesEvent': return 'alert-circle';
      case 'PullRequestEvent': return 'git-pull-request';
      case 'force_push': return 'git-branch';
      case 'workflow_failure': return 'alert-triangle';
      case 'secret_exposure': return 'shield-alert';
      case 'mass_deletion': return 'trash-2';
      case 'bursty_activity': return 'activity';
      case 'anomalous_activity': return 'alert-circle';
      default: return 'alert-triangle';
    }
  }

  // Helper to get structured summary for display
  function getDisplaySummary(anomaly) {
    // Get component scores
    const componentScores: ComponentScores = {
      behavioral: anomaly.behavioral_anomaly_score || 0,
      content: anomaly.content_risk_score || 0,
      temporal: anomaly.temporal_anomaly_score || 0,
      repository: anomaly.repository_criticality_score || 0
    };

    // Try to parse AI summary first
    const parsedSummary = parseAISummary(anomaly.ai_summary);
    
    if (parsedSummary) {
      return parsedSummary;
    }

    // Generate fallback summary
    return generateFallbackSummary(
      anomaly.event_type,
      anomaly.final_anomaly_score,
      anomaly.repository_name,
      componentScores
    );
  }

  // Get detection method badge info
  function getDetectionInfo(anomaly) {
    const componentScores: ComponentScores = {
      behavioral: Number(anomaly.behavioral_anomaly_score || anomaly.detection_scores?.behavioral) || 0,
      content: Number(anomaly.content_risk_score || anomaly.detection_scores?.content) || 0,
      temporal: Number(anomaly.temporal_anomaly_score || anomaly.detection_scores?.temporal) || 0,
      repository: Number(anomaly.repository_criticality_score || anomaly.detection_scores?.repository_criticality) || 0
    };

    console.log('IncidentFeed detection scores:', componentScores);
    return getPrimaryDetectionMethod(componentScores);
  }

  function safeParseDate(dateString) {
    if (!dateString) return null;
    try {
      const date = new Date(dateString);
      return isNaN(date.getTime()) ? null : date;
    } catch {
      return null;
    }
  }

  function timeAgo(dateString) {
    const date = safeParseDate(dateString);
    if (!date) return 'Unknown time';
    
    const minutes = Math.floor((Date.now() - date.getTime()) / (1000 * 60));
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }

  function formatTime(dateString) {
    const date = safeParseDate(dateString);
    if (!date) return 'Invalid Date';
    return date.toLocaleTimeString();
  }

</script>

<Card class="p-6 bg-terminal-surface/50 border-terminal-border h-full flex flex-col max-w-full overflow-hidden">
  <div class="flex items-center justify-between mb-4">
    <div class="flex items-center space-x-2">
      <Icon name="alert-triangle" class="h-5 w-5 text-crypto-orange" />
      <h3 class="text-lg font-semibold text-terminal-text font-mono">Live Anomaly Feed</h3>
      {#if processingStats.events_processed > 0}
        <span class="text-xs text-gray-400 ml-2">
          ({processingStats.events_processed} events processed, {processingStats.anomalies_detected} anomalies)
        </span>
      {/if}
    </div>
    <div class="flex items-center space-x-2">
      <Button 
        variant="ghost" 
        size="sm"
        onclick={() => anomalyStore.loadPage(pagination.page, pagination.limit)}
        disabled={loading}
        class="text-gray-400 hover:text-gray-100"
      >
        <Icon name="refresh-cw" class="h-4 w-4 mr-2" />
        Refresh
      </Button>
      <Button 
        variant={isLive ? "default" : "secondary"} 
        size="sm"
        onclick={toggleLive}
        class={isLive ? "bg-green-600 hover:bg-green-700" : "bg-orange-600 hover:bg-orange-700"}
      >
        <Icon name={isLive ? "pause" : "play"} class="h-4 w-4 mr-2" />
        {isLive ? "Live" : "Paused"}
      </Button>
    </div>
  </div>

  <div class="space-y-4 flex-1 overflow-y-auto min-h-0 max-w-full">
    {#if anomalies.length > 0}
      {#each anomalies as anomaly}
        {@const summary = getDisplaySummary(anomaly)}
        {@const detectionMethod = getDetectionInfo(anomaly)}
        {@const riskIndicators = parseRiskIndicators(anomaly.high_risk_indicators)}
        
        <div 
          class="p-4 rounded-lg border border-gray-600 bg-gray-800/50 hover:bg-gray-800/70 transition-colors cursor-pointer max-w-full overflow-hidden"
          onclick={() => openAnomalyDetail(anomaly)}
          role="button"
          tabindex="0"
          onkeydown={(e) => e.key === 'Enter' && openAnomalyDetail(anomaly)}
        >
          <div class="flex items-start justify-between">
            <div class="flex items-start space-x-3 flex-1">
              <div class="p-2 rounded-lg bg-gray-700 border border-gray-600">
                <Icon 
                  name={getEventTypeIcon(anomaly.event_type)} 
                  class="h-4 w-4 {getSeverityColor(anomaly.severity_level)}" 
                />
              </div>
              
              <div class="flex-1 min-w-0 max-w-full overflow-hidden">
                <div class="flex items-center space-x-2 mb-2">
                  <h4 class="text-sm font-medium text-gray-100 truncate">
                    {summary.title || getIncidentTypeDisplay(anomaly.event_type)}
                  </h4>
                  <Badge variant={getSeverityVariant(anomaly.severity_level, anomaly.final_anomaly_score)}>
                    {anomaly.severity_level}
                  </Badge>
                  <Badge variant="secondary" class="text-xs">
                    {Math.round(anomaly.final_anomaly_score * 100)}%
                  </Badge>
                </div>

                <div class="flex items-center space-x-2 mb-2">
                  <Badge variant="outline" class="text-xs bg-purple-900/30 border-purple-400/50 text-purple-300">
                    <Icon name="zap" class="h-3 w-3 mr-1" />
                    {detectionMethod.method}
                  </Badge>
                  <span class="text-xs text-gray-500">•</span>
                  <span class="text-xs text-gray-400">{(detectionMethod.score * 100).toFixed(0)}% confidence</span>
                </div>
                
                <div class="flex items-center space-x-4 mb-3 text-xs text-gray-400">
                  <a 
                    href="/repository/{encodeURIComponent(anomaly.repository_name)}" 
                    class="font-mono text-blue-400 hover:text-blue-300 flex items-center space-x-1"
                    onclick={(e) => e.stopPropagation()}
                  >
                    <Icon name="github" class="h-3 w-3" />
                    <span>{anomaly.repository_name}</span>
                  </a>
                  <span>•</span>
                  <span class="font-mono text-cyan-400 flex items-center space-x-1">
                    <Icon name="user" class="h-3 w-3" />
                    <span>{anomaly.user_login}</span>
                  </span>
                  <span>•</span>
                  <div class="flex items-center space-x-1">
                    <Icon name="clock" class="h-3 w-3" />
                    <span>{timeAgo(anomaly.timestamp || anomaly.detection_timestamp)}</span>
                  </div>
                </div>
                
                {#if summary.root_cause && summary.root_cause.length > 0}
                  <div class="mb-2">
                    <div class="flex items-center space-x-1 mb-1">
                      <Icon name="search" class="h-3 w-3 text-orange-400" />
                      <span class="text-xs font-medium text-orange-400">Root Cause:</span>
                    </div>
                    <ul class="text-sm text-gray-300 space-y-1">
                      {#each summary.root_cause.slice(0, 2) as cause}
                        <li class="flex items-start space-x-2">
                          <span class="text-orange-400 mt-1">•</span>
                          <span class="flex-1">{cause}</span>
                        </li>
                      {/each}
                      {#if summary.root_cause.length > 2}
                        <li class="text-xs text-gray-500 ml-4">+{summary.root_cause.length - 2} more causes...</li>
                      {/if}
                    </ul>
                  </div>
                {/if}

                <!-- High Risk Indicators Preview -->
                {#if riskIndicators.indicators.length > 0}
                  <div class="flex items-center space-x-2 flex-wrap">
                    <Icon name="alert-triangle" class="h-3 w-3 text-red-400" />
                    <span class="text-xs text-red-400 font-medium">Risk Factors:</span>
                    {#each riskIndicators.indicators.slice(0, 2) as indicator}
                      <Badge variant="outline" class="text-xs bg-red-900/20 border-red-400/30 text-red-300">
                        {indicator}
                      </Badge>
                    {/each}
                    {#if riskIndicators.indicators.length > 2}
                      <span class="text-xs text-gray-500">+{riskIndicators.indicators.length - 2} more</span>
                    {/if}
                  </div>
                {/if}
              </div>
            </div>
            
            <!-- Score and Status -->
            <div class="flex items-center space-x-3">
              <div class="text-right space-y-1">
                <div class="text-xs text-gray-400 font-mono">
                  {formatTime(anomaly.timestamp || anomaly.detection_timestamp)}
                </div>
                <div class="text-xs font-mono {getSeverityColor(anomaly.final_anomaly_score)}">
                  {anomaly.final_anomaly_score.toFixed(2)}
                </div>
                {#if summary.threat_level}
                  <div class="text-xs font-medium text-red-400">
                    {summary.threat_level}
                  </div>
                {/if}
              </div>
              <div class="w-2 h-2 rounded-full bg-green-400 animate-pulse"></div>
            </div>
          </div>
        </div>
      {/each}
    {:else}
      <!-- Skeleton loading state -->
      {#each Array(4) as _, i}
        <div class="p-4 rounded-lg border border-gray-600 bg-gray-800/30">
          <div class="flex items-start justify-between">
            <div class="flex items-start space-x-3 flex-1">
              <div class="p-2 rounded-lg bg-gray-700">
                <div class="h-4 w-4 bg-gray-600 rounded animate-pulse"></div>
              </div>
              
              <div class="flex-1 min-w-0 space-y-2">
                <div class="flex items-center space-x-2">
                  <div class="h-4 bg-gray-600 rounded animate-pulse w-48"></div>
                  <div class="h-5 bg-gray-600 rounded animate-pulse w-12"></div>
                </div>
                
                <div class="flex items-center space-x-4 text-xs">
                  <div class="h-3 bg-gray-600 rounded animate-pulse w-24"></div>
                  <div class="h-3 bg-gray-600 rounded animate-pulse w-16"></div>
                  <div class="h-3 bg-gray-600 rounded animate-pulse w-20"></div>
                </div>
                
                <div class="h-4 bg-gray-600 rounded animate-pulse w-64"></div>
              </div>
            </div>
            
            <div class="flex items-center space-x-2">
              <div class="h-3 bg-gray-600 rounded animate-pulse w-16"></div>
              <div class="w-2 h-2 rounded-full bg-gray-600 animate-pulse"></div>
            </div>
          </div>
        </div>
      {/each}
    {/if}
  </div>

  <!-- Pagination Controls -->
  {#if pagination.total > 0}
    <div class="mt-4 pt-4 border-t border-gray-600">
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
          <span class="text-xs text-gray-400 font-mono">
            Page {pagination.page} of {pagination.pages} ({pagination.total} total)
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
        
        <div class="flex items-center space-x-2 text-xs text-gray-400">
          <div class="w-2 h-2 {isConnected ? 'bg-green-400' : 'bg-red-400'} rounded-full {isConnected ? 'animate-pulse' : ''}"></div>
          <span>{isConnected ? 'Live monitoring active' : 'Viewing historical data'}</span>
        </div>
      </div>
    </div>
  {/if}
</Card>

<!-- Anomaly Detail Modal -->
<IncidentDetailModal 
  show={showModal} 
  incident={selectedAnomaly} 
  onclose={closeModal} 
/>