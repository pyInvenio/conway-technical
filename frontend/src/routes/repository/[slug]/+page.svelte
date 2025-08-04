<script lang="ts">
  import { page } from '$app/stores';
  import Icon from '$lib/components/ui/Icon.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import IncidentDetailModal from '$lib/components/dashboard/IncidentDetailModal.svelte';
  import { 
    parseAISummary, 
    parseRiskIndicators, 
    getIncidentTypeDisplay, 
    getSeverityColor,
    getPrimaryDetectionMethod,
    generateFallbackSummary
  } from '$lib/utils/summaryParser';
  
  let { data } = $props();
  
  // Define interface locally to avoid import issues
  interface ComponentScores {
    behavioral: number;
    content: number;
    temporal: number;
    repository: number;
  }
  
  // Calculate repository threat landscape
  let threatAnalysis = $derived(
    (() => {
      if (!data.repository.anomalies || data.repository.anomalies.length === 0) {
        return { 
          criticalAnomalies: 0, 
          highAnomalies: 0, 
          totalAnomalies: 0,
          threatCategories: {},
          riskTrend: 'stable'
        };
      }

      const anomalies = data.repository.anomalies;
      const critical = anomalies.filter(a => a.severity_level === 'CRITICAL').length;
      const high = anomalies.filter(a => a.severity_level === 'HIGH').length;
      
      // Categorize threats by primary detection method  
      const categories = {};
      anomalies.forEach(anomaly => {
        const componentScores: ComponentScores = {
          behavioral: anomaly.behavioral_anomaly_score || 0,
          content: anomaly.content_risk_score || 0,
          temporal: anomaly.temporal_anomaly_score || 0,
          repository: anomaly.repository_criticality_score || 0
        };
        
        const primary = getPrimaryDetectionMethod(componentScores);
        const category = primary.method;
        categories[category] = (categories[category] || 0) + 1;
      });

      return {
        criticalAnomalies: critical,
        highAnomalies: high,
        totalAnomalies: anomalies.length,
        threatCategories: categories,
        riskTrend: critical > 0 ? 'increasing' : high > 2 ? 'elevated' : 'stable'
      };
    })()
  );
  
  // Modal state
  let selectedIncident = $state(null);
  let showModal = $state(false);
  
  function openIncidentDetail(incident) {
    selectedIncident = incident;
    showModal = true;
  }
  
  function closeModal() {
    showModal = false;
    selectedIncident = null;
  }
  
  function getSeverityVariant(severity) {
    if (severity >= 0.8) return 'error';
    if (severity >= 0.6) return 'warning';
    return 'info';
  }
  
  function getTypeIcon(type) {
    if (!type) return 'alert-triangle';
    switch (type.toLowerCase()) {
      case 'pushevent':
      case 'force_push': return 'git-branch';
      case 'workflowrunevent':
      case 'workflow_failure': return 'alert-triangle';
      case 'deleteevent':
      case 'mass_deletion': return 'trash-2';
      case 'bursty_activity': return 'activity';
      case 'suspicious_commits': return 'file-warning';
      case 'anomalous_activity': return 'alert-circle';
      case 'pullrequestevent': return 'git-pull-request';
      case 'issuesevent': return 'alert-circle';
      case 'createevent': return 'plus';
      case 'releaseevent': return 'tag';
      case 'forkevent': return 'git-fork';
      case 'watchevent': return 'eye';
      default: return 'alert-triangle';
    }
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
  
  function getRiskColor(score) {
    if (score >= 80) return 'from-red-500 to-orange-500';
    if (score >= 60) return 'from-orange-500 to-yellow-500';
    return 'from-green-500 to-blue-500';
  }
</script>

<svelte:head>
  <title>Repository: {data.repository.name} - GitHub Monitor</title>
</svelte:head>

<div class="min-h-screen bg-gray-900 text-gray-100">
  <div class="container mx-auto px-6 py-8">
    <!-- Breadcrumb -->
    <nav class="flex items-center space-x-2 text-sm text-gray-400 mb-6">
      <a href="/" class="hover:text-gray-100 transition-colors">Dashboard</a>
      <Icon name="chevron-right" class="h-4 w-4" />
      <span class="text-gray-100">Repository</span>
      <Icon name="chevron-right" class="h-4 w-4" />
      <span class="text-gray-100 font-mono">{data.repository.name}</span>
    </nav>

    <!-- Repository Header -->
    <div class="mb-8">
      <div class="flex items-start justify-between mb-6">
        <div class="flex items-center space-x-4">
          <Icon name="github" class="h-8 w-8 text-gray-400" />
          <div>
            <h1 class="text-3xl font-bold text-gray-100 font-mono">{data.repository.name}</h1>
            <div class="flex items-center space-x-4 mt-2">
              <a 
                href="https://github.com/{data.repository.name}" 
                target="_blank" 
                rel="noopener noreferrer"
                class="text-blue-400 hover:text-blue-300 text-sm flex items-center space-x-1"
              >
                <Icon name="external-link" class="h-4 w-4" />
                <span>View on GitHub</span>
              </a>
              <span class="text-gray-400 text-sm">•</span>
              <span class="text-gray-400 text-sm">Last activity: {timeAgo(data.repository.lastActivity)}</span>
            </div>
          </div>
        </div>
        
        <Badge variant={data.repository.status === 'critical' ? 'error' : data.repository.status === 'warning' ? 'warning' : 'success'}>
          {data.repository.status}
        </Badge>
      </div>

      <!-- Threat Landscape Overview -->
      <div class="space-y-6">
        <h2 class="text-xl font-semibold text-gray-100 flex items-center space-x-2">
          <Icon name="shield-alert" class="h-5 w-5 text-red-400" />
          <span>Repository Threat Landscape</span>
        </h2>

        <!-- Risk Metrics -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
          <Card class="p-6 bg-red-900/20 border-red-400/30">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold text-red-400">Critical Threats</h3>
              <Icon name="alert-octagon" class="h-6 w-6 text-red-400" />  
            </div>
            <div class="text-3xl font-mono text-red-400 mb-2">{threatAnalysis.criticalAnomalies}</div>
            <p class="text-xs text-gray-400">Requiring immediate attention</p>
          </Card>

          <Card class="p-6 bg-orange-900/20 border-orange-400/30">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold text-orange-400">High Risk Events</h3>
              <Icon name="alert-triangle" class="h-6 w-6 text-orange-400" />
            </div>
            <div class="text-3xl font-mono text-orange-400 mb-2">{threatAnalysis.highAnomalies}</div>
            <p class="text-xs text-gray-400">Elevated security concerns</p>
          </Card>

          <Card class="p-6 bg-gray-800/50 border-gray-600">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold text-gray-100">Overall Risk Score</h3>
              <Icon name="gauge" class="h-6 w-6 text-gray-400" />
            </div>
            <div class="text-3xl font-mono {getSeverityColor(data.repository.riskScore / 100)} mb-2">{data.repository.riskScore}/100</div>
            <div class="w-full bg-gray-700 rounded-full h-2">
              <div 
                class="h-2 rounded-full bg-gradient-to-r {getRiskColor(data.repository.riskScore)}"
                style="width: {data.repository.riskScore}%"
              ></div>
            </div>
          </Card>

          <Card class="p-6 bg-blue-900/20 border-blue-400/30">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold text-blue-400">Monitoring Status</h3>
              <div class="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
            </div>
            <div class="text-lg font-medium text-green-400 mb-2">Active</div>
            <p class="text-xs text-gray-400">Real-time threat detection enabled</p>
          </Card>
        </div>

        <!-- Detection Methods Breakdown -->
        {#if threatAnalysis && threatAnalysis.threatCategories && Object.keys(threatAnalysis.threatCategories).length > 0}
          <Card class="p-6 bg-gray-800/50 border-gray-600">
            <h3 class="text-lg font-semibold text-gray-100 mb-4 flex items-center space-x-2">
              <Icon name="pie-chart" class="h-5 w-5 text-purple-400" />
              <span>AI Detection Methods</span>
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {#each Object.entries(threatAnalysis.threatCategories) as [method, count]}
                <div class="p-4 bg-gray-900/50 rounded-lg border border-gray-600">
                  <div class="flex items-center justify-between mb-2">
                    <span class="text-sm font-medium text-gray-300">{method}</span>
                    <Icon name="zap" class="h-4 w-4 text-purple-400" />
                  </div>
                  <div class="text-2xl font-mono text-purple-400 mb-1">{count}</div>
                  <div class="text-xs text-gray-400">
                    {((count / threatAnalysis.totalAnomalies) * 100).toFixed(1)}% of threats
                  </div>
                  <div class="w-full bg-gray-700 rounded-full h-1 mt-2">
                    <div class="bg-purple-400 h-1 rounded-full" 
                         style="width: {(count / threatAnalysis.totalAnomalies) * 100}%"></div>
                  </div>
                </div>
              {/each}
            </div>
          </Card>
        {/if}

        <!-- Risk Trend Analysis -->
        <Card class="p-6 bg-gray-800/50 border-gray-600">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-semibold text-gray-100 flex items-center space-x-2">
              <Icon name="trending-up" class="h-5 w-5 text-yellow-400" />
              <span>Risk Assessment</span>
            </h3>
            <Badge variant="outline" class="
              {threatAnalysis.riskTrend === 'increasing' ? 'bg-red-900/30 border-red-400/50 text-red-300' :
               threatAnalysis.riskTrend === 'elevated' ? 'bg-orange-900/30 border-orange-400/50 text-orange-300' :
               'bg-green-900/30 border-green-400/50 text-green-300'}
            ">
              {threatAnalysis.riskTrend === 'increasing' ? 'High Risk' :
               threatAnalysis.riskTrend === 'elevated' ? 'Elevated Risk' : 'Stable'}
            </Badge>
          </div>
          
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="space-y-3">
              <h4 class="text-sm font-medium text-gray-300">Threat Summary</h4>
              <div class="space-y-2">
                <div class="flex justify-between text-sm">
                  <span class="text-gray-400">Total Anomalies:</span>
                  <span class="text-gray-100 font-mono">{threatAnalysis.totalAnomalies}</span>
                </div>
                <div class="flex justify-between text-sm">
                  <span class="text-gray-400">High Priority:</span>
                  <span class="text-orange-400 font-mono">{threatAnalysis.criticalAnomalies + threatAnalysis.highAnomalies}</span>
                </div>
                <div class="flex justify-between text-sm">
                  <span class="text-gray-400">Last Activity:</span>
                  <span class="text-gray-100 font-mono">{timeAgo(data.repository.lastActivity)}</span>
                </div>
              </div>
            </div>

            <div class="space-y-3">
              <h4 class="text-sm font-medium text-gray-300">Detection</h4>
              <div class="space-y-2 text-sm text-gray-400">
                <div class="flex items-center space-x-2">
                  <Icon name="check-circle" class="h-4 w-4 text-green-400" />
                  <span>Force push monitoring</span>
                </div>
                <div class="flex items-center space-x-2">
                  <Icon name="check-circle" class="h-4 w-4 text-green-400" />
                  <span>Workflow failure detection</span>
                </div>
                <div class="flex items-center space-x-2">
                  <Icon name="check-circle" class="h-4 w-4 text-green-400" />
                  <span>Secret exposure scanning</span>
                </div>
                <div class="flex items-center space-x-2">
                  <Icon name="check-circle" class="h-4 w-4 text-green-400" />
                  <span>Bursty activity analysis</span>
                </div>
              </div>
            </div>

            <div class="space-y-3">
              <h4 class="text-sm font-medium text-gray-300">Recommendations</h4>
              <div class="space-y-2 text-sm">
                {#if threatAnalysis.riskTrend === 'increasing'}
                  <div class="flex items-center space-x-2 text-red-300">
                    <Icon name="alert-triangle" class="h-4 w-4" />
                    <span>Immediate security review required</span>
                  </div>
                  <div class="flex items-center space-x-2 text-orange-300">
                    <Icon name="shield" class="h-4 w-4" />
                    <span>Enable enhanced monitoring</span>
                  </div>
                {:else if threatAnalysis.riskTrend === 'elevated'}
                  <div class="flex items-center space-x-2 text-orange-300">
                    <Icon name="eye" class="h-4 w-4" />
                    <span>Monitor closely for patterns</span>
                  </div>
                  <div class="flex items-center space-x-2 text-blue-300">
                    <Icon name="settings" class="h-4 w-4" />
                    <span>Review access controls</span>
                  </div>
                {:else}
                  <div class="flex items-center space-x-2 text-green-300">
                    <Icon name="check-circle" class="h-4 w-4" />
                    <span>Security posture is stable</span>
                  </div>
                  <div class="flex items-center space-x-2 text-blue-300">
                    <Icon name="refresh-ccw" class="h-4 w-4" />
                    <span>Continue regular monitoring</span>
                  </div>
                {/if}
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>

    <!-- Incidents Section -->
    <Card class="p-6 bg-gray-800/50 border-gray-600">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-xl font-semibold text-gray-100 flex items-center space-x-2">
          <Icon name="alert-triangle" class="h-5 w-5 text-orange-400" />
          <span>Security Incidents ({data.repository.anomalies ? data.repository.anomalies.length : 0})</span>
        </h2>
      </div>

      {#if data.repository.anomalies && data.repository.anomalies.length > 0}
        <div class="space-y-4">
          {#each data.repository.anomalies as incident}
            {@const componentScores = {
              behavioral: incident.behavioral_anomaly_score || 0,
              content: incident.content_risk_score || 0,
              temporal: incident.temporal_anomaly_score || 0,
              repository: incident.repository_criticality_score || 0
            }}
            {@const summary = parseAISummary(incident.ai_summary) || 
              generateFallbackSummary(
                incident.event_type,
                incident.final_anomaly_score,
                incident.repository_name,
                componentScores
              )}
            {@const detectionInfo = getPrimaryDetectionMethod(componentScores)}
            <div 
              class="p-4 rounded-lg border border-gray-600 bg-gray-900/50 hover:bg-gray-900/70 transition-colors cursor-pointer"
              onclick={() => openIncidentDetail(incident)}
              role="button"
              tabindex="0"
              onkeydown={(e) => e.key === 'Enter' && openIncidentDetail(incident)}
            >
              <div class="flex items-start justify-between">
                <div class="flex items-start space-x-3 flex-1">
                  <div class="p-2 rounded-lg bg-gray-700 border border-gray-600">
                    <Icon 
                      name={getTypeIcon(incident.event_type)} 
                      class="h-4 w-4 text-orange-400" 
                    />
                  </div>
                  
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center space-x-2 mb-2">
                      <h4 class="text-sm font-medium text-gray-100 truncate">
                        {incident.title || `${incident.event_type} anomaly detected`}
                      </h4>
                      <Badge variant={getSeverityVariant(incident.final_anomaly_score)}>
                        {Math.round((incident.final_anomaly_score || 0) * 100)}%
                      </Badge>
                      <Badge variant="outline" class="bg-blue-900/30 border-blue-400/50 text-blue-300 text-xs">
                        <Icon name="zap" class="h-3 w-3 mr-1" />
                        {detectionInfo.method}
                      </Badge>
                    </div>
                    
                    <div class="flex items-center space-x-4 mb-2 text-xs text-gray-400">
                      <span>{incident.event_type || 'Unknown'}</span>
                      <span>•</span>
                      <div class="flex items-center space-x-1">
                        <Icon name="clock" class="h-3 w-3" />
                        <span>{timeAgo(incident.detection_timestamp || incident.created_at)}</span>
                      </div>
                      {#if incident.event_id}
                        <span>•</span>
                        <span>Event #{incident.event_id}</span>
                      {/if}
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
                        </ul>
                      </div>
                    {:else}
                      <p class="text-sm text-gray-400">
                        Security anomaly detected in {incident.event_type}
                      </p>
                    {/if}
                  </div>
                </div>
                
                <div class="flex items-center space-x-2">
                  <div class="text-right">
                    <div class="text-xs text-gray-400 font-mono">
                      {new Date(incident.detection_timestamp || incident.created_at).toLocaleTimeString()}
                    </div>
                  </div>
                  <Icon name="chevron-right" class="h-4 w-4 text-gray-400" />
                </div>
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <div class="text-center py-12">
          <Icon name="shield-check" class="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 class="text-lg font-medium text-gray-100 mb-2">No incidents detected</h3>
          <p class="text-gray-400">This repository appears to be operating normally.</p>
        </div>
      {/if}
    </Card>
  </div>
</div>

<!-- Incident Detail Modal -->
<IncidentDetailModal 
  show={showModal} 
  incident={selectedIncident} 
  onclose={closeModal} 
/>