import logging
from datetime import datetime
from playwright.sync_api import sync_playwright
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting NFL roster scraping...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        logger.info("Navigating to NFL teams page...")
        page.goto("https://www.nfl.com/teams", timeout=60000)
        roster_data: list[dict[str, str]] = []

        team_selectors = page.query_selector_all(".nfl-c-custom-promo__body")
        logger.info(f"Found {len(team_selectors)} team sections")

        # First, collect all team data before navigating
        teams_data: list[dict[str, str]] = []
        for i, team_section in enumerate(team_selectors, 1):
            team_name_element = team_section.query_selector("h4 p")
            if not team_name_element:
                logger.warning(f"Team name not found for section {i}")
                continue
            team_name = team_name_element.inner_text().strip()

            team_link = team_section.query_selector(
                'a[data-link_name="1st CTA View Profile"]'
            )
            if not team_link:
                logger.warning(f"Team link not found for {team_name}")
                continue

            team_url = team_link.get_attribute("href")
            team_roster_url = f"https://www.nfl.com{team_url}roster"
            teams_data.append({
                "name": team_name,
                "roster_url": team_roster_url
            })

        # Now process each team's roster
        for i, team_data in enumerate(teams_data, 1):
            team_name = team_data["name"]
            team_roster_url = team_data["roster_url"]
            
            logger.info(
                f"Processing team {i}/{len(teams_data)}: {team_name}"
            )
            logger.debug(f"Navigating to roster: {team_roster_url}")

            page.goto(team_roster_url, timeout=60000)
            page.wait_for_load_state("domcontentloaded")

            # Get player rows from roster table
            player_rows = page.query_selector_all("tbody tr")
            logger.info(f"Found {len(player_rows)} players for {team_name}")

            # Collect all player data from current page before any navigation
            players_data: list[dict[str, str]] = []
            for j, row in enumerate(player_rows, 1):
                cols = row.query_selector_all("td")
                if len(cols) < 8:
                    logger.warning(
                        f"Insufficient columns for player {j} in {team_name}"
                    )
                    continue

                player_link_element = cols[0].query_selector(
                    "a.nfl-o-roster__player-name"
                )
                if not player_link_element:
                    logger.warning(
                        f"Player link not found for row {j} in {team_name}"
                    )
                    continue

                player_name = player_link_element.inner_text().strip()
                jersey_number = cols[1].inner_text().strip()
                position = cols[2].inner_text().strip()
                status = cols[3].inner_text().strip()
                height = cols[4].inner_text().strip()
                weight = cols[5].inner_text().strip()
                experience = cols[6].inner_text().strip()
                college = cols[7].inner_text().strip()
                player_link = player_link_element.get_attribute("href") or ""

                players_data.append({
                    "name": player_name,
                    "jersey_number": jersey_number,
                    "position": position,
                    "status": status,
                    "height": height,
                    "weight": weight,
                    "experience": experience,
                    "college": college,
                    "player_link": player_link
                })

            # Now fetch ages for each player
            for player_data in players_data:
                player_name = player_data["name"]
                logger.debug(f"Processing player: {player_name}")
                
                player_age = ""
                if player_data["player_link"]:
                    try:
                        logger.debug(f"Fetching age for {player_name}")
                        page.goto(
                            f"https://www.nfl.com{player_data['player_link']}", timeout=60000
                        )
                        page.wait_for_load_state("domcontentloaded")
                        
                        age_element = page.query_selector(
                            '.nfl-c-player-info__key:has-text("Age") + .nfl-c-player-info__value'
                        )
                        player_age = (
                            age_element.inner_text().strip()
                            if age_element
                            else "N/A"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error fetching player age for {player_name}: {e}"
                        )
                        player_age = "N/A"

                player_key = (
                    f"{player_name}_{team_name}".lower()
                    .replace(" ", "_")
                    .replace("/", "_")
                )

                roster_data.append(
                    {
                        "player": player_name,
                        "jersey_n": player_data["jersey_number"],
                        "position": player_data["position"],
                        "status": player_data["status"],
                        "team": team_name,
                        "height": player_data["height"],
                        "weight": player_data["weight"],
                        "age": player_age,
                        "experience": player_data["experience"],
                        "college": player_data["college"],
                        "player_key": player_key,
                        "date_scraped": datetime.now().strftime("%Y-%m-%d"),
                    }
                )

        logger.info(f"Scraped data for {len(roster_data)} total players")
        logger.info("Saving data to Excel file...")

        df = pd.DataFrame(roster_data)
        df.to_excel("roster_data.xlsx", index=False)

        logger.info("Data saved successfully to roster_data.xlsx")
        browser.close()
        logger.info("Scraping completed successfully")


if __name__ == "__main__":
    main()
