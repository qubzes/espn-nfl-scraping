import argparse
import logging
import os
import re
from datetime import date, datetime
from typing import Any, Optional

import pandas as pd
from playwright.sync_api import (
    Browser,
    Page,
    TimeoutError,
    sync_playwright,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Global browser instance
browser: Optional[Browser] = None


def generate_date_ranges(start_date: date, end_date: date) -> list[tuple[int, int]]:
    """Generate list of (year, month) tuples covering the date range."""
    date_ranges: set[tuple[int, int]] = set()
    current = start_date

    while current <= end_date:
        date_ranges.add((current.year, current.month))
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1, day=1)
        else:
            current = current.replace(month=current.month + 1, day=1)

    return sorted(date_ranges)


def get_player_position(player_url: str) -> str:
    """Fetch player position from their profile page."""
    global browser
    if not browser:
        logger.error("Browser not initialized")
        return ""

    page = None
    try:
        page = browser.new_page()
        logger.debug(f"Fetching position from: {player_url}")
        page.goto(player_url, timeout=60000)

        position_element = page.query_selector(".nfl-c-player-header__position")
        position = position_element.inner_text().strip() if position_element else ""

        page.close()
        logger.debug(f"Found position: {position}")
        return position

    except TimeoutError:
        logger.warning(f"Timeout while fetching player position from {player_url}")
        if page:
            page.close()
        return ""
    except Exception as e:
        logger.error(f"Error fetching player position from {player_url}: {str(e)}")
        if page:
            page.close()
        return ""


def fetch_and_process_transactions(
    page: Page, year: int, month: int, start_date: date, end_date: date
) -> list[dict[str, str]]:
    """Fetch and immediately process transaction rows for a given year and month."""
    base_url = f"https://www.nfl.com/transactions/league/signings/{year}/{month}"
    transactions: list[dict[str, str]] = []
    page_number = 1
    after_token = None

    logger.info(f"Fetching and processing transactions for {year}-{month:02d}")

    while True:
        url = f"{base_url}?after={after_token}" if after_token else base_url
        try:
            logger.debug(f"Navigating to page {page_number}: {url}")
            page.goto(url, timeout=60000)

            rows = page.query_selector_all(".d3-o-table--detailed tbody tr")
            if not rows:
                logger.warning(f"No transaction rows found on page {page_number}")
                break

            # Process rows immediately while DOM is still valid
            page_transactions = process_transaction_rows(
                [(row, year) for row in rows], start_date, end_date
            )
            transactions.extend(page_transactions)
            logger.debug(
                f"Processed {len(page_transactions)} transactions from page {page_number}"
            )

            next_page_link = page.query_selector(".nfl-o-table-pagination__next")
            if not next_page_link:
                logger.info(f"No more pages for {year}-{month:02d}")
                break

            href = next_page_link.get_attribute("href")
            after_token = (
                href.split("after=")[-1] if href and "after=" in href else None
            )
            page_number += 1

        except TimeoutError:
            logger.error(
                f"Timeout while loading page {page_number} for {year}-{month:02d}"
            )
            break
        except Exception as e:
            logger.error(
                f"Error fetching page {page_number} for {year}-{month:02d}: {str(e)}"
            )
            break

    logger.info(
        f"Total transactions collected for {year}-{month:02d}: {len(transactions)}"
    )
    return transactions


