"""Versioned founder-gated research queues."""
from intelligence_director.models import ResearchQueue,ResearchQueueItem
def build_queue(items:list[ResearchQueueItem],*,parent_queue_id=None,version:int=1)->ResearchQueue:
    ordered=[item.model_copy(update={"order":index}) for index,item in enumerate(sorted(items,key=lambda x:(-x.priority_score.overall,str(x.queue_item_id))),1)]
    if len({x.queue_item_id for x in ordered})!=len(ordered): raise ValueError("Duplicate queue item IDs are forbidden.")
    return ResearchQueue(items=ordered,parent_queue_id=parent_queue_id,version=version,execution_enabled=False)
def revise_queue(queue:ResearchQueue,items:list[ResearchQueueItem])->ResearchQueue:
    return build_queue(items,parent_queue_id=queue.queue_id,version=queue.version+1)
