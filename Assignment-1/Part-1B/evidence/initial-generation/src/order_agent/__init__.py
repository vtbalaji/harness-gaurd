"""New-order announcement extraction agent (spec 001-order-extraction-agent).

Reads the raw text of one NSE/BSE corporate announcement and returns one schema-1.0 JSON
object. The model under test is the local ``qwen3.5:4b`` on Ollama; everything around it
(guards, parser, validation, assembly) is deterministic code.
"""

__version__ = "0.1.0"
SCHEMA_VERSION = "1.0"
