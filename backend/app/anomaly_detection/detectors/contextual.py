from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import logging
import aiohttp
import json
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)

class RepositoryContextScorer:
    """Repository context scoring for criticality assessment and severity multipliers"""
    
    def __init__(self, redis_client=None, github_token: Optional[str] = None):
        self.redis_client = redis_client
        self.github_token = github_token
        
        # Cache configuration
        self.repo_cache_ttl = 7200  # 2 hours for repository data
        self.contributor_cache_ttl = 3600  # 1 hour for contributor data
        
        # Repository context feature names for ML integration
        self.context_feature_names = [
            'repository_criticality_score',
            'stars_normalized',
            'forks_normalized', 
            'contributors_count_normalized',
            'recent_activity_score',
            'security_policy_score',
            'protected_branches_score',
            'dependency_risk_score',
            'popularity_momentum_score'
        ]
        
        # Scoring weights for different repository factors
        self.criticality_weights = {
            'stars': 0.25,
            'forks': 0.20,
            'contributors': 0.15,
            'activity': 0.15,
            'security_features': 0.10,
            'age': 0.05,
            'language': 0.05,
            'dependencies': 0.05
        }
        
        # High-value indicators
        self.high_value_indicators = {
            'languages': ['python', 'javascript', 'typescript', 'java', 'go', 'rust', 'c++'],
            'topics': ['security', 'crypto', 'blockchain', 'api', 'framework', 'library'],
            'names': ['production', 'prod', 'api', 'core', 'main', 'master', 'infra'],
            'organizations': ['microsoft', 'google', 'facebook', 'amazon', 'apple', 'netflix']
        }
        
        # Security feature weights
        self.security_feature_weights = {
            'has_security_policy': 0.3,
            'has_vulnerability_alerts': 0.2,
            'branch_protection_enabled': 0.3,
            'has_dependency_scanning': 0.2
        }
    
    async def analyze_repository_context(
        self,
        repo_name: str,
        events: List[Dict[str, Any]],
        context_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze repository context for criticality scoring"""
        
        # Get repository information from GitHub API
        repo_info = await self._get_repository_info(repo_name)
        
        if not repo_info:
            return {
                'repository_criticality_score': 0.5,  # Default medium criticality
                'context_features': np.zeros(len(self.context_feature_names)).tolist(),
                'analysis_type': 'fallback_scoring',
                'error': 'Could not fetch repository information'
            }
        
        # Extract context features
        context_features = await self._extract_context_features(repo_info, events)
        
        # Calculate overall criticality score
        criticality_score = self._calculate_criticality_score(repo_info, context_features)
        
        # Analyze contributor patterns
        contributor_analysis = await self._analyze_contributors(repo_name, repo_info)
        
        # Generate context insights
        context_insights = self._generate_context_insights(repo_info, contributor_analysis)
        
        return {
            'repository_criticality_score': float(criticality_score),
            'context_features': context_features.tolist(),
            'feature_names': self.context_feature_names,
            'repository_info': {
                'name': repo_info.get('name'),
                'full_name': repo_info.get('full_name'),
                'private': repo_info.get('private', False),
                'visibility': repo_info.get('visibility', 'public'),
                'stars': repo_info.get('stargazers_count', 0),
                'forks': repo_info.get('forks_count', 0),
                'language': repo_info.get('language'),
                'created_at': repo_info.get('created_at'),
                'updated_at': repo_info.get('updated_at')
            },
            'contributor_analysis': contributor_analysis,
            'context_insights': context_insights,
            'analysis_type': 'full_context_analysis'
        }
    
    async def _get_repository_info(self, repo_name: str) -> Optional[Dict[str, Any]]:
        """Get repository information from GitHub API with caching"""
        
        # Check cache first
        cached_info = await self._get_cached_repo_info(repo_name)
        if cached_info:
            return cached_info
        
        # Fetch from GitHub API
        if not self.github_token:
            logger.warning(f"No GitHub token provided, cannot fetch repo info for {repo_name}")
            return None
        
        url = f"https://api.github.com/repos/{repo_name}"
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Anomaly-Detector'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        repo_info = await response.json()
                        
                        # Also fetch additional security info
                        security_info = await self._get_repository_security_info(repo_name, session, headers)
                        if security_info:
                            repo_info.update(security_info)
                        
                        # Cache the result
                        await self._cache_repo_info(repo_name, repo_info)
                        return repo_info
                    
                    elif response.status == 404:
                        logger.info(f"Repository {repo_name} not found")
                    elif response.status == 403:
                        logger.warning(f"Rate limited or access denied for repo {repo_name}")
                    else:
                        logger.warning(f"Failed to fetch repo info for {repo_name}: {response.status}")
        
        except Exception as e:
            logger.error(f"Error fetching repository info for {repo_name}: {e}")
        
        return None
    
    async def _get_repository_security_info(
        self, 
        repo_name: str, 
        session: aiohttp.ClientSession, 
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """Fetch additional security-related repository information"""
        security_info = {}
        
        try:
            # Check for security policy
            security_url = f"https://api.github.com/repos/{repo_name}/community/profile"
            async with session.get(security_url, headers=headers) as response:
                if response.status == 200:
                    community_data = await response.json()
                    security_info['has_security_policy'] = bool(community_data.get('files', {}).get('security'))
                    security_info['has_code_of_conduct'] = bool(community_data.get('files', {}).get('code_of_conduct'))
                    security_info['has_contributing'] = bool(community_data.get('files', {}).get('contributing'))
            
            # Check for vulnerability alerts (this requires special permissions)
            # We'll skip this as it requires admin access to the repository
            security_info['has_vulnerability_alerts'] = False  # Default assumption
            
            # Check branch protection (for default branch)
            # This also requires push access, so we'll estimate based on other factors
            security_info['branch_protection_enabled'] = False  # Default assumption
            
        except Exception as e:
            logger.debug(f"Could not fetch security info for {repo_name}: {e}")
        
        return security_info
    
    async def _extract_context_features(
        self, 
        repo_info: Dict[str, Any], 
        events: List[Dict[str, Any]]
    ) -> np.ndarray:
        """Extract repository context features as numpy array"""
        features = np.zeros(len(self.context_feature_names))
        
        # Extract basic repository metrics
        stars = repo_info.get('stargazers_count', 0)
        forks = repo_info.get('forks_count', 0)
        size = repo_info.get('size', 0)  # Repository size in KB
        
        # Feature 0: Overall repository criticality score
        
        # Feature 1: Stars normalized (using log scale for better distribution)
        features[1] = min(np.log10(stars + 1) / 6, 1.0)
        
        # Feature 2: Forks normalized 
        features[2] = min(np.log10(forks + 1) / 5, 1.0)
        
        # Feature 3: Contributors count normalized (estimated from forks ratio)
        # GitHub API doesn't provide contributor count without additional calls, chose to estimate for faster calls
        estimated_contributors = min(forks * 0.1 + stars * 0.01, 1000)
        features[3] = min(np.log10(estimated_contributors + 1) / 3, 1.0)
        
        # Feature 4: Recent activity score
        features[4] = self._calculate_recent_activity_score(repo_info, events)
        
        # Feature 5: Security policy score
        features[5] = self._calculate_security_policy_score(repo_info)
        
        # Feature 6: Protected branches score (estimated)
        features[6] = self._estimate_branch_protection_score(repo_info)
        
        # Feature 7: Dependency risk score (based on language and size)
        features[7] = self._calculate_dependency_risk_score(repo_info)
        
        # Feature 8: Popularity momentum score
        features[8] = self._calculate_popularity_momentum_score(repo_info)
        
        return features
    
    def _calculate_recent_activity_score(
        self, 
        repo_info: Dict[str, Any], 
        events: List[Dict[str, Any]]
    ) -> float:
        """Calculate recent activity score"""
        
        # Time since last update
        updated_at = repo_info.get('updated_at')
        if updated_at:
            try:
                last_update = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                days_since_update = (datetime.utcnow().replace(tzinfo=last_update.tzinfo) - last_update).days
                
                # Score based on recency (higher = more recent)
                if days_since_update <= 1:
                    time_score = 1.0
                elif days_since_update <= 7:
                    time_score = 0.8
                elif days_since_update <= 30:
                    time_score = 0.6
                elif days_since_update <= 90:
                    time_score = 0.4
                else:
                    time_score = 0.2
            except (ValueError, AttributeError):
                time_score = 0.5
        else:
            time_score = 0.5
        
        # Boost score if we have recent events
        event_boost = min(len(events) / 10, 0.3)  # Max 0.3 boost for 10+ events
        
        return min(time_score + event_boost, 1.0)
    
    def _calculate_security_policy_score(self, repo_info: Dict[str, Any]) -> float:
        """Calculate security policy score"""
        score = 0.0
        
        # Security policy
        if repo_info.get('has_security_policy'):
            score += self.security_feature_weights['has_security_policy']
        
        # Vulnerability alerts
        if repo_info.get('has_vulnerability_alerts'):
            score += self.security_feature_weights['has_vulnerability_alerts']
        
        # Branch protection
        if repo_info.get('branch_protection_enabled'):
            score += self.security_feature_weights['branch_protection_enabled']
        
        # Dependency scanning (estimated based on language)
        language = repo_info.get('language', '').lower()
        if language in ['javascript', 'python', 'java', 'ruby', 'go']:
            score += 0.1  # Assume common languages have dependency scanning
        
        return min(score, 1.0)
    
    def _estimate_branch_protection_score(self, repo_info: Dict[str, Any]) -> float:
        """Estimate branch protection score based on repository characteristics"""
        score = 0.0
        
        # Larger, more popular repos are more likely to have branch protection
        stars = repo_info.get('stargazers_count', 0)
        forks = repo_info.get('forks_count', 0)
        
        if stars > 100 or forks > 20:
            score += 0.3
        if stars > 1000 or forks > 100:
            score += 0.3
        if stars > 10000 or forks > 1000:
            score += 0.4
        
        # Organization repos are more likely to have protection
        owner = repo_info.get('owner', {})
        if owner.get('type') == 'Organization':
            score += 0.2
        
        return min(score, 1.0)
    
    def _calculate_dependency_risk_score(self, repo_info: Dict[str, Any]) -> float:
        """Calculate dependency risk score based on language and complexity"""
        size = repo_info.get('size', 0)
        
        # Size-based risk (larger projects tend to have more dependencies)
        if size > 100000: 
            size_risk = 0.8
        elif size > 10000: 
            size_risk = 0.6
        elif size > 1000: 
            size_risk = 0.4
        else:
            size_risk = 0.2
        
        # Combined risk
        return min(size_risk, 1.0)
    
    def _calculate_popularity_momentum_score(self, repo_info: Dict[str, Any]) -> float:
        """Calculate popularity momentum score"""
        
        # Age of repository
        created_at = repo_info.get('created_at')
        if created_at:
            try:
                created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                age_days = (datetime.utcnow().replace(tzinfo=created_date.tzinfo) - created_date).days
                age_years = age_days / 365.25
            except (ValueError, AttributeError):
                age_years = 1.0  # Default
        else:
            age_years = 1.0
        
        # Stars and forks
        stars = repo_info.get('stargazers_count', 0)
        forks = repo_info.get('forks_count', 0)
        
        # Calculate momentum (popularity per year)
        if age_years > 0:
            stars_per_year = stars / age_years
            forks_per_year = forks / age_years
            
            # Normalize momentum score
            momentum = min((stars_per_year / 1000) + (forks_per_year / 100), 1.0)
        else:
            momentum = 0.0
        
        return momentum
    
    def _calculate_criticality_score(
        self, 
        repo_info: Dict[str, Any], 
        context_features: np.ndarray
    ) -> float:
        """Calculate overall repository criticality score"""
        
        # Base score from features (excluding the first feature which is the overall score)
        feature_weights = np.array([
            0.0,   # repository_criticality_score (not used in calculation)
            0.25,  # stars_normalized
            0.20,  # forks_normalized
            0.15,  # contributors_count_normalized
            0.15,  # recent_activity_score
            0.10,  # security_policy_score
            0.05,  # protected_branches_score
            0.05,  # dependency_risk_score
            0.05   # popularity_momentum_score
        ])
        
        base_score = np.dot(context_features, feature_weights)
        
        # Additional qualitative factors
        qualitative_boost = 0.0
        
        # High-value language boost
        language = repo_info.get('language', '').lower()
        if language in self.high_value_indicators['languages']:
            qualitative_boost += 0.1
        
        # High-value topics boost
        topics = repo_info.get('topics', [])
        for topic in topics:
            if topic.lower() in self.high_value_indicators['topics']:
                qualitative_boost += 0.05
                break
        
        # Organization vs personal repo
        owner = repo_info.get('owner', {})
        if owner.get('type') == 'Organization':
            qualitative_boost += 0.1
        
        # Well-known organization boost
        owner_login = owner.get('login', '').lower()
        if owner_login in self.high_value_indicators['organizations']:
            qualitative_boost += 0.2
        
        # Repository name indicators
        repo_name = repo_info.get('name', '').lower()
        for indicator in self.high_value_indicators['names']:
            if indicator in repo_name:
                qualitative_boost += 0.05
                break
        
        # Final criticality score
        final_score = min(base_score + qualitative_boost, 1.0)
        
        # Update the first feature with the calculated criticality score
        context_features[0] = final_score
        
        return final_score
    
    async def _analyze_contributors(
        self, 
        repo_name: str, 
        repo_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze repository contributors"""
        
        # Check cache first
        cached_analysis = await self._get_cached_contributor_analysis(repo_name)
        if cached_analysis:
            return cached_analysis
        
        # For now, we'll do a basic analysis without additional API calls
        # In a full implementation, you might fetch contributors list
        analysis = {
            'estimated_contributor_count': max(
                repo_info.get('forks_count', 0) // 10,  # Rough estimate
                1
            ),
            'is_organization_owned': repo_info.get('owner', {}).get('type') == 'Organization',
            'owner_login': repo_info.get('owner', {}).get('login'),
            'contributor_diversity_score': 0.5,  # Default medium diversity
            'analysis_type': 'estimated'
        }
        
        # Cache the analysis
        await self._cache_contributor_analysis(repo_name, analysis)
        
        return analysis
    
    def _generate_context_insights(
        self, 
        repo_info: Dict[str, Any], 
        contributor_analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate human-readable context insights"""
        insights = []
        
        stars = repo_info.get('stargazers_count', 0)
        forks = repo_info.get('forks_count', 0)
        language = repo_info.get('language')
        owner_type = repo_info.get('owner', {}).get('type')
        
        # Popularity insights
        if stars > 10000:
            insights.append(f"Highly popular repository with {stars:,} stars")
        elif stars > 1000:
            insights.append(f"Popular repository with {stars:,} stars")
        elif stars > 100:
            insights.append(f"Moderately popular repository with {stars} stars")
        
        # Activity insights
        if forks > 1000:
            insights.append(f"Heavily forked project ({forks:,} forks) indicating active community")
        elif forks > 100:
            insights.append(f"Well-forked project ({forks} forks) with good community engagement")
        
        # Language insights
        if language:
            insights.append(f"Primary language: {language}")
            if language.lower() in ['javascript', 'python', 'java']:
                insights.append("Uses language with complex dependency ecosystem")
        
        # Ownership insights
        if owner_type == 'Organization':
            insights.append("Organization-owned repository (typically higher security standards)")
        
        # Security insights
        if repo_info.get('has_security_policy'):
            insights.append("Has established security policy")
        
        if repo_info.get('private'):
            insights.append("Private repository (higher security sensitivity)")
        
        return insights
    
    async def _get_cached_repo_info(self, repo_name: str) -> Optional[Dict[str, Any]]:
        """Get cached repository information"""
        if not self.redis_client:
            return None
        
        try:
            safe_repo_name = repo_name.replace('/', ':')
            cache_key = f"repo_context_info:{safe_repo_name}"
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Failed to get cached repo info for {repo_name}: {e}")
        
        return None
    
    async def _cache_repo_info(self, repo_name: str, repo_info: Dict[str, Any]):
        """Cache repository information"""
        if not self.redis_client:
            return
        
        try:
            safe_repo_name = repo_name.replace('/', ':')
            cache_key = f"repo_context_info:{safe_repo_name}"
            await self.redis_client.setex(
                cache_key,
                self.repo_cache_ttl,
                json.dumps(repo_info, default=str)
            )
        except Exception as e:
            logger.warning(f"Failed to cache repo info for {repo_name}: {e}")
    
    async def _get_cached_contributor_analysis(self, repo_name: str) -> Optional[Dict[str, Any]]:
        """Get cached contributor analysis"""
        if not self.redis_client:
            return None
        
        try:
            safe_repo_name = repo_name.replace('/', ':')
            cache_key = f"repo_contributors:{safe_repo_name}"
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Failed to get cached contributor analysis for {repo_name}: {e}")
        
        return None
    
    async def _cache_contributor_analysis(self, repo_name: str, analysis: Dict[str, Any]):
        """Cache contributor analysis"""
        if not self.redis_client:
            return
        
        try:
            safe_repo_name = repo_name.replace('/', ':')
            cache_key = f"repo_contributors:{safe_repo_name}"
            await self.redis_client.setex(
                cache_key,
                self.contributor_cache_ttl,
                json.dumps(analysis, default=str)
            )
        except Exception as e:
            logger.warning(f"Failed to cache contributor analysis for {repo_name}: {e}")
    
    def get_context_features_for_ml(
        self, 
        repo_name: str, 
        events: List[Dict[str, Any]]
    ) -> np.ndarray:
        """Get repository context feature vector for ML models"""
        result = asyncio.run(self.analyze_repository_context(repo_name, events))
        return np.array(result['context_features'])
    
    def get_criticality_multiplier(self, criticality_score: float) -> float:
        """Get severity multiplier based on repository criticality"""
        if criticality_score >= 0.8:
            return 1.5  # High criticality repos get 1.5x severity multiplier
        elif criticality_score >= 0.6:
            return 1.3  # Medium-high criticality
        elif criticality_score >= 0.4:
            return 1.1  # Medium criticality
        else:
            return 1.0  # Low criticality repos get no multiplier