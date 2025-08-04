<script>
    import { getContext } from 'svelte';
    
    let { incident, onclick } = $props();
    
    const severityColors = {
        CRITICAL: 'border-red-600 bg-red-600/10',
        HIGH: 'border-red-500 bg-red-500/10',
        MEDIUM: 'border-yellow-500 bg-yellow-500/10',
        LOW: 'border-green-500 bg-green-500/10',
        INFO: 'border-blue-500 bg-blue-500/10'
    };
    
    const severityBadgeColors = {
        CRITICAL: 'bg-red-600/30 text-red-300 border border-red-500/50',
        HIGH: 'bg-red-500/20 text-red-400',
        MEDIUM: 'bg-yellow-500/20 text-yellow-400',
        LOW: 'bg-green-500/20 text-green-400',
        INFO: 'bg-blue-500/20 text-blue-400'
    };
    
    const getSeverityLevel = (incident) => {
        // Use new severity_level if available, otherwise fallback to score-based
        if (incident.severity_level) {
            return incident.severity_level;
        }
        if (incident.severity >= 0.85) return 'CRITICAL';
        if (incident.severity >= 0.65) return 'HIGH';
        if (incident.severity >= 0.35) return 'MEDIUM';
        if (incident.severity >= 0.15) return 'LOW';
        return 'INFO';
    };
    
    const formatTime = (timestamp) => {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        return date.toLocaleDateString();
    };
    
    const severity = $derived(getSeverityLevel(incident));
    
    // Fetch additional context on hover
    let additionalContext = $state(null);
    let loadingContext = $state(false);
    
    async function fetchContext() {
        if (additionalContext || loadingContext) return;
        
        loadingContext = true;
        try {
            const response = await fetch(`/api/context/repo?id=${encodeURIComponent(incident.repo_name)}`);
            if (response.ok) {
                additionalContext = await response.json();
            }
        } catch (error) {
            console.error('Failed to fetch context:', error);
        } finally {
            loadingContext = false;
        }
    }
</script>

<button
    onclick={onclick}
    onmouseenter={fetchContext}
    class="w-full text-left bg-slate-800 border {severityColors[severity]} rounded-lg p-6 
           hover:border-opacity-100 border-opacity-50 transition-all duration-200 
           hover:transform hover:-translate-y-1 hover:shadow-lg group"
>
    <div class="flex items-start justify-between mb-3">
        <div class="flex-1">
            <h3 class="font-semibold text-white text-lg group-hover:text-blue-400 transition-colors">
                {incident.repo_name}
            </h3>
            <span class="text-sm text-slate-400 capitalize">
                {incident.incident_type.replace(/_/g, ' ')}
            </span>
        </div>
        <div class="flex flex-col items-end gap-2">
            <span class="px-2 py-1 rounded text-xs font-medium {severityBadgeColors[severity]}">
                {severity}
            </span>
            <span class="text-xs text-slate-500">{formatTime(incident.created_at)}</span>
        </div>
    </div>
    
    <h4 class="text-sm font-medium text-slate-200 mb-2">{incident.title}</h4>
    
    <div class="space-y-2">
        <div>
            <h5 class="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">Root Cause</h5>
            <ul class="space-y-1">
                {#each incident.root_cause.slice(0, 2) as cause}
                    <li class="text-sm text-slate-300 flex items-start gap-2">
                        <span class="text-slate-500 mt-1">•</span>
                        <span>{cause}</span>
                    </li>
                {/each}
            </ul>
        </div>
    </div>
    
    <!-- New Anomaly Detection Scores -->
    {#if incident.anomaly_data?.detection_scores}
        <div class="mt-4 space-y-2">
            <h5 class="text-xs font-medium text-slate-400 uppercase tracking-wider">Detection Scores</h5>
            <div class="grid grid-cols-2 gap-2">
                {#if incident.anomaly_data.detection_scores.behavioral}
                    <div class="flex items-center justify-between text-xs">
                        <span class="text-slate-400">Behavioral</span>
                        <span class="text-slate-300">{(incident.anomaly_data.detection_scores.behavioral * 100).toFixed(0)}%</span>
                    </div>
                {/if}
                {#if incident.anomaly_data.detection_scores.content}
                    <div class="flex items-center justify-between text-xs">
                        <span class="text-slate-400">Content</span>
                        <span class="text-slate-300">{(incident.anomaly_data.detection_scores.content * 100).toFixed(0)}%</span>
                    </div>
                {/if}
                {#if incident.anomaly_data.detection_scores.temporal}
                    <div class="flex items-center justify-between text-xs">
                        <span class="text-slate-400">Temporal</span>
                        <span class="text-slate-300">{(incident.anomaly_data.detection_scores.temporal * 100).toFixed(0)}%</span>
                    </div>
                {/if}
                {#if incident.anomaly_data.detection_scores.repository_criticality}
                    <div class="flex items-center justify-between text-xs">
                        <span class="text-slate-400">Repo Risk</span>
                        <span class="text-slate-300">{(incident.anomaly_data.detection_scores.repository_criticality * 100).toFixed(0)}%</span>
                    </div>
                {/if}
            </div>
        </div>
    {:else if incident.entropy_score}
        <!-- Fallback to old entropy score -->
        <div class="mt-4">
            <div class="flex items-center justify-between text-xs text-slate-400 mb-1">
                <span>Activity Entropy</span>
                <span>{(incident.entropy_score * 100).toFixed(0)}%</span>
            </div>
            <div class="w-full h-1 bg-slate-700 rounded-full overflow-hidden">
                <div 
                    class="h-full transition-all duration-500 {incident.entropy_score > 0.7 ? 'bg-red-500' : 'bg-blue-500'}"
                    style="width: {incident.entropy_score * 100}%"
                />
            </div>
        </div>
    {/if}

    <!-- Final Anomaly Score Bar -->
    {#if incident.severity}
        <div class="mt-3">
            <div class="flex items-center justify-between text-xs text-slate-400 mb-1">
                <span>Anomaly Score</span>
                <span>{(incident.severity * 100).toFixed(1)}%</span>
            </div>
            <div class="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
                <div 
                    class="h-full transition-all duration-500 {
                        incident.severity >= 0.85 ? 'bg-red-600' :
                        incident.severity >= 0.65 ? 'bg-red-500' :
                        incident.severity >= 0.35 ? 'bg-yellow-500' :
                        incident.severity >= 0.15 ? 'bg-green-500' : 'bg-blue-500'
                    }"
                    style="width: {incident.severity * 100}%"
                />
            </div>
        </div>
    {/if}
    
    {#if additionalContext}
        <div class="mt-3 pt-3 border-t border-slate-700">
            <div class="grid grid-cols-2 gap-2 text-xs">
                <div>
                    <span class="text-slate-500">Stars:</span>
                    <span class="text-slate-300 ml-1">{additionalContext.stargazers_count}</span>
                </div>
                <div>
                    <span class="text-slate-500">Language:</span>
                    <span class="text-slate-300 ml-1">{additionalContext.language || 'Unknown'}</span>
                </div>
            </div>
        </div>
    {/if}
</button>