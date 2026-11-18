"""Research Intelligence Engine.

A local pipeline: public RSS goes into SQLite, headlines are clustered into
events, those events are ranked, and a short brief is written (and optionally
emailed). This package does not call a language model.
"""

__version__ = "0.1.0"
