"""Uniform error taxonomy for the unified Apify TOV import layer.

``PrivateProfileError`` is defined for back-compat with the Instagram service
(used in a later task); the current ``TovImportService.analyze`` maps Apify
transport failures to ``ServiceError`` and empty results to ``NoPostsError``.
"""


class PrivateProfileError(Exception):
    ...


class NoPostsError(Exception):
    ...


class ServiceError(Exception):
    ...
