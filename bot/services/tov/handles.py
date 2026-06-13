import re
from bot.db.channels import INSTAGRAM, TIKTOK, LINKEDIN

_PATTERNS = {
    INSTAGRAM: r"instagram\.com/([^/?&#]+)",
    TIKTOK: r"tiktok\.com/@([^/?&#]+)",
    LINKEDIN: r"linkedin\.com/in/([^/?&#]+)",
}

def extract_handle(channel: str, raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("empty handle")
    pat = _PATTERNS.get(channel)
    if pat:
        m = re.search(pat, raw)
        if m:
            return m.group(1).strip("/")
    return raw.lstrip("@").strip("/")
