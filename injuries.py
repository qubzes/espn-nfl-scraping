import argparse
import logging
import re
from datetime import datetime
from typing import Dict, List

import pandas as pd
from playwright.sync_api import Browser, sync_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class InjuryData:
    def __init__(
        self,
        player: str,
        position: str,
        team: str,
        injuries: str,
        practice_status: str,
        game_status: str,
        date: str,
    ) -> None:
        self.player = player
        self.position = position
        self.team = team
        self.injuries = injuries
        self.practice_status = practice_status
        self.game_status = game_status
        self.date = date
        self.player_key = f"{player}_{team}".lower().replace(" ", "_").replace("/", "_")

    def to_dict(self) -> Dict[str, str]:
        return {
            "player": self.player,
            "position": self.position,
            "team": self.team,
            "injuries": self.injuries,
            "practice_status": self.practice_status,
            "game_status": self.game_status,
            "date": self.date,
            "player_key": self.player_key,
        }


def parse_game_date(date_header: str, year: int) -> str:
    """Parse game date from header like 'THURSDAY, SEPTEMBER 7TH' and return formatted date."""
    try:
        # Extract month and day from header
        # Remove day of week and extract month/day
        date_part = date_header.split(", ")[1] if ", " in date_header else date_header

        # Remove ordinal suffixes (TH, ST, ND, RD)
        date_clean = re.sub(r"(\d+)(ST|ND|RD|TH)", r"\1", date_part.upper())

        # Parse the date with the provided year
        date_str = f"{date_clean} {year}"
        parsed_date = datetime.strptime(date_str, "%B %d %Y")

        return parsed_date.strftime("%Y-%m-%d")
    except Exception as e:
        logger.warning(f"Could not parse date from '{date_header}': {e}")
        return datetime.now().strftime("%Y-%m-%d")


def scrape_injury_reports(browser: Browser, year: int, week: int) -> List[InjuryData]:
    """Scrape NFL injury reports for a specific year and week."""
    page = browser.new_page()
    all_injuries: List[InjuryData] = []

    try:
        url = f"https://www.nfl.com/injuries/league/{year}/reg{week}"
        logger.info(f"Navigating to: {url}")
        page.goto(url, timeout=60000)

        # Find the main injury report wrap
        injury_wrap = page.query_selector(".nfl-o-injury-report__wrap")
        if not injury_wrap:
            logger.warning("Could not find injury report wrap")
            return []

        # Get all elements in order (headers and units)
        all_elements = injury_wrap.query_selector_all(
            "h2.d3-o-section-title, .nfl-o-injury-report__unit"
        )

        current_date = ""

        for element in all_elements:
            # Check if this is a date header
            if element.get_attribute("class") == "d3-o-section-title":
                date_text = element.inner_text().strip()
                current_date = parse_game_date(date_text, year)
                logger.info(f"Processing games on: {current_date}")
                continue

            # This is an injury report unit
            if current_date:
                injuries_for_unit = process_injury_unit(element, current_date)
                all_injuries.extend(injuries_for_unit)

        logger.info(f"Total injury records collected: {len(all_injuries)}")
        return all_injuries

    except Exception as e:
        logger.error(f"Error scraping injury reports: {e}")
        return []
    finally:
        page.close()


def process_injury_unit(unit_element, game_date: str) -> List[InjuryData]:
    """Process a single injury report unit (one game)."""
    injuries = []

    try:
        # Process each team's injury table
        team_sections = unit_element.query_selector_all(".nfl-t-stats__title")
        injury_tables = unit_element.query_selector_all(
            ".d3-o-table--horizontal-scroll table"
        )

        for team_section, table in zip(team_sections, injury_tables):
            # Get team name from section title
            team_name_element = team_section.query_selector(
                ".d3-o-section-sub-title span"
            )
            if not team_name_element:
                continue

            team_name = team_name_element.inner_text().strip()
            logger.debug(f"Processing team: {team_name}")

            # Process injury table rows
            rows = table.query_selector_all("tbody tr")
            for row in rows:
                cells = row.query_selector_all("td")
                if len(cells) < 5:
                    continue

                # Extract player name
                player_link = cells[0].query_selector("a")
                if not player_link:
                    continue
                player_name = player_link.inner_text().strip()

                # Extract position
                position = cells[1].inner_text().strip()

                # Extract injuries - use empty string if not present
                injuries_text = cells[2].inner_text().strip()

                # Extract practice status - use empty string if not present
                practice_status = cells[3].inner_text().strip()

                # Extract game status - use empty string if not present
                game_status = cells[4].inner_text().strip()

                injury_data = InjuryData(
                    player=player_name,
                    position=position,
                    team=team_name,
                    injuries=injuries_text,
                    practice_status=practice_status,
                    game_status=game_status,
                    date=game_date,
                )
                injuries.append(injury_data)
                logger.debug(f"Added injury data for {player_name} on {game_date}")

    except Exception as e:
        logger.error(f"Error processing injury unit: {e}")

    return injuries


def save_injury_data(injuries: List[InjuryData], year: int, week: int) -> None:
    """Save injury data to Excel file."""
    if not injuries:
        logger.warning("No injury data to save")
        return

    df = pd.DataFrame([injury.to_dict() for injury in injuries])

    filename = f"injuries_{year}_week{week}.xlsx"
    df.to_excel(filename, index=False)
    logger.info(f"Saved {len(injuries)} injury records to {filename}")


def main() -> None:
    """Main function to scrape NFL injury reports."""
    parser = argparse.ArgumentParser(description="NFL Injury Reports Scraper")
    parser.add_argument(
        "--year", type=int, required=True, help="NFL season year (e.g., 2023)"
    )
    parser.add_argument(
        "--week", type=int, required=True, help="NFL week number (1-18)"
    )

    args = parser.parse_args()

    if args.week < 1 or args.week > 18:
        logger.error("Week must be between 1 and 18")
        return

    logger.info(f"Starting injury report scraping for {args.year} week {args.week}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            injuries = scrape_injury_reports(browser, args.year, args.week)
            if injuries:
                save_injury_data(injuries, args.year, args.week)
                logger.info("✅ Injury report scraping completed successfully")
            else:
                logger.warning("❌ No injury data found")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
