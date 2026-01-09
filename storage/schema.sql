-- Hypothesis Research Engine Database Schema
-- SQLite schema for storing evaluation results
-- All tables are append-only (no updates or deletes)

-- Table: hypotheses
-- Stores metadata about each hypothesis
CREATE TABLE IF NOT EXISTS hypotheses (
    hypothesis_id TEXT PRIMARY KEY,
    parameters_json TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);




-- Table: policies
-- Stores research policy definitions
CREATE TABLE IF NOT EXISTS policies (
    policy_id TEXT PRIMARY KEY,
    policy_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- Table: evaluations
-- Stores results of each evaluation run
CREATE TABLE IF NOT EXISTS evaluations (
    evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hypothesis_id TEXT NOT NULL,
    policy_id TEXT, -- FK to policies
    policy_hash TEXT, -- Stored redundantly for easy check
    parameters_hash TEXT NOT NULL,
    market_symbol TEXT NOT NULL,
    test_start_timestamp TIMESTAMP NOT NULL,
    test_end_timestamp TIMESTAMP NOT NULL,
    evaluation_run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Walk-forward metadata
    window_index INTEGER,
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    window_type TEXT, -- 'TRAIN' or 'TEST'
    
    -- Sample type
    sample_type TEXT, -- 'IN_SAMPLE' or 'OUT_OF_SAMPLE'
    
    -- Market Regime
    market_regime TEXT,
    
    -- Trade statistics
    trade_count INTEGER NOT NULL,
    entry_count INTEGER NOT NULL,
    exit_count INTEGER NOT NULL,
    
    -- Performance metrics
    mean_return_per_trade REAL,
    sharpe_ratio REAL,
    max_drawdown REAL,
    profit_factor REAL,
    win_rate REAL,
    total_return REAL,
    total_pnl REAL,
    
    -- Risk Metrics (Benchmark Relative)
    beta REAL,
    alpha REAL,
    information_ratio REAL,
    cagr REAL,
    
    -- Benchmark comparison
    benchmark_return_pct REAL,
    benchmark_pnl REAL,
    
    -- Cost assumptions
    assumed_costs_bps REAL NOT NULL,
    
    -- Capital
    initial_capital REAL NOT NULL,
    final_equity REAL NOT NULL,
    
    -- Result tag (for categorization)
    result_tag TEXT,
    
    -- Metadata
    bars_processed INTEGER,
    average_trade_duration_days REAL,
    
    FOREIGN KEY (hypothesis_id) REFERENCES hypotheses(hypothesis_id),
    FOREIGN KEY (policy_id) REFERENCES policies(policy_id)
);

-- Table: trades
-- Stores individual trade records
CREATE TABLE IF NOT EXISTS trades (
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id INTEGER NOT NULL,
    trade_type TEXT NOT NULL, -- 'ENTRY' or 'EXIT'
    side TEXT NOT NULL, -- 'LONG' or 'SHORT'
    execution_price REAL NOT NULL,
    size REAL NOT NULL,
    execution_timestamp TIMESTAMP NOT NULL,
    decision_timestamp TIMESTAMP NOT NULL,
    cost_bps REAL NOT NULL,
    total_cost REAL NOT NULL,
    
    -- For exits only
    entry_price REAL,
    entry_timestamp TIMESTAMP,
    realized_pnl REAL,
    trade_duration_days REAL,
    
    FOREIGN KEY (evaluation_id) REFERENCES evaluations(evaluation_id)
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_evaluations_hypothesis ON evaluations(hypothesis_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_symbol ON evaluations(market_symbol);
CREATE INDEX IF NOT EXISTS idx_evaluations_timestamp ON evaluations(evaluation_run_timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_evaluation ON trades(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(execution_timestamp);


-- Table: batches
-- Stores batch execution configurations
CREATE TABLE IF NOT EXISTS batches (
    batch_id TEXT PRIMARY KEY,
    market_symbol TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    policy_id TEXT, -- Explicit link to the research policy used
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (policy_id) REFERENCES policies(policy_id)
);

-- Table: batch_rankings
-- Stores ranking results for hypotheses within a batch
CREATE TABLE IF NOT EXISTS batch_rankings (
    batch_id TEXT,
    hypothesis_id TEXT,
    research_score REAL,
    rank INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id),
    FOREIGN KEY (hypothesis_id) REFERENCES hypotheses(hypothesis_id)
);


-- Table: hypothesis_status_history
-- Tracks lifecycle state transitions
CREATE TABLE IF NOT EXISTS hypothesis_status_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hypothesis_id TEXT NOT NULL,
    batch_id TEXT, -- Triggering batch
    policy_id TEXT, -- Policy governing decision
    status TEXT NOT NULL, -- DRAFT, EVALUATED, PROMOTED, FROZEN, RETIRED
    decision_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rationale_json TEXT,
    FOREIGN KEY (hypothesis_id) REFERENCES hypotheses(hypothesis_id),
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id),
    FOREIGN KEY (policy_id) REFERENCES policies(policy_id)
);


-- Table: portfolio_evaluations
-- Stores snapshots of portfolio simulation evaluations
CREATE TABLE IF NOT EXISTS portfolio_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_tag TEXT NOT NULL, -- Tag to group evaluations (e.g. "WF_V1_TEST")
    timestamp TIMESTAMP NOT NULL,
    total_capital REAL,
    cash REAL,
    realized_pnl REAL,
    unrealized_pnl REAL,
    drawdown_pct REAL,
    allocations_json TEXT, -- JSON snapshot of allocations
    policy_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (policy_id) REFERENCES policies(policy_id)
);
