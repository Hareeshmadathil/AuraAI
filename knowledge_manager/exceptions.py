"""Safe persistence and policy errors."""
class KnowledgeManagerError(Exception):
    def __init__(self,message:str,*,code:str="KNOWLEDGE_MANAGER_ERROR"): super().__init__(message); self.code=code
