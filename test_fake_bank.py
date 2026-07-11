import asyncio

from app.services.fake_bank import (
    fake_bank_service,
    FakeBankTimeoutError,
    FakeBankServerError,
)

async def main():
    for i in range(100):
        try:
            result = await fake_bank_service.process_transaction(
                amount=999.99,
                currency="INR",
                reference=f"TEST-{i}"
            )
            print(f"{i}: {result}")

        except FakeBankTimeoutError as e:
            print(f"{i}: TIMEOUT -> {e}")

        except FakeBankServerError as e:
            print(f"{i}: HTTP500 -> {e}")

asyncio.run(main())