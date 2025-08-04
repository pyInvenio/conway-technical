from typing import Dict, Any, List, Optional, Tuple, Set
import re
import numpy as np
import logging
from collections import defaultdict
import asyncio
import aiohttp
from datetime import datetime

logger = logging.getLogger(__name__)

class ContentAnomalyDetector:
    """Content-based anomaly detection using secret patterns and suspicious file analysis"""
    
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token
        
        # Secret detection patterns with severity weights
        self.secret_patterns = {
            # High severity secrets
            'aws_access_key': {
                'pattern': r'AKIA[0-9A-Z]{16}',
                'severity': 0.9,
                'description': 'AWS Access Key ID'
            },
            'aws_secret_key': {
                'pattern': r'(?i)aws[_\-\s]*secret[_\-\s]*key[_\-\s]*[:=]\s*[\'"]?[A-Za-z0-9/+=]{40}[\'"]?',
                'severity': 0.9,
                'description': 'AWS Secret Access Key'
            },
            'github_token': {
                'pattern': r'ghp_[a-zA-Z0-9]{36}',
                'severity': 0.9,
                'description': 'GitHub Personal Access Token'
            },
            'github_oauth': {
                'pattern': r'gho_[a-zA-Z0-9]{36}',
                'severity': 0.8,
                'description': 'GitHub OAuth Token'
            },
            'github_app_token': {
                'pattern': r'(ghu|ghs)_[a-zA-Z0-9]{36}',
                'severity': 0.8,
                'description': 'GitHub App Token'
            },
            'private_key': {
                'pattern': r'-----BEGIN\s+.*\s+PRIVATE\s+KEY-----',
                'severity': 0.9,
                'description': 'Private Key'
            },
            'jwt_token': {
                'pattern': r'eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*',
                'severity': 0.7,
                'description': 'JWT Token'
            },
            'slack_token': {
                'pattern': r'xox[baprs]-[0-9]{12}-[0-9]{12}-[a-zA-Z0-9]{24}',
                'severity': 0.8,
                'description': 'Slack Token'
            },
            'stripe_key': {
                'pattern': r'sk_live_[a-zA-Z0-9]{24}',
                'severity': 0.9,
                'description': 'Stripe Live Key'
            },
            
            # Medium severity patterns
            'api_key_generic': {
                'pattern': r'(?i)[aA][pP][iI][_\-\s]*[kK][eE][yY][_\-\s]*[:=]\s*[\'"]?[a-zA-Z0-9]{20,}[\'"]?',
                'severity': 0.6,
                'description': 'Generic API Key'
            },
            'password': {
                'pattern': r'(?i)[pP][aA][sS][sS][wW][oO][rR][dD][_\-\s]*[:=]\s*[\'"]?[^\s\'"]{8,}[\'"]?',
                'severity': 0.5,
                'description': 'Password'
            },
            'secret_generic': {
                'pattern': r'(?i)[sS][eE][cC][rR][eE][tT][_\-\s]*[:=]\s*[\'"]?[a-zA-Z0-9]{16,}[\'"]?',
                'severity': 0.6,
                'description': 'Generic Secret'
            },
            'token_generic': {
                'pattern': r'(?i)[tT][oO][kK][eE][nN][_\-\s]*[:=]\s*[\'"]?[a-zA-Z0-9]{20,}[\'"]?',
                'severity': 0.5,
                'description': 'Generic Token'
            },
            
            # Database and connection strings
            'connection_string': {
                'pattern': r'(?i)(mongodb|mysql|postgresql|redis|elastic)://[^\s]+',
                'severity': 0.7,
                'description': 'Database Connection String'
            },
            'database_url': {
                'pattern': r'(?i)database[_\-\s]*url[_\-\s]*[:=]\s*[\'"]?[^\s\'"]+[\'"]?',
                'severity': 0.7,
                'description': 'Database URL'
            }
        }
        
        # Suspicious file patterns with risk scores
        self.suspicious_file_patterns = {
            'credentials': {
                'extensions': ['.env', '.env.local', '.env.production', '.env.staging'],
                'names': ['credentials', 'secrets', 'config.ini', 'application.properties'],
                'risk_score': 0.8,
                'description': 'Credential files'
            },
            'keys': {
                'extensions': ['.pem', '.key', '.p12', '.pfx', '.jks', '.keystore'],
                'names': ['id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519'],
                'risk_score': 0.9,
                'description': 'Cryptographic keys'
            },
            'config': {
                'extensions': ['.yml', '.yaml', '.json', '.xml', '.conf'],
                'names': ['database.yml', 'application.yml', 'secrets.yml', 'config.json'],
                'risk_score': 0.4,  # Lowered since many are just normal configs
                'conditions': ['password', 'secret', 'key', 'token', 'api'],
                'description': 'Configuration files'
            },
            'docker': {
                'names': ['Dockerfile', 'docker-compose.yml', 'docker-compose.yaml', '.dockerignore'],
                'risk_score': 0.3,  # Lowered, mostly legitimate
                'conditions': ['secret', 'password', 'token'],
                'description': 'Docker files'
            },
            'cloud': {
                'extensions': ['.tfvars', '.tf'],
                'names': ['terraform.tfvars', 'ansible-vault', 'kubeconfig', '.aws/credentials'],
                'risk_score': 0.7,
                'description': 'Cloud configuration'
            },
            'backup': {
                'extensions': ['.sql', '.dump', '.backup', '.bak'],
                'names': ['backup.sql', 'dump.sql'],
                'risk_score': 0.5,
                'description': 'Database backups'
            }
        }
        
        # File content analysis thresholds
        self.large_file_threshold = 10000  # bytes
        self.max_diff_size = 50000  # Maximum diff size to analyze
        
        # Feature vector for ML integration
        self.content_feature_names = [
            'secret_pattern_count',
            'high_severity_secret_count', 
            'suspicious_file_count',
            'credential_file_count',
            'key_file_count',
            'large_file_changes',
            'binary_file_changes',
            'deletion_to_addition_ratio',
            'avg_secret_severity'
        ]
    
    async def analyze_content_anomalies(
        self,
        events: List[Dict[str, Any]], 
        context_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze content for security anomalies"""
        
        # Extract content features as numpy array
        content_features = await self._extract_content_features(events, context_data)
        
        # Detect secrets and suspicious patterns
        secret_detections = await self._detect_secrets_in_events(events)
        
        # Analyze file changes for suspicious patterns
        file_analysis = await self._analyze_file_changes(events)
        
        # Calculate content risk score
        content_risk_score = self._calculate_content_risk_score(
            content_features, secret_detections, file_analysis
        )
        
        return {
            'content_risk_score': float(content_risk_score),
            'secret_detections': secret_detections,
            'file_analysis': file_analysis,
            'content_features': content_features.tolist(),
            'feature_names': self.content_feature_names,
            'high_risk_indicators': self._identify_high_risk_indicators(
                secret_detections, file_analysis
            )
        }
    
    async def _extract_content_features(
        self, 
        events: List[Dict[str, Any]], 
        context_data: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """Extract content-based features as numpy array"""
        features = np.zeros(len(self.content_feature_names))
        
        if not events:
            return features
        
        # Analyze all events for content patterns
        total_secret_patterns = 0
        high_severity_secrets = 0
        suspicious_files = 0
        credential_files = 0
        key_files = 0
        large_files = 0
        binary_files = 0
        total_deletions = 0
        total_additions = 0
        secret_severities = []
        
        for event in events:
            event_type = event.get('type')
            
            if event_type == 'PushEvent':
                payload = event.get('payload', {})
                commits = payload.get('commits', [])
                
                for commit in commits:
                    # Analyze commit message for secrets
                    message = commit.get('message', '')
                    commit_secrets = self._scan_text_for_secrets(message)
                    total_secret_patterns += len(commit_secrets)
                    
                    for secret in commit_secrets:
                        severity = self.secret_patterns[secret['type']]['severity']
                        secret_severities.append(severity)
                        if severity >= 0.8:
                            high_severity_secrets += 1
                
                # Analyze modified files (if available in payload)
                if 'size' in payload:  # GitHub webhook includes file count
                    file_count = payload['size']
                    large_files += 1 if file_count > 50 else 0
        
        # Try to get more detailed file information from context
        if context_data and 'files' in context_data:
            files = context_data['files']
            
            for file_info in files:
                filename = file_info.get('filename', '')
                additions = file_info.get('additions', 0)
                deletions = file_info.get('deletions', 0)
                changes = file_info.get('changes', 0)
                
                total_additions += additions
                total_deletions += deletions
                
                # Check file characteristics
                if changes > self.large_file_threshold:
                    large_files += 1
                
                if self._is_binary_file(filename):
                    binary_files += 1
                
                # Check for suspicious file patterns
                file_risk = self._analyze_suspicious_file(filename)
                if file_risk['is_suspicious']:
                    suspicious_files += 1
                    if file_risk['category'] == 'credentials':
                        credential_files += 1
                    elif file_risk['category'] == 'keys':
                        key_files += 1
                
                # Analyze file content patch for secrets
                patch = file_info.get('patch', '')
                if patch and len(patch) < self.max_diff_size:
                    patch_secrets = self._scan_text_for_secrets(patch)
                    total_secret_patterns += len(patch_secrets)
                    
                    for secret in patch_secrets:
                        severity = self.secret_patterns[secret['type']]['severity']
                        secret_severities.append(severity)
                        if severity >= 0.8:
                            high_severity_secrets += 1
        
        # Populate feature vector
        features[0] = total_secret_patterns
        features[1] = high_severity_secrets
        features[2] = suspicious_files
        features[3] = credential_files
        features[4] = key_files
        features[5] = large_files
        features[6] = binary_files
        
        # Deletion to addition ratio (indicates potential data removal)
        if total_additions > 0:
            features[7] = total_deletions / total_additions
        else:
            features[7] = 1.0 if total_deletions > 0 else 0.0
        
        # Average secret severity
        if secret_severities:
            features[8] = np.mean(secret_severities)
        
        return features
    
    def _scan_text_for_secrets(self, text: str) -> List[Dict[str, Any]]:
        """Scan text for secret patterns"""
        detected_secrets = []
        
        for secret_type, pattern_info in self.secret_patterns.items():
            pattern = pattern_info['pattern']
            matches = re.finditer(pattern, text)
            
            for match in matches:
                detected_secrets.append({
                    'type': secret_type,
                    'pattern': pattern_info['description'],
                    'severity': pattern_info['severity'],
                    'match': match.group()[:20] + '...' if len(match.group()) > 20 else match.group(),
                    'position': match.span()
                })
        
        return detected_secrets
    
    def _analyze_suspicious_file(self, filename: str) -> Dict[str, Any]:
        """Analyze if a file is suspicious based on patterns"""
        filename_lower = filename.lower()
        basename = filename_lower.split('/')[-1]  # Get just the filename
        
        for category, config in self.suspicious_file_patterns.items():
            # Check extensions
            if 'extensions' in config:
                for ext in config['extensions']:
                    if filename_lower.endswith(ext.lower()):
                        return {
                            'is_suspicious': True,
                            'category': category,
                            'risk_score': config['risk_score'],
                            'reason': f'Matches suspicious extension: {ext}',
                            'description': config['description']
                        }
            
            # Check exact filenames
            if 'names' in config:
                for name in config['names']:
                    if basename == name.lower() or filename_lower.endswith('/' + name.lower()):
                        return {
                            'is_suspicious': True,
                            'category': category,
                            'risk_score': config['risk_score'],
                            'reason': f'Matches suspicious filename: {name}',
                            'description': config['description']
                        }
            
            # Check conditional patterns (filename contains certain keywords)
            if 'conditions' in config:
                for condition in config['conditions']:
                    if condition.lower() in filename_lower:
                        return {
                            'is_suspicious': True,
                            'category': category,
                            'risk_score': config['risk_score'],
                            'reason': f'Contains suspicious keyword: {condition}',
                            'description': config['description']
                        }
        
        return {'is_suspicious': False}
    
    def _is_binary_file(self, filename: str) -> bool:
        """Check if file is likely binary"""
        binary_extensions = {
            '.exe', '.bin', '.dll', '.so', '.dylib', '.jar', '.war', '.ear',
            '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',
            '.mp3', '.mp4', '.avi', '.mkv', '.pdf', '.doc', '.docx',
            '.xls', '.xlsx', '.ppt', '.pptx'
        }
        
        filename_lower = filename.lower()
        return any(filename_lower.endswith(ext) for ext in binary_extensions)
    
    async def _detect_secrets_in_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect secrets across all events"""
        all_secrets = []
        
        for event in events:
            event_secrets = []
            event_type = event.get('type')
            
            if event_type == 'PushEvent':
                payload = event.get('payload', {})
                commits = payload.get('commits', [])
                
                for commit in commits:
                    # Scan commit message
                    message = commit.get('message', '')
                    commit_secrets = self._scan_text_for_secrets(message)
                    
                    for secret in commit_secrets:
                        secret['location'] = 'commit_message'
                        secret['commit_sha'] = commit.get('sha', '')[:8]
                        secret['commit_url'] = commit.get('url', '')
                        event_secrets.append(secret)
            
            # Add event context to secrets
            for secret in event_secrets:
                secret['event_id'] = event.get('id')
                secret['repository'] = event.get('repo_name')
                secret['actor'] = event.get('actor_login')
                secret['timestamp'] = event.get('created_at')
                
            all_secrets.extend(event_secrets)
        
        return all_secrets
    
    async def _analyze_file_changes(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze file changes for suspicious patterns"""
        analysis = {
            'suspicious_files': [],
            'large_changes': [],
            'binary_changes': [],
            'mass_deletions': [],
            'credential_modifications': [],
            'total_files_changed': 0,
            'total_lines_added': 0,
            'total_lines_deleted': 0
        }
        
        for event in events:
            if event.get('type') == 'PushEvent':
                payload = event.get('payload', {})
                
                # Basic stats from payload
                size = payload.get('size', 0)
                analysis['total_files_changed'] += size
                
                commits = payload.get('commits', [])
                for commit in commits:
                    commit_sha = commit.get('sha', '')[:8]
                    
                    # If we have detailed file information, use it
                    # (This would come from GitHub's API if we fetch commit details)
                    if self.github_token:
                        # Could fetch detailed commit info here
                        pass
        
        return analysis
    
    def _calculate_content_risk_score(
        self,
        content_features: np.ndarray,
        secret_detections: List[Dict[str, Any]],
        file_analysis: Dict[str, Any]
    ) -> float:
        """Calculate overall content risk score with improved weighting"""
        
        # Largely just heuristical at this point
        feature_weights = np.array([
            0.25,  # secret_pattern_count
            0.35,  # high_severity_secret_count  
            0.08,  # suspicious_file_count
            0.18,  # credential_file_count
            0.25,  # key_file_count
            0.20,  # large_file_changes
            0.05,  # binary_file_changes
            0.12,  # deletion_to_addition_ratio
            0.30   # avg_secret_severity
        ])
        
        normalized_features = 1 / (1 + np.exp(-content_features * 0.5))  # Sigmoid with scaling
        
        # Calculate weighted score
        base_score = np.dot(normalized_features, feature_weights)
        
        # Boost score based on high-severity secrets
        severity_boost = 0.0
        if secret_detections:
            max_severity = max(s['severity'] for s in secret_detections)
            severity_boost = max_severity * 0.3
        
        # Boost for multiple different secret types (indicates systematic compromise)
        unique_secret_types = len(set(s['type'] for s in secret_detections))
        diversity_boost = min(unique_secret_types * 0.1, 0.3)
        
        # Final score
        final_score = min(base_score + severity_boost + diversity_boost, 1.0)
        
        return final_score
    
    def _identify_high_risk_indicators(
        self,
        secret_detections: List[Dict[str, Any]],
        file_analysis: Dict[str, Any]
    ) -> List[str]:
        """Identify high-risk indicators for explanation"""
        indicators = []
        
        # Secret-based indicators
        high_severity_secrets = [s for s in secret_detections if s['severity'] >= 0.8]
        if high_severity_secrets:
            indicators.append(f"{len(high_severity_secrets)} high-severity secrets detected")
        
        if len(secret_detections) >= 5:
            indicators.append("Multiple secret patterns in single event")
        
        unique_types = set(s['type'] for s in secret_detections)
        if len(unique_types) >= 3:
            indicators.append("Diverse secret types suggest compromised system")
        
        # File-based indicators
        if file_analysis.get('credential_modifications'):
            indicators.append("Credential files modified")
        
        if file_analysis.get('mass_deletions'):
            indicators.append("Mass file deletions detected")
        
        if file_analysis.get('total_lines_deleted', 0) > file_analysis.get('total_lines_added', 0) * 2:
            indicators.append("Significant code deletion (potential cleanup)")
        
        return indicators
    
    async def fetch_commit_details(self, repo_name: str, commit_sha: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed commit information from GitHub API"""
        if not self.github_token:
            return None
        
        url = f"https://api.github.com/repos/{repo_name}/commits/{commit_sha}"
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.warning(f"Failed to fetch commit {commit_sha}: {response.status}")
        except Exception as e:
            logger.error(f"Error fetching commit details: {e}")
        
        return None
    
    def get_content_features_for_ml(self, events: List[Dict[str, Any]]) -> np.ndarray:
        """Get content feature vector for ML models"""
        return asyncio.run(self._extract_content_features(events))
    
    def get_secret_patterns(self) -> Dict[str, Any]:
        """Get secret patterns for external use"""
        return self.secret_patterns
    
    def get_suspicious_file_patterns(self) -> Dict[str, Any]:
        """Get suspicious file patterns for external use"""
        return self.suspicious_file_patterns