import dynamo_dlm as dlm

import time
from datetime import timedelta

CONCURRENT_WORKERS = 10
CONCURRENT_LOCKS = 4
JOB_COUNT = 20
JOB_DURATION = 5  # seconds


def f(i):
    print(f"{i} pre-lock", flush=True)
    lock = dlm.DynamoDbLock("smoke test", concurrency=CONCURRENT_LOCKS)
    print(f"{i} count: {lock.count()}", flush=True)
    with lock:
        print(f"{i} acquired", flush=True)
        time.sleep(JOB_DURATION)
    print(f"{i} released", flush=True)


if __name__ == "__main__":
    from multiprocessing import Pool

    start = time.time()
    with Pool(CONCURRENT_WORKERS) as pool:
        pool.map(f, range(JOB_COUNT))
    print(f"Took {timedelta(seconds=time.time() - start)}")
