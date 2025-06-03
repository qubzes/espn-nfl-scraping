import os
from datetime import datetime
from typing import Dict, List

import pandas as pd
from playwright.sync_api import Browser, sync_playwright

# Position abbreviation to full name mapping
POSITION_MAPPING = {
    "LDE": "Left Defensive End",
    "LDT": "Left Defensive Tackle",
    "RDT": "Right Defensive Tackle",
    "RDE": "Right Defensive End",
    "WLB": "Weakside Linebacker",
    "MLB": "Middle Linebacker",
    "SLB": "Strongside Linebacker",
    "LCB": "Left Cornerback",
    "SS": "Strong Safety",
    "FS": "Free Safety",
    "RCB": "Right Cornerback",
    "NB": "Nickel Back",
    "PK": "Place Kicker",
    "P": "Punter",
    "H": "Holder",
    "PR": "Punt Returner",
    "KR": "Kick Returner",
    "LS": "Long Snapper",
    "WR": "Wide Receiver",
    "LT": "Left Tackle",
    "LG": "Left Guard",
    "C": "Center",
    "RG": "Right Guard",
    "RT": "Right Tackle",
    "QB": "Quarterback",
    "TE": "Tight End",
    "RB": "Running Back",
    "FB": "Fullback",
}


# Data Models
class PlayerDepthData:
    def __init__(
        self,
        player_name: str,
        position: str,
        depth_order: str,
        team: str,
        scraped_date: str,
    ) -> None:
        self.player_name = player_name
        self.position = position
        self.depth_order = depth_order
        self.team = team
        self.scraped_date = scraped_date
        self.player_key = (
            f"{player_name}_{team}".lower().replace(" ", "_").replace("/", "_")
        )

    def to_dict(self) -> Dict[str, str]:
        return {
            "player_name": self.player_name,
            "position": self.position,
            "depth_order": self.depth_order,
            "team": self.team,
            "scraped_date": self.scraped_date,
            "player_key": self.player_key,
        }


class TeamData:
    def __init__(self, name: str, url: str) -> None:
        self.name = name
        self.url = url


def scrape_teams(browser: Browser) -> List[TeamData]:
    """Scrape NFL team names and depth chart URLs."""
    page = browser.new_page()
    try:
        page.goto(
            "https://www.espn.com/nfl/story/_/id/29098001/nfl-depth-charts-all-32-teams",
            timeout=60000,
        )
        team_elements = page.query_selector_all("article h2 a")[:32]
        teams = [
            TeamData(
                name=team.inner_text().strip(),
                url=team.get_attribute("href") or "",
            )
            for team in team_elements
            if team.inner_text().strip() and team.get_attribute("href")
        ]
        return teams
    except Exception as e:
        print(f"Failed to scrape teams: {e}")
        return []
    finally:
        page.close()


def get_team_depth(
    browser: Browser, team_name: str, depth_url: str
) -> List[PlayerDepthData]:
    """Scrape depth chart for a single NFL team."""
    page = browser.new_page()
    scraped_date = datetime.now().strftime("%Y-%m-%d")

    try:
        page.goto(depth_url, timeout=30000)
        page.wait_for_selector(".ResponsiveTable", timeout=10000)
        all_players: List[PlayerDepthData] = []
        tables = page.query_selector_all(".ResponsiveTable")

        for table in tables:
            tbody_elements = table.query_selector_all("table tbody")
            if len(tbody_elements) < 2:
                continue

            position_table, player_table = tbody_elements[0], tbody_elements[1]
            positions = position_table.query_selector_all("tr")
            player_rows = player_table.query_selector_all("tr")

            for pos_row, player_row in zip(positions, player_rows):
                pos_cell = pos_row.query_selector("td span")
                position_abbr = pos_cell.inner_text().strip() if pos_cell else ""
                # Convert abbreviation to full position name
                position = POSITION_MAPPING.get(position_abbr, position_abbr)

                player_cells = player_row.query_selector_all("td")

                depth_labels = ["starter", "second", "third", "fourth"]
                for i, cell in enumerate(player_cells[:4]):
                    # Look for anchor link (player name) within the cell
                    player_link = cell.query_selector("a.AnchorLink")
                    if player_link:
                        player_name = player_link.inner_text().strip()
                        # Skip if player name is just "-" or empty
                        if player_name and player_name != "-":
                            all_players.append(
                                PlayerDepthData(
                                    player_name=player_name,
                                    position=position,
                                    depth_order=depth_labels[i],
                                    team=team_name,
                                    scraped_date=scraped_date,
                                )
                            )

        return all_players
    except Exception as e:
        print(f"Failed to scrape depth chart for {team_name}: {e}")
        return []
    finally:
        page.close()


def save_all_data(all_data: List[PlayerDepthData]) -> None:
    """Save all depth chart data to a single Excel file."""
    df = pd.DataFrame([player.to_dict() for player in all_data])
    excel_file_path = "depth_chart.xlsx"
    df.to_excel(excel_file_path, index=False)
    print(f"Saved all depth chart data to {excel_file_path}")


def main() -> None:
    """Scrape and save depth charts for all NFL teams."""
    all_player_data: List[PlayerDepthData] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            teams = scrape_teams(browser)
            print(f"Found {len(teams)} NFL teams")

            for team in teams:
                print(f"Processing {team.name}...")
                depth_data = get_team_depth(browser, team.name, team.url)
                if depth_data:
                    all_player_data.extend(depth_data)
                    print(f"✅ Completed {team.name} - {len(depth_data)} players")
                else:
                    print(f"❌ No depth chart data for {team.name}")

            if all_player_data:
                save_all_data(all_player_data)
                print(f"Total players processed: {len(all_player_data)}")

        except Exception as e:
            print(f"Fatal error: {e}")
        finally:
            browser.close()

    print("🎉 Finished processing all teams!")


if __name__ == "__main__":
    main()
