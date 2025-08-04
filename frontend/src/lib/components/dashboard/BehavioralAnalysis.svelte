<script lang="ts">
  import Card from '$lib/components/ui/Card.svelte';
  import Icon from '$lib/components/ui/Icon.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';

  interface BehavioralAnomalyData {
    behavioral_anomaly_score: number;
    detected_anomalies: Array<{
      type: string;
      feature_name?: string;
      current_value?: number;
      baseline_mean?: number;
      baseline_std?: number;
      z_score?: number;
      severity: number;
      mahalanobis_distance?: number;
      chi2_critical?: number;
    }>;
    current_features: number[];
    feature_names: string[];
    baseline_comparison?: Record<string, {
      current: number;
      baseline_mean: number;
      baseline_std: number;
      percent_change: number;
      z_score: number;
      direction: 'increase' | 'decrease' | 'stable';
    }>;
    confidence?: number;
    analysis_type: string;
  }

  interface AnomalyData {
    behavioral_analysis?: BehavioralAnomalyData;
    repository_name?: string;
    user_login?: string;
    event_timestamp?: string;
  }

  // Props
  let { anomalyData = null }: { anomalyData: AnomalyData | null } = $props();

  // Behavioral feature descriptions for better UI
  const featureDescriptions = {
    'events_per_hour': 'Events Per Hour',
    'repository_diversity_ratio': 'Repository Diversity',
    'avg_inter_event_interval_minutes': 'Inter-Event Interval (min)',
    'commit_message_length_avg': 'Avg Commit Message Length',
    'files_changed_per_commit_avg': 'Files Per Commit',
    'activity_burst_score': 'Activity Burst Score',
    'time_spread_hours': 'Time Spread (hours)',
    'event_type_entropy': 'Event Type Diversity',
    'weekend_activity_ratio': 'Weekend Activity Ratio',
    'off_hours_activity_ratio': 'Off-Hours Activity Ratio'
  };

  const behavioralData = $derived(anomalyData?.behavioral_analysis);
  const hasData = $derived(behavioralData && behavioralData.current_features?.length > 0);
  const anomalies = $derived(behavioralData?.detected_anomalies || []);
  const statisticalAnomalies = $derived(anomalies.filter(a => a.type === 'statistical_deviation'));
  const multivariateAnomalies = $derived(anomalies.filter(a => a.type === 'multivariate_anomaly'));

  function getSeverityColor(severity: number): string {
    if (severity >= 0.8) return 'bg-red-500';
    if (severity >= 0.6) return 'bg-orange-500';
    if (severity >= 0.4) return 'bg-yellow-500';
    return 'bg-green-500';
  }

  function getSeverityVariant(severity: number): 'error' | 'warning' | 'info' {
    if (severity >= 0.8) return 'error';
    if (severity >= 0.6) return 'warning';
    return 'info';
  }

  function formatFeatureValue(value: number, featureName: string): string {
    if (featureName.includes('ratio') || featureName.includes('score')) {
      return (value * 100).toFixed(1) + '%';
    }
    if (featureName.includes('minutes') || featureName.includes('hours')) {
      return value.toFixed(1);
    }
    return value.toFixed(2);
  }

  function getDirectionIcon(direction: string): string {
    switch (direction) {
      case 'increase': return 'trending-up';
      case 'decrease': return 'trending-down';
      default: return 'minus';
    }
  }

  function getDirectionColor(direction: string, zScore: number): string {
    if (direction === 'stable') return 'text-gray-400';
    const isAnomalous = Math.abs(zScore) > 2.0;
    if (direction === 'increase') {
      return isAnomalous ? 'text-red-400' : 'text-blue-400';
    } else {
      return isAnomalous ? 'text-orange-400' : 'text-green-400';
    }
  }

  // Generate radar chart data for visualization
  const radarData = $derived(hasData ? behavioralData.feature_names.map((name, index) => ({
    feature: featureDescriptions[name] || name,
    current: behavioralData.current_features[index] || 0,
    baseline: behavioralData.baseline_comparison?.[name]?.baseline_mean || 0,
    normalized: Math.min(behavioralData.current_features[index] / 10, 1) // Simple normalization for display
  })) : []);
