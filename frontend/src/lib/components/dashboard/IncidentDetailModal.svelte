<script lang="ts">
  import Modal from "$lib/components/ui/Modal.svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import Icon from "$lib/components/ui/Icon.svelte";
  import {
    parseAISummary,
    parseRiskIndicators,
    getIncidentTypeDisplay,
    getSeverityColor,
    getPrimaryDetectionMethod,
    generateFallbackSummary,
    formatTechnicalSummary,
    type ComponentScores,
  } from "$lib/utils/summaryParser";
  import {
    createAnalysisBreakdown,
    type AnalysisBreakdown,
  } from "$lib/utils/patternInterpreter";
  import {
    generateGitHubEventUrl,
    generateCommitUrls,
    getEventUrlDescription,
    generateInvestigationUrls,
  } from "$lib/utils/githubUrls";
  import { browser } from "$app/environment";

  let { show = false, incident = null, onclose } = $props();

  let anomaly = $derived(incident);

  let enhancedSummary = $derived(
    anomaly
      ? (() => {
          const componentScores: ComponentScores = {
            behavioral:
              Number(
                anomaly.behavioral_anomaly_score ||
                  anomaly.detection_scores?.behavioral
              ) || 0,
            content:
              Number(
                anomaly.content_risk_score || anomaly.detection_scores?.content
              ) || 0,
            temporal:
              Number(
                anomaly.temporal_anomaly_score ||
                  anomaly.detection_scores?.temporal
              ) || 0,
            repository:
              Number(
                anomaly.repository_criticality_score ||
                  anomaly.detection_scores?.repository_criticality
              ) || 0,
          };

          // Parse AI summary or generate fallback
          const parsedSummary =
            parseAISummary(anomaly.ai_summary) ||
            generateFallbackSummary(
              anomaly.event_type,
              anomaly.final_anomaly_score,
              anomaly.repository_name,
              componentScores
            );

          console.log("Modal parsed summary:", parsedSummary);
          return formatTechnicalSummary(parsedSummary);
        })()
      : null
  );

  let detectionMethod = $derived(
    anomaly
      ? (() => {
          const componentScores: ComponentScores = {
            behavioral:
              Number(
                anomaly.behavioral_anomaly_score ||
                  anomaly.detection_scores?.behavioral
              ) || 0,
            content:
              Number(
                anomaly.content_risk_score || anomaly.detection_scores?.content
              ) || 0,
            temporal:
              Number(
                anomaly.temporal_anomaly_score ||
                  anomaly.detection_scores?.temporal
              ) || 0,
            repository:
              Number(
                anomaly.repository_criticality_score ||
                  anomaly.detection_scores?.repository_criticality
              ) || 0,
          };

          console.log("Modal component scores:", componentScores);
          return getPrimaryDetectionMethod(componentScores);
        })()
      : null
  );

  // Create detailed pattern analysis
  let patternAnalysis = $derived(
    anomaly
      ? (() => {
          const behavioralData = parseJsonField(anomaly.behavioral_analysis);
          const contentData = parseJsonField(anomaly.content_analysis);
          const temporalData = parseJsonField(anomaly.temporal_analysis);
          const repositoryData = parseJsonField(anomaly.repository_context);
          const detectionScores = anomaly.detection_scores || {
            behavioral: Number(anomaly.behavioral_anomaly_score) || 0,
            content: Number(anomaly.content_risk_score) || 0,
            temporal: Number(anomaly.temporal_anomaly_score) || 0,
            repository_criticality:
              Number(anomaly.repository_criticality_score) || 0,
          };

          return createAnalysisBreakdown(
            behavioralData,
            contentData,
            temporalData,
            repositoryData,
            detectionScores
          );
        })()
      : null
  );

  // Generate GitHub URLs based on event type and payload
  let githubUrls = $derived(
    anomaly
      ? generateInvestigationUrls(
          anomaly.repository_name,
          anomaly.event_type,
          anomaly.user_login,
          anomaly.event_payload
        )
      : null
  );

  let eventUrl = $derived(
    anomaly
      ? generateGitHubEventUrl(
          anomaly.event_type,
          anomaly.repository_name,
          anomaly.event_payload
        )
      : null
  );

  let eventUrlDescription = $derived(
    anomaly
      ? getEventUrlDescription(anomaly.event_type, anomaly.event_payload)
      : "View on GitHub"
  );

  let commitUrls = $derived(
    anomaly
      ? generateCommitUrls(anomaly.repository_name, anomaly.event_payload)
      : []
  );

  function getSeverityVariant(severityLevel, score) {
    if (severityLevel === "CRITICAL" || score >= 0.8) return "error";
    if (severityLevel === "HIGH" || score >= 0.6) return "warning";
    if (severityLevel === "MEDIUM" || score >= 0.4) return "warning";
    return "info";
  }

  function formatDate(dateString) {
    if (!dateString) return "Unknown date";
    try {
      const date = new Date(dateString);
      return isNaN(date.getTime()) ? "Invalid date" : date.toLocaleString();
    } catch {
      return "Invalid date";
    }
  }

  function getGitHubRepoUrl(repoName) {
    return `https://github.com/${repoName}`;
  }

  function getEventTypeIcon(eventType) {
    switch (eventType) {
      case "PushEvent":
        return "git-branch";
      case "WorkflowRunEvent":
        return "alert-triangle";
      case "DeleteEvent":
        return "trash-2";
      case "MemberEvent":
        return "users";
      case "ReleaseEvent":
        return "tag";
      case "ForkEvent":
        return "git-fork";
      case "IssuesEvent":
        return "alert-circle";
      case "PullRequestEvent":
        return "git-pull-request";
      default:
        return "alert-triangle";
    }
  }

  function parseJsonField(field) {
    if (!field) return null;
    if (typeof field === "string") {
      try {
        return JSON.parse(field);
      } catch {
        return null;
      }
    }
    return field;
  }
