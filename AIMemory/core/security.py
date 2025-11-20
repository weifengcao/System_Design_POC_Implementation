import re

class SecurityManager:
    def __init__(self):
        # Simple regex-based PII scrubber for demonstration
        self.patterns = {
            "email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
            "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b"
        }

    def scrub_pii(self, text: str) -> str:
        scrubbed_text = text
        for pii_type, pattern in self.patterns.items():
            scrubbed_text = re.sub(pattern, f"[{pii_type.upper()}_REDACTED]", scrubbed_text)
        return scrubbed_text
