# GitHub Anomaly Detection System

A real-time GitHub activity monitoring system with AI-powered anomaly detection that identifies suspicious patterns across public repositories using multi-factor behavioral analysis.

https://conway-technical.fly.dev

Auth with your Github PAT, connect to websocket by clicking the websocket "Disconnected/Connected" button in the navbar, and refresh the page to start.
<img width="3837" height="2042" alt="image" src="https://github.com/user-attachments/assets/5683e762-3934-4d9f-a3af-d1f47970872c" />
<img width="3823" height="2022" alt="image" src="https://github.com/user-attachments/assets/97044fb4-8949-46b0-8030-a5bd708868df" />

## Architecture Overview

The system employs a multi-tier architecture designed for scalability and real-time processing:

- **Backend**: FastAPI with async Python, PostgreSQL, Redis
- **Frontend**: SvelteKit with Svelte 5 + runes, TailwindCSS
- **Real-time**: WebSocket connections with Redis pub/sub
- **Processing**: Distributed workers with batch processing
- **AI Integration**: Optional OpenAI for intelligent summarization
- **AI for development**: Used Claude Code (Opus and Sonnet 4) for code generation assistance

## Approaches

### 1. Multi-Factor Anomaly Detection

The system combines four independent detection methods that analyze different aspects of GitHub activity. I believed that since the endpoint outputs a lot of different data and that GitHub ingests so much activity at every timeframe, it makes more sense to just identify outliers in general activity; ideas were inspired from momentum trading, entropy, and basic statistical analysis. 

#### Behavioral Analysis (backend/app/anomaly_detection/detectors/behavioral.py)
- Extracts 10 behavioral features using numpy arrays for efficient computation
- Implements EWMA (Exponentially Weighted Moving Average) for adaptive baselines
- Uses Mahalanobis distance for multivariate anomaly detection
- Features include: events per hour, repository diversity, activity bursts, event type entropy, off-hours activity

#### Temporal Pattern Detection (backend/app/anomaly_detection/detectors/temporal.py)
- Fetches baseline activity from GitHub API for users and repositories
- Detects coordinated multi-actor activities within time windows
- Identifies activity bursts using sliding window analysis
- Performs chi-square tests for unusual timing distributions
- Tracks velocity acceleration to detect escalating threats

#### Content Risk Analysis (backend/app/anomaly_detection/detectors/content.py)
- Scans for exposed secrets and credentials in commits
- Analyzes commit messages for suspicious keywords
- Detects force pushes and branch deletions
- Identifies mass file deletions and repository vandalism

#### Repository Context Scoring (backend/app/anomaly_detection/detectors/contextual.py)
- Evaluates repository criticality based on activity patterns
- Compares current activity against historical baselines
- Considers repository size, contributor count, and update frequency

### 2. Smart Data Ingestion

#### Distributed Rate Limit Management (backend/app/poller.py)
- Redis-based coordination between multiple pollers
- Circuit breaker pattern for API failures
- Exponential backoff with jitter
- Semaphore-based concurrent request limiting

#### Priority-Based Event Filtering
```python
high_priority_types = {"PushEvent", "WorkflowRunEvent", "DeleteEvent", "MemberEvent"}
medium_priority_types = {"PullRequestEvent", "IssuesEvent", "CreateEvent"}
low_priority_types = {"WatchEvent", "StarEvent"}  # Sampled at 20%
```

Based on these events, we could elevate these and perform deeper analyses, such as user behavior history and repository history analysis, code diffs, better AI agent workflows on this context etc.

### 3. Visualizations

#### Detection Matrix (frontend/src/lib/components/dashboard/DetectionMatrix.svelte)
- Cell intensity based on normalized anomaly count and average score
- Interactive cells reveal detailed statistics
- Summary cards for force pushes, workflow failures, secret risks

#### Live Incident Feed
- Real-time WebSocket updates with processing statistics
- AI-generated summaries with root cause bullets
- Primary detection method badges with confidence scores
- Risk factor tags and severity indicators