</script>

<Card class="p-6 bg-terminal-surface/50 border-terminal-border">
  <div class="flex items-center justify-between mb-6">
    <div class="flex items-center space-x-3">
      <div class="p-2 rounded-lg bg-blue-600/20 border border-blue-600/30">
        <Icon name="user-check" class="h-5 w-5 text-blue-400" />
      </div>
      <div>
        <h3 class="text-lg font-semibold text-terminal-text font-mono">Behavioral Analysis</h3>
        {#if anomalyData?.user_login}
          <p class="text-sm text-gray-400">User: {anomalyData.user_login}</p>
        {/if}
      </div>
    </div>
    
    {#if hasData}
      <div class="flex items-center space-x-4">
        <div class="text-right">
          <p class="text-sm text-gray-400">Anomaly Score</p>
          <div class="flex items-center space-x-2">
            <span class="text-2xl font-bold text-white">
              {(behavioralData.behavioral_anomaly_score * 100).toFixed(1)}%
            </span>
            <Badge variant={getSeverityVariant(behavioralData.behavioral_anomaly_score)}>
              {behavioralData.behavioral_anomaly_score >= 0.8 ? 'Critical' : 
               behavioralData.behavioral_anomaly_score >= 0.6 ? 'High' : 
               behavioralData.behavioral_anomaly_score >= 0.4 ? 'Medium' : 'Low'}
            </Badge>
          </div>
        </div>
        
        {#if behavioralData.confidence}
          <div class="text-right">
            <p class="text-sm text-gray-400">Confidence</p>
            <span class="text-lg font-semibold text-white">
              {(behavioralData.confidence * 100).toFixed(0)}%
            </span>
          </div>
        {/if}
      </div>
    {/if}
  </div>

  {#if !hasData}
    <div class="text-center py-8">
      <Icon name="alert-circle" class="h-12 w-12 text-gray-400 mx-auto mb-3" />
      <p class="text-gray-400">No behavioral analysis data available</p>
    </div>
  {:else}
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Feature Comparison Table -->
      <div>
        <h4 class="text-sm font-semibold text-gray-300 mb-3 flex items-center">
          <Icon name="bar-chart-3" class="h-4 w-4 mr-2" />
          Feature Analysis
        </h4>
        
        <div class="bg-gray-800/50 rounded-lg overflow-hidden">
          <div class="max-h-80 overflow-y-auto">
            <table class="w-full text-sm">
              <thead class="bg-gray-700/50 sticky top-0">
                <tr class="text-left">
                  <th class="px-3 py-2 text-gray-300">Feature</th>
                  <th class="px-3 py-2 text-gray-300">Current</th>
                  <th class="px-3 py-2 text-gray-300">Change</th>
                  <th class="px-3 py-2 text-gray-300">Z-Score</th>
                </tr>
              </thead>
              <tbody>
                {#each behavioralData.feature_names as featureName, index}
                  {@const current = behavioralData.current_features[index]}
                  {@const comparison = behavioralData.baseline_comparison?.[featureName]}
                  <tr class="border-t border-gray-700/50 hover:bg-gray-700/30">
                    <td class="px-3 py-2">
                      <div class="font-medium text-gray-100">
                        {featureDescriptions[featureName] || featureName}
                      </div>
                    </td>
                    <td class="px-3 py-2 font-mono text-white">
                      {formatFeatureValue(current, featureName)}
                    </td>
                    <td class="px-3 py-2">
                      {#if comparison}
                        <div class="flex items-center space-x-1">
                          <Icon 
                            name={getDirectionIcon(comparison.direction)} 
                            class="h-3 w-3 {getDirectionColor(comparison.direction, comparison.z_score)}" 
                          />
                          <span class="text-xs {getDirectionColor(comparison.direction, comparison.z_score)}">
                            {comparison.percent_change > 0 ? '+' : ''}{comparison.percent_change.toFixed(1)}%
                          </span>
                        </div>
                      {:else}
                        <span class="text-gray-500 text-xs">No baseline</span>
                      {/if}
                    </td>
                    <td class="px-3 py-2">
                      {#if comparison}
                        <span class="font-mono text-xs {Math.abs(comparison.z_score) > 2 ? 'text-red-400' : 'text-gray-400'}">
                          {comparison.z_score.toFixed(2)}
                        </span>
                      {:else}
                        <span class="text-gray-500 text-xs">—</span>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Detected Anomalies -->
      <div>
        <h4 class="text-sm font-semibold text-gray-300 mb-3 flex items-center">
          <Icon name="alert-triangle" class="h-4 w-4 mr-2" />
          Detected Anomalies ({anomalies.length})
        </h4>
        
        <div class="space-y-3 max-h-80 overflow-y-auto">
          {#if anomalies.length === 0}
            <div class="text-center py-4">
              <Icon name="check-circle" class="h-8 w-8 text-green-400 mx-auto mb-2" />
              <p class="text-sm text-gray-400">No anomalies detected</p>
            </div>
          {:else}
            {#each anomalies as anomaly}
              <div class="bg-gray-800/50 rounded-lg p-3 border-l-4 {getSeverityColor(anomaly.severity)}">
                <div class="flex items-start justify-between">
                  <div class="flex-1">
                    <div class="flex items-center space-x-2 mb-1">
                      <span class="text-sm font-medium text-white">
                        {anomaly.type === 'statistical_deviation' ? 'Statistical Deviation' : 
                         anomaly.type === 'multivariate_anomaly' ? 'Multivariate Anomaly' : 
                         anomaly.type}
                      </span>
                      <Badge variant={getSeverityVariant(anomaly.severity)} size="sm">
                        {(anomaly.severity * 100).toFixed(0)}%
                      </Badge>
                    </div>
                    
                    {#if anomaly.feature_name}
                      <p class="text-sm text-gray-300 mb-1">
                        Feature: {featureDescriptions[anomaly.feature_name] || anomaly.feature_name}
                      </p>
                    {/if}
                    
                    <div class="flex items-center space-x-4 text-xs text-gray-400">
                      {#if anomaly.current_value !== undefined}
                        <span>Current: {formatFeatureValue(anomaly.current_value, anomaly.feature_name || '')}</span>
                      {/if}
                      {#if anomaly.z_score !== undefined}
                        <span>Z-score: {anomaly.z_score.toFixed(2)}</span>
                      {/if}
                      {#if anomaly.mahalanobis_distance !== undefined}
                        <span>Mahalanobis: {anomaly.mahalanobis_distance.toFixed(2)}</span>
                      {/if}
                    </div>
                  </div>
                </div>
              </div>
            {/each}
          {/if}
        </div>
      </div>
    </div>

    <!-- Analysis Summary -->
    <div class="mt-6 pt-4 border-t border-gray-700">
      <div class="flex items-center justify-between text-sm">
        <div class="flex items-center space-x-4 text-gray-400">
          <span>Analysis Type: {behavioralData.analysis_type}</span>
          {#if anomalyData?.event_timestamp}
            <span>Timestamp: {new Date(anomalyData.event_timestamp).toLocaleString()}</span>
          {/if}
        </div>
        
        <div class="flex items-center space-x-2">
          <div class="w-2 h-2 rounded-full {hasData ? 'bg-green-400 animate-pulse' : 'bg-gray-400'}"></div>
          <span class="text-xs text-gray-400">
            {behavioralData.confidence ? 'High Confidence' : 'Analysis Complete'}
          </span>
        </div>
      </div>
    </div>
  {/if}
</Card>