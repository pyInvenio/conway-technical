<script lang="ts">
  import Card from "$lib/components/ui/Card.svelte";
  import Icon from "$lib/components/ui/Icon.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import { onMount } from "svelte";

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

  // API data state
  let matrixData = $state(null);
  let loading = $state(true);
  let error = $state(null);

  // State
  let selectedCell: MatrixCell | null = $state(null);
  let hoveredCell: MatrixCell | null = $state(null);
  let showDetails = $state(false);

  async function fetchMatrixData() {
    loading = true;
    error = null;

    try {
      const response = await fetch(
        "/api/v1/anomalies/detection-matrix?hours=24"
      );
      if (!response.ok) {
        throw new Error(`Failed to fetch matrix data: ${response.status}`);
      }

      const data = await response.json();
      matrixData = data;
      console.log("Loaded matrix data:", data);
    } catch (err) {
      console.error("Error loading matrix data:", err);
      error = err.message;
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    fetchMatrixData();
  });

  const detectionMethods = $derived(
    matrixData?.detectionMethods || [
      { key: "behavioral", label: "Behavioral", color: "bg-orange-500" },
      { key: "content", label: "Content Analysis", color: "bg-red-500" },
      { key: "temporal", label: "Temporal Patterns", color: "bg-yellow-500" },
      { key: "repository", label: "Repository Context", color: "bg-blue-500" },
    ]
  );

  const timeSlots = $derived(matrixData?.timeSlots || []);

  const detectionMatrix = $derived(matrixData?.matrix || []);

  const maxValues = $derived.by(() => {
    if (!detectionMatrix || detectionMatrix.length === 0) {
      return { maxCount: 1, maxAvgScore: 1 };
    }

    const maxCount = Math.max(...detectionMatrix.map((cell) => cell.count), 1);
    const maxAvgScore = Math.max(
      ...detectionMatrix.map((cell) => cell.avgScore),
      0.1
    );

    return { maxCount, maxAvgScore };
  });

  const getCellIntensity = (cell: MatrixCell): number => {
    if (cell.count === 0) return 0;

    const normalizedCount = cell.count / maxValues.maxCount;
    const normalizedScore = cell.avgScore / maxValues.maxAvgScore;

    return (normalizedCount + normalizedScore) / 2;
  };

  const getCellColor = (cell: MatrixCell): string => {
    const intensity = getCellIntensity(cell);

    if (intensity === 0) return "rgb(75, 85, 99)";

    const alpha = Math.max(intensity, 0.2);

    return `rgba(251, 146, 60, ${alpha})`;
  };

  function handleCellClick(cell: MatrixCell) {
    if (cell.count > 0) {
      selectedCell =
        selectedCell?.method === cell.method &&
        selectedCell?.timeSlot === cell.timeSlot
          ? null
          : cell;
      showDetails = selectedCell !== null;
    }
  }

  function handleCellHover(cell: MatrixCell) {
    hoveredCell = cell;
  }

  function handleCellLeave() {
    hoveredCell = null;
  }

  const githubEvents = $derived.by(() => {
    if (!matrixData?.eventTypes)
      return {
        forcePushEvents: 0,
        workflowFailures: 0,
        highContentRisk: 0,
        total: 0,
      };

    const pushEvents = matrixData.eventTypes["PushEvent"]?.count || 0;
    const workflowEvents =
      matrixData.eventTypes["WorkflowRunEvent"]?.count || 0;

    let highContentCount = 0;
    for (const [eventType, data] of Object.entries(matrixData.eventTypes)) {
      if (data.avgScore > 0.7) {
        highContentCount += data.count;
      }
    }

    return {
      forcePushEvents: pushEvents,
      workflowFailures: workflowEvents,
      highContentRisk: highContentCount,
      total: matrixData.summary.totalAnomalies,
    };
  });

  const matrixStats = $derived.by(() => {
    if (!matrixData)
      return {
        totalAnomalies: 0,
        criticalAnomalies: 0,
        methodCounts: [],
      };

    const methodCounts = detectionMethods.map((method) => {
      const count = detectionMatrix
        .filter((cell) => cell.method === method.key)
        .reduce((sum, cell) => sum + cell.count, 0);
      return { method: method.label, count };
    });

    return {
      totalAnomalies: matrixData.summary.totalAnomalies,
      criticalAnomalies: matrixData.summary.criticalAnomalies,
      methodCounts,
    };
  });
</script>

