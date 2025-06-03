import os
from typing import Dict, List

import pandas as pd
from playwright.sync_api import Browser, sync_playwright


# Data Models
class PositionData:
    def __init__(self, position: str, starter: str, second: str, third: str, fourth: str) -> None:
        self.position = position
        self.starter = starter
        self.second = second
        self.third = third
        self.fourth = fourth

    def to_dict(self) -> Dict[str, str]:
        return {
            "position": self.position,
            "starter": self.starter,
            "second": self.second,
            "third": self.third,
            "fourth": self.fourth,
        }


class TeamData:
    def __init__(self, name: str, url: str) -> None:
        self.name = name
        self.url = url


def scrape_teams(browser: Browser) -> List[TeamData]:
    """Scrape NFL team names and depth chart URLs."""
    page = browser.new_page()
    try:
        page.goto("https://www.espn.com/nfl/story/_/id/29098001/nfl-depth-charts-all-32-teams", timeout=60000)
        team_elements = page.query_selector_all("article h2 a")[:32]
        teams = [
            TeamData(name=team.inner_text().strip(), url=team.get_attribute("href") or "")
            for team in team_elements
            if team.inner_text().strip() and team.get_attribute("href")
        ]
        return teams
    except Exception as e:
        print(f"Failed to scrape teams: {e}")
        return []
    finally:
        page.close()


def get_team_depth(browser: Browser, team_name: str, depth_url: str) -> Dict[str, List[PositionData]]:
    """Scrape depth chart for a single NFL team."""
    page = browser.new_page()
    try:
        page.goto(depth_url, timeout=30000)
        page.wait_for_selector(".ResponsiveTable", timeout=10000)
        formations: Dict[str, List[PositionData]] = {}
        tables = page.query_selector_all(".ResponsiveTable")
        for table in tables:
            title_element = table.query_selector(".Table__Title")
            formation_name = title_element.inner_text().strip().lower().replace(" ", "_") if title_element else "unknown"
            tbody_elements = table.query_selector_all("table tbody")
            if len(tbody_elements) < 2:
                continue
            position_table, player_table = tbody_elements[0], tbody_elements[1]
            positions = position_table.query_selector_all("tr")
            player_rows = player_table.query_selector_all("tr")
            formation_positions: List[PositionData] = []
            for pos_row, player_row in zip(positions, player_rows):
                pos_cell = pos_row.query_selector("td span")
                position = pos_cell.inner_text().strip() if pos_cell else ""
                player_cells = player_row.query_selector_all("td")
                players = [cell.inner_text().strip() for cell in player_cells]
                while len(players) < 4:
                    players.append("")
                formation_positions.append(
                    PositionData(
                        position=position,
                        starter=players[0],
                        second=players[1],
                        third=players[2],
                        fourth=players[3],
                    )
                )
            formations[formation_name] = formation_positions
        return formations
    except Exception as e:
        print(f"Failed to scrape depth chart for {team_name}: {e}")
        return {}
    finally:
        page.close()


def save_team_data(team_name: str, data: Dict[str, List[PositionData]]) -> None:
    """Save depth chart data in JSON and Excel formats."""
    os.makedirs("depth_chart", exist_ok=True)
    team_filename = team_name.lower().replace(' ', '_')
    excel_file_path = os.path.join("depth_chart", f"{team_filename}.xlsx")
    all_rows: List[List[str]] = []
    for formation, positions in data.items():
        all_rows.append([formation.upper()])
        all_rows.append(["Position", "Starter", "Second", "Third", "Fourth"])
        for pos in positions:
            all_rows.append([pos.position, pos.starter, pos.second, pos.third, pos.fourth])
        all_rows.append([])
    pd.DataFrame(all_rows).to_excel(excel_file_path, index=False, header=False)
    print(f"Saved depth chart to {excel_file_path}")


def main() -> None:
    """Scrape and save depth charts for all NFL teams."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            teams = scrape_teams(browser)
            print(f"Found {len(teams)} NFL teams")
            for team in teams:
                print(f"Processing {team.name}...")
                depth_data = get_team_depth(browser, team.name, team.url)
                if depth_data:
                    save_team_data(team.name, depth_data)
                    print(f"✅ Completed {team.name}")
                else:
                    print(f"❌ No depth chart data for {team.name}")
        except Exception as e:
            print(f"Fatal error: {e}")
        finally:
            browser.close()
    print("🎉 Finished processing all teams!")



if __name__ == "__main__":
    main()