#### Repository Monitor
- Activity heatmaps showing temporal patterns
- Repository risk scores with trend analysis
- Contributor diversity metrics

#### Interactive dashboard
- Dashboard that shows everything, allows for interaction and deeper links to the actual GH events. 

## Technical Implementation

### Backend Architecture

```
backend/
       app/
          anomaly_detection/
                detectors/         # Detection algorithms
                models/            # Anomaly scoring
                profiles/          # User/repo profiling
                optimization/      # AI summarization
                stream_processor.py # Main processing pipeline
             poller.py             # GitHub API ingestion
             worker.py             # Queue processing
             main.py               # FastAPI application
```

### Key Algorithms

1. **EWMA Baseline Updates**
   ```python
   new_mean = alpha * current_features + (1 - alpha) * old_mean
   new_var = alpha * (current_features - new_mean)� + (1 - alpha) * old_var
   ```

2. **Burst Detection**
   - Sliding window analysis over 5-minute intervals
   - Threshold: 5+ events in window with rate > 2 events/minute

3. **Cold Start Heuristics**
   - Multi-tier thresholds for new users/repos
   - Variable scoring ranges (0.3-0.9) based on severity

4. **Parallel Processing Pipeline**
   - All detection methods run concurrently
   - Batch processing up to 50 events
   - Smart pre-filtering reduces AI load by ~90%

### Database Schema

- **github_events**: Raw event storage with JSON payloads
- **anomaly_detections**: Detected anomalies with component scores
- **user_profiles**: Behavioral baselines (EWMA features)
- **repository_profiles**: Activity patterns and metrics
- **temporal_patterns**: Specific temporal anomalies
- **secret_detections**: Credential exposure tracking

### Performance Optimizations

1. **Batch Processing**: Process events in groups of 50
2. **Pre-filtering**: Quick heuristics before expensive analysis
3. **Parallel Detection**: All methods run concurrently
4. **Smart Caching**: Redis TTL caching for API responses
5. **Compressed Storage**: Reduced payloads for low-priority events
6. **Optimized Indexes**: Composite indexes for time-series queries

## Infrastructure

### Local Development
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.main

# Frontend
cd frontend
npm install
npm run dev
```

### Docker Deployment
```bash
docker-compose up -d
```

### Environment Variables
```env
DATABASE_URL=postgresql://user:pass@localhost/conway_technical
REDIS_URL=redis://localhost:6379
GITHUB_TOKEN=your-github-pat
OPENAI_API_KEY=optional-for-ai-summaries
```

## Scalability

- **Horizontal Scaling**: Multiple worker processes
- **Queue-based Architecture**: Redis for job distribution
- **Caching Layer**: Reduce API calls and database queries
- **Efficient Algorithms**: Numpy-based computations
- **Rate Limit Aware**: Adaptive polling with backoff

## Future Enhancements

1. Machine learning models trained on labeled anomalies. Most trivial way beyond heuristics that would be effective in classifying behavior. I would personally do some sort of random forest system due to the number of signals, trading off with the eval time.
2. Unsupervised methods. I actually had tried to implement some Self-Organizing Map and VAE methods but did not have time to refine them and make them super robust. I believe this is more effective than ML since GH activity is so sparse and sporadic; labeling can result in possible overfitting to certain users' or demographics' coding behaviors; therefore, as a general anomaly detector, unsupervised methods to find out of distribution behavior would provide better signals.
3. Full information theory modeling. This was what I kind of wanted to build out in this repo; could we have some algorithm or modeling system to parse behavior data into functions? Granularly noisy but overall repetitive functions are probably human (sporadic behaviors during dev but they follow dev work week patterns) vs maybe a bot runs noisy overall but have more granularly similar behaviors.
4. Behavior linking. In a lot of AML and DeFi anomaly detection, we often look at the behaviors of certain wallets/the movement of money. The movement of commit behavior and activity on GH + tracking associated accounts and organizations could lead to some interesting findings there. 

## License

MIT License - See LICENSE file for details