<Card class="p-6 bg-terminal-surface/50 border-terminal-border">
  {#if loading}
    <div class="flex items-center justify-center py-8">
      <div class="text-gray-400">Loading detection matrix...</div>
    </div>
  {:else if error}
    <div class="flex items-center justify-center py-8">
      <div class="text-red-400">Error: {error}</div>
    </div>
  {:else}
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center space-x-3">
        <div
          class="p-2 rounded-lg bg-purple-600/20 border border-purple-600/30"
        >
          <Icon name="grid-3x3" class="h-5 w-5 text-purple-400" />
        </div>
        <div>
          <p class="text-sm text-gray-400">
            AI detection methods vs time periods (24h)
          </p>
        </div>
      </div>

      <div class="text-right">
        <div class="text-lg font-bold text-white">
          {matrixStats?.totalAnomalies || 0}
        </div>
        <div class="text-xs text-gray-400">Total Anomalies</div>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <div class="p-3 bg-red-900/20 border border-red-400/30 rounded-lg">
        <div class="flex items-center justify-between mb-2">
          <Icon name="git-branch" class="h-4 w-4 text-red-400" />
          <span class="text-xs text-red-400">Force Push</span>
        </div>
        <div class="text-lg font-mono text-red-400">
          {githubEvents?.forcePushEvents || 0}
        </div>
        <div class="text-xs text-gray-400">Git history rewrites</div>
      </div>

      <div class="p-3 bg-yellow-900/20 border border-yellow-400/30 rounded-lg">
        <div class="flex items-center justify-between mb-2">
          <Icon name="alert-triangle" class="h-4 w-4 text-yellow-400" />
          <span class="text-xs text-yellow-400">Workflow Fails</span>
        </div>
        <div class="text-lg font-mono text-yellow-400">
          {githubEvents?.workflowFailures || 0}
        </div>
        <div class="text-xs text-gray-400">CI/CD disruptions</div>
      </div>

      <div class="p-3 bg-orange-900/20 border border-orange-400/30 rounded-lg">
        <div class="flex items-center justify-between mb-2">
          <Icon name="shield-alert" class="h-4 w-4 text-orange-400" />
          <span class="text-xs text-orange-400">Secret Risk</span>
        </div>
        <div class="text-lg font-mono text-orange-400">
          {githubEvents?.highContentRisk || 0}
        </div>
        <div class="text-xs text-gray-400">Credential exposure</div>
      </div>

      <div class="p-3 bg-purple-900/20 border border-purple-400/30 rounded-lg">
        <div class="flex items-center justify-between mb-2">
          <Icon name="zap" class="h-4 w-4 text-purple-400" />
          <span class="text-xs text-purple-400">Critical</span>
        </div>
        <div class="text-lg font-mono text-purple-400">
          {matrixStats?.criticalAnomalies || 0}
        </div>
        <div class="text-xs text-gray-400">High severity</div>
      </div>
    </div>

    <div class="bg-gray-900/50 rounded-lg p-4 mb-6">
      <div class="grid grid-cols-7 gap-1">
        <div class="p-2"></div>
        {#each timeSlots as timeSlot}
          <div class="p-2 text-center">
            <div class="text-xs text-gray-400 font-medium">
              {timeSlot.label}
            </div>
          </div>
        {/each}

        {#each detectionMethods as method}
          <div class="p-2">
            <span class="text-xs text-gray-300 font-medium">{method.label}</span
            >
          </div>

          <!-- Cells for this method -->
          {#each timeSlots as timeSlot}
            {@const cell = Array.isArray(detectionMatrix)
              ? detectionMatrix.find(
                  (c) => c.method === method.key && c.timeSlot === timeSlot.key
                )
              : null}
            {#if cell}
              <div
                class="p-2 h-16 rounded border-2 cursor-pointer transition-all duration-200 relative bg-gray-800"
                style="border-color: {getCellColor(cell)}"
                onclick={() => handleCellClick(cell)}
                onmouseenter={() => handleCellHover(cell)}
                onmouseleave={handleCellLeave}
                role="button"
                tabindex="0"
                onkeydown={(e) => e.key === "Enter" && handleCellClick(cell)}
              >
                {#if cell.count > 0}
                  <div class="text-center">
                    <div class="text-sm font-bold text-white">{cell.count}</div>
                    <div class="text-xs text-gray-300">
                      {(cell.avgScore * 100).toFixed(0)}%
                    </div>
                    {#if cell.criticalCount > 0}
                      <div
                        class="absolute top-1 right-1 w-2 h-2 bg-red-400 rounded-full"
                      ></div>
                    {/if}
                  </div>
                {/if}
              </div>
            {/if}
          {/each}
        {/each}
      </div>
    </div>

    <div class="text-xs text-gray-400 mb-4">
      <div class="flex items-center justify-between mb-2">
        <div class="flex items-center space-x-4">
          <span>Cell shows: Count / Avg Score%</span>
          <div class="flex items-center space-x-1">
            <div class="w-2 h-2 bg-red-400 rounded-full"></div>
            <span>Critical anomalies present</span>
          </div>
        </div>
      </div>
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <span>Intensity: Normalized (relative to max count & score)</span>
        </div>
        <div class="flex items-center space-x-2">
          <span>Example:</span>
          <div class="flex space-x-1">
            <div
              class="w-3 h-3 bg-gray-800 border-2"
              style="border-color: rgb(75, 85, 99)"
            ></div>
            <div
              class="w-3 h-3 bg-gray-800 border-2"
              style="border-color: rgba(251, 146, 60, 0.4)"
            ></div>
            <div
              class="w-3 h-3 bg-gray-800 border-2"
              style="border-color: rgba(251, 146, 60, 0.7)"
            ></div>
            <div
              class="w-3 h-3 bg-gray-800 border-2"
              style="border-color: rgba(251, 146, 60, 1)"
            ></div>
          </div>
        </div>
      </div>
    </div>

    {#if selectedCell && selectedCell.count > 0}
      <div class="border-t border-gray-600 pt-4">
        <div class="flex items-center justify-between mb-4">
          <h4 class="text-md font-semibold text-gray-100">
            {detectionMethods.find((m) => m.key === selectedCell.method)?.label}
            -
            {timeSlots.find((t) => t.key === selectedCell.timeSlot)?.label}
          </h4>
          <Button
            variant="ghost"
            size="sm"
            onclick={() => (selectedCell = null)}
          >
            <Icon name="x" class="h-4 w-4" />
          </Button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h5 class="text-sm font-medium text-gray-300 mb-3">
              Detected Anomalies ({selectedCell.count})
            </h5>
            <div class="space-y-2 max-h-48 overflow-y-auto">
              {#if selectedCell.anomalyIds && selectedCell.anomalyIds.length > 0}
                <div class="p-3 bg-gray-800/50 rounded border border-gray-600">
                  <div class="text-sm text-gray-300">
                    {selectedCell.count} anomalies detected in this time period
                  </div>
                  <div class="text-xs text-gray-400 mt-2">
                    Average score: {(selectedCell.avgScore * 100).toFixed(1)}%
                  </div>
                </div>
              {:else}
                <div class="text-xs text-gray-500 text-center">
                  No detailed information available
                </div>
              {/if}
            </div>
          </div>

          <div>
            <h5 class="text-sm font-medium text-gray-300 mb-3">Statistics</h5>
            <div class="space-y-3">
              <div class="flex justify-between">
                <span class="text-sm text-gray-400">Total Count:</span>
                <span class="text-sm text-white font-mono"
                  >{selectedCell.count}</span
                >
              </div>
              <div class="flex justify-between">
                <span class="text-sm text-gray-400">Average Score:</span>
                <span class="text-sm text-white font-mono"
                  >{(selectedCell.avgScore * 100).toFixed(1)}%</span
                >
              </div>
              <div class="flex justify-between">
                <span class="text-sm text-gray-400">Max Score:</span>
                <span class="text-sm text-white font-mono"
                  >{(selectedCell.maxScore * 100).toFixed(1)}%</span
                >
              </div>
              <div class="flex justify-between">
                <span class="text-sm text-gray-400">Critical Anomalies:</span>
                <span class="text-sm text-red-400 font-mono"
                  >{selectedCell.criticalCount}</span
                >
              </div>
            </div>
          </div>
        </div>
      </div>
    {/if}
  {/if}
</Card>

{#if hoveredCell && hoveredCell.count > 0}
  <div
    class="fixed pointer-events-none z-50 bg-gray-800 border border-gray-600 rounded-lg p-3 text-sm text-white shadow-lg"
    style="left: {event?.clientX + 10}px; top: {event?.clientY - 10}px;"
  >
    <div class="font-semibold mb-1">
      {detectionMethods.find((m) => m.key === hoveredCell.method)?.label}
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
