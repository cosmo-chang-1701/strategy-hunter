import os
import httpx
import logging
from fastapi import HTTPException
from typing import List

from .. import schemas

from ..config import settings

log = logging.getLogger(__name__)


class OptionChainService:
    def __init__(self, is_live: bool):
        self.is_live = is_live
        self.api_key = settings.POLYGON_API_KEY

    async def get_option_chain(
        self, ticker: str, expiration_date: str
    ) -> schemas.OptionChain:
        if self.is_live:
            return await self._fetch_and_process_live_option_chain(
                ticker, expiration_date
            )
        else:
            return self._get_mock_option_chain(ticker, expiration_date)

    def _get_mock_option_chain(
        self, ticker: str, expiration_date: str
    ) -> schemas.OptionChain:
        """
        產生並回傳一份寫死的、結構完整的假資料。
        """
        log.info("(Service) Returning mock option chain data.")
        underlying_price = 215.50

        mock_calls = [
            schemas.OptionContract(
                symbol=f"O:{ticker.upper()}{expiration_date[2:].replace('-', '')}C00210000",
                strike_price=210.0,
                contract_type="call",
                bid=7.50,
                ask=7.60,
                last_price=7.55,
                volume=150,
                open_interest=1200,
                implied_volatility=0.28,
                delta=0.65,
                gamma=0.05,
                theta=-0.12,
                vega=0.35,
                is_itm=True,
            ),
            schemas.OptionContract(
                symbol=f"O:{ticker.upper()}{expiration_date[2:].replace('-', '')}C00215000",
                strike_price=215.0,
                contract_type="call",
                bid=4.20,
                ask=4.25,
                last_price=4.22,
                volume=350,
                open_interest=2500,
                implied_volatility=0.27,
                delta=0.51,
                gamma=0.07,
                theta=-0.15,
                vega=0.40,
                is_itm=True,
            ),
            schemas.OptionContract(
                symbol=f"O:{ticker.upper()}{expiration_date[2:].replace('-', '')}C00220000",
                strike_price=220.0,
                contract_type="call",
                bid=2.10,
                ask=2.15,
                last_price=2.13,
                volume=280,
                open_interest=1800,
                implied_volatility=0.26,
                delta=0.35,
                gamma=0.06,
                theta=-0.14,
                vega=0.38,
                is_itm=False,
            ),
        ]

        mock_puts = [
            schemas.OptionContract(
                symbol=f"O:{ticker.upper()}{expiration_date[2:].replace('-', '')}P00210000",
                strike_price=210.0,
                contract_type="put",
                bid=2.80,
                ask=2.85,
                last_price=2.83,
                volume=180,
                open_interest=1500,
                implied_volatility=0.28,
                delta=-0.38,
                gamma=0.06,
                theta=-0.13,
                vega=0.36,
                is_itm=False,
            ),
            schemas.OptionContract(
                symbol=f"O:{ticker.upper()}{expiration_date[2:].replace('-', '')}P00215000",
                strike_price=215.0,
                contract_type="put",
                bid=4.80,
                ask=4.90,
                last_price=4.85,
                volume=320,
                open_interest=2200,
                implied_volatility=0.27,
                delta=-0.49,
                gamma=0.07,
                theta=-0.15,
                vega=0.40,
                is_itm=False,
            ),
            schemas.OptionContract(
                symbol=f"O:{ticker.upper()}{expiration_date[2:].replace('-', '')}P00220000",
                strike_price=220.0,
                contract_type="put",
                bid=7.90,
                ask=8.00,
                last_price=7.95,
                volume=210,
                open_interest=1900,
                implied_volatility=0.29,
                delta=-0.62,
                gamma=0.05,
                theta=-0.11,
                vega=0.34,
                is_itm=True,
            ),
        ]

        return schemas.OptionChain(
            isMock=True,
            underlying_price=underlying_price,
            calls=mock_calls,
            puts=mock_puts,
        )

    async def _fetch_and_process_live_option_chain(
        self, ticker: str, expiration_date: str
    ) -> schemas.OptionChain:
        """
        從 Polygon.io API 獲取選擇權鏈並處理它。
        """
        log.info(
            f"(Service) Fetching LIVE option chain for {ticker} on {expiration_date}"
        )
        # 1. Fetch underlying price
        underlying_price = await self._fetch_underlying_price(ticker)

        # 2. Fetch option chain snapshot
        url = f"https://api.polygon.io/v3/snapshot/options/{ticker}?expiration_date={expiration_date}&limit=1000"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                calls = []
                puts = []

                for contract_snapshot in data.get("results", []):
                    details = contract_snapshot.get("details", {})
                    greeks = contract_snapshot.get("greeks", {})
                    last_trade = contract_snapshot.get("last_trade", {})
                    quote = contract_snapshot.get("quote", {})

                    # Skip if essential data is missing
                    if not all(
                        [
                            details.get("ticker"),
                            details.get("strike_price"),
                            details.get("contract_type"),
                            quote.get("bid") is not None,
                            quote.get("ask") is not None,
                        ]
                    ):
                        continue

                    option_contract = schemas.OptionContract(
                        symbol=details.get("ticker"),
                        strike_price=details.get("strike_price"),
                        contract_type=details.get("contract_type"),
                        bid=quote.get("bid"),
                        ask=quote.get("ask"),
                        last_price=last_trade.get("price"),
                        volume=details.get("volume"),
                        open_interest=details.get("open_interest"),
                        implied_volatility=greeks.get("implied_volatility"),
                        delta=greeks.get("delta"),
                        gamma=greeks.get("gamma"),
                        theta=greeks.get("theta"),
                        vega=greeks.get("vega"),
                        is_itm=contract_snapshot.get("in_the_money", False),
                    )
                    if option_contract.contract_type == "call":
                        calls.append(option_contract)
                    else:
                        puts.append(option_contract)

                # Sort by strike price
                calls.sort(key=lambda x: x.strike_price)
                puts.sort(key=lambda x: x.strike_price)

                return schemas.OptionChain(
                    isMock=False,
                    underlying_price=underlying_price,
                    calls=calls,
                    puts=puts,
                )

            except httpx.HTTPStatusError as e:
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=f"Error fetching data from Polygon API: {e.response.text}",
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"An unexpected error occurred: {str(e)}"
                )

    async def _fetch_underlying_price(self, ticker: str) -> float:
        """Fetches the last trade price for the underlying stock."""
        url = f"https://api.polygon.io/v2/last/trade/{ticker}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                return data["results"]["p"]
            except Exception as e:
                log.error(f"Could not fetch underlying price for {ticker}: {e}")
                # In a real app, you might want to raise an exception
                # or have a more sophisticated fallback.
                raise HTTPException(
                    status_code=500,
                    detail=f"Could not fetch underlying price for {ticker}.",
                )

    async def fetch_option_expirations(self, ticker: str) -> List[str]:
        """
        獲取指定股票所有可用的選擇權到期日列表。
        """
        if self.is_live:
            return await self._fetch_live_option_expirations(ticker)
        else:
            return self._get_mock_option_expirations()

    def _get_mock_option_expirations(self) -> List[str]:
        """
        回傳一個假的到期日列表。
        """
        log.info(f"(Service) Returning MOCK option expirations.")
        return ["2024-08-16", "2024-08-23", "2024-08-30", "2024-09-20"]

    async def _fetch_live_option_expirations(self, ticker: str) -> List[str]:
        """
        從 Polygon.io API 獲取真實的到期日。
        """
        log.info(f"(Service) Fetching LIVE option expirations for {ticker}")
        url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&limit=1000"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        expirations = set()
        async with httpx.AsyncClient() as client:
            try:
                while url:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    data = response.json()

                    for contract in data.get("results", []):
                        expirations.add(contract.get("expiration_date"))

                    next_url = data.get("next_url")
                    if next_url:
                        # The next_url from polygon already contains the api key, so we don't need to add it again.
                        # We will strip it and use our header method.
                        # Create a new header for the next request
                        url = f"{next_url}"
                    else:
                        url = None

                return sorted(list(expirations))

            except httpx.HTTPStatusError as e:
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=f"Error fetching expirations from Polygon API: {e.response.text}",
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"An unexpected error occurred: {str(e)}"
                )


# =============================================================================
# Backwards compatibility - to be removed after full refactoring
# =============================================================================


def get_mock_option_chain() -> schemas.OptionChain:
    # Note: This mock doesn't have ticker/expiration context, so it's less ideal.
    return OptionChainService(is_live=False)._get_mock_option_chain("SPY", "2024-09-20")


async def fetch_and_process_option_chain(
    ticker: str, expiration_date: str
) -> schemas.OptionChain:
    service = OptionChainService(is_live=True)
    return await service.get_option_chain(ticker, expiration_date)


async def fetch_option_expirations(ticker: str) -> List[str]:
    is_live = settings.POLYGON_API_KEY is not None
    service = OptionChainService(is_live=is_live)
    return await service.fetch_option_expirations(ticker)
