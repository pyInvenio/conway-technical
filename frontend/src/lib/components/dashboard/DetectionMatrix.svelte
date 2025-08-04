<script lang="ts">
  console.log('🚀 DetectionMatrix component loading...');
  
  import Card from '$lib/components/ui/Card.svelte';
  import Icon from '$lib/components/ui/Icon.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { 
    getPrimaryDetectionMethod,
    parseAISummary,
    generateFallbackSummary,
    type ComponentScores 
  } from '$lib/utils/summaryParser';
  import { anomalyStore } from '$lib/stores/incidents.svelte';
  
  console.log('✅ DetectionMatrix imports loaded');
  
  // Basic test
  console.log('🧪 Testing anomalyStore access:', anomalyStore);
  console.log('🧪 Testing anomalyStore.anomalies:', anomalyStore.anomalies);

  interface AnomalyDataPoint {
    id: string;
    repository_name: string;
    user_login: string;
    timestamp?: string;
    detection_timestamp: string;
    event_type: string;
    final_anomaly_score: number;
    severity_level: string;
    behavioral_anomaly_score: number;
    content_risk_score: number;
    temporal_anomaly_score: number;
    repository_criticality_score: number;
    detection_scores?: {
      behavioral?: number;
      content?: number;
      temporal?: number;
      repository_criticality?: number;
    };
    ai_summary?: string;
  }

  interface MatrixCell {
    method: string;
    timeSlot: string;
    anomalies: AnomalyDataPoint[];
    count: number;
    avgScore: number;
    maxScore: number;
    criticalCount: number;
  }

  // Copy EXACT pattern from IncidentFeed - CLEAN
  const anomalies = $derived(anomalyStore.anomalies);
  const safeAnomalies = anomalies || [];
  
  // Simple effect to watch changes
  $effect(() => {
    console.log('✅ DetectionMatrix: anomalies updated to', anomalies?.length || 0);
  });

  // State
  let selectedCell: MatrixCell | null = $state(null);
  let hoveredCell: MatrixCell | null = $state(null);
  let showDetails = $state(false);

  // Detection methods configuration
  const detectionMethods = [
    { 
      key: 'behavioral', 
      label: 'Behavioral AI', 
      icon: 'users', 
      color: 'bg-orange-500',
      description: 'User behavior pattern analysis'
    },
    { 
      key: 'content', 
      label: 'Content Analysis', 
      icon: 'file-text', 
      color: 'bg-red-500',
      description: 'Secret detection & code analysis'
    },
    { 
      key: 'temporal', 
      label: 'Temporal Patterns', 
      icon: 'clock', 
      color: 'bg-yellow-500',
      description: 'Time-based anomaly detection'
    },
    { 
      key: 'repository', 
      label: 'Repository Context', 
      icon: 'shield', 
      color: 'bg-blue-500',
      description: 'Repository criticality scoring'
    }
  ];

  // Time slots configuration (last 24 hours in 4-hour chunks)
  const timeSlots = [
    { key: '0-4h', label: 'Last 4h', hours: 4 },
    { key: '4-8h', label: '4-8h ago', hours: 8 },
    { key: '8-12h', label: '8-12h ago', hours: 12 },
    { key: '12-16h', label: '12-16h ago', hours: 16 },
    { key: '16-20h', label: '16-20h ago', hours: 20 },
    { key: '20-24h', label: '20-24h ago', hours: 24 }
  ];

  // Create detection matrix
  const detectionMatrix = $derived(() => {
    const matrix: MatrixCell[] = [];
    const now = new Date();
    
    console.log('DetectionMatrix: Building matrix with', safeAnomalies.length, 'anomalies');
    console.log('DetectionMatrix: Current time:', now);

    detectionMethods.forEach(method => {
      timeSlots.forEach(timeSlot => {
        // Filter anomalies for this method and time slot
        const cellAnomalies = safeAnomalies.filter(anomaly => {
          // Check time slot
          const anomalyTime = new Date(anomaly.timestamp || anomaly.detection_timestamp);
          const hoursAgo = (now.getTime() - anomalyTime.getTime()) / (1000 * 60 * 60);
          const inTimeSlot = hoursAgo >= (timeSlot.hours - 4) && hoursAgo < timeSlot.hours;
          
          // Log first few anomalies for debugging
          if (method.key === 'behavioral' && timeSlot.key === '0-4h' && safeAnomalies.indexOf(anomaly) < 3) {
            console.log('DetectionMatrix: Time filtering debug for', anomaly.repository_name, ':', {
              timestamp: anomaly.timestamp || anomaly.detection_timestamp,
              anomalyTime: anomalyTime,
              hoursAgo: hoursAgo,
              timeSlot: timeSlot.key + ' (' + (timeSlot.hours - 4) + '-' + timeSlot.hours + 'h)',
              inTimeSlot: inTimeSlot
            });
          }
          
          if (!inTimeSlot) return false;

          // Check if this is the primary detection method
          const componentScores: ComponentScores = {
            behavioral: Number(anomaly.behavioral_anomaly_score || anomaly.detection_scores?.behavioral) || 0,
            content: Number(anomaly.content_risk_score || anomaly.detection_scores?.content) || 0,
            temporal: Number(anomaly.temporal_anomaly_score || anomaly.detection_scores?.temporal) || 0,
            repository: Number(anomaly.repository_criticality_score || anomaly.detection_scores?.repository_criticality) || 0
          };

          console.log('DetectionMatrix anomaly data for', anomaly.repository_name, ':', {
            flat_scores: {
              behavioral: anomaly.behavioral_anomaly_score,
              content: anomaly.content_risk_score,
              temporal: anomaly.temporal_anomaly_score,
              repository: anomaly.repository_criticality_score
            },
            nested_scores: anomaly.detection_scores,
            final_scores: componentScores
          });

          const primaryMethod = getPrimaryDetectionMethod(componentScores);
          console.log('DetectionMatrix primary method for', anomaly.repository_name, ':', primaryMethod);
          
          // Map method names to match our keys
          const methodMap = {
            'Behavioral Analysis': 'behavioral',
            'Content Analysis': 'content', 
            'Temporal Analysis': 'temporal',
            'Repository Analysis': 'repository'
          };

          return methodMap[primaryMethod.method] === method.key;
        });

        // Calculate cell statistics
        const count = cellAnomalies.length;
        const scores = cellAnomalies.map(a => a.final_anomaly_score);
        const avgScore = count > 0 ? scores.reduce((sum, score) => sum + score, 0) / count : 0;
        const maxScore = count > 0 ? Math.max(...scores) : 0;
        const criticalCount = cellAnomalies.filter(a => 
          a.severity_level === 'CRITICAL' || a.final_anomaly_score >= 0.8
        ).length;

        matrix.push({
          method: method.key,
          timeSlot: timeSlot.key,
          anomalies: cellAnomalies,
          count,
          avgScore,
          maxScore,
          criticalCount
        });
        
        // Log cells with anomalies
        if (count > 0) {
          console.log(`DetectionMatrix: Cell ${method.key}-${timeSlot.key} has ${count} anomalies`);
        }
      });
    });

    const totalCellsWithData = matrix.filter(cell => cell.count > 0).length;
    console.log(`DetectionMatrix: Generated ${matrix.length} total cells, ${totalCellsWithData} with data`);
    
    return matrix;
  });

  // Get cell intensity for visual display (0-1)
  const getCellIntensity = (cell: MatrixCell): number => {
    if (cell.count === 0) return 0;
    
    // Combine count and severity for intensity
    const countWeight = Math.min(cell.count / 5, 1); // Max intensity at 5+ anomalies
    const severityWeight = cell.maxScore;
    
    return Math.min((countWeight * 0.6) + (severityWeight * 0.4), 1);
  };

  // Get cell color based on method and intensity
  const getCellColor = (cell: MatrixCell): string => {
    const intensity = getCellIntensity(cell);
    const method = detectionMethods.find(m => m.key === cell.method);
    
    if (intensity === 0) return 'bg-gray-800';
    
    const alpha = Math.max(intensity, 0.3); // Minimum visibility
    const baseColor = method?.color || 'bg-gray-500';
    
    // Convert to rgba with calculated alpha
    const colorMap = {
      'bg-orange-500': `rgba(249, 115, 22, ${alpha})`,
      'bg-red-500': `rgba(239, 68, 68, ${alpha})`,
      'bg-yellow-500': `rgba(234, 179, 8, ${alpha})`,
      'bg-blue-500': `rgba(59, 130, 246, ${alpha})`
    };
    
    return colorMap[baseColor] || `rgba(107, 114, 128, ${alpha})`;
  };

  // Handle cell click
  function handleCellClick(cell: MatrixCell) {
    if (cell.count > 0) {
      selectedCell = selectedCell?.method === cell.method && selectedCell?.timeSlot === cell.timeSlot ? null : cell;
      showDetails = selectedCell !== null;
    }
  }

  // Handle cell hover
  function handleCellHover(cell: MatrixCell) {
    hoveredCell = cell;
  }

  function handleCellLeave() {
    hoveredCell = null;
  }

  const githubEvents = $derived(() => {
    
    const forcePushEvents = safeAnomalies.filter(a => 
      a?.event_type === 'PushEvent' && (a?.final_anomaly_score || 0) > 0.5
    );
    
    const workflowFailures = safeAnomalies.filter(a => 
      a?.event_type === 'WorkflowRunEvent' && (a?.final_anomaly_score || 0) > 0.5
    );
    
    const highContentRisk = safeAnomalies.filter(a => 
      (a?.content_risk_score || 0) > 0.7
    );

    return {
      forcePushEvents: forcePushEvents || [],
      workflowFailures: workflowFailures || [], 
      highContentRisk: highContentRisk || [],
      total: (forcePushEvents?.length || 0) + (workflowFailures?.length || 0) + (highContentRisk?.length || 0)
    };
  });

  // Summary statistics
  const matrixStats = $derived(() => {
    const totalAnomalies = safeAnomalies.length;
    const criticalAnomalies = safeAnomalies.filter(a => 
      a?.severity_level === 'CRITICAL' || (a?.final_anomaly_score || 0) >= 0.8
    ).length;
    
    const methodCounts = detectionMethods.map(method => {
      const count = Array.isArray(detectionMatrix) 
        ? detectionMatrix
            .filter(cell => cell.method === method.key)
            .reduce((sum, cell) => sum + cell.count, 0)
        : 0;
      return { method: method.label, count };
    });

    return {
      totalAnomalies,
      criticalAnomalies,
      methodCounts
    };
  });
