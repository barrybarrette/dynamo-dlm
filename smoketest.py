import dynamo_dlm as dlm

import time
from datetime import timedelta

CONCURRENT_WORKERS = 4
JOB_COUNT = 20
JOB_DURATION = 5  # seconds


def f(i):
    print(f"{i} pre-lock", flush=True)
    with dlm.DynamoDbLock("smoke test", concurrency=CONCURRENT_WORKERS):
        print(f"{i} acquired", flush=True)
        time.sleep(JOB_DURATION)
    print(f"{i} released", flush=True)


if __name__ == "__main__":
    from multiprocessing import Pool

    start = time.time()
    with Pool(CONCURRENT_WORKERS) as pool:
        pool.map(f, range(JOB_COUNT))
    print(f"Took {timedelta(seconds=time.time() - start)}")