</script>

<Modal {show} title="Security Incident Analysis" {onclose}>
  {#snippet children()}
    {#if anomaly && enhancedSummary}
      <div class="space-y-6">
        <div class="border-b border-gray-600 pb-4">
          <div class="flex items-start justify-between mb-3">
            <div class="flex-1">
              <h3 class="text-xl font-semibold text-gray-100 mb-2">
                {enhancedSummary.title}
              </h3>
              <div class="flex items-center space-x-2 mb-3">
                <Badge
                  variant="outline"
                  class="bg-purple-900/30 border-purple-400/50 text-purple-300"
                >
                  <Icon
                    name={getEventTypeIcon(anomaly.event_type)}
                    class="h-3 w-3 mr-1"
                  />
                  {getIncidentTypeDisplay(anomaly.event_type)}
                </Badge>
                {#if detectionMethod}
                  <Badge
                    variant="outline"
                    class="bg-blue-900/30 border-blue-400/50 text-blue-300"
                  >
                    <Icon name="zap" class="h-3 w-3 mr-1" />
                    {detectionMethod.method}
                  </Badge>
                {/if}
              </div>
              <div class="flex items-center space-x-4 text-sm text-gray-400">
                <div class="flex items-center space-x-2">
                  <Icon name="github" class="h-4 w-4" />
                  <a
                    href={getGitHubRepoUrl(anomaly.repository_name)}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="text-blue-400 hover:text-blue-300 font-mono"
                  >
                    {anomaly.repository_name}
                  </a>
                </div>
                <div class="flex items-center space-x-1">
                  <Icon name="user" class="h-4 w-4" />
                  <span class="font-mono text-cyan-400"
                    >{anomaly.user_login}</span
                  >
                </div>
                <div class="flex items-center space-x-1">
                  <Icon name="clock" class="h-4 w-4" />
                  <span
                    >{formatDate(
                      anomaly.timestamp || anomaly.detection_timestamp
                    )}</span
                  >
                </div>
              </div>
            </div>
            <div class="text-right space-y-2">
              <div
                class="text-lg font-mono {getSeverityColor(
                  anomaly.final_anomaly_score
                )}"
              >
                {Math.round(anomaly.final_anomaly_score * 100)}%
              </div>
              {#if enhancedSummary.threat_level}
                <div class="text-sm font-medium text-red-400">
                  {enhancedSummary.threat_level}
                </div>
              {/if}
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div class="space-y-4">
            <h4
              class="text-lg font-semibold text-gray-100 flex items-center space-x-2"
            >
              <Icon name="search" class="h-5 w-5 text-orange-400" />
              <span>Root Cause Analysis</span>
            </h4>
            <div
              class="bg-gray-900/50 rounded-lg border border-orange-400/30 p-4"
            >
              {#if enhancedSummary && enhancedSummary.root_cause && enhancedSummary.root_cause.length > 0}
                <ul class="space-y-3">
                  {#each enhancedSummary.root_cause as cause, index}
                    <li class="flex items-start space-x-3">
                      <div
                        class="w-6 h-6 rounded-full bg-orange-400/20 border border-orange-400/50 flex items-center justify-center text-xs font-medium text-orange-400 mt-0.5"
                      >
                        {index + 1}
                      </div>
                      <span class="text-gray-300 flex-1 leading-relaxed"
                        >{cause}</span
                      >
                    </li>
                  {/each}
                </ul>
              {:else}
                <p class="text-gray-400 italic">
                  Automated analysis in progress...
                </p>
              {/if}
            </div>
          </div>

          <div class="space-y-4">
            <h4
              class="text-lg font-semibold text-gray-100 flex items-center space-x-2"
            >
              <Icon name="alert-triangle" class="h-5 w-5 text-red-400" />
              <span>Impact Assessment</span>
            </h4>
            <div class="bg-gray-900/50 rounded-lg border border-red-400/30 p-4">
              {#if enhancedSummary && enhancedSummary.impact && enhancedSummary.impact.length > 0}
                <ul class="space-y-3">
                  {#each enhancedSummary.impact as impact, index}
                    <li class="flex items-start space-x-3">
                      <div
                        class="w-6 h-6 rounded-full bg-red-400/20 border border-red-400/50 flex items-center justify-center text-xs font-medium text-red-400 mt-0.5"
                      >
                        {index + 1}
                      </div>
                      <span class="text-gray-300 flex-1 leading-relaxed"
                        >{impact}</span
                      >
                    </li>
                  {/each}
                </ul>
              {:else}
                <p class="text-gray-400 italic">Impact evaluation pending...</p>
              {/if}
            </div>
          </div>

          <div class="space-y-4">
            <h4
              class="text-lg font-semibold text-gray-100 flex items-center space-x-2"
            >
              <Icon name="list-checks" class="h-5 w-5 text-green-400" />
              <span>Immediate Actions</span>
            </h4>
            <div
              class="bg-gray-900/50 rounded-lg border border-green-400/30 p-4"
            >
              {#if enhancedSummary && enhancedSummary.next_steps && enhancedSummary.next_steps.length > 0}
                <ul class="space-y-3">
                  {#each enhancedSummary.next_steps as step, index}
                    <li class="flex items-start space-x-3">
                      <div
                        class="w-6 h-6 rounded-full bg-green-400/20 border border-green-400/50 flex items-center justify-center text-xs font-medium text-green-400 mt-0.5"
                      >
                        {index + 1}
                      </div>
                      <span class="text-gray-300 flex-1 leading-relaxed"
                        >{step}</span
                      >
                    </li>
                  {/each}
                </ul>
              {:else}
                <p class="text-gray-400 italic">
                  Action plan being generated...
                </p>
              {/if}
            </div>

            {#if enhancedSummary && enhancedSummary.urgency}
              <div
                class="mt-4 p-3 bg-yellow-900/20 border border-yellow-400/50 rounded-lg"
              >
                <div class="flex items-center space-x-2">
                  <Icon name="clock" class="h-4 w-4 text-yellow-400" />
                  <span class="text-sm font-medium text-yellow-400"
                    >Urgency Level</span
                  >
                </div>
                <p class="text-sm text-gray-300 mt-1">
                  {enhancedSummary.urgency}
                </p>
              </div>
            {/if}
          </div>
        </div>

        <div class="space-y-4">
          <h4
            class="text-lg font-semibold text-gray-100 flex items-center space-x-2"
          >
            <Icon name="brain" class="h-5 w-5 text-purple-400" />
            <span>AI Detection Analysis</span>
          </h4>

          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="p-4 bg-gray-900/50 rounded-lg border border-gray-600">
              <div class="flex items-center justify-between mb-2">
                <h5 class="text-xs font-medium text-gray-300">
                  Behavioral Analysis
                </h5>
                <Icon name="users" class="h-4 w-4 text-orange-400" />
              </div>
              <div class="space-y-2">
                <p class="text-lg font-mono text-orange-400">
                  {(
                    (Number(
                      anomaly.behavioral_anomaly_score ||
                        anomaly.detection_scores?.behavioral
                    ) || 0) * 100
                  ).toFixed(1)}%
                </p>
                <div class="w-full bg-gray-700 rounded-full h-2">
                  <div
                    class="bg-orange-400 h-2 rounded-full transition-all duration-300"
                    style="width: {(Number(
                      anomaly.behavioral_anomaly_score ||
                        anomaly.detection_scores?.behavioral
                    ) || 0) * 100}%"
                  ></div>
                </div>
                <p class="text-xs text-gray-400">User behavior patterns</p>
              </div>
            </div>

            <div class="p-4 bg-gray-900/50 rounded-lg border border-gray-600">
              <div class="flex items-center justify-between mb-2">
                <h5 class="text-xs font-medium text-gray-300">
                  Content Analysis
                </h5>
                <Icon name="file-text" class="h-4 w-4 text-red-400" />
              </div>
              <div class="space-y-2">
                <p class="text-lg font-mono text-red-400">
                  {(
                    (Number(
                      anomaly.content_risk_score ||
                        anomaly.detection_scores?.content
                    ) || 0) * 100
                  ).toFixed(1)}%
                </p>
                <div class="w-full bg-gray-700 rounded-full h-2">
                  <div
                    class="bg-red-400 h-2 rounded-full transition-all duration-300"
                    style="width: {(Number(
                      anomaly.content_risk_score ||
                        anomaly.detection_scores?.content
                    ) || 0) * 100}%"
                  ></div>
                </div>
                <p class="text-xs text-gray-400">Code & data patterns</p>
              </div>
            </div>

            <div class="p-4 bg-gray-900/50 rounded-lg border border-gray-600">
              <div class="flex items-center justify-between mb-2">
                <h5 class="text-xs font-medium text-gray-300">
                  Temporal Analysis
                </h5>
                <Icon name="clock" class="h-4 w-4 text-yellow-400" />
              </div>
              <div class="space-y-2">
                <p class="text-lg font-mono text-yellow-400">
                  {(
                    (Number(
                      anomaly.temporal_anomaly_score ||
                        anomaly.detection_scores?.temporal
                    ) || 0) * 100
                  ).toFixed(1)}%
                </p>
                <div class="w-full bg-gray-700 rounded-full h-2">
                  <div
                    class="bg-yellow-400 h-2 rounded-full transition-all duration-300"
                    style="width: {(Number(
                      anomaly.temporal_anomaly_score ||
                        anomaly.detection_scores?.temporal
                    ) || 0) * 100}%"
                  ></div>
                </div>
                <p class="text-xs text-gray-400">Timing patterns</p>
              </div>
            </div>

            <div class="p-4 bg-gray-900/50 rounded-lg border border-gray-600">
              <div class="flex items-center justify-between mb-2">
                <h5 class="text-xs font-medium text-gray-300">
                  Repository Risk
                </h5>
                <Icon name="shield" class="h-4 w-4 text-blue-400" />
              </div>
              <div class="space-y-2">
                <p class="text-lg font-mono text-blue-400">
                  {(
                    (Number(
                      anomaly.repository_criticality_score ||
                        anomaly.detection_scores?.repository_criticality
                    ) || 0) * 100
                  ).toFixed(1)}%
                </p>
                <div class="w-full bg-gray-700 rounded-full h-2">
                  <div
                    class="bg-blue-400 h-2 rounded-full transition-all duration-300"
                    style="width: {(Number(
                      anomaly.repository_criticality_score ||
                        anomaly.detection_scores?.repository_criticality
                    ) || 0) * 100}%"
                  ></div>
                </div>
                <p class="text-xs text-gray-400">Repository criticality</p>
              </div>
            </div>
          </div>

          {#if detectionMethod}
            <div
              class="mt-4 p-4 bg-purple-900/20 border border-purple-400/50 rounded-lg"
            >
              <div class="flex items-center justify-between">
                <div>
                  <h5 class="text-sm font-medium text-purple-300 mb-1">
                    Primary Detection Method
                  </h5>
                  <p class="text-gray-300">{detectionMethod.description}</p>
                </div>
                <div class="text-right">
                  <div class="text-lg font-mono text-purple-400">
                    {(detectionMethod.score * 100).toFixed(0)}%
                  </div>
                  <div class="text-xs text-gray-400">Confidence</div>
                </div>
              </div>
            </div>
          {/if}

          <!-- Pattern Analysis Insights -->
          {#if patternAnalysis && patternAnalysis.primary_reasons.length > 0}
            <div class="mt-4 space-y-4">
              <h5
                class="text-sm font-medium text-purple-300 flex items-center space-x-2"
              >
                <Icon name="brain" class="h-4 w-4" />
                <span>Detection Reasoning</span>
              </h5>

              <!-- Risk Assessment -->
              <div
                class="p-3 bg-indigo-900/20 border border-indigo-400/30 rounded-lg"
              >
                <p class="text-sm text-indigo-200 font-medium mb-1">
                  Risk Assessment
                </p>
                <p class="text-xs text-gray-300">
                  {patternAnalysis.risk_assessment}
                </p>
              </div>

              <!-- Primary Reasons -->
              <div class="space-y-3">
                <p
                  class="text-xs font-medium text-gray-400 uppercase tracking-wide"
                >
                  Primary Detection Reasons
                </p>
                {#each patternAnalysis.primary_reasons as reason}
                  <div
                    class="p-3 bg-gray-900/30 border-l-4 {reason.severity ===
                    'high'
                      ? 'border-red-400'
                      : reason.severity === 'medium'
                        ? 'border-yellow-400'
                        : 'border-blue-400'} rounded-r-lg"
                  >
                    <div class="flex items-start justify-between mb-2">
                      <h6 class="text-sm font-medium text-gray-200">
                        {reason.title}
                      </h6>
                      <Badge
                        variant="outline"
                        class="text-xs {reason.severity === 'high'
                          ? 'bg-red-900/30 border-red-400/50 text-red-300'
                          : reason.severity === 'medium'
                            ? 'bg-yellow-900/30 border-yellow-400/50 text-yellow-300'
                            : 'bg-blue-900/30 border-blue-400/50 text-blue-300'}"
                      >
                        {reason.severity}
                      </Badge>
                    </div>
                    <p class="text-xs text-gray-400 mb-2">
                      {reason.description}
                    </p>
                    {#if reason.technical_detail}
                      <p class="text-xs text-gray-500 font-mono">
                        {reason.technical_detail}
                      </p>
                    {/if}
                    {#if reason.recommendation}
                      <div
                        class="mt-2 p-2 bg-gray-800/50 rounded text-xs text-gray-300"
                      >
                        <Icon
                          name="lightbulb"
                          class="h-3 w-3 inline mr-1 text-yellow-400"
                        />
                        {reason.recommendation}
                      </div>
                    {/if}
                  </div>
                {/each}
              </div>

              <!-- Supporting Factors -->
              {#if patternAnalysis.supporting_factors.length > 0}
                <div class="space-y-2">
                  <p
                    class="text-xs font-medium text-gray-400 uppercase tracking-wide"
                  >
                    Supporting Factors
                  </p>
                  {#each patternAnalysis.supporting_factors as factor}
                    <div
                      class="p-2 bg-gray-900/20 border border-gray-600/30 rounded"
                    >
                      <div class="flex items-center justify-between">
                        <span class="text-xs text-gray-300">{factor.title}</span
                        >
                        <span class="text-xs text-gray-500"
                          >{factor.category}</span
                        >
                      </div>
                      <p class="text-xs text-gray-400 mt-1">
                        {factor.description}
                      </p>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}
        </div>

        <!-- Remove raw AI summary display - using structured format instead -->

        <!-- High Risk Indicators -->
        {#if anomaly.high_risk_indicators}
          {@const riskIndicators = parseRiskIndicators(
            anomaly.high_risk_indicators
          )}
          {#if riskIndicators.indicators.length > 0}
            <div class="space-y-4">
              <h4
                class="text-lg font-semibold text-gray-100 flex items-center space-x-2"
              >
                <Icon name="shield-alert" class="h-5 w-5 text-red-400" />
                <span>Security Risk Factors</span>
              </h4>
              <div
                class="bg-red-900/20 border border-red-400/50 rounded-lg p-4"
              >
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {#each riskIndicators.indicators as indicator, index}
                    <div
                      class="flex items-start space-x-3 p-3 bg-gray-900/50 rounded-lg"
                    >
                      <div
                        class="w-6 h-6 rounded-full bg-red-400/20 border border-red-400/50 flex items-center justify-center text-xs font-medium text-red-400 mt-0.5"
                      >
                        !
                      </div>
                      <div class="flex-1">
                        <span class="text-gray-200 font-medium"
                          >{indicator}</span
                        >
                      </div>
                    </div>
                  {/each}
                </div>

                <div
                  class="mt-4 flex items-center justify-between p-3 bg-gray-900/30 rounded-lg"
                >
                  <div class="flex items-center space-x-2">
                    <Icon name="gauge" class="h-4 w-4 text-red-400" />
                    <span class="text-sm text-gray-300">Risk Assessment</span>
                  </div>
                  <div class="flex items-center space-x-4">
                    <Badge
                      variant="outline"
                      class="bg-red-900/30 border-red-400/50 text-red-300"
                    >
                      {riskIndicators.severity.toUpperCase()}
                    </Badge>
                    <span class="text-sm font-mono text-red-400">
                      {(riskIndicators.confidence * 100).toFixed(0)}% confidence
                    </span>
                  </div>
                </div>
              </div>
            </div>
          {/if}
        {/if}

        <!-- Analysis Details -->
        {#if anomaly.behavioral_analysis || anomaly.content_analysis || anomaly.temporal_analysis || anomaly.repository_context}
          {@const behavioralAnalysis = parseJsonField(
            anomaly.behavioral_analysis
          )}
          {@const contentAnalysis = parseJsonField(anomaly.content_analysis)}
          {@const temporalAnalysis = parseJsonField(anomaly.temporal_analysis)}
          {@const repositoryContext = parseJsonField(
            anomaly.repository_context
          )}
          <div class="space-y-4">
            <h4
              class="text-lg font-semibold text-gray-100 flex items-center space-x-2"
            >
              <Icon name="code" class="h-5 w-5 text-blue-400" />
              <span>Analysis Details</span>
            </h4>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              {#if behavioralAnalysis}
                <div class="p-3 bg-gray-900 rounded-lg border border-gray-600">
                  <h5 class="text-sm font-medium text-orange-400 mb-2">
                    Behavioral Analysis
                  </h5>
                  <pre
                    class="text-xs text-gray-300 font-mono overflow-x-auto whitespace-pre-wrap max-h-32 overflow-y-auto">{JSON.stringify(
                      behavioralAnalysis,
                      null,
                      2
                    )}</pre>
                </div>
              {/if}

              {#if contentAnalysis}
                <div class="p-3 bg-gray-900 rounded-lg border border-gray-600">
                  <h5 class="text-sm font-medium text-red-400 mb-2">
                    Content Analysis
                  </h5>
                  <pre
                    class="text-xs text-gray-300 font-mono overflow-x-auto whitespace-pre-wrap max-h-32 overflow-y-auto">{JSON.stringify(
                      contentAnalysis,
                      null,
                      2
                    )}</pre>
                </div>
              {/if}

              {#if temporalAnalysis}
                <div class="p-3 bg-gray-900 rounded-lg border border-gray-600">
                  <h5 class="text-sm font-medium text-yellow-400 mb-2">
                    Temporal Analysis
                  </h5>
                  <pre
                    class="text-xs text-gray-300 font-mono overflow-x-auto whitespace-pre-wrap max-h-32 overflow-y-auto">{JSON.stringify(
                      temporalAnalysis,
                      null,
                      2
                    )}</pre>
                </div>
              {/if}

              {#if repositoryContext}
                <div class="p-3 bg-gray-900 rounded-lg border border-gray-600">
                  <h5 class="text-sm font-medium text-blue-400 mb-2">
                    Repository Context
                  </h5>
                  <pre
                    class="text-xs text-gray-300 font-mono overflow-x-auto whitespace-pre-wrap max-h-32 overflow-y-auto">{JSON.stringify(
                      repositoryContext,
                      null,
                      2
                    )}</pre>
                </div>
              {/if}
            </div>
          </div>
        {/if}

        <!-- Investigation Actions -->
        <div class="space-y-4">
          <!-- Primary Action - Specific Event Link -->
          {#if eventUrl}
            <div
              class="p-3 bg-green-900/20 border border-green-400/30 rounded-lg"
            >
              <div class="flex items-center justify-between mb-2">
                <h5 class="text-sm font-medium text-green-300">
                  Primary Investigation
                </h5>
                <Badge
                  variant="outline"
                  class="bg-green-900/30 border-green-400/50 text-green-300 text-xs"
                >
                  {anomaly.event_type}
                </Badge>
              </div>
              <a
                href={eventUrl}
                target="_blank"
                rel="noopener noreferrer"
                class="flex items-center space-x-2 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-sm transition-colors font-medium"
              >
                <Icon name="external-link" class="h-4 w-4" />
                <span>{eventUrlDescription}</span>
              </a>
            </div>
          {/if}

          <!-- Commit Details (for PushEvent) -->
          {#if commitUrls.length > 0}
            <div class="space-y-2">
              <h5 class="text-sm font-medium text-gray-300">Related Commits</h5>
              {#each commitUrls.slice(0, 3) as commit}
                <div
                  class="p-2 bg-gray-900/50 border border-gray-600/30 rounded"
                >
                  <div class="flex items-center justify-between">
                    <code class="text-xs text-blue-400 font-mono"
                      >{commit.sha.substring(0, 8)}</code
                    >
                    <a
                      href={commit.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      class="text-xs text-blue-400 hover:text-blue-300"
                    >
                      <Icon name="external-link" class="h-3 w-3 inline" />
                    </a>
                  </div>
                  <p class="text-xs text-gray-400 mt-1 truncate">
                    {commit.message}
                  </p>
                </div>
              {/each}
              {#if commitUrls.length > 3}
                <p class="text-xs text-gray-500">
                  ... and {commitUrls.length - 3} more commits
                </p>
              {/if}
            </div>
          {/if}

          <!-- Secondary Investigation Links -->
          {#if githubUrls}
            <div class="flex flex-row gap-3">
              <a
                href={githubUrls.userActivity}
                target="_blank"
                rel="noopener noreferrer"
                class="flex items-center space-x-2 px-3 py-2 bg-orange-600 hover:bg-orange-700 rounded-lg text-sm transition-colors"
              >
                <Icon name="user" class="h-4 w-4" />
                <span>User Activity</span>
              </a>

              <a
                href={githubUrls.insights}
                target="_blank"
                rel="noopener noreferrer"
                class="flex items-center space-x-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm transition-colors"
              >
                <Icon name="bar-chart-3" class="h-4 w-4" />
                <span>Repository Insights</span>
              </a>
            </div>
          {/if}

          <!-- Internal Analysis Links -->
          <div class="flex flex-wrap gap-3 pt-2 border-t border-gray-600">
            <a
              href="/event/{anomaly.event_id}"
              class="flex items-center space-x-2 px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors"
            >
              <Icon name="search" class="h-4 w-4" />
              <span>Event Details</span>
            </a>
            <a
              href="/repository/{encodeURIComponent(anomaly.repository_name)}"
              class="flex items-center space-x-2 px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors"
            >
              <Icon name="github" class="h-4 w-4" />
              <span>Repository Analysis</span>
            </a>
          </div>
        </div>
      </div>
    {/if}
  {/snippet}
</Modal>
