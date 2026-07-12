import asyncio
import random
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class FakeBankTimeoutError(Exception):
    """Raised when the fake bank simulates a network or processing timeout."""
    pass

class FakeBankServerError(Exception):
    """Raised when the fake bank simulates an HTTP 500 Internal Server Error."""
    pass

class FakeBankConfig:
    """
    Configuration for adjusting probabilities and delays of the Fake Bank service.
    Probabilities should ideally sum to 1.0 (excluding the delay parameters).
    """
    SUCCESS_PROBABILITY: float = 0.00
    FAILURE_PROBABILITY: float = 0.00
    TIMEOUT_PROBABILITY: float = 1.00
    HTTP_500_PROBABILITY: float = 0.00
    DUPLICATE_PROBABILITY: float = 0.00
    
    MIN_DELAY_SECONDS: float = 0.1
    MAX_DELAY_SECONDS: float = 2.0

class FakeBankService:
    def __init__(self, config: FakeBankConfig = FakeBankConfig()):
        self.config = config

    async def process_transaction(self, amount: float, currency: str, reference: str) -> Dict[str, str]:
        """
        Simulates an external bank processing a transaction.
        Handles random delays, timeouts, server errors, duplicates, failures, and successes.
        """
        # 1. Random delay simulation
        delay = random.uniform(self.config.MIN_DELAY_SECONDS, self.config.MAX_DELAY_SECONDS)
        logger.info(f"FakeBank: Processing transaction {reference}... (simulating delay of {delay:.2f}s)")
        await asyncio.sleep(delay)

        # Roll a number between 0.0 and 1.0 to determine the outcome
        outcome_roll = random.random()
        cumulative_prob = 0.0

        # 2. Simulate Random Timeout
        cumulative_prob += self.config.TIMEOUT_PROBABILITY
        if outcome_roll < cumulative_prob:
            logger.warning(f"FakeBank: Simulated connection TIMEOUT for {reference}.")
            raise FakeBankTimeoutError("The bank connection timed out before a response was received.")

        # 3. Simulate Random HTTP 500
        cumulative_prob += self.config.HTTP_500_PROBABILITY
        if outcome_roll < cumulative_prob:
            logger.error(f"FakeBank: Simulated HTTP 500 Internal Server Error for {reference}.")
            raise FakeBankServerError("The bank experienced an internal server error (HTTP 500).")

        # 4. Simulate Duplicate Response
        cumulative_prob += self.config.DUPLICATE_PROBABILITY
        if outcome_roll < cumulative_prob:
            logger.warning(f"FakeBank: Simulated DUPLICATE transaction for {reference}.")
            # Idempotency generally dictates we return SUCCESS for duplicates without erroring
            return {"status": "SUCCESS"}

        # 5. Simulate Random FAILURE
        cumulative_prob += self.config.FAILURE_PROBABILITY
        if outcome_roll < cumulative_prob:
            logger.info(f"FakeBank: Simulated transaction FAILURE for {reference}.")
            return {"status": "FAILED"}

        # 6. Simulate Random SUCCESS (Fallback for remaining probability)
        logger.info(f"FakeBank: Simulated transaction SUCCESS for {reference}.")
        return {"status": "SUCCESS"}

# Expose a singleton instance for use across the application
fake_bank_service = FakeBankService()
