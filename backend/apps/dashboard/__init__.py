"""The dashboard app: Bubble in, `PerformancePayload` out.

    views.py        the six `/api/` endpoints
    source.py       pulls the four Bubble tables and caches one snapshot
    schema.py       the Bubble field names, in one place
    metrics.py      the aggregations (grown out of `scripts/play_bubble.py`)
    filters.py      applies the filter bar to the deal rows
    params.py       parses the query string the React app sends
    serializers.py  snake_case -> the camelCase in `frontend/src/lib/api-types.ts`
    sample.py       deterministic stand-in rows for running without credentials
"""
