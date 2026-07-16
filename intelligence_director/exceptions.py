"""Safe Intelligence Director errors."""
class IntelligenceDirectorError(Exception):
    def __init__(self,message:str,*,code:str="INTELLIGENCE_DIRECTOR_ERROR"):
        super().__init__(message); self.code=code
