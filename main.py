import json
import os
from typing import List, Union, Dict
from pydantic import BaseModel, RootModel
from playwright.sync_api import sync_playwright, Browser
import pandas as pd


# Injury Models
class InjuryData(BaseModel):
    date: str
    name: str
    position: str
    status: str
    details: str


class Injuries(BaseModel):
    injuries: List[InjuryData]


# Depth Chart Models
class PositionData(BaseModel):
    position: str
    starter: str
    second: str
    third: str
    fourth: str


class DepthChartData(RootModel[Dict[str, List[PositionData]]]):
    root: Dict[str, List[PositionData]]


# Roster Models
class PlayerData(BaseModel):
    name: str
    position: str
    age: str
    height: str
    weight: str
    experience: str
    college: str


class RosterData(BaseModel):
    offense: List[PlayerData]
    defense: List[PlayerData]
    special_teams: List[PlayerData]
    injured_reserve_or_out: List[PlayerData]
    coach: str


# Transaction Models
class TransactionData(BaseModel):
    date: str
    details: str


class Transactions(RootModel[Dict[str, List[TransactionData]]]):
    root: Dict[str, List[TransactionData]]


# Team Model
class TeamData(BaseModel):
    name: str
    url: str


def scrape_teams(browser: Browser) -> List[TeamData]:
    """Scrape NFL team names and depth chart URLs using a single browser."""
    page = browser.new_page()
    try:
        page.goto(
            "https://www.espn.com/nfl/story/_/id/29098001/nfl-depth-charts-all-32-teams",
            timeout=60000,
        )
        page.wait_for_selector("article h2 a", timeout=10000)
        team_elements = page.query_selector_all("article h2 a")
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
        raise RuntimeError(f"Failed to scrape teams: {e}")
    finally:
        page.close()


def get_team_depth(
    browser: Browser, team_name: str, depth_url: str
) -> DepthChartData:
    """Get depth chart for a single NFL team using a single browser."""
    page = browser.new_page()
    try:
        page.goto(depth_url, timeout=30000)
        page.wait_for_selector(".ResponsiveTable", timeout=10000)
        formations: Dict[str, List[PositionData]] = {}
        tables = page.query_selector_all(".ResponsiveTable")
        for table in tables:
            title_element = table.query_selector(".Table__Title")
            formation_name = (
                title_element.inner_text().strip().lower().replace(" ", "_")
                if title_element
                else "unknown"
            )
            tbody_elements = table.query_selector_all("table tbody")
            if len(tbody_elements) >= 2:
                position_table = tbody_elements[0]
                player_table = tbody_elements[1]
                positions = position_table.query_selector_all("tr")
                player_rows = player_table.query_selector_all("tr")
                formation_positions: List[PositionData] = []
                for position_row, player_row in zip(positions, player_rows):
                    position_cell = position_row.query_selector("td span")
                    position = (
                        position_cell.inner_text().strip()
                        if position_cell
                        else ""
                    )
                    player_cells = player_row.query_selector_all("td")
                    players: List[str] = []
                    for cell in player_cells:
                        link = cell.query_selector("a")
                        if link:
                            players.append(link.inner_text().strip())
                        else:
                            players.append(cell.inner_text().strip())
                    while len(players) < 4:
                        players.append("")
                    position_data = PositionData(
                        position=position,
                        starter=players[0] if len(players) > 0 else "",
                        second=players[1] if len(players) > 1 else "",
                        third=players[2] if len(players) > 2 else "",
                        fourth=players[3] if len(players) > 3 else "",
                    )
                    formation_positions.append(position_data)
                formations[formation_name] = formation_positions
        return DepthChartData(root=formations)
    except Exception as e:
        raise RuntimeError(
            f"Failed to scrape depth chart for {team_name}: {e}"
        )
    finally:
        page.close()


