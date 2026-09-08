"""Pure domain layer.

Contains no Django imports and no I/O. Everything here is plain Python that can
be unit-tested without a settings module, a database, or a network connection.

    types.py         the Invoice record and its enums
    filters.py       the filter set the dashboard sends, plus row filtering
    aggregations.py  pure functions that turn rows into dashboard payloads
"""
