import time


# ==========================================
# EXPONENTIAL BACKOFF STRATEGY
# ==========================================

class BackoffStrategy:

    def __init__(self):

        self.base_delay = 2

        self.max_delay = 30

    # ==========================================
    # EXECUTE BACKOFF
    # ==========================================

    def wait(
        self,
        retry_attempt: int
    ):

        delay = min(

            self.base_delay
            *
            (2 ** retry_attempt),

            self.max_delay
        )

        print(
            f"\n⏳ Retrying in "
            f"{delay} seconds...\n"
        )

        time.sleep(delay)