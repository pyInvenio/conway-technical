<script lang="ts">
  import Card from '$lib/components/ui/Card.svelte';
  import Icon from '$lib/components/ui/Icon.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';

  interface RepositoryInfo {
    name: string;
    full_name: string;
    private: boolean;
    visibility: string;
    stars: number;
    forks: number;
    language: string;
    created_at: string;
    updated_at: string;
  }

  interface ContributorAnalysis {
    estimated_contributor_count: number;
    is_organization_owned: boolean;
    owner_login: string;
    contributor_diversity_score: number;
    analysis_type: string;
  }

  interface RepositoryContextData {
    repository_criticality_score: number;
    context_features: number[];
    feature_names: string[];
    repository_info: RepositoryInfo;
    contributor_analysis: ContributorAnalysis;
    context_insights: string[];
    analysis_type: string;
  }

  interface AnomalyData {
    repository_context?: RepositoryContextData;
    repository_name?: string;
    user_login?: string;
    event_timestamp?: string;
  }

  // Props
  let { anomalyData = null }: { anomalyData: AnomalyData | null } = $props();

  // Context feature descriptions
  const contextFeatureDescriptions = {
    'repository_criticality_score': 'Overall Criticality',
    'stars_normalized': 'Popularity (Stars)',
    'forks_normalized': 'Community (Forks)',
    'contributors_count_normalized': 'Contributors',
    'recent_activity_score': 'Recent Activity',
    'security_policy_score': 'Security Features',
    'protected_branches_score': 'Branch Protection',
    'dependency_risk_score': 'Dependency Risk',
    'popularity_momentum_score': 'Growth Momentum'
  };

  // Language colors for better visualization
  const languageColors = {
    'javascript': 'bg-yellow-500',
    'typescript': 'bg-blue-500',
    'python': 'bg-green-500',
    'java': 'bg-red-500',
    'go': 'bg-cyan-500',
    'rust': 'bg-orange-500',
    'c++': 'bg-purple-500',
    'ruby': 'bg-red-600',
    'php': 'bg-indigo-500',
    'swift': 'bg-orange-600'
  };

  const contextData = $derived(anomalyData?.repository_context);
  const hasData = $derived(contextData && contextData.context_features?.length > 0);
  const repoInfo = $derived(contextData?.repository_info);
  const contributorInfo = $derived(contextData?.contributor_analysis);
  const insights = $derived(contextData?.context_insights || []);

  function getCriticalityLevel(score: number): string {
    if (score >= 0.8) return 'Critical';
    if (score >= 0.6) return 'High';
    if (score >= 0.4) return 'Medium';
    return 'Low';
  }

  function getCriticalityColor(score: number): string {
    if (score >= 0.8) return 'text-red-400';
    if (score >= 0.6) return 'text-orange-400';
    if (score >= 0.4) return 'text-yellow-400';
    return 'text-green-400';
  }

  function getCriticalityVariant(score: number): 'error' | 'warning' | 'info' {
    if (score >= 0.8) return 'error';
    if (score >= 0.6) return 'warning';
    return 'info';
  }

  function formatNumber(num: number): string {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  }

  function formatDate(dateString: string): string {
    try {
      return new Date(dateString).toLocaleDateString();
    } catch {
      return dateString;
    }
  }

  function getLanguageColor(language: string): string {
    const lang = language?.toLowerCase();
    return languageColors[lang] || 'bg-gray-500';
  }

  function formatFeatureValue(value: number, featureName: string): string {
    if (featureName.includes('score') || featureName.includes('normalized')) {
      return (value * 100).toFixed(1) + '%';
    }
    return value.toFixed(2);
  }

  function getFeatureIntensity(value: number): string {
    if (value >= 0.8) return 'Very High';
    if (value >= 0.6) return 'High';
    if (value >= 0.4) return 'Medium';
    if (value >= 0.2) return 'Low';
    return 'Very Low';
  }

  function getFeatureColor(value: number): string {
    if (value >= 0.8) return 'text-red-400';
    if (value >= 0.6) return 'text-orange-400';
    if (value >= 0.4) return 'text-yellow-400';
    if (value >= 0.2) return 'text-blue-400';
    return 'text-gray-400';
  }

  function getVisibilityIcon(isPrivate: boolean): string {
    return isPrivate ? 'lock' : 'globe';
  }

  function getVisibilityColor(isPrivate: boolean): string {
    return isPrivate ? 'text-red-400' : 'text-green-400';
  }

  function getOwnerTypeIcon(isOrganization: boolean): string {
    return isOrganization ? 'building-2' : 'user';
  }

  function getCriticalityMultiplier(score: number): number {
    if (score >= 0.8) return 1.5;
    if (score >= 0.6) return 1.3;
    if (score >= 0.4) return 1.1;
    return 1.0;
  }

  // Generate circular progress for criticality score
  function getCircularProgress(score: number): string {
    const circumference = 2 * Math.PI * 40; // radius = 40
    const strokeDasharray = circumference;
    const strokeDashoffset = circumference - (score * circumference);
    return `stroke-dasharray: ${strokeDasharray}; stroke-dashoffset: ${strokeDashoffset};`;
  }
