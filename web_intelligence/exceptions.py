"""Stable safe errors for web intelligence."""
from core import AuraAIError
class WebIntelligenceError(AuraAIError): pass
class UnsafeUrlError(WebIntelligenceError): pass
class ApprovalError(WebIntelligenceError): pass
class RobotsDeniedError(WebIntelligenceError): pass
class ResourceLimitError(WebIntelligenceError): pass
