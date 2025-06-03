from datetime import datetime
from playwright.sync_api import sync_playwright
import pandas as pd


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto("https://www.nfl.com/teams", timeout=60000)
        roster_data: list[dict[str, str]] = []

        team_selectors = page.query_selector_all(".nfl-c-custom-promo__body")
        for team_section in team_selectors:
            team_name_element = team_section.query_selector("h4 p")
            if not team_name_element:
                continue
            team_name = team_name_element.inner_text().strip()

            team_link = team_section.query_selector(
                'a[data-link_name="1st CTA View Profile"]'
            )
            if not team_link:
                continue
            team_url = team_link.get_attribute("href")
            team_roster_url = f"https://www.nfl.com{team_url}roster"

            page.goto(team_roster_url, timeout=60000)

            # Get player rows from roster table
            player_rows = page.query_selector_all("tbody tr")

            for row in player_rows:
                cols = row.query_selector_all("td")
                if len(cols) < 8:
                    continue

                player_link_element = cols[0].query_selector(
                    "a.nfl-o-roster__player-name"
                )
                if not player_link_element:
                    continue

                player_name = player_link_element.inner_text().strip()
                jersey_number = cols[1].inner_text().strip()
                position = cols[2].inner_text().strip()
                status = cols[3].inner_text().strip()
                height = cols[4].inner_text().strip()
                weight = cols[5].inner_text().strip()
                experience = cols[6].inner_text().strip()
                college = cols[7].inner_text().strip()
                player_age = ""

                player_link = player_link_element.get_attribute("href")
                if player_link:
                    try:
                        page.goto(
                            f"https://www.nfl.com{player_link}", timeout=60000
                        )
                        age_element = page.query_selector(
                            '.nfl-c-player-info__key:has-text("Age") + .nfl-c-player-info__value'
                        )
                        player_age = (
                            age_element.inner_text().strip()
                            if age_element
                            else "N/A"
                        )
                    except Exception as e:
                        print(
                            f"Error fetching player age for {player_name}: {e}"
                        )
                        pass

                player_key = (
                    f"{player_name}_{team_name}".lower()
                    .replace(" ", "_")
                    .replace("/", "_")
                )

                roster_data.append(
                    {
                        "player": player_name,
                        "jersey_n": jersey_number,
                        "position": position,
                        "status": status,
                        "team": team_name,
                        "height": height,
                        "weight": weight,
                        "age": player_age,
                        "experience": experience,
                        "college": college,
                        "player_key": player_key,
                        "date_scraped": datetime.now().strftime("%Y-%m-%d"),
                    }
                )

        df = pd.DataFrame(roster_data)
        df.to_excel("roster_data.xlsx", index=False)

        browser.close()


if __name__ == "__main__":
    main()
