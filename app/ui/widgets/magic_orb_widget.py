"""
MagicOrbWidget — Compatibility wrapper re-exporting FeatherAIButton.
"""

from .feather_ai_button import FeatherAIButton

# Re-export FeatherAIButton as MagicOrbWidget for full backwards compatibility
MagicOrbWidget = FeatherAIButton
