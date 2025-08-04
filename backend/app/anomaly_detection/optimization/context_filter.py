from typing import Dict, Any, List, Optional, Set
import json
import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SmartContextFilter:
    """Advanced context filtering and compression for efficient token usage"""
    
    def __init__(self):
        # Incident-specific field priorities (higher number = more important)
        self.field_priorities = {
            'force_push': {
                'ref': 10,              # Branch name crucial
                'forced': 10,           # Force push indicator
                'commits': 9,           # Commit details
                'actor_login': 8,       # Who did it
                'before': 7,            # Previous commit
                'repository_info': 6,   # Repo context
                'timestamp': 5
            },
            'workflow_failure': {
                'workflow_run': 10,     # Workflow details
                'conclusion': 10,       # Failure type
                'head_commit': 9,       # What triggered it
                'actor_login': 8,       # Who triggered
                'repository_info': 7,   # Repo context
                'pull_requests': 6,     # Related PRs
                'timestamp': 5
            },
            'secret_exposure': {
                'commits': 10,          # Commit content crucial
                'files_changed': 10,    # Which files
                'diff_content': 9,      # Actual changes
                'actor_login': 8,       # Who committed
                'ref': 7,               # Which branch
                'repository_info': 6,   # Repo visibility
                'timestamp': 5
            },
            'mass_deletion': {
                'ref_type': 10,         # What was deleted
                'ref': 10,              # Reference name
                'actor_login': 9,       # Who deleted
                'pusher_type': 8,       # User vs system
                'repository_info': 7,   # Repo context
                'timestamp': 6
            },
            'bursty_activity': {
                'event_types': 10,      # Types of events
                'actor_distribution': 9, # Actor patterns
                'time_distribution': 9,  # Time patterns
                'events_per_minute': 8, # Rate metrics
                'unique_actors': 7,     # Actor count
                'repository_info': 6,   # Repo context
                'timestamp': 5
            }
        }
        
        # Secret detection patterns for content analysis
        self.secret_patterns = {
            'aws_access_key': r'AKIA[0-9A-Z]{16}',
            'github_token': r'ghp_[a-zA-Z0-9]{36}',
            'github_oauth': r'gho_[a-zA-Z0-9]{36}',
            'github_app_token': r'(ghu|ghs)_[a-zA-Z0-9]{36}',
            'private_key': r'-----BEGIN\s+.*\s+PRIVATE\s+KEY-----',
            'api_key': r'[aA][pP][iI][_\-\s]*[kK][eE][yY][_\-\s]*[:=]\s*[\'"]?[a-zA-Z0-9]{20,}',
            'password': r'[pP][aA][sS][sS][wW][oO][rR][dD][_\-\s]*[:=]\s*[\'"]?[^\s\'"]{8,}',
            'secret': r'[sS][eE][cC][rR][eE][tT][_\-\s]*[:=]\s*[\'"]?[a-zA-Z0-9]{16,}',
            'token': r'[tT][oO][kK][eE][nN][_\-\s]*[:=]\s*[\'"]?[a-zA-Z0-9]{20,}',
            'slack_token': r'xox[baprs]-[0-9]{12}-[0-9]{12}-[a-zA-Z0-9]{24}',
            'stripe_key': r'sk_live_[a-zA-Z0-9]{24}',
            'jwt_token': r'eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*'
        }
        
        # Suspicious file patterns
        self.suspicious_files = {
            'credentials': ['.env', '.env.local', '.env.production', 'credentials', 'config.json'],
            'keys': ['id_rsa', 'id_dsa', '*.pem', '*.key', '*.p12', '*.pfx'],
            'config': ['database.yml', 'application.yml', 'secrets.yml', 'config.ini'],
            'docker': ['Dockerfile', 'docker-compose.yml', '.dockerignore'],
            'cloud': ['terraform.tfvars', 'ansible-vault', 'kubeconfig']
        }
    
    def filter_and_compress(
        self, 
        context_data: Dict[str, Any], 
        incident_type: str, 
        compression_level: str = 'medium'
    ) -> Dict[str, Any]:
        """
        Filter and compress context data based on incident type and compression level
        
        compression_level: 'low' (keep most), 'medium' (balanced), 'high' (minimal)
        """
        
        if compression_level == 'low':
            return self._light_compression(context_data, incident_type)
        elif compression_level == 'medium':
            return self._medium_compression(context_data, incident_type)
        else:  # high compression
            return self._aggressive_compression(context_data, incident_type)
    
    def _light_compression(self, context_data: Dict[str, Any], incident_type: str) -> Dict[str, Any]:
        """Light compression - remove only clearly irrelevant data"""
        compressed = context_data.copy()
        
        # Remove fields that are never useful for any incident type
        irrelevant_fields = ['raw_response', 'full_payload', '_links', 'node_id']
        for field in irrelevant_fields:
            compressed.pop(field, None)
        
        # Truncate very long arrays
        for key, value in compressed.items():
            if isinstance(value, list) and len(value) > 10:
                compressed[key] = value[:10]  # Keep first 10 items
            elif isinstance(value, str) and len(value) > 2000:
                compressed[key] = value[:2000] + "... [truncated]"
        
        return compressed
    
    def _medium_compression(self, context_data: Dict[str, Any], incident_type: str) -> Dict[str, Any]:
        """Medium compression - keep fields based on incident type priorities"""
        priorities = self.field_priorities.get(incident_type, {})
        compressed = {}
        
        # Sort fields by priority and keep top ones
        for field, data in context_data.items():
            priority = priorities.get(field, 3)  # Default priority
            
            if priority >= 6:  # High priority fields
                compressed[field] = self._compress_field_value(data, 'light')
            elif priority >= 4:  # Medium priority fields  
                compressed[field] = self._compress_field_value(data, 'medium')
            # Skip low priority fields (< 4)
        
        # Always include basic incident info
        essential_fields = ['actor_login', 'repository_info', 'timestamp']
        for field in essential_fields:
            if field in context_data and field not in compressed:
                compressed[field] = context_data[field]
        
        return compressed
    
    def _aggressive_compression(self, context_data: Dict[str, Any], incident_type: str) -> Dict[str, Any]:
        """Aggressive compression - keep only the most critical fields"""
        priorities = self.field_priorities.get(incident_type, {})
        compressed = {}
        
        # Only keep highest priority fields
        for field, data in context_data.items():
            priority = priorities.get(field, 0)
            
            if priority >= 8:  # Only very high priority
                compressed[field] = self._compress_field_value(data, 'aggressive')
        
        # Ensure minimal context exists
        if 'actor_login' in context_data:
            compressed['actor'] = context_data['actor_login']
        if 'repository_info' in context_data:
            repo = context_data['repository_info']
            compressed['repo'] = {
                'name': repo.get('name'),
                'visibility': repo.get('visibility'),
                'default_branch': repo.get('default_branch')
            }
        
        return compressed
    
    def _compress_field_value(self, value: Any, level: str) -> Any:
        """Compress individual field values based on compression level"""
        
        if isinstance(value, dict):
            if level == 'aggressive':
                # Keep only 2-3 most important keys
                important_keys = ['name', 'message', 'sha', 'ref', 'conclusion', 'status']
                return {k: v for k, v in value.items() if k in important_keys}[:3]
            elif level == 'medium':
                # Keep important keys, truncate long values
                result = {}
                for k, v in value.items():
                    if k.startswith('_') or k in ['raw', 'full_', 'complete_']:
                        continue  # Skip internal/verbose fields
                    if isinstance(v, str) and len(v) > 200:
                        result[k] = v[:200] + "..."
                    elif isinstance(v, list) and len(v) > 5:
                        result[k] = v[:5]
                    else:
                        result[k] = v
                return result
            else:  # light
                return {k: v for k, v in value.items() if not k.startswith('_')}
        
        elif isinstance(value, list):
            max_items = {'aggressive': 2, 'medium': 5, 'light': 10}[level]
            return value[:max_items]
        
        elif isinstance(value, str):
            max_length = {'aggressive': 100, 'medium': 300, 'light': 1000}[level]
            if len(value) > max_length:
                return value[:max_length] + "..."
            return value
        
        return value
    
    def analyze_content_risk(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze context for content-based security risks"""
        risks = {
            'secrets_detected': [],
            'suspicious_files': [],
            'risk_score': 0.0,
            'high_risk_indicators': []
        }
        
        # Analyze commits for secrets
        commits = context_data.get('commits', [])
        for commit in commits[:5]:  # Check first 5 commits
            message = commit.get('message', '')
            
            # Check commit message for secrets
            for secret_type, pattern in self.secret_patterns.items():
                if re.search(pattern, message, re.IGNORECASE):
                    risks['secrets_detected'].append({
                        'type': secret_type,
                        'location': 'commit_message',
                        'commit_sha': commit.get('sha', '')[:8]
                    })
                    risks['risk_score'] += 0.3
        
        # Analyze file changes
        if 'files' in context_data:
            files = context_data['files']
            for file_info in files:
                filename = file_info.get('filename', '')
                
                # Check for suspicious files
                for category, patterns in self.suspicious_files.items():
                    for pattern in patterns:
                        if self._matches_pattern(filename, pattern):
                            risks['suspicious_files'].append({
                                'file': filename,
                                'category': category,
                                'changes': file_info.get('changes', 0)
                            })
                            risks['risk_score'] += 0.2
                
                # Check file content for secrets (if available)
                patch = file_info.get('patch', '')
                if patch:
                    for secret_type, pattern in self.secret_patterns.items():
                        if re.search(pattern, patch, re.IGNORECASE):
                            risks['secrets_detected'].append({
                                'type': secret_type,
                                'location': 'file_content',
                                'file': filename
                            })
                            risks['risk_score'] += 0.4
        
        # High-risk indicators
        if risks['risk_score'] > 0.5:
            risks['high_risk_indicators'].append('Multiple secret patterns detected')
        
        if len(risks['suspicious_files']) > 3:
            risks['high_risk_indicators'].append('Numerous sensitive files modified')
        
        # Check for environment/config changes
        env_files = [f for f in risks['suspicious_files'] if 'credentials' in f.get('category', '')]
        if env_files:
            risks['high_risk_indicators'].append('Environment/credential files modified')
        
        # Normalize risk score
        risks['risk_score'] = min(risks['risk_score'], 1.0)
        
        return risks
    
    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Check if filename matches pattern (supports wildcards)"""
        import fnmatch
        return fnmatch.fnmatch(filename.lower(), pattern.lower())
    
    def extract_behavioral_features(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract features for behavioral analysis"""
        features = {
            'actor_count': 0,
            'unique_repos': set(),
            'event_types': [],
            'time_patterns': {},
            'interaction_patterns': {}
        }
        
        # Extract actor information
        actors = context_data.get('unique_actors', [])
        features['actor_count'] = len(actors)
        
        # Extract event types
        events = context_data.get('events', [])
        for event in events:
            event_type = event.get('type', 'unknown')
            features['event_types'].append(event_type)
            
            # Track repository interactions
            repo_name = event.get('repo_name', 'unknown')
            features['unique_repos'].add(repo_name)
            
            # Time pattern analysis
            timestamp = event.get('created_at')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    hour = dt.hour
                    features['time_patterns'][hour] = features['time_patterns'].get(hour, 0) + 1
                except (ValueError, AttributeError):
                    pass
        
        # Convert sets to lists for JSON serialization
        features['unique_repos'] = list(features['unique_repos'])
        features['repo_count'] = len(features['unique_repos'])
        
        # Calculate event type distribution
        from collections import Counter
        type_counts = Counter(features['event_types'])
        features['event_type_distribution'] = dict(type_counts.most_common(10))
        
        return features
    
    def get_compression_stats(self, original: Dict[str, Any], compressed: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate compression statistics"""
        original_size = len(json.dumps(original, default=str))
        compressed_size = len(json.dumps(compressed, default=str))
        
        compression_ratio = (original_size - compressed_size) / original_size if original_size > 0 else 0
        
        return {
            'original_size_bytes': original_size,
            'compressed_size_bytes': compressed_size,
            'compression_ratio': compression_ratio,
            'space_saved_bytes': original_size - compressed_size,
            'fields_removed': len(original) - len(compressed),
            'estimated_token_savings': int((original_size - compressed_size) / 4)  # Rough estimate
        }