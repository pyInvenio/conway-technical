<script lang="ts">
  import Card from '$lib/components/ui/Card.svelte';
  import Icon from '$lib/components/ui/Icon.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';

  interface TemporalPattern {
    type: string;
    start_time?: string;
    duration_minutes?: number;
    duration_hours?: number;
    event_count?: number;
    events_per_minute?: number;
    events_per_hour?: number;
    actor_count?: number;
    actors?: string[];
    severity: number;
    chi2_statistic?: number;
    p_value?: number;
    peak_hour_gmt?: number;
    peak_hour_count?: number;
    expected_count?: number;
  }

  interface TemporalData {
    temporal_anomaly_score: number;
    temporal_features: number[];
    feature_names: string[];
    detected_patterns: TemporalPattern[];
    analysis_type: string;
  }

  interface AnomalyData {
    temporal_analysis?: TemporalData;
    repository_name?: string;
    user_login?: string;
    event_timestamp?: string;
  }

  // Props
  let { anomalyData = null }: { anomalyData: AnomalyData | null } = $props();

  // Temporal feature descriptions
  const temporalFeatureDescriptions = {
    'events_per_minute_current': 'Current Events/Min',
    'events_per_minute_baseline_ratio': 'Baseline Ratio',
    'burst_intensity_score': 'Burst Intensity',
    'inter_event_regularity_score': 'Regularity Score',
    'coordination_score': 'Coordination Score',
    'off_hours_intensity_ratio': 'Off-Hours Ratio',
    'weekend_activity_ratio': 'Weekend Ratio',
    'time_concentration_score': 'Time Concentration',
    'velocity_acceleration': 'Velocity Acceleration'
  };

  // Pattern type icons and colors
  const patternTypeConfig = {
    'activity_burst': {
      icon: 'zap',
      color: 'text-yellow-400',
      bgColor: 'bg-yellow-500/20',
      borderColor: 'border-yellow-500/30',
      description: 'High activity burst'
    },
    'coordinated_activity': {
      icon: 'users',
      color: 'text-red-400',
      bgColor: 'bg-red-500/20',
      borderColor: 'border-red-500/30',
      description: 'Coordinated multi-actor activity'
    },
    'unusual_timing_distribution': {
      icon: 'clock',
      color: 'text-purple-400',
      bgColor: 'bg-purple-500/20',
      borderColor: 'border-purple-500/30',
      description: 'Unusual timing pattern'
    },
    'sustained_high_activity': {
      icon: 'trending-up',
      color: 'text-orange-400',
      bgColor: 'bg-orange-500/20',
      borderColor: 'border-orange-500/30',
      description: 'Sustained high activity'
    }
  };

  const temporalData = $derived(anomalyData?.temporal_analysis);
  const hasData = $derived(temporalData && temporalData.temporal_features?.length > 0);
  const patterns = $derived(temporalData?.detected_patterns || []);

  // Categorize patterns by severity
  const criticalPatterns = $derived(patterns.filter(p => p.severity >= 0.8));
  const highPatterns = $derived(patterns.filter(p => p.severity >= 0.6 && p.severity < 0.8));
  const mediumPatterns = $derived(patterns.filter(p => p.severity >= 0.4 && p.severity < 0.6));

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

  function getSeverityLabel(severity: number): string {
    if (severity >= 0.8) return 'Critical';
    if (severity >= 0.6) return 'High';
    if (severity >= 0.4) return 'Medium';
    return 'Low';
  }

  function formatFeatureValue(value: number, featureName: string): string {
    if (featureName.includes('ratio') || featureName.includes('score')) {
      return (value * 100).toFixed(1) + '%';
    }
    if (featureName.includes('events_per_minute')) {
      return value.toFixed(2) + '/min';
    }
    return value.toFixed(2);
  }

  function formatDuration(pattern: TemporalPattern): string {
    if (pattern.duration_hours) {
      return `${pattern.duration_hours}h`;
    }
    if (pattern.duration_minutes) {
      return `${pattern.duration_minutes}m`;
    }
    return 'Unknown';
  }

  function formatTimestamp(timestamp: string): string {
    try {
      return new Date(timestamp).toLocaleString();
    } catch {
      return timestamp;
    }
  }

  function getPatternConfig(patternType: string) {
    return patternTypeConfig[patternType] || {
      icon: 'activity',
      color: 'text-gray-400',
      bgColor: 'bg-gray-500/20',
      borderColor: 'border-gray-500/30',
      description: patternType
    };
  }

  function getFeatureIntensity(value: number): string {
    if (value >= 0.8) return 'Very High';
    if (value >= 0.6) return 'High';
    if (value >= 0.4) return 'Medium';
    if (value >= 0.2) return 'Low';
    return 'Very Low';
  }

  function getFeatureIntensityColor(value: number): string {
    if (value >= 0.8) return 'text-red-400';
    if (value >= 0.6) return 'text-orange-400';
    if (value >= 0.4) return 'text-yellow-400';
    if (value >= 0.2) return 'text-blue-400';
    return 'text-gray-400';
  }

  // Generate 24-hour activity heatmap data
  const activityHeatmap = $derived(temporalData ? Array.from({ length: 24 }, (_, hour) => {
    // For demonstration, we'll use the off-hours ratio and time concentration to simulate activity
    const baseActivity = 0.1;
    const offHoursRatio = temporalData.temporal_features[5] || 0;
    const timeConcentration = temporalData.temporal_features[7] || 0;
    
    // Simulate higher activity during off-hours if ratio is high
    let activity = baseActivity;
    if ((hour >= 2 && hour <= 8) || (hour >= 14 && hour <= 16)) {
      activity += offHoursRatio * 0.5;
    }
    
    // Add time concentration effect
    if (timeConcentration > 0.5) {
      activity += Math.random() * timeConcentration * 0.3;
    }
    
    return {
      hour,
      activity: Math.min(activity, 1),
      label: `${hour.toString().padStart(2, '0')}:00`
    };
  }) : []);