</script>

<Card class="p-6 bg-terminal-surface/50 border-terminal-border">
  <div class="flex items-center justify-between mb-6">
    <div class="flex items-center space-x-3">
      <div class="p-2 rounded-lg bg-green-600/20 border border-green-600/30">
        <Icon name="git-branch" class="h-5 w-5 text-green-400" />
      </div>
      <div>
        <h3 class="text-lg font-semibold text-terminal-text font-mono">Repository Context</h3>
        {#if anomalyData?.repository_name}
          <p class="text-sm text-gray-400">{anomalyData.repository_name}</p>
        {/if}
      </div>
    </div>
    
    {#if hasData}
      <div class="flex items-center space-x-4">
        <!-- Criticality Score Gauge -->
        <div class="relative">
          <svg class="w-20 h-20 transform -rotate-90" viewBox="0 0 100 100">
            <!-- Background circle -->
            <circle 
              cx="50" cy="50" r="40" 
              stroke="currentColor" 
              stroke-width="8" 
              fill="none" 
              class="text-gray-700"
            />
            <!-- Progress circle -->
            <circle 
              cx="50" cy="50" r="40" 
              stroke="currentColor" 
              stroke-width="8" 
              fill="none" 
              class="{getCriticalityColor(contextData.repository_criticality_score)}"
              style="{getCircularProgress(contextData.repository_criticality_score)}"
              stroke-linecap="round"
            />
          </svg>
          <div class="absolute inset-0 flex items-center justify-center">
            <div class="text-center">
              <div class="text-lg font-bold text-white">
                {(contextData.repository_criticality_score * 100).toFixed(0)}%
              </div>
              <div class="text-xs text-gray-400">Critical</div>
            </div>
          </div>
        </div>
        
        <div class="text-right">
          <Badge variant={getCriticalityVariant(contextData.repository_criticality_score)} size="lg">
            {getCriticalityLevel(contextData.repository_criticality_score)}
          </Badge>
          <p class="text-xs text-gray-400 mt-1">
            {getCriticalityMultiplier(contextData.repository_criticality_score)}x severity multiplier
          </p>
        </div>
      </div>
    {/if}
  </div>

  {#if !hasData}
    <div class="text-center py-8">
      <Icon name="git-branch" class="h-12 w-12 text-gray-400 mx-auto mb-3" />
      <p class="text-gray-400">No repository context analysis available</p>
    </div>
  {:else}
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Repository Information -->
      <div>
        <h4 class="text-sm font-semibold text-gray-300 mb-3 flex items-center">
          <Icon name="info" class="h-4 w-4 mr-2" />
          Repository Details
        </h4>
        
        {#if repoInfo}
          <div class="bg-gray-800/30 rounded-lg p-4 space-y-4">
            <!-- Basic Info -->
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-2">
                <Icon name={getVisibilityIcon(repoInfo.private)} class="h-4 w-4 {getVisibilityColor(repoInfo.private)}" />
                <span class="font-mono text-white">{repoInfo.full_name}</span>
              </div>
              <Badge variant={repoInfo.private ? 'error' : 'info'} size="sm">
                {repoInfo.visibility}
              </Badge>
            </div>

            <!-- Stats Grid -->
            <div class="grid grid-cols-2 gap-4">
              <div class="text-center p-3 bg-gray-700/30 rounded">
                <Icon name="star" class="h-4 w-4 text-yellow-400 mx-auto mb-1" />
                <div class="text-lg font-bold text-white">{formatNumber(repoInfo.stars)}</div>
                <div class="text-xs text-gray-400">Stars</div>
              </div>
              
              <div class="text-center p-3 bg-gray-700/30 rounded">
                <Icon name="git-fork" class="h-4 w-4 text-blue-400 mx-auto mb-1" />
                <div class="text-lg font-bold text-white">{formatNumber(repoInfo.forks)}</div>
                <div class="text-xs text-gray-400">Forks</div>
              </div>
            </div>

            <!-- Language & Dates -->
            {#if repoInfo.language}
              <div class="flex items-center space-x-2">
                <div class="w-3 h-3 rounded-full {getLanguageColor(repoInfo.language)}"></div>
                <span class="text-sm text-gray-300">{repoInfo.language}</span>
              </div>
            {/if}

            <div class="text-sm text-gray-400 space-y-1">
              <div>Created: {formatDate(repoInfo.created_at)}</div>
              <div>Updated: {formatDate(repoInfo.updated_at)}</div>
            </div>
          </div>
        {/if}

        <!-- Contributor Analysis -->
        {#if contributorInfo}
          <div class="mt-4">
            <h5 class="text-xs font-semibold text-gray-400 mb-2">Contributor Analysis</h5>
            <div class="bg-gray-800/30 rounded-lg p-3 space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-sm text-gray-300">Owner Type</span>
                <div class="flex items-center space-x-1">
                  <Icon name={getOwnerTypeIcon(contributorInfo.is_organization_owned)} class="h-3 w-3 text-gray-400" />
                  <span class="text-sm text-white">
                    {contributorInfo.is_organization_owned ? 'Organization' : 'Personal'}
                  </span>
                </div>
              </div>
              
              <div class="flex items-center justify-between">
                <span class="text-sm text-gray-300">Est. Contributors</span>
                <span class="text-sm font-mono text-white">{contributorInfo.estimated_contributor_count}</span>
              </div>
              
              <div class="flex items-center justify-between">
                <span class="text-sm text-gray-300">Diversity Score</span>
                <span class="text-sm font-mono text-white">
                  {(contributorInfo.contributor_diversity_score * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>
        {/if}
      </div>

      <!-- Context Features -->
      <div>
        <h4 class="text-sm font-semibold text-gray-300 mb-3 flex items-center">
          <Icon name="bar-chart-3" class="h-4 w-4 mr-2" />
          Context Metrics
        </h4>
        
        <div class="space-y-2 max-h-80 overflow-y-auto">
          {#each contextData.feature_names as featureName, index}
            {@const value = contextData.context_features[index]}
            {@const intensity = getFeatureIntensity(value)}
            {@const intensityColor = getFeatureColor(value)}
            
            <div class="bg-gray-800/30 rounded p-3">
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm text-gray-300">
                  {contextFeatureDescriptions[featureName] || featureName}
                </span>
                <div class="flex items-center space-x-2">
                  <span class="text-sm font-mono text-white">
                    {formatFeatureValue(value, featureName)}
                  </span>
                  <span class="text-xs {intensityColor}">
                    {intensity}
                  </span>
                </div>
              </div>
              
              <!-- Feature value bar -->
              <div class="w-full bg-gray-700 rounded-full h-2">
                <div 
                  class="h-2 rounded-full transition-all duration-300 {
                    value >= 0.8 ? 'bg-red-400' :
                    value >= 0.6 ? 'bg-orange-400' :
                    value >= 0.4 ? 'bg-yellow-400' :
                    value >= 0.2 ? 'bg-blue-400' : 'bg-gray-400'
                  }"
                  style="width: {Math.max(value * 100, 5)}%"
                ></div>
              </div>
            </div>
          {/each}
        </div>
      </div>
    </div>

    <!-- Context Insights -->
    {#if insights.length > 0}
      <div class="mt-6">
        <h4 class="text-sm font-semibold text-gray-300 mb-3 flex items-center">
          <Icon name="lightbulb" class="h-4 w-4 mr-2" />
          Context Insights
        </h4>
        
        <div class="bg-blue-900/20 border border-blue-500/30 rounded-lg p-4">
          <ul class="space-y-2">
            {#each insights as insight}
              <li class="flex items-start space-x-2">
                <Icon name="info" class="h-4 w-4 text-blue-400 mt-0.5 flex-shrink-0" />
                <span class="text-sm text-blue-100">{insight}</span>
              </li>
            {/each}
          </ul>
        </div>
      </div>
    {/if}

    <!-- Risk Assessment Summary -->
    <div class="mt-6 p-4 bg-gray-800/30 rounded-lg">
      <h5 class="text-sm font-semibold text-gray-300 mb-3">Risk Assessment Summary</h5>
      
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="text-center">
          <div class="text-2xl font-bold {getCriticalityColor(contextData.repository_criticality_score)}">
            {getCriticalityLevel(contextData.repository_criticality_score)}
          </div>
          <div class="text-xs text-gray-400">Repository Risk</div>
        </div>
        
        <div class="text-center">
          <div class="text-2xl font-bold text-white">
            {getCriticalityMultiplier(contextData.repository_criticality_score)}x
          </div>
          <div class="text-xs text-gray-400">Severity Multiplier</div>
        </div>
        
        <div class="text-center">
          <div class="text-2xl font-bold text-white">
            {repoInfo?.private ? 'Private' : 'Public'}
          </div>
          <div class="text-xs text-gray-400">Visibility Impact</div>
        </div>
      </div>
    </div>

    <!-- Analysis Footer -->
    <div class="mt-6 pt-4 border-t border-gray-700">
      <div class="flex items-center justify-between text-sm">
        <div class="flex items-center space-x-4 text-gray-400">
          <span>Analysis: {contextData.analysis_type}</span>
          {#if contributorInfo?.analysis_type}
            <span>Contributors: {contributorInfo.analysis_type}</span>
          {/if}
        </div>
        
        <div class="flex items-center space-x-2">
          <div class="w-2 h-2 rounded-full {contextData.repository_criticality_score > 0.6 ? 'bg-orange-400 animate-pulse' : 'bg-green-400'}"></div>
          <span class="text-xs text-gray-400">
            {contextData.repository_criticality_score > 0.6 ? 'High-Value Repository' : 'Context Analysis Complete'}
          </span>
        </div>
      </div>
    </div>
  {/if}
</Card>