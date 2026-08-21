# queue

Asynchronous job processing.

**Phase:** 12  
**Status:** placeholder

Redis is declared in Compose as the broker. The worker library (Celery or an alternative) is chosen in Phase 12 after comparing operational fit.

`workers/` will host the process that dequeues jobs and calls `model/`.