def get_team_roster(
    browser: Browser, team_name: str, roster_url: str
) -> RosterData:
    """Scrape roster for a single NFL team using a single browser."""
    page = browser.new_page()
    try:
        page.goto(roster_url, timeout=30000)
        page.wait_for_selector("table tbody", timeout=10000)
        tables = page.query_selector_all("table tbody")
        roster = RosterData(
            offense=[],
            defense=[],
            special_teams=[],
            injured_reserve_or_out=[],
            coach="",
        )
        for idx, table in enumerate(tables):
            rows = table.query_selector_all("tr")
            players: List[PlayerData] = []
            for row in rows:
                cols = row.query_selector_all("td")
                if len(cols) >= 8:
                    name = cols[1].inner_text().strip()
                    position = cols[2].inner_text().strip()
                    age = cols[3].inner_text().strip() or ""
                    height = cols[4].inner_text().strip() or ""
                    weight = cols[5].inner_text().strip() or ""
                    experience = cols[6].inner_text().strip() or ""
                    college = cols[7].inner_text().strip() or ""
                    players.append(
                        PlayerData(
                            name=name,
                            position=position,
                            age=age,
                            height=height,
                            weight=weight,
                            experience=experience,
                            college=college,
                        )
                    )
            if idx == 0:
                roster.offense = players
            elif idx == 1:
                roster.defense = players
            elif idx == 2:
                roster.special_teams = players
            elif idx == 3:
                roster.injured_reserve_or_out = players
        coach_element = page.query_selector(".pt4")
        roster.coach = (
            coach_element.inner_text().strip().replace("Coach ", "")
            if coach_element
            else "Unknown"
        )
        return roster
    except Exception as e:
        raise RuntimeError(f"Failed to scrape roster for {team_name}: {e}")
    finally:
        page.close()


def get_team_injuries(
    browser: Browser, team_name: str, injury_url: str
) -> Injuries:
    """Scrape injury data for a single NFL team using a single browser."""
    page = browser.new_page()
    try:
        page.goto(injury_url, timeout=60000)
        page.wait_for_selector(".Card__Content", timeout=10000)
        injuries: List[InjuryData] = []
        date_elements = page.query_selector_all(".pb3.bb.bb--dotted")
        for date_element in date_elements:
            date = date_element.inner_text().strip()
            content_list = date_element.evaluate_handle(
                "element => element.nextElementSibling"
            ).as_element()
            class_attr = (
                content_list.get_attribute("class") if content_list else None
            )
            if content_list and class_attr and "ContentList" in class_attr:
                injury_items = content_list.query_selector_all(
                    ".ContentList__Item"
                )
                for item in injury_items:
                    name_element = item.query_selector(".Athlete__PlayerName")
                    position_element = item.query_selector(
                        ".Athlete__NameDetails"
                    )
                    status_element = item.query_selector(".TextStatus")
                    details_element = item.query_selector(
                        ".pt3.clr-gray-04.n8"
                    )
                    name = (
                        name_element.inner_text().strip()
                        if name_element
                        else ""
                    )
                    position = (
                        position_element.inner_text().strip()
                        if position_element
                        else ""
                    )
                    status = (
                        status_element.inner_text().strip()
                        if status_element
                        else ""
                    )
                    details = (
                        details_element.inner_text().strip()
                        if details_element
                        else ""
                    )
                    injury_data = InjuryData(
                        date=date,
                        name=name,
                        position=position,
                        status=status,
                        details=details,
                    )
                    injuries.append(injury_data)
        return Injuries(injuries=injuries)
    except Exception as e:
        raise RuntimeError(f"Failed to scrape injuries for {team_name}: {e}")
    finally:
        page.close()


def get_team_transactions(
    browser: Browser, team_name: str, transaction_url: str
) -> Transactions:
    """Scrape transaction data for a single NFL team using a single browser."""
    page = browser.new_page()
    try:
        page.goto(transaction_url, timeout=60000)
        page.wait_for_selector(".ResponsiveTable", timeout=10000)
        transactions: Dict[str, List[TransactionData]] = {}
        tables = page.query_selector_all(".ResponsiveTable")
        for table in tables:
            month_element = table.query_selector(".Table__Title")
            if not month_element:
                continue
            month = month_element.inner_text().strip().lower()
            transactions[month] = []
            rows = table.query_selector_all("tbody tr")
            for row in rows:
                date_cell = row.query_selector("td:nth-child(1) span")
                details_cell = row.query_selector("td:nth-child(2) span")
                if date_cell and details_cell:
                    date = date_cell.inner_text().strip()
                    details = details_cell.inner_text().strip()
                    transactions[month].append(
                        TransactionData(date=date, details=details)
                    )
        return Transactions(root=transactions)
    except Exception as e:
        raise RuntimeError(
            f"Failed to scrape transactions for {team_name}: {e}"
        )
    finally:
        page.close()


