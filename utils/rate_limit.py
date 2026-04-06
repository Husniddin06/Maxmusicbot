import time
from collections import defaultdict
from typing import Dict, Tuple

user_requests: Dict[int, list] = defaultdict(list)
RATE_LIMIT = 5
RATE_WINDOW = 60

def check_rate_limit(user_id: int) -> Tuple[bool, int]:
    now = time.time()
    user_requests[user_id] = [t for t in user_requests[user_id] if now - t < RATE_WINDOW]
    if len(user_requests[user_id]) >= RATE_LIMIT:
        return False, int(RATE_WINDOW - (now - user_requests[user_id][0]))
    user_requests[user_id].append(now)
    return True, 0
