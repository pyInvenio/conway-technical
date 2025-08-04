<script lang="ts">
  import Card from '$lib/components/ui/Card.svelte';
  import Icon from '$lib/components/ui/Icon.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';

  interface SecretDetection {
    type: string;
    pattern: string;
    severity: number;
    match: string;
    position: [number, number];
    location?: string;
    commit_sha?: string;
    commit_url?: string;
    event_id?: string;
    repository?: string;
    actor?: string;
    timestamp?: string;
  }

  interface FileAnalysis {
    suspicious_files: Array<{
      filename: string;
      category: string;
      risk_score: number;
      reason: string;
      description: string;
    }>;
    large_changes: Array<{
      filename: string;
      additions: number;
      deletions: number;
      changes: number;
    }>;
    binary_changes: string[];
    mass_deletions: Array<{
      filename: string;
      deletions: number;
    }>;
    credential_modifications: Array<{
      filename: string;
      type: string;
    }>;
    total_files_changed: number;
    total_lines_added: number;
    total_lines_deleted: number;
  }

  interface ContentRiskData {
    content_risk_score: number;
    secret_detections: SecretDetection[];
    file_analysis: FileAnalysis;
    content_features: number[];
    feature_names: string[];
    high_risk_indicators: string[];
  }

  interface AnomalyData {
    content_analysis?: ContentRiskData;
    repository_name?: string;
    user_login?: string;
    event_timestamp?: string;
  }

  // Props
  let { anomalyData = null }: { anomalyData: AnomalyData | null } = $props();

  // Content feature descriptions
  const contentFeatureDescriptions = {
    'secret_pattern_count': 'Secret Patterns Found',
    'high_severity_secret_count': 'High Severity Secrets',
    'suspicious_file_count': 'Suspicious Files',
    'credential_file_count': 'Credential Files',
    'key_file_count': 'Key Files',
    'large_file_changes': 'Large File Changes',
    'binary_file_changes': 'Binary File Changes',
    'deletion_to_addition_ratio': 'Deletion/Addition Ratio',
    'avg_secret_severity': 'Average Secret Severity'
  };

  // Secret type icons
  const secretTypeIcons = {
    'aws_access_key': 'cloud',
    'aws_secret_key': 'cloud',
    'github_token': 'github',
    'github_oauth': 'github',
    'github_app_token': 'github',
    'private_key': 'key',
    'jwt_token': 'shield',
    'slack_token': 'message-square',
    'stripe_key': 'credit-card',
    'api_key_generic': 'link',
    'password': 'lock',
    'secret_generic': 'eye-off',
    'token_generic': 'hash',
    'connection_string': 'database',
    'database_url': 'database'
  };

  const contentData = $derived(anomalyData?.content_analysis);
  const hasData = $derived(contentData && contentData.content_features?.length > 0);
  const secrets = $derived(contentData?.secret_detections || []);
  const fileAnalysis = $derived(contentData?.file_analysis);
  const highRiskIndicators = $derived(contentData?.high_risk_indicators || []);

  // Categorize secrets by severity
  const criticalSecrets = $derived(secrets.filter(s => s.severity >= 0.8));
  const highSecrets = $derived(secrets.filter(s => s.severity >= 0.6 && s.severity < 0.8));
  const mediumSecrets = $derived(secrets.filter(s => s.severity >= 0.4 && s.severity < 0.6));
  const lowSecrets = $derived(secrets.filter(s => s.severity < 0.4));

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

  function getSecretIcon(secretType: string): string {
    return secretTypeIcons[secretType] || 'alert-triangle';
  }

  function formatFeatureValue(value: number, featureName: string): string {
    if (featureName.includes('ratio') || featureName.includes('severity')) {
      return (value * 100).toFixed(1) + '%';
    }
    if (featureName.includes('count')) {
      return Math.round(value).toString();
    }
    return value.toFixed(2);
  }

  function getRiskCategoryColor(category: string): string {
    switch (category) {
      case 'keys': return 'text-red-400';
      case 'credentials': return 'text-orange-400';
      case 'config': return 'text-yellow-400';
      case 'cloud': return 'text-blue-400';
      case 'backup': return 'text-purple-400';
      default: return 'text-gray-400';
    }
  }

  function truncateMatch(match: string, maxLength: number = 30): string {
    if (match.length <= maxLength) return match;
    return match.substring(0, maxLength) + '...';
  }

  // File type risk heatmap data
  const fileTypeRisks = $derived(fileAnalysis ? [
    { type: 'Credential Files', count: fileAnalysis.credential_modifications?.length || 0, risk: 'high' },
    { type: 'Config Files', count: fileAnalysis.suspicious_files?.filter(f => f.category === 'config').length || 0, risk: 'medium' },
    { type: 'Key Files', count: fileAnalysis.suspicious_files?.filter(f => f.category === 'keys').length || 0, risk: 'critical' },
    { type: 'Large Changes', count: fileAnalysis.large_changes?.length || 0, risk: 'medium' },
    { type: 'Binary Changes', count: fileAnalysis.binary_changes?.length || 0, risk: 'low' },
    { type: 'Mass Deletions', count: fileAnalysis.mass_deletions?.length || 0, risk: 'high' }
  ] : []);