def save_team_data(
    team_name: str,
    data: Union[DepthChartData, RosterData, Injuries, Transactions],
    data_type: str,
) -> None:
    """Save team data in both JSON and Excel formats with separate Excel files."""
    folder_name = f"data/{team_name.lower().replace(' ', '_')}"
    os.makedirs(folder_name, exist_ok=True)

    # Save JSON
    json_file_path = os.path.join(folder_name, f"{data_type}.json")
    with open(json_file_path, "w", encoding="utf-8") as f:
        json.dump(data.model_dump(), f, indent=2)
    print(f"Saved {data_type} to {json_file_path}")

    # Save to separate Excel file
    excel_file_path = os.path.join(folder_name, f"{data_type}.xlsx")

    if isinstance(data, DepthChartData):
        # Process DepthChartData
        all_rows: List[List[str]] = []
        for formation, positions in data.root.items():
            # Add formation as subtitle
            all_rows.append([formation.upper()])
            # Add headers
            headers = ["Position", "Starter", "Second", "Third", "Fourth"]
            all_rows.append(headers)
            # Add data
            for pos in positions:
                all_rows.append(
                    [
                        pos.position,
                        pos.starter,
                        pos.second,
                        pos.third,
                        pos.fourth,
                    ]
                )
            # Add empty row
            all_rows.append([])

    elif isinstance(data, RosterData):
        # Process RosterData
        all_rows = []
        for category in [
            "offense",
            "defense",
            "special_teams",
            "injured_reserve_or_out",
        ]:
            players = getattr(data, category)
            if players:
                # Add category as subtitle
                all_rows.append([category.upper()])
                # Add headers
                headers = [
                    "Name",
                    "Position",
                    "Age",
                    "Height",
                    "Weight",
                    "Experience",
                    "College",
                ]
                all_rows.append(headers)
                # Add data
                for player in players:
                    all_rows.append(
                        [
                            player.name,
                            player.position,
                            player.age,
                            player.height,
                            player.weight,
                            player.experience,
                            player.college,
                        ]
                    )
                # Add empty row
                all_rows.append([])
        # Add coach info
        all_rows.append(["COACH"])
        all_rows.append([data.coach])

    elif isinstance(data, Injuries):
        # Process Injuries
        all_rows = [["INJURIES"]]
        headers = ["Date", "Name", "Position", "Status", "Details"]
        all_rows.append(headers)
        for injury in data.injuries:
            all_rows.append(
                [
                    injury.date,
                    injury.name,
                    injury.position,
                    injury.status,
                    injury.details,
                ]
            )
        all_rows.append([])

    else:
        # Process Transactions
        all_rows = []
        for month, transactions in data.root.items():
            # Add month as subtitle
            all_rows.append([month.upper()])
            # Add headers
            headers = ["Date", "Details"]
            all_rows.append(headers)
            # Add data
            for transaction in transactions:
                all_rows.append([transaction.date, transaction.details])
            # Add empty row
            all_rows.append([])

    df = pd.DataFrame(all_rows)
    df.to_excel(excel_file_path, index=False, header=False)  # type: ignore

    print(f"Saved {data_type} to {excel_file_path}")


def main() -> None:
    """Main function that scrapes depth charts, rosters, injuries, and transactions for all NFL teams."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                teams = scrape_teams(browser)
                print(f"Found {len(teams)} NFL teams")
                for team in teams:
                    print(f"\nProcessing {team.name}...")
                    try:
                        # 1. Get depth chart
                        print(f"  Getting depth chart for {team.name}...")
                        depth_data = get_team_depth(
                            browser, team.name, team.url
                        )
                        save_team_data(team.name, depth_data, "depth_chart")
                        # 2. Get roster
                        print(f"  Getting roster for {team.name}...")
                        roster_url = team.url.replace("/depth/", "/roster/")
                        roster_data = get_team_roster(
                            browser, team.name, roster_url
                        )
                        save_team_data(team.name, roster_data, "roster")
                        # 3. Get injuries
                        print(f"  Getting injuries for {team.name}...")
                        injury_url = team.url.replace("/depth/", "/injuries/")
                        injury_data = get_team_injuries(
                            browser, team.name, injury_url
                        )
                        save_team_data(team.name, injury_data, "injuries")
                        # 4. Get transactions
                        print(f"  Getting transactions for {team.name}...")
                        transaction_url = team.url.replace(
                            "/depth/", "/transactions/"
                        )
                        transaction_data = get_team_transactions(
                            browser, team.name, transaction_url
                        )
                        save_team_data(
                            team.name, transaction_data, "transactions"
                        )
                        print(f"  ✅ Completed {team.name}")
                    except Exception as e:
                        print(f"  ❌ Error processing {team.name}: {e}")
                        continue
                print("\n🎉 Finished processing all teams!")
            finally:
                browser.close()
    except Exception as e:
        print(f"Fatal error: {e}")


if __name__ == "__main__":
    main()
