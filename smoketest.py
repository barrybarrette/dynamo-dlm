import dynamo_dlm as dlm

import time
from datetime import timedelta


def f(i):
    with dlm.DynamoDbLock("smoketest"):
        pass


if __name__ == "__main__":
    from multiprocessing import Pool

    num_threads = 50
    start = time.time()
    with Pool(num_threads) as pool:
        pool.map(f, range(num_threads))
    print(f"Took {timedelta(seconds=time.time() - start)}")
    print('github please run this')