</script>

<Card class="p-6 bg-terminal-surface/50 border-terminal-border">
  <div class="flex items-center justify-between mb-6">
    <div class="flex items-center space-x-3">
      <div class="p-2 rounded-lg bg-red-600/20 border border-red-600/30">
        <Icon name="shield-alert" class="h-5 w-5 text-red-400" />
      </div>
      <div>
        <h3 class="text-lg font-semibold text-terminal-text font-mono">Content Risk Analysis</h3>
        {#if anomalyData?.repository_name}
          <p class="text-sm text-gray-400">Repository: {anomalyData.repository_name}</p>
        {/if}
      </div>
    </div>
    
    {#if hasData}
      <div class="flex items-center space-x-4">
        <div class="text-right">
          <p class="text-sm text-gray-400">Risk Score</p>
          <div class="flex items-center space-x-2">
            <span class="text-2xl font-bold text-white">
              {(contentData.content_risk_score * 100).toFixed(1)}%
            </span>
            <Badge variant={getSeverityVariant(contentData.content_risk_score)}>
              {getSeverityLabel(contentData.content_risk_score)}
            </Badge>
          </div>
        </div>
        
        <div class="text-right">
          <p class="text-sm text-gray-400">Secrets Found</p>
          <span class="text-lg font-semibold text-white">
            {secrets.length}
          </span>
        </div>
      </div>
    {/if}
  </div>

  {#if !hasData}
    <div class="text-center py-8">
      <Icon name="shield-check" class="h-12 w-12 text-gray-400 mx-auto mb-3" />
      <p class="text-gray-400">No content risk analysis available</p>
    </div>
  {:else}
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Secret Detections -->
      <div>
        <h4 class="text-sm font-semibold text-gray-300 mb-3 flex items-center">
          <Icon name="key" class="h-4 w-4 mr-2" />
          Secret Detections ({secrets.length})
        </h4>
        
        <div class="space-y-3 max-h-80 overflow-y-auto">
          {#if secrets.length === 0}
            <div class="text-center py-4">
              <Icon name="shield-check" class="h-8 w-8 text-green-400 mx-auto mb-2" />
              <p class="text-sm text-gray-400">No secrets detected</p>
            </div>
          {:else}
            {#each secrets as secret}
              <div class="bg-gray-800/50 rounded-lg p-3 border-l-4 {getSeverityColor(secret.severity)}">
                <div class="flex items-start justify-between">
                  <div class="flex-1">
                    <div class="flex items-center space-x-2 mb-2">
                      <Icon name={getSecretIcon(secret.type)} class="h-4 w-4 text-white" />
                      <span class="text-sm font-medium text-white">
                        {secret.pattern}
                      </span>
                      <Badge variant={getSeverityVariant(secret.severity)} size="sm">
                        {getSeverityLabel(secret.severity)}
                      </Badge>
                    </div>
                    
                    <div class="bg-gray-900/50 rounded p-2 mb-2">
                      <code class="text-xs font-mono text-gray-300">
                        {truncateMatch(secret.match)}
                      </code>
                    </div>
                    
                    <div class="flex items-center space-x-4 text-xs text-gray-400">
                      {#if secret.location}
                        <span>Location: {secret.location}</span>
                      {/if}
                      {#if secret.commit_sha}
                        <span>Commit: {secret.commit_sha}</span>
                      {/if}
                      <span>Severity: {(secret.severity * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                </div>
              </div>
            {/each}
          {/if}
        </div>

        <!-- Secret severity breakdown -->
        {#if secrets.length > 0}
          <div class="mt-4 grid grid-cols-4 gap-2">
            <div class="text-center">
              <div class="text-lg font-bold text-red-400">{criticalSecrets.length}</div>
              <div class="text-xs text-gray-400">Critical</div>
            </div>
            <div class="text-center">
              <div class="text-lg font-bold text-orange-400">{highSecrets.length}</div>
              <div class="text-xs text-gray-400">High</div>
            </div>
            <div class="text-center">
              <div class="text-lg font-bold text-yellow-400">{mediumSecrets.length}</div>
              <div class="text-xs text-gray-400">Medium</div>
            </div>
            <div class="text-center">
              <div class="text-lg font-bold text-green-400">{lowSecrets.length}</div>
              <div class="text-xs text-gray-400">Low</div>
            </div>
          </div>
        {/if}
      </div>

      <!-- File Risk Analysis -->
      <div>
        <h4 class="text-sm font-semibold text-gray-300 mb-3 flex items-center">
          <Icon name="file-warning" class="h-4 w-4 mr-2" />
          File Risk Analysis
        </h4>
        
        <!-- File type risk heatmap -->
        <div class="space-y-2 mb-4">
          {#each fileTypeRisks as fileType}
            <div class="flex items-center justify-between p-2 rounded bg-gray-800/30">
              <span class="text-sm text-gray-300">{fileType.type}</span>
              <div class="flex items-center space-x-2">
                <span class="text-sm font-mono text-white">{fileType.count}</span>
                <div class="w-3 h-3 rounded-full {
                  fileType.risk === 'critical' ? 'bg-red-500' :
                  fileType.risk === 'high' ? 'bg-orange-500' :
                  fileType.risk === 'medium' ? 'bg-yellow-500' : 'bg-green-500'
                }"></div>
              </div>
            </div>
          {/each}
        </div>

        <!-- Suspicious files -->
        {#if fileAnalysis?.suspicious_files?.length > 0}
          <div class="space-y-2 max-h-48 overflow-y-auto">
            <h5 class="text-xs font-semibold text-gray-400 mb-2">Suspicious Files:</h5>
            {#each fileAnalysis.suspicious_files as file}
              <div class="bg-gray-800/50 rounded p-2">
                <div class="flex items-center justify-between mb-1">
                  <span class="text-sm font-mono text-white truncate">{file.filename}</span>
                  <Badge variant={getSeverityVariant(file.risk_score)} size="sm">
                    {(file.risk_score * 100).toFixed(0)}%
                  </Badge>
                </div>
                <div class="flex items-center space-x-2 text-xs">
                  <span class="{getRiskCategoryColor(file.category)}">{file.category}</span>
                  <span class="text-gray-400">•</span>
                  <span class="text-gray-400">{file.reason}</span>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>

    <!-- Content Features -->
    {#if contentData.content_features && contentData.feature_names}
      <div class="mt-6">
        <h4 class="text-sm font-semibold text-gray-300 mb-3 flex items-center">
          <Icon name="bar-chart-3" class="h-4 w-4 mr-2" />
          Content Risk Metrics
        </h4>
        
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {#each contentData.feature_names as featureName, index}
            {@const value = contentData.content_features[index]}
            <div class="bg-gray-800/30 rounded-lg p-3 text-center">
              <div class="text-lg font-bold text-white font-mono">
                {formatFeatureValue(value, featureName)}
              </div>
              <div class="text-xs text-gray-400 mt-1">
                {contentFeatureDescriptions[featureName] || featureName}
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- High Risk Indicators -->
    {#if highRiskIndicators.length > 0}
      <div class="mt-6">
        <h4 class="text-sm font-semibold text-gray-300 mb-3 flex items-center">
          <Icon name="alert-circle" class="h-4 w-4 mr-2" />
          High Risk Indicators
        </h4>
        
        <div class="bg-red-900/20 border border-red-500/30 rounded-lg p-4">
          <ul class="space-y-2">
            {#each highRiskIndicators as indicator}
              <li class="flex items-start space-x-2">
                <Icon name="alert-triangle" class="h-4 w-4 text-red-400 mt-0.5 flex-shrink-0" />
                <span class="text-sm text-red-100">{indicator}</span>
              </li>
            {/each}
          </ul>
        </div>
      </div>
    {/if}

    <!-- Analysis Summary -->
    <div class="mt-6 pt-4 border-t border-gray-700">
      <div class="flex items-center justify-between text-sm">
        <div class="flex items-center space-x-4 text-gray-400">
          <span>Total Files: {fileAnalysis?.total_files_changed || 0}</span>
          <span>Lines Added: {fileAnalysis?.total_lines_added || 0}</span>
          <span>Lines Deleted: {fileAnalysis?.total_lines_deleted || 0}</span>
        </div>
        
        <div class="flex items-center space-x-2">
          <div class="w-2 h-2 rounded-full {contentData.content_risk_score > 0.5 ? 'bg-red-400 animate-pulse' : 'bg-green-400'}"></div>
          <span class="text-xs text-gray-400">
            {contentData.content_risk_score > 0.5 ? 'High Risk Content' : 'Content Analysis Complete'}
          </span>
        </div>
      </div>
    </div>
  {/if}
</Card>