</script>

<Card class="p-6 bg-terminal-surface/50 border-terminal-border">
  {#if safeAnomalies}
    <div style="display:none">{console.log('🎯 DetectionMatrix rendering with anomalies:', safeAnomalies.length)}</div>
  {/if}
  <div class="flex items-center justify-between mb-6">
    <div class="flex items-center space-x-3">
      <div class="p-2 rounded-lg bg-purple-600/20 border border-purple-600/30">
        <Icon name="grid-3x3" class="h-5 w-5 text-purple-400" />
      </div>
      <div>
        <p class="text-sm text-gray-400">AI detection methods vs time periods (24h)</p>
      </div>
    </div>
    
    <div class="text-right">
      <div class="text-lg font-bold text-white">{matrixStats?.totalAnomalies || 0}</div>
      <div class="text-xs text-gray-400">Total Anomalies</div>
    </div>
  </div>

  <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
    <div class="p-3 bg-red-900/20 border border-red-400/30 rounded-lg">
      <div class="flex items-center justify-between mb-2">
        <Icon name="git-branch" class="h-4 w-4 text-red-400" />
        <span class="text-xs text-red-400">Force Push</span>
      </div>
      <div class="text-lg font-mono text-red-400">{githubEvents?.forcePushEvents?.length || 0}</div>
      <div class="text-xs text-gray-400">Git history rewrites</div>
    </div>

    <div class="p-3 bg-yellow-900/20 border border-yellow-400/30 rounded-lg">
      <div class="flex items-center justify-between mb-2">
        <Icon name="alert-triangle" class="h-4 w-4 text-yellow-400" />
        <span class="text-xs text-yellow-400">Workflow Fails</span>
      </div>
      <div class="text-lg font-mono text-yellow-400">{githubEvents?.workflowFailures?.length || 0}</div>
      <div class="text-xs text-gray-400">CI/CD disruptions</div>
    </div>

    <div class="p-3 bg-orange-900/20 border border-orange-400/30 rounded-lg">
      <div class="flex items-center justify-between mb-2">
        <Icon name="shield-alert" class="h-4 w-4 text-orange-400" />
        <span class="text-xs text-orange-400">Secret Risk</span>
      </div>
      <div class="text-lg font-mono text-orange-400">{githubEvents?.highContentRisk?.length || 0}</div>
      <div class="text-xs text-gray-400">Credential exposure</div>
    </div>

    <div class="p-3 bg-purple-900/20 border border-purple-400/30 rounded-lg">
      <div class="flex items-center justify-between mb-2">
        <Icon name="zap" class="h-4 w-4 text-purple-400" />
        <span class="text-xs text-purple-400">Critical</span>
      </div>
      <div class="text-lg font-mono text-purple-400">{matrixStats?.criticalAnomalies || 0}</div>
      <div class="text-xs text-gray-400">High severity</div>
    </div>
  </div>

  <!-- Detection Matrix Grid -->
  <div class="bg-gray-900/50 rounded-lg p-4 mb-6">
    <div class="grid grid-cols-7 gap-1">
      <!-- Header row -->
      <div class="p-2"></div>
      {#each timeSlots as timeSlot}
        <div class="p-2 text-center">
          <div class="text-xs text-gray-400 font-medium">{timeSlot.label}</div>
        </div>
      {/each}

      <!-- Matrix rows -->
      {#each detectionMethods as method}
        <!-- Method label -->
        <div class="p-2 flex items-center space-x-2">
          <Icon name={method.icon} class="h-3 w-3 text-gray-400" />
          <span class="text-xs text-gray-300 font-medium">{method.label}</span>
        </div>

        <!-- Cells for this method -->
        {#each timeSlots as timeSlot}
          {@const cell = Array.isArray(detectionMatrix) ? detectionMatrix.find(c => c.method === method.key && c.timeSlot === timeSlot.key) : null}
          {#if cell}
            <div 
              class="p-2 h-16 rounded border border-gray-600 cursor-pointer transition-all duration-200 hover:border-gray-400 relative"
              style="background: {getCellColor(cell)}"
              onclick={() => handleCellClick(cell)}
              onmouseenter={() => handleCellHover(cell)}
              onmouseleave={handleCellLeave}
              role="button"
              tabindex="0"
              onkeydown={(e) => e.key === 'Enter' && handleCellClick(cell)}
            >
              {#if cell.count > 0}
                <div class="text-center">
                  <div class="text-sm font-bold text-white">{cell.count}</div>
                  <div class="text-xs text-gray-300">{(cell.avgScore * 100).toFixed(0)}%</div>
                  {#if cell.criticalCount > 0}
                    <div class="absolute top-1 right-1 w-2 h-2 bg-red-400 rounded-full"></div>
                  {/if}
                </div>
              {/if}
            </div>
          {/if}
        {/each}
      {/each}
    </div>
  </div>

  <!-- Legend -->
  <div class="flex items-center justify-between text-xs text-gray-400 mb-4">
    <div class="flex items-center space-x-4">
      <span>Cell shows: Count / Avg Score</span>
      <div class="flex items-center space-x-1">
        <div class="w-2 h-2 bg-red-400 rounded-full"></div>
        <span>Critical anomalies present</span>
      </div>
    </div>
    <div class="flex items-center space-x-2">
      <span>Intensity:</span>
      <div class="flex space-x-1">
        <div class="w-3 h-3 bg-gray-800 border border-gray-600"></div>
        <div class="w-3 h-3 bg-purple-500/30 border border-gray-600"></div>
        <div class="w-3 h-3 bg-purple-500/60 border border-gray-600"></div>
        <div class="w-3 h-3 bg-purple-500 border border-gray-600"></div>
      </div>
    </div>
  </div>

  <!-- Selected Cell Details -->
  {#if selectedCell && selectedCell.count > 0}
    <div class="border-t border-gray-600 pt-4">
      <div class="flex items-center justify-between mb-4">
        <h4 class="text-md font-semibold text-gray-100">
          {detectionMethods.find(m => m.key === selectedCell.method)?.label} - {timeSlots.find(t => t.key === selectedCell.timeSlot)?.label}
        </h4>
        <Button variant="ghost" size="sm" onclick={() => selectedCell = null}>
          <Icon name="x" class="h-4 w-4" />
        </Button>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Anomaly List -->
        <div>
          <h5 class="text-sm font-medium text-gray-300 mb-3">Detected Anomalies ({selectedCell.count})</h5>
          <div class="space-y-2 max-h-48 overflow-y-auto">
            {#each selectedCell.anomalies.slice(0, 10) as anomaly}
              <div class="p-3 bg-gray-800/50 rounded border border-gray-600">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-sm text-gray-100 font-mono">{anomaly.repository_name}</span>
                  <Badge variant="outline" class="text-xs">
                    {(anomaly.final_anomaly_score * 100).toFixed(0)}%
                  </Badge>
                </div>
                <div class="flex items-center space-x-2 text-xs text-gray-400">
                  <Icon name="user" class="h-3 w-3" />
                  <span>{anomaly.user_login}</span>
                  <span>•</span>
                  <span>{anomaly.event_type}</span>
                </div>
              </div>
            {/each}
            {#if selectedCell.count > 10}
              <div class="text-xs text-gray-500 text-center">
                +{selectedCell.count - 10} more anomalies...
              </div>
            {/if}
          </div>
        </div>

        <!-- Statistics -->
        <div>
          <h5 class="text-sm font-medium text-gray-300 mb-3">Statistics</h5>
          <div class="space-y-3">
            <div class="flex justify-between">
              <span class="text-sm text-gray-400">Total Count:</span>
              <span class="text-sm text-white font-mono">{selectedCell.count}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-sm text-gray-400">Average Score:</span>
              <span class="text-sm text-white font-mono">{(selectedCell.avgScore * 100).toFixed(1)}%</span>
            </div>
            <div class="flex justify-between">
              <span class="text-sm text-gray-400">Max Score:</span>
              <span class="text-sm text-white font-mono">{(selectedCell.maxScore * 100).toFixed(1)}%</span>
            </div>
            <div class="flex justify-between">
              <span class="text-sm text-gray-400">Critical Anomalies:</span>
              <span class="text-sm text-red-400 font-mono">{selectedCell.criticalCount}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  {/if}
</Card>

<!-- Hover Tooltip -->
{#if hoveredCell && hoveredCell.count > 0}
  <div class="fixed pointer-events-none z-50 bg-gray-800 border border-gray-600 rounded-lg p-3 text-sm text-white shadow-lg"
       style="left: {event?.clientX + 10}px; top: {event?.clientY - 10}px;">
    <div class="font-semibold mb-1">
      {detectionMethods.find(m => m.key === hoveredCell.method)?.label}
    </div>
    <div class="text-gray-300 text-xs space-y-1">
      <div>Count: {hoveredCell.count}</div>
      <div>Avg Score: {(hoveredCell.avgScore * 100).toFixed(1)}%</div>
      {#if hoveredCell.criticalCount > 0}
        <div class="text-red-400">Critical: {hoveredCell.criticalCount}</div>
      {/if}
    </div>
  </div>
{/if}