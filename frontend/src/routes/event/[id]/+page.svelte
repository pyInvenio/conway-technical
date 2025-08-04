<script lang="ts">
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import Icon from "$lib/components/ui/Icon.svelte";
  import Card from "$lib/components/ui/Card.svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import Navbar from "$lib/components/dashboard/Navbar.svelte";
  import {
    parseAISummary,
    parseRiskIndicators,
    getIncidentTypeDisplay,
    getSeverityColor,
    getPrimaryDetectionMethod,
    generateFallbackSummary,
    type ComponentScores,
  } from "$lib/utils/summaryParser";

  let { data } = $props();

  // Get the primary anomaly for this event
  let primaryAnomaly = $derived(
    data.relatedAnomalies && data.relatedAnomalies.length > 0
      ? data.relatedAnomalies[0]
      : null
  );

  // Enhanced summary for anomaly display
  let enhancedSummary = $derived(
    primaryAnomaly
      ? (() => {
          const componentScores: ComponentScores = {
            behavioral: Number(primaryAnomaly.behavioral_anomaly_score) || 0,
            content: Number(primaryAnomaly.content_risk_score) || 0,
            temporal: Number(primaryAnomaly.temporal_anomaly_score) || 0,
            repository:
              Number(primaryAnomaly.repository_criticality_score) || 0,
          };

          const summary =
            parseAISummary(primaryAnomaly.ai_summary) ||
            generateFallbackSummary(
              primaryAnomaly.event_type,
              primaryAnomaly.final_anomaly_score,
              primaryAnomaly.repository_name,
              componentScores
            );

          console.log("Event page enhanced summary:", summary);
          return summary;
        })()
      : null
  );

  // Get detection method
  let detectionMethod = $derived(
    primaryAnomaly
      ? (() => {
          const componentScores: ComponentScores = {
            behavioral: Number(primaryAnomaly.behavioral_anomaly_score) || 0,
            content: Number(primaryAnomaly.content_risk_score) || 0,
            temporal: Number(primaryAnomaly.temporal_anomaly_score) || 0,
            repository:
              Number(primaryAnomaly.repository_criticality_score) || 0,
          };

          return getPrimaryDetectionMethod(componentScores);
        })()
      : null
  );
  function formatDate(dateString) {
    return new Date(dateString).toLocaleString();
  }

  function getTypeIcon(type) {
    switch (type.toLowerCase()) {
      case "pushEvent":
        return "git-commit";
      case "pullRequestEvent":
        return "git-pull-request";
      case "issuesEvent":
        return "alert-circle";
      case "createEvent":
        return "plus";
      case "deleteEvent":
        return "trash-2";
      case "releaseEvent":
        return "tag";
      case "forkEvent":
        return "git-branch";
      case "watchEvent":
        return "eye";
      case "publicEvent":
        return "globe";
      default:
        return "activity";
    }
  }

  function getSeverityVariant(severity) {
    if (severity >= 0.8) return "error";
    if (severity >= 0.6) return "warning";
    return "info";
  }

  function getGitHubEventUrl(repoName, eventType, payload) {
    // Generate more useful GitHub URLs based on event type
    switch (eventType.toLowerCase()) {
      case "pushevent":
        if (payload?.commits?.[0]?.sha) {
          return `https://github.com/${repoName}/commit/${payload.commits[0].sha}`;
        }
        return `https://github.com/${repoName}/commits`;
      case "pullrequestevent":
        if (payload?.pull_request?.number) {
          return `https://github.com/${repoName}/pull/${payload.pull_request.number}`;
        }
        return `https://github.com/${repoName}/pulls`;
      case "issuesevent":
        if (payload?.issue?.number) {
          return `https://github.com/${repoName}/issues/${payload.issue.number}`;
        }
        return `https://github.com/${repoName}/issues`;
      case "releaseevent":
        if (payload?.release?.tag_name) {
          return `https://github.com/${repoName}/releases/tag/${payload.release.tag_name}`;
        }
        return `https://github.com/${repoName}/releases`;
      case "createevent":
      case "deleteevent":
        if (payload?.ref_type === "branch" && payload?.ref) {
          return `https://github.com/${repoName}/branches`;
        }
        if (payload?.ref_type === "tag" && payload?.ref) {
          return `https://github.com/${repoName}/tags`;
        }
        return `https://github.com/${repoName}`;
      case "forkevent":
        if (payload?.forkee?.html_url) {
          return payload.forkee.html_url;
        }
        return `https://github.com/${repoName}/network/members`;
      default:
        return `https://github.com/${repoName}`;
    }
  }

  function getGitHubRepoUrl(repoName) {
    return `https://github.com/${repoName}`;
  }