</script>

<Card class="p-6 bg-terminal-surface/50 border-terminal-border">
  <div class="flex items-center justify-between mb-6">
    <div class="flex items-center space-x-3">
      <div class="p-2 rounded-lg bg-purple-600/20 border border-purple-600/30">
        <Icon name="activity" class="h-5 w-5 text-purple-400" />
      </div>
      <div>
        <h3 class="text-lg font-semibold text-terminal-text font-mono">Temporal Pattern Analysis</h3>
        {#if anomalyData?.user_login}
          <p class="text-sm text-gray-400">Activity patterns for: {anomalyData.user_login}</p>
        {/if}
      </div>
    </div>
    
    {#if hasData}
      <div class="flex items-center space-x-4">
        <div class="text-right">
          <p class="text-sm text-gray-400">Temporal Score</p>
          <div class="flex items-center space-x-2">
            <span class="text-2xl font-bold text-white">
              {(temporalData.temporal_anomaly_score * 100).toFixed(1)}%
            </span>
            <Badge variant={getSeverityVariant(temporalData.temporal_anomaly_score)}>
              {getSeverityLabel(temporalData.temporal_anomaly_score)}
            </Badge>
          </div>
        </div>
        
        <div class="text-right">
          <p class="text-sm text-gray-400">Patterns</p>
          <span class="text-lg font-semibold text-white">
            {patterns.length}
          </span>
        </div>
      </div>
    {/if}
  </div>

  {#if !hasData}
    <div class="text-center py-8">
      <Icon name="clock" class="h-12 w-12 text-gray-400 mx-auto mb-3" />
      <p class="text-gray-400">No temporal pattern analysis available</p>
    </div>
  {:else}
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Detected Patterns -->
      <div>
        <h4 class="text-sm font-semibold text-gray-300 mb-3 flex items-center">
          <Icon name="search" class="h-4 w-4 mr-2" />
          Detected Patterns ({patterns.length})
        </h4>
        
        <div class="space-y-3 max-h-80 overflow-y-auto">
          {#if patterns.length === 0}
            <div class="text-center py-4">
              <Icon name="check-circle" class="h-8 w-8 text-green-400 mx-auto mb-2" />
              <p class="text-sm text-gray-400">No unusual patterns detected</p>
            </div>
          {:else}
            {#each patterns as pattern}
              {@const config = getPatternConfig(pattern.type)}
              <div class="rounded-lg p-4 border-l-4 {config.bgColor} {config.borderColor}">
                <div class="flex items-start justify-between mb-3">
                  <div class="flex items-center space-x-2">
                    <Icon name={config.icon} class="h-4 w-4 {config.color}" />
                    <span class="text-sm font-medium text-white">
                      {config.description}
                    </span>
                    <Badge variant={getSeverityVariant(pattern.severity)} size="sm">
                      {getSeverityLabel(pattern.severity)}
                    </Badge>
                  </div>
                </div>
                
                <div class="grid grid-cols-2 gap-4 text-xs">
                  {#if pattern.start_time}
                    <div>
                      <span class="text-gray-400">Start Time:</span>
                      <div class="text-white font-mono">{formatTimestamp(pattern.start_time)}</div>
                    </div>
                  {/if}
                  
                  {#if pattern.duration_minutes || pattern.duration_hours}
                    <div>
                      <span class="text-gray-400">Duration:</span>
                      <div class="text-white font-mono">{formatDuration(pattern)}</div>
                    </div>
                  {/if}
                  
                  {#if pattern.event_count}
                    <div>
                      <span class="text-gray-400">Events:</span>
                      <div class="text-white font-mono">{pattern.event_count}</div>
                    </div>
                  {/if}
                  
                  {#if pattern.events_per_minute}
                    <div>
                      <span class="text-gray-400">Rate:</span>
                      <div class="text-white font-mono">{pattern.events_per_minute.toFixed(2)}/min</div>
                    </div>
                  {/if}
                  
                  {#if pattern.actor_count}
                    <div>
                      <span class="text-gray-400">Actors:</span>
                      <div class="text-white font-mono">{pattern.actor_count}</div>
                    </div>
                  {/if}
                  
                  {#if pattern.peak_hour_gmt !== undefined}
                    <div>
                      <span class="text-gray-400">Peak Hour:</span>
                      <div class="text-white font-mono">{pattern.peak_hour_gmt.toString().padStart(2, '0')}:00 GMT</div>
                    </div>
                  {/if}
                </div>

                {#if pattern.actors && pattern.actors.length > 0}
                  <div class="mt-3">
                    <span class="text-xs text-gray-400">Involved actors:</span>
                    <div class="flex flex-wrap gap-1 mt-1">
                      {#each pattern.actors.slice(0, 5) as actor}
                        <span class="px-2 py-1 bg-gray-700/50 rounded text-xs text-gray-300 font-mono">
                          {actor}
                        </span>
                      {/each}
                      {#if pattern.actors.length > 5}
                        <span class="px-2 py-1 bg-gray-700/50 rounded text-xs text-gray-400">
                          +{pattern.actors.length - 5} more
                        </span>
                      {/if}
                    </div>
                  </div>
                {/if}

                {#if pattern.p_value !== undefined}
                  <div class="mt-2 text-xs text-gray-400">
                    Statistical significance: p = {pattern.p_value.toFixed(4)}
                  </div>
                {/if}
              </div>
            {/each}
          {/if}
        </div>

        <!-- Pattern severity breakdown -->
        {#if patterns.length > 0}
          <div class="mt-4 grid grid-cols-3 gap-2">
            <div class="text-center">
              <div class="text-lg font-bold text-red-400">{criticalPatterns.length}</div>
              <div class="text-xs text-gray-400">Critical</div>
            </div>
            <div class="text-center">
              <div class="text-lg font-bold text-orange-400">{highPatterns.length}</div>
              <div class="text-xs text-gray-400">High</div>
            </div>
            <div class="text-center">
              <div class="text-lg font-bold text-yellow-400">{mediumPatterns.length}</div>
              <div class="text-xs text-gray-400">Medium</div>
            </div>
          </div>
        {/if}
      </div>

      <!-- Temporal Features & Activity Heatmap -->
      <div>
        <h4 class="text-sm font-semibold text-gray-300 mb-3 flex items-center">
          <Icon name="bar-chart-3" class="h-4 w-4 mr-2" />
          Temporal Features
        </h4>
        
        <!-- Feature intensity grid -->
        <div class="grid grid-cols-1 gap-2 mb-6">
          {#each temporalData.feature_names as featureName, index}
            {@const value = temporalData.temporal_features[index]}
            {@const intensity = getFeatureIntensity(value)}
            {@const intensityColor = getFeatureIntensityColor(value)}
            
            <div class="bg-gray-800/30 rounded p-2">
              <div class="flex items-center justify-between">
                <span class="text-xs text-gray-300">
                  {temporalFeatureDescriptions[featureName] || featureName}
                </span>
                <div class="flex items-center space-x-2">
                  <span class="text-xs font-mono text-white">
                    {formatFeatureValue(value, featureName)}
                  </span>
                  <span class="text-xs {intensityColor}">
                    {intensity}
                  </span>
                </div>
              </div>
              
              <!-- Feature intensity bar -->
              <div class="mt-1 w-full bg-gray-700 rounded-full h-1">
                <div 
                  class="h-1 rounded-full transition-all duration-300 {
                    value >= 0.8 ? 'bg-red-400' :
                    value >= 0.6 ? 'bg-orange-400' :
                    value >= 0.4 ? 'bg-yellow-400' :
                    value >= 0.2 ? 'bg-blue-400' : 'bg-gray-400'
                  }"
                  style="width: {(value * 100)}%"
                ></div>
              </div>
            </div>
          {/each}
        </div>

        <!-- 24-hour activity heatmap -->
        <h5 class="text-xs font-semibold text-gray-400 mb-2">24-Hour Activity Pattern</h5>
        <div class="bg-gray-800/30 rounded-lg p-3">
          <div class="grid grid-cols-12 gap-1">
            {#each activityHeatmap as hour}
              <div 
                class="h-6 rounded text-xs flex items-center justify-center text-white font-mono transition-all duration-200 hover:scale-110"
                class:bg-gray-600={hour.activity < 0.1}
                class:bg-green-600={hour.activity >= 0.1 && hour.activity < 0.3}
                class:bg-yellow-600={hour.activity >= 0.3 && hour.activity < 0.6}
                class:bg-orange-600={hour.activity >= 0.6 && hour.activity < 0.8}
                class:bg-red-600={hour.activity >= 0.8}
                title="{hour.label}: {(hour.activity * 100).toFixed(1)}% activity"
              >
                {hour.hour}
              </div>
            {/each}
          </div>
          <div class="flex justify-between text-xs text-gray-400 mt-2">
            <span>00:00</span>
            <span>06:00</span>
            <span>12:00</span>
            <span>18:00</span>
            <span>23:00</span>
          </div>
          <div class="flex items-center justify-center space-x-4 mt-2 text-xs text-gray-400">
            <div class="flex items-center space-x-1">
              <div class="w-3 h-3 bg-gray-600 rounded"></div>
              <span>Low</span>
            </div>
            <div class="flex items-center space-x-1">
              <div class="w-3 h-3 bg-yellow-600 rounded"></div>
              <span>Medium</span>
            </div>
            <div class="flex items-center space-x-1">
              <div class="w-3 h-3 bg-red-600 rounded"></div>
              <span>High</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Analysis Summary -->
    <div class="mt-6 pt-4 border-t border-gray-700">
      <div class="flex items-center justify-between text-sm">
        <div class="flex items-center space-x-4 text-gray-400">
          <span>Analysis: {temporalData.analysis_type}</span>
          {#if anomalyData?.event_timestamp}
            <span>Event Time: {formatTimestamp(anomalyData.event_timestamp)}</span>
          {/if}
        </div>
        
        <div class="flex items-center space-x-2">
          <div class="w-2 h-2 rounded-full {temporalData.temporal_anomaly_score > 0.5 ? 'bg-orange-400 animate-pulse' : 'bg-green-400'}"></div>
          <span class="text-xs text-gray-400">
            {temporalData.temporal_anomaly_score > 0.5 ? 'Temporal Anomalies Detected' : 'Normal Temporal Patterns'}
          </span>
        </div>
      </div>
    </div>
  {/if}
</Card>