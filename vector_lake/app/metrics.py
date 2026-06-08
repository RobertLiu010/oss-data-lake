"""Business metrics for Vector Lake observability.

All metrics are lazily initialized — if prometheus_client is not installed,
the module provides no-op stubs so the rest of the code can call them safely.

Metric naming follows Prometheus conventions:
  - _total suffix for counters
  - _seconds suffix for histograms
  - lowercase with underscores

Categories:
  1. Pipeline: entities processed, chunks created, embedding latency
  2. Index: parquet writes, LanceDB syncs, rebuilds
  3. SyncQueue: enqueue, dequeue, retry, queue depth
  4. Reconciler: scans, drifts detected, repairs
  5. Search: queries by type, latency
  6. Entity: CRUD operations
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy initialization — all metrics are None until _init() is called
# ---------------------------------------------------------------------------

_initialized = False

# Pipeline
PIPELINE_ENTITIES_TOTAL: Any = None
PIPELINE_CHUNKS_TOTAL: Any = None
PIPELINE_EMBEDDING_SECONDS: Any = None
PIPELINE_ERRORS_TOTAL: Any = None

# Index
INDEX_PARQUET_WRITES_TOTAL: Any = None
INDEX_LANCE_SYNCS_TOTAL: Any = None
INDEX_LANCE_SYNC_SECONDS: Any = None
INDEX_REBUILDS_TOTAL: Any = None
INDEX_CHUNKS_INDEXED: Any = None

# SyncQueue
SYNC_ENQUEUE_TOTAL: Any = None
SYNC_DEQUEUE_TOTAL: Any = None
SYNC_RETRY_TOTAL: Any = None
SYNC_QUEUE_DEPTH: Any = None
SYNC_WORKER_ERRORS_TOTAL: Any = None

# Reconciler
RECONCILE_SCANS_TOTAL: Any = None
RECONCILE_DRIFTS_TOTAL: Any = None
RECONCILE_REPAIRS_TOTAL: Any = None
RECONCILE_SECONDS: Any = None

# Search
SEARCH_QUERIES_TOTAL: Any = None
SEARCH_SECONDS: Any = None
SEARCH_RESULTS_RETURNED: Any = None

# Entity
ENTITY_OPS_TOTAL: Any = None


def init_metrics() -> bool:
    """Initialize all business metrics. Returns True if prometheus_client is available."""
    global _initialized
    global PIPELINE_ENTITIES_TOTAL, PIPELINE_CHUNKS_TOTAL
    global PIPELINE_EMBEDDING_SECONDS, PIPELINE_ERRORS_TOTAL
    global INDEX_PARQUET_WRITES_TOTAL, INDEX_LANCE_SYNCS_TOTAL
    global INDEX_LANCE_SYNC_SECONDS, INDEX_REBUILDS_TOTAL, INDEX_CHUNKS_INDEXED
    global SYNC_ENQUEUE_TOTAL, SYNC_DEQUEUE_TOTAL, SYNC_RETRY_TOTAL
    global SYNC_QUEUE_DEPTH, SYNC_WORKER_ERRORS_TOTAL
    global RECONCILE_SCANS_TOTAL, RECONCILE_DRIFTS_TOTAL
    global RECONCILE_REPAIRS_TOTAL, RECONCILE_SECONDS
    global SEARCH_QUERIES_TOTAL, SEARCH_SECONDS, SEARCH_RESULTS_RETURNED
    global ENTITY_OPS_TOTAL

    if _initialized:
        return True

    try:
        from prometheus_client import Counter, Gauge, Histogram
    except ImportError:
        logger.info("prometheus_client not installed, business metrics disabled")
        return False

    # Pipeline
    PIPELINE_ENTITIES_TOTAL = Counter(
        "vl_pipeline_entities_total",
        "Total entities processed through pipeline",
        ["status"],  # success / failure
    )
    PIPELINE_CHUNKS_TOTAL = Counter(
        "vl_pipeline_chunks_total",
        "Total chunks created by chunking service",
    )
    PIPELINE_EMBEDDING_SECONDS = Histogram(
        "vl_pipeline_embedding_seconds",
        "Time spent embedding chunks",
        ["batch_size"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )
    PIPELINE_ERRORS_TOTAL = Counter(
        "vl_pipeline_errors_total",
        "Total pipeline errors",
        ["stage"],  # rep / embed / index
    )

    # Index
    INDEX_PARQUET_WRITES_TOTAL = Counter(
        "vl_index_parquet_writes_total",
        "Total parquet file writes",
    )
    INDEX_LANCE_SYNCS_TOTAL = Counter(
        "vl_index_lance_syncs_total",
        "Total LanceDB sync operations",
        ["status"],  # success / failure
    )
    INDEX_LANCE_SYNC_SECONDS = Histogram(
        "vl_index_lance_sync_seconds",
        "Time spent syncing parquet to LanceDB",
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    )
    INDEX_REBUILDS_TOTAL = Counter(
        "vl_index_rebuilds_total",
        "Total LanceDB table rebuilds",
    )
    INDEX_CHUNKS_INDEXED = Counter(
        "vl_index_chunks_indexed_total",
        "Total chunks indexed into LanceDB",
    )

    # SyncQueue
    SYNC_ENQUEUE_TOTAL = Counter(
        "vl_sync_enqueue_total",
        "Total sync tasks enqueued",
    )
    SYNC_DEQUEUE_TOTAL = Counter(
        "vl_sync_dequeue_total",
        "Total sync tasks dequeued (processed)",
        ["status"],  # success / failure
    )
    SYNC_RETRY_TOTAL = Counter(
        "vl_sync_retry_total",
        "Total sync task retries",
    )
    SYNC_QUEUE_DEPTH = Gauge(
        "vl_sync_queue_depth",
        "Current sync queue depth",
    )
    SYNC_WORKER_ERRORS_TOTAL = Counter(
        "vl_sync_worker_errors_total",
        "Total sync worker errors",
    )

    # Reconciler
    RECONCILE_SCANS_TOTAL = Counter(
        "vl_reconcile_scans_total",
        "Total reconcile scans",
    )
    RECONCILE_DRIFTS_TOTAL = Counter(
        "vl_reconcile_drifts_total",
        "Total drifts detected",
        ["drift_type"],
    )
    RECONCILE_REPAIRS_TOTAL = Counter(
        "vl_reconcile_repairs_total",
        "Total drifts repaired",
        ["drift_type"],
    )
    RECONCILE_SECONDS = Histogram(
        "vl_reconcile_seconds",
        "Time spent in reconcile",
        buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    )

    # Search
    SEARCH_QUERIES_TOTAL = Counter(
        "vl_search_queries_total",
        "Total search queries",
        ["search_type"],  # semantic / lexical / hybrid
    )
    SEARCH_SECONDS = Histogram(
        "vl_search_seconds",
        "Search query latency",
        ["search_type"],
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    )
    SEARCH_RESULTS_RETURNED = Counter(
        "vl_search_results_returned_total",
        "Total search results returned",
        ["search_type"],
    )

    # Entity
    ENTITY_OPS_TOTAL = Counter(
        "vl_entity_ops_total",
        "Total entity operations",
        ["operation"],  # create / read / update / delete / content_update
    )

    _initialized = True
    logger.info("Business metrics initialized")
    return True


# ---------------------------------------------------------------------------
# Safe increment / observe helpers (no-op if metrics not initialized)
# ---------------------------------------------------------------------------


def _inc(counter: Any, *labels: str, amount: int = 1) -> None:
    """Safely increment a counter. No-op if not initialized."""
    if counter is not None:
        try:
            if labels:
                counter.labels(*labels).inc(amount)
            else:
                counter.inc(amount)
        except Exception as e:
            logger.debug("Metrics inc failed: %s", e)


def _observe(histogram: Any, value: float, *labels: str) -> None:
    """Safely observe a histogram value. No-op if not initialized."""
    if histogram is not None:
        try:
            if labels:
                histogram.labels(*labels).observe(value)
            else:
                histogram.observe(value)
        except Exception as e:
            logger.debug("Metrics observe failed: %s", e)


def _set(gauge: Any, value: float, *labels: str) -> None:
    """Safely set a gauge value. No-op if not initialized."""
    if gauge is not None:
        try:
            if labels:
                gauge.labels(*labels).set(value)
            else:
                gauge.set(value)
        except Exception as e:
            logger.debug("Metrics set failed: %s", e)


# ---------------------------------------------------------------------------
# Convenience functions for use in service code
# ---------------------------------------------------------------------------


def record_pipeline_entity(status: str = "success") -> None:
    _inc(PIPELINE_ENTITIES_TOTAL, status)


def record_pipeline_chunks(count: int) -> None:
    if PIPELINE_CHUNKS_TOTAL is not None:
        _inc(PIPELINE_CHUNKS_TOTAL, amount=count)


def record_embedding_latency(seconds: float, batch_size: int = 1) -> None:
    _observe(PIPELINE_EMBEDDING_SECONDS, seconds, str(batch_size))


def record_pipeline_error(stage: str) -> None:
    _inc(PIPELINE_ERRORS_TOTAL, stage)


def record_parquet_write() -> None:
    _inc(INDEX_PARQUET_WRITES_TOTAL)


def record_lance_sync(status: str = "success", seconds: float = 0.0) -> None:
    _inc(INDEX_LANCE_SYNCS_TOTAL, status)
    if seconds > 0:
        _observe(INDEX_LANCE_SYNC_SECONDS, seconds)


def record_lance_rebuild() -> None:
    _inc(INDEX_REBUILDS_TOTAL)


def record_chunks_indexed(count: int) -> None:
    _inc(INDEX_CHUNKS_INDEXED, amount=count)


def record_sync_enqueue() -> None:
    _inc(SYNC_ENQUEUE_TOTAL)


def record_sync_dequeue(status: str = "success") -> None:
    _inc(SYNC_DEQUEUE_TOTAL, status)


def record_sync_retry() -> None:
    _inc(SYNC_RETRY_TOTAL)


def set_sync_queue_depth(depth: int) -> None:
    _set(SYNC_QUEUE_DEPTH, depth)


def record_sync_worker_error() -> None:
    _inc(SYNC_WORKER_ERRORS_TOTAL)


def record_reconcile_scan() -> None:
    _inc(RECONCILE_SCANS_TOTAL)


def record_reconcile_drift(drift_type: str) -> None:
    _inc(RECONCILE_DRIFTS_TOTAL, drift_type)


def record_reconcile_repair(drift_type: str) -> None:
    _inc(RECONCILE_REPAIRS_TOTAL, drift_type)


def record_reconcile_latency(seconds: float) -> None:
    _observe(RECONCILE_SECONDS, seconds)


def record_search_query(search_type: str, seconds: float, results: int) -> None:
    _inc(SEARCH_QUERIES_TOTAL, search_type)
    _observe(SEARCH_SECONDS, seconds, search_type)
    if SEARCH_RESULTS_RETURNED is not None:
        _inc(SEARCH_RESULTS_RETURNED, search_type, amount=results)


def record_entity_op(operation: str) -> None:
    _inc(ENTITY_OPS_TOTAL, operation)
