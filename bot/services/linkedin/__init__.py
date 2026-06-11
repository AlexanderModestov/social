"""Public facade for the vendored linkedin-skills libs.

Re-exports the dispatch-layer entry points and URL helpers. The underlying
modules are byte-identical copies of the upstream MIT repo; see each module
for details.
"""
from .url_parser import parse_linkedin_url, build_parent_comment_urn
from .backend_selector import active_backend, publish, fetch_post, manual_mode_message

__all__ = [
    "parse_linkedin_url",
    "build_parent_comment_urn",
    "active_backend",
    "publish",
    "fetch_post",
    "manual_mode_message",
]