def process_transaction_rows(
    rows: list[tuple[Any, int]], start_date: date, end_date: date
) -> list[dict[str, str]]:
    """Process transaction rows and return formatted transaction data."""
    transactions: list[dict[str, str]] = []

    logger.debug(f"Processing {len(rows)} transaction rows")

    logger.info(f"Processing {len(rows)} transaction rows")

    for row, row_year in rows:
        try:
            date_cell = row.query_selector("td:nth-child(3)")
            date_text = date_cell.inner_text().strip() if date_cell else ""
            if not date_text or not re.match(r"\d{1,2}/\d{1,2}", date_text):
                logger.warning(f"Invalid or missing date format: {date_text}")
                continue

            month_num, day = map(int, date_text.split("/"))

            try:
                trans_date = datetime(row_year, month_num, day).date()
                if not (start_date <= trans_date <= end_date):
                    logger.debug(f"Date {trans_date} outside range, skipping")
                    continue
            except ValueError:
                logger.warning(f"Invalid date: {row_year}-{month_num:02d}-{day:02d}")
                continue

            # Extract from team
            from_team_fullname_cell = row.query_selector(
                "td:nth-child(1) .d3-o-club-fullname"
            )
            from_team_fullname = (
                from_team_fullname_cell.inner_text().strip()
                if from_team_fullname_cell
                else ""
            )

            # Extract to team
            to_team_fullname_cell = row.query_selector(
                "td:nth-child(2) .d3-o-club-fullname"
            )
            to_team_fullname = (
                to_team_fullname_cell.inner_text().strip()
                if to_team_fullname_cell
                else ""
            )

            # Extract player name and URL
            player_link = row.query_selector("td:nth-child(4) a")
            if not player_link:
                player_cell = row.query_selector("td:nth-child(4)")
                player_name = player_cell.inner_text().strip() if player_cell else "Unknown Player"
                player_href = None
            else:
                player_name = player_link.inner_text().strip()
                player_href = player_link.get_attribute("href")

            # Get position from player profile page
            position = (
                get_player_position(f"https://www.nfl.com{player_href}")
                if player_href
                else ""
            )

            # Extract transaction type
            transaction_cell = row.query_selector("td:nth-child(6)")
            transaction_type = (
                transaction_cell.inner_text().strip() if transaction_cell else ""
            )

            # Generate player key
            player_key = (
                f"{player_name}_{to_team_fullname}".lower()
                .replace(" ", "_")
                .replace(".", "")
            )

            transaction_data: dict[str, str] = {
                "from_team_fullname": from_team_fullname,
                "to_team_fullname": to_team_fullname,
                "date": str(trans_date.strftime("%Y-%m-%d")),
                "player": player_name,
                "position": position,
                "transaction": transaction_type,
                "player_key": player_key,
            }
            transactions.append(transaction_data)
            logger.debug(f"Added transaction: {player_key}")

        except Exception as e:
            logger.error(f"Error processing row: {str(e)}")
    logger.debug(f"Processed {len(transactions)} valid transactions")
    return transactions


def main() -> None:
    global browser

    parser = argparse.ArgumentParser(description="NFL Transactions Scraper")
    parser.add_argument(
        "--start-date", type=str, help="Start date in YYYY-MM-DD format"
    )
    parser.add_argument("--end-date", type=str, help="End date in YYYY-MM-DD format")

    args = parser.parse_args()

    try:
        if args.start_date and args.end_date:
            start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()

            if start_date > end_date:
                logger.error("Start date must be before or equal to end date")
                return

            date_ranges = generate_date_ranges(start_date, end_date)
        elif args.start_date or args.end_date:
            logger.error("Both --start-date and --end-date must be provided together")
            return
        else:
            today = datetime.now().date()
            start_date = end_date = today
            date_ranges = [(today.year, today.month)]
            logger.info("No date range provided, using today's date as default")

        logger.info(f"Processing date range: {start_date} to {end_date}")
        
        # Create directory if it doesn't exist
        output_dir = "nfl/transactions"
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename with date range
        filename = f"nfl_transaction_{start_date}_to_{end_date}.xlsx"
        filepath = os.path.join(output_dir, filename)
        
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()

            all_transactions: list[dict[str, str]] = []
            for year, month in date_ranges:
                month_transactions = fetch_and_process_transactions(
                    page, year, month, start_date, end_date
                )
                all_transactions.extend(month_transactions)

            df = pd.DataFrame(all_transactions)
            df.to_excel(filepath, index=False)  # type: ignore
            logger.info(
                f"Saved {len(all_transactions)} transactions to {filepath}"
            )
            browser.close()

    except ValueError as e:
        logger.error(f"Invalid date format: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")


if __name__ == "__main__":
    main()