</script>

<svelte:head>
  <title>Event {data.event.id} - GitHub Monitor</title>
</svelte:head>

<div class="min-h-screen bg-gray-900 text-gray-100">
  <Navbar />

  <main class="container mx-auto px-6 py-8 space-y-8">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center space-x-4">
        <Button
          onclick={() => goto("/")}
          variant="ghost"
          size="sm"
          class="text-gray-400 hover:text-gray-100"
        >
          <Icon name="arrow-left" class="h-4 w-4 mr-2" />
          Back to Dashboard
        </Button>
        <div class="h-6 w-px bg-gray-600"></div>
        <div class="flex items-center space-x-2">
          <Icon
            name={getTypeIcon(data.event.type)}
            class="h-5 w-5 text-blue-400"
          />
          <h1 class="text-2xl font-bold text-gray-100 font-mono">
            Event Details
          </h1>
        </div>
      </div>

      <div class="flex items-center space-x-2">
        <a
          href={getGitHubEventUrl(
            data.event.repo_name,
            data.event.type,
            data.event.payload
          )}
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center space-x-2 px-3 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-600 rounded-lg text-sm text-gray-300 hover:text-gray-100 transition-colors"
        >
          <Icon name="external-link" class="h-4 w-4" />
          <span>View on GitHub</span>
        </a>
      </div>
    </div>

    <!-- Event Overview -->
    <Card class="p-6 bg-terminal-surface/50 border-terminal-border">
      <div class="space-y-6">
        <!-- Header Info -->
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center space-x-3 mb-4">
              <div class="p-3 rounded-lg bg-gray-800 border border-gray-600">
                <Icon
                  name={getTypeIcon(data.event.type)}
                  class="h-6 w-6 text-blue-400"
                />
              </div>
              <div>
                <h2 class="text-xl font-semibold text-gray-100 font-mono">
                  {data.event.type}
                </h2>
                <p class="text-sm text-gray-400">Event ID: {data.event.id}</p>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div class="p-4 bg-gray-900 rounded-lg border border-gray-600">
                <h3 class="text-sm font-medium text-gray-300 mb-2">
                  Repository
                </h3>
                <a
                  href="/repository/{encodeURIComponent(data.event.repo_name)}"
                  class="text-blue-400 hover:text-blue-300 font-mono text-sm"
                >
                  {data.event.repo_name}
                </a>
              </div>

              <div class="p-4 bg-gray-900 rounded-lg border border-gray-600">
                <h3 class="text-sm font-medium text-gray-300 mb-2">Actor</h3>
                <div class="flex items-center space-x-2">
                  <Icon name="user" class="h-4 w-4 text-gray-400" />
                  <span class="text-gray-100 font-mono text-sm"
                    >{data.event.actor_login}</span
                  >
                </div>
              </div>

              <div class="p-4 bg-gray-900 rounded-lg border border-gray-600">
                <h3 class="text-sm font-medium text-gray-300 mb-2">
                  Timestamp
                </h3>
                <div class="flex items-center space-x-2">
                  <Icon name="clock" class="h-4 w-4 text-gray-400" />
                  <span class="text-gray-100 text-sm"
                    >{formatDate(data.event.created_at)}</span
                  >
                </div>
              </div>
            </div>

            <div class="flex items-center space-x-4 text-sm">
              <div class="flex items-center space-x-2">
                <div
                  class="w-2 h-2 {data.event.processed
                    ? 'bg-green-400'
                    : 'bg-orange-400'} rounded-full"
                ></div>
                <span class="text-gray-400">
                  {data.event.processed ? "Processed" : "Pending Processing"}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Card>

    {#if primaryAnomaly && enhancedSummary}
      <Card class="p-6 bg-terminal-surface/50 border-terminal-border">
        <div class="space-y-6">
          <!-- Analysis Header -->
          <div
            class="flex items-center justify-between border-b border-gray-600 pb-4"
          >
            <h3
              class="text-lg font-semibold text-gray-100 flex items-center space-x-2"
            >
              <span>AI Security Analysis</span>
            </h3>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Root Cause -->
            <div class="space-y-3">
              <h4
                class="text-md font-semibold text-orange-400 flex items-center space-x-2"
              >
                <Icon name="search" class="h-4 w-4" />
                <span>Root Cause</span>
              </h4>
              <div
                class="bg-orange-900/20 border border-orange-400/30 rounded-lg p-4"
              >
                {#if enhancedSummary && enhancedSummary.root_cause && enhancedSummary.root_cause.length > 0}
                  <ul class="space-y-2">
                    {#each enhancedSummary.root_cause as cause, index}
                      <li class="flex items-start space-x-2 text-sm">
                        <div
                          class="w-5 h-5 rounded-full bg-orange-400/20 border border-orange-400/50 flex items-center justify-center text-xs font-medium text-orange-400 mt-0.5 flex-shrink-0"
                        >
                          {index + 1}
                        </div>
                        <span class="text-gray-300 flex-1">{cause}</span>
                      </li>
                    {/each}
                  </ul>
                  {#if enhancedSummary.incident_type}
                    <div class="mt-3 pt-3 border-t border-orange-400/30">
                      <p class="text-xs text-orange-400 font-medium">
                        Detection Type: {enhancedSummary.incident_type}
                      </p>
                    </div>
                  {/if}
                {:else}
                  <div class="space-y-2">
                    <p class="text-gray-400 text-sm italic">
                      Analyzing event patterns...
                    </p>
                    <div class="flex items-center space-x-2">
                      <div
                        class="animate-pulse bg-gray-600 h-3 w-3 rounded-full"
                      ></div>
                      <span class="text-xs text-gray-500"
                        >AI analysis running</span
                      >
                    </div>
                  </div>
                {/if}
              </div>
            </div>

            <!-- Impact Assessment -->
            <div class="space-y-3">
              <h4
                class="text-md font-semibold text-red-400 flex items-center space-x-2"
              >
                <Icon name="alert-triangle" class="h-4 w-4" />
                <span>Impact</span>
              </h4>
              <div
                class="bg-red-900/20 border border-red-400/30 rounded-lg p-4"
              >
                {#if enhancedSummary && enhancedSummary.impact && enhancedSummary.impact.length > 0}
                  <ul class="space-y-2">
                    {#each enhancedSummary.impact as impact, index}
                      <li class="flex items-start space-x-2 text-sm">
                        <div
                          class="w-5 h-5 rounded-full bg-red-400/20 border border-red-400/50 flex items-center justify-center text-xs font-medium text-red-400 mt-0.5 flex-shrink-0"
                        >
                          {index + 1}
                        </div>
                        <span class="text-gray-300 flex-1">{impact}</span>
                      </li>
                    {/each}
                  </ul>
                  {#if enhancedSummary.threat_level}
                    <div class="mt-3 pt-3 border-t border-red-400/30">
                      <p class="text-xs text-red-400 font-medium">
                        Threat Level: {enhancedSummary.threat_level}
                      </p>
                    </div>
                  {/if}
                {:else}
                  <div class="space-y-2">
                    <p class="text-gray-400 text-sm italic">
                      Evaluating security impact...
                    </p>
                    <div class="flex items-center space-x-2">
                      <div
                        class="animate-pulse bg-gray-600 h-3 w-3 rounded-full"
                      ></div>
                      <span class="text-xs text-gray-500"
                        >Impact assessment in progress</span
                      >
                    </div>
                  </div>
                {/if}
              </div>
            </div>

            <!-- Next Steps -->
            <div class="space-y-3">
              <h4
                class="text-md font-semibold text-green-400 flex items-center space-x-2"
              >
                <Icon name="list-checks" class="h-4 w-4" />
                <span>Recommended Actions</span>
              </h4>
              <div
                class="bg-green-900/20 border border-green-400/30 rounded-lg p-4"
              >
                {#if enhancedSummary && enhancedSummary.next_steps && enhancedSummary.next_steps.length > 0}
                  <ul class="space-y-2">
                    {#each enhancedSummary.next_steps as step, index}
                      <li class="flex items-start space-x-2 text-sm">
                        <div
                          class="w-5 h-5 rounded-full bg-green-400/20 border border-green-400/50 flex items-center justify-center text-xs font-medium text-green-400 mt-0.5 flex-shrink-0"
                        >
                          {index + 1}
                        </div>
                        <span class="text-gray-300 flex-1">{step}</span>
                      </li>
                    {/each}
                  </ul>
                  {#if enhancedSummary.urgency}
                    <div class="mt-3 pt-3 border-t border-green-400/30">
                      <div class="flex items-center space-x-2">
                        <Icon name="clock" class="h-3 w-3 text-green-400" />
                        <p class="text-xs text-green-400 font-medium">
                          {enhancedSummary.urgency}
                        </p>
                      </div>
                    </div>
                  {/if}
                  {#if enhancedSummary.recommendations && enhancedSummary.recommendations.length > 0}
                    <div class="mt-3 pt-3 border-t border-green-400/30">
                      <p class="text-xs text-green-400 font-medium mb-2">
                        Additional Recommendations:
                      </p>
                      <ul class="space-y-1">
                        {#each enhancedSummary.recommendations as rec}
                          <li
                            class="text-xs text-gray-400 flex items-start space-x-1"
                          >
                            <span>•</span>
                            <span>{rec}</span>
                          </li>
                        {/each}
                      </ul>
                    </div>
                  {/if}
                {:else}
                  <div class="space-y-2">
                    <p class="text-gray-400 text-sm italic">
                      Generating action plan...
                    </p>
                    <div class="flex items-center space-x-2">
                      <div
                        class="animate-pulse bg-gray-600 h-3 w-3 rounded-full"
                      ></div>
                      <span class="text-xs text-gray-500"
                        >AI recommendations loading</span
                      >
                    </div>
                  </div>
                {/if}
              </div>
            </div>
          </div>

          <!-- Detection Scores -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="p-3 bg-gray-900/50 rounded-lg border border-gray-600">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs text-gray-400">Behavioral</span>
                <Icon name="users" class="h-3 w-3 text-orange-400" />
              </div>
              <div class="text-lg font-mono text-orange-400">
                {(
                  (Number(primaryAnomaly.behavioral_anomaly_score) || 0) * 100
                ).toFixed(1)}%
              </div>
              <div class="w-full bg-gray-700 rounded-full h-1 mt-2">
                <div
                  class="bg-orange-400 h-1 rounded-full"
                  style="width: {(Number(
                    primaryAnomaly.behavioral_anomaly_score
                  ) || 0) * 100}%"
                ></div>
              </div>
            </div>

            <div class="p-3 bg-gray-900/50 rounded-lg border border-gray-600">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs text-gray-400">Content</span>
                <Icon name="file-text" class="h-3 w-3 text-red-400" />
              </div>
              <div class="text-lg font-mono text-red-400">
                {(
                  (Number(primaryAnomaly.content_risk_score) || 0) * 100
                ).toFixed(1)}%
              </div>
              <div class="w-full bg-gray-700 rounded-full h-1 mt-2">
                <div
                  class="bg-red-400 h-1 rounded-full"
                  style="width: {(Number(primaryAnomaly.content_risk_score) ||
                    0) * 100}%"
                ></div>
              </div>
            </div>

            <div class="p-3 bg-gray-900/50 rounded-lg border border-gray-600">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs text-gray-400">Temporal</span>
                <Icon name="clock" class="h-3 w-3 text-yellow-400" />
              </div>
              <div class="text-lg font-mono text-yellow-400">
                {(
                  (Number(primaryAnomaly.temporal_anomaly_score) || 0) * 100
                ).toFixed(1)}%
              </div>
              <div class="w-full bg-gray-700 rounded-full h-1 mt-2">
                <div
                  class="bg-yellow-400 h-1 rounded-full"
                  style="width: {(Number(
                    primaryAnomaly.temporal_anomaly_score
                  ) || 0) * 100}%"
                ></div>
              </div>
            </div>

            <div class="p-3 bg-gray-900/50 rounded-lg border border-gray-600">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs text-gray-400">Repository</span>
                <Icon name="shield" class="h-3 w-3 text-blue-400" />
              </div>
              <div class="text-lg font-mono text-blue-400">
                {(
                  (Number(primaryAnomaly.repository_criticality_score) || 0) *
                  100
                ).toFixed(1)}%
              </div>
              <div class="w-full bg-gray-700 rounded-full h-1 mt-2">
                <div
                  class="bg-blue-400 h-1 rounded-full"
                  style="width: {(Number(
                    primaryAnomaly.repository_criticality_score
                  ) || 0) * 100}%"
                ></div>
              </div>
            </div>
          </div>

          <!-- Risk Indicators -->
          {#if primaryAnomaly.high_risk_indicators}
            {@const riskIndicators = parseRiskIndicators(
              primaryAnomaly.high_risk_indicators
            )}
            {#if riskIndicators.indicators.length > 0}
              <div class="space-y-3">
                <h4
                  class="text-md font-semibold text-red-400 flex items-center space-x-2"
                >
                  <Icon name="alert-octagon" class="h-4 w-4" />
                  <span>Risk Factors Detected</span>
                </h4>
                <div class="flex flex-wrap gap-2">
                  {#each riskIndicators.indicators as indicator}
                    <Badge
                      variant="outline"
                      class="bg-red-900/30 border-red-400/50 text-red-300 text-xs"
                    >
                      <Icon name="alert-triangle" class="h-3 w-3 mr-1" />
                      {indicator}
                    </Badge>
                  {/each}
                </div>
              </div>
            {/if}
          {/if}

          <!-- Quick Actions -->
          <div class="border-t border-gray-600 pt-4">
            <div class="flex flex-wrap gap-3">
              <a
                href="/repository/{encodeURIComponent(data.event.repo_name)}"
                class="flex items-center space-x-2 px-3 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-sm transition-colors"
              >
                <Icon name="github" class="h-4 w-4" />
                <span>Repository Analysis</span>
              </a>
              <button
                class="flex items-center space-x-2 px-3 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-sm transition-colors"
                onclick={() =>
                  navigator.clipboard.writeText(
                    JSON.stringify(enhancedSummary, null, 2)
                  )}
              >
                <Icon name="copy" class="h-4 w-4" />
                <span>Copy Analysis</span>
              </button>
            </div>
          </div>
        </div>
      </Card>
    {/if}

    <!-- Related Incidents -->
    {#if data.event.related_incidents && data.event.related_incidents.length > 0}
      <Card class="p-6 bg-terminal-surface/50 border-terminal-border">
        <div class="space-y-4">
          <h3
            class="text-lg font-semibold text-gray-100 flex items-center space-x-2"
          >
            <Icon name="alert-triangle" class="h-5 w-5 text-orange-400" />
            <span
              >Related Security Incidents ({data.event.related_incidents
                .length})</span
            >
          </h3>

          <div class="space-y-4">
            {#each data.event.related_incidents as incident}
              <div class="p-4 rounded-lg border border-gray-600 bg-gray-800/50">
                <div class="flex items-center justify-between mb-3">
                  <div class="flex items-center space-x-3">
                    <h4 class="text-sm font-medium text-gray-100">
                      {incident.title}
                    </h4>
                    <Badge variant={getSeverityVariant(incident.severity)}>
                      {Math.round(incident.severity * 100)}%
                    </Badge>
                  </div>
                  <div class="text-xs text-gray-400">
                    {incident.incident_type} • {formatDate(incident.created_at)}
                  </div>
                </div>

                <!-- Show related events from this incident -->
                {#if incident.event_ids && incident.event_ids.length > 1}
                  <div class="text-xs text-gray-400 mb-2">
                    Other Events in this Incident ({incident.event_ids.length -
                      1} more):
                  </div>
                  <div class="grid gap-2 max-h-32 overflow-y-auto">
                    {#each incident.event_ids
                      .filter((id) => id !== data.event.id)
                      .slice(0, 5) as eventId}
                      <div
                        class="flex items-center justify-between p-2 bg-gray-900 rounded border border-gray-600"
                      >
                        <a
                          href="/event/{eventId}"
                          class="text-xs font-mono text-blue-400 hover:text-blue-300"
                        >
                          Event ID: {eventId}
                        </a>
                        <Icon
                          name="arrow-right"
                          class="h-3 w-3 text-gray-400"
                        />
                      </div>
                    {/each}
                    {#if incident.event_ids.length > 6}
                      <div class="text-xs text-gray-400 text-center">
                        +{incident.event_ids.length - 6} more events in this incident
                      </div>
                    {/if}
                  </div>
                {:else}
                  <div class="text-xs text-gray-500 italic">
                    This is the only event in incident #{incident.id}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      </Card>
    {/if}

    <!-- Event Payload -->
    {#if data.event.payload}
      <Card class="p-6 bg-terminal-surface/50 border-terminal-border">
        <div class="space-y-4">
          <h3
            class="text-lg font-semibold text-gray-100 flex items-center space-x-2"
          >
            <Icon name="code" class="h-5 w-5 text-blue-400" />
            <span>Event Payload</span>
          </h3>

          <div class="p-4 bg-gray-900 rounded-lg border border-gray-600">
            <pre
              class="text-sm text-gray-300 font-mono overflow-x-auto whitespace-pre-wrap">{JSON.stringify(
                data.event.payload,
                null,
                2
              )}</pre>
          </div>
        </div>
      </Card>
    {/if}

    <!-- Raw Response -->
    {#if data.event.raw_response}
      <Card class="p-6 bg-terminal-surface/50 border-terminal-border">
        <div class="space-y-4">
          <h3
            class="text-lg font-semibold text-gray-100 flex items-center space-x-2"
          >
            <Icon name="database" class="h-5 w-5 text-purple-400" />
            <span>Raw GitHub Response</span>
          </h3>

          <div
            class="p-4 bg-gray-900 rounded-lg border border-gray-600 max-h-96 overflow-y-auto"
          >
            <pre
              class="text-sm text-gray-300 font-mono overflow-x-auto whitespace-pre-wrap">{JSON.stringify(
                data.event.raw_response,
                null,
                2
              )}</pre>
          </div>
        </div>
      </Card>
    {/if}
  </main>
</div>
