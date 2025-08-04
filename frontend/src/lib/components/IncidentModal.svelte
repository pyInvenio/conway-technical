<script>
  import { fade, fly } from "svelte/transition";

  let { incident, onclose } = $props();

  let activeTab = $state("summary");
  let additionalContext = $state(null);
  let loadingContext = $state(false);

  const tabs = [
    { id: "summary", label: "Summary", icon: "📊" },
    { id: "timeline", label: "Timeline", icon: "⏱️" },
    { id: "context", label: "Context", icon: "🔍" },
    { id: "raw", label: "Raw Data", icon: "💾" },
  ];

  async function loadAdditionalContext() {
    if (additionalContext || loadingContext) return;

    loadingContext = true;
    try {
      const [repoResponse, actorResponse] = await Promise.all([
        fetch(`/api/context/repo?id=${encodeURIComponent(incident.repo_name)}`),
        fetch(
          `/api/context/user?id=${encodeURIComponent(incident.raw_context?.actor || "unknown")}`
        ),
      ]);

      additionalContext = {
        repo: repoResponse.ok ? await repoResponse.json() : null,
        actor: actorResponse.ok ? await actorResponse.json() : null,
      };
    } catch (error) {
      console.error("Failed to load context:", error);
    } finally {
      loadingContext = false;
    }
  }

  $effect(() => {
    if (activeTab === "context") {
      loadAdditionalContext();
    }
  });
</script>

<div
  class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
  transition:fade={{ duration: 200 }}
  onclick={onclose}
>
  <div
    class="bg-slate-800 rounded-xl shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden"
    transition:fly={{ y: 20, duration: 300 }}
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
    role="dialog"
    aria-modal="true"
  >
    <!-- Header -->
    <div class="p-6 border-b border-slate-700 flex items-start justify-between">
      <div class="flex-1">
        <h2 class="text-2xl font-bold text-white mb-2">{incident.title}</h2>
        <div class="flex items-center gap-4 text-sm text-slate-400">
          <span>{incident.repo_name}</span>
          <span>•</span>
          <span>{new Date(incident.created_at).toLocaleString()}</span>
        </div>
      </div>
      <button
        onclick={onclose}
        class="text-slate-400 hover:text-white transition-colors p-2"
      >
        <svg
          class="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </button>
    </div>

    <!-- Tabs -->
    <div class="flex border-b border-slate-700 px-6">
      {#each tabs as tab}
        <button
          onclick={() => (activeTab = tab.id)}
          class="px-4 py-3 text-sm font-medium transition-colors relative
                           {activeTab === tab.id
            ? 'text-white'
            : 'text-slate-400 hover:text-slate-200'}"
        >
          <span class="flex items-center gap-2">
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </span>
          {#if activeTab === tab.id}
            <div class="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500"></div>
          {/if}
        </button>
      {/each}
    </div>

    <!-- Content -->
    <div class="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
      {#if activeTab === "summary"}
        <div class="space-y-6">
          <div>
            <h3
              class="text-lg font-semibold text-white mb-3 flex items-center gap-2"
            >
              <span class="text-red-400">⚠️</span> Root Cause Analysis
            </h3>
            <ul class="space-y-2">
              {#each incident.root_cause as cause}
                <li class="flex items-start gap-3 text-slate-300">
                  <span class="text-blue-400 mt-1">▸</span>
                  <span>{cause}</span>
                </li>
              {/each}
            </ul>
          </div>

          <div>
            <h3
              class="text-lg font-semibold text-white mb-3 flex items-center gap-2"
            >
              <span class="text-yellow-400">💥</span> Impact Assessment
            </h3>
            <ul class="space-y-2">
              {#each incident.impact as impact}
                <li class="flex items-start gap-3 text-slate-300">
                  <span class="text-yellow-400 mt-1">▸</span>
                  <span>{impact}</span>
                </li>
              {/each}
            </ul>
          </div>

          <div>
            <h3
              class="text-lg font-semibold text-white mb-3 flex items-center gap-2"
            >
              <span class="text-green-400">✅</span> Recommended Actions
            </h3>
            <ul class="space-y-2">
              {#each incident.next_steps as step, i}
                <li class="flex items-start gap-3 text-slate-300">
                  <span class="text-green-400 mt-1">{i + 1}.</span>
                  <span>{step}</span>
                </li>
              {/each}
            </ul>
          </div>

          <div class="grid grid-cols-2 gap-4 p-4 bg-slate-900/50 rounded-lg">
            <div>
              <span class="text-sm text-slate-400">Severity Score</span>
              <div class="text-2xl font-bold text-white">
                {(incident.severity * 100).toFixed(0)}%
              </div>
            </div>
            <div>
              <span class="text-sm text-slate-400">Entropy Score</span>
              <div class="text-2xl font-bold text-white">
                {incident.entropy_score
                  ? (incident.entropy_score * 100).toFixed(0) + "%"
                  : "N/A"}
              </div>
            </div>
            <div>
              <span class="text-sm text-slate-400">Incident Type</span>
              <div class="text-lg font-medium text-white capitalize">
                {incident.incident_type.replace(/_/g, " ")}
              </div>
            </div>
            <div>
              <span class="text-sm text-slate-400">Events Analyzed</span>
              <div class="text-lg font-medium text-white">
                {incident.event_ids.length}
              </div>
            </div>
          </div>
        </div>
      {:else if activeTab === "context"}
        {#if loadingContext}
          <div class="flex items-center justify-center py-12">
            <div class="text-slate-400">Loading context...</div>
          </div>
        {:else if additionalContext}
          <div class="space-y-6">
            {#if additionalContext.repo}
              <div>
                <h3 class="text-lg font-semibold text-white mb-3">
                  Repository Information
                </h3>
                <div
                  class="grid grid-cols-2 gap-4 p-4 bg-slate-900/50 rounded-lg"
                >
                  <div>
                    <span class="text-sm text-slate-400">Created</span>
                    <div class="text-white">
                      {new Date(
                        additionalContext.repo.created_at
                      ).toLocaleDateString()}
                    </div>
                  </div>
                  <div>
                    <span class="text-sm text-slate-400">Language</span>
                    <div class="text-white">
                      {additionalContext.repo.language || "Unknown"}
                    </div>
                  </div>
                  <div>
                    <span class="text-sm text-slate-400">Stars</span>
                    <div class="text-white">
                      {additionalContext.repo.stargazers_count}
                    </div>
                  </div>
                  <div>
                    <span class="text-sm text-slate-400">Open Issues</span>
                    <div class="text-white">
                      {additionalContext.repo.open_issues_count}
                    </div>
                  </div>
                </div>
              </div>
            {/if}
          </div>
        {/if}
      {:else if activeTab === "raw"}
        <pre
          class="bg-slate-900 rounded-lg p-4 text-xs text-slate-300 overflow-x-auto">
{JSON.stringify(incident, null, 2)}
                </pre>
      {/if}
    </div>
  </div>
</div>