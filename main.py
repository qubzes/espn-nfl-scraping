import os
from typing import Any, Dict, List

from pydantic import BaseModel, Field
from scrapegraphai.graphs import SmartScraperGraph  # type: ignore


class TeamData(BaseModel):
    name: str = Field(description="NFL team name")
    url: str = Field(description="Team depth chart URL")


class TeamsResponse(BaseModel):
    teams: List[TeamData] = Field(description="List of NFL teams")


def scrape_nfl_teams() -> TeamsResponse:
    """Scrape NFL team names and depth chart URLs from ESPN."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    config: Dict[str, Any] = {
        "llm": {"api_key": api_key, "model": "openai/gpt-4o-mini"},
        "headless": True,
        "verbose": True,
    }

    scraper = SmartScraperGraph(
        prompt="Extract NFL team names and their depth chart URLs as JSON: {'teams': [{'name': str, 'url': str}]}",
        source="https://www.espn.com/nfl/story/_/id/29098001/nfl-depth-charts-all-32-teams",
        config=config,
        schema=TeamsResponse,
    )

    result = scraper.run()

    return TeamsResponse.model_validate(result)


def main() -> None:
    try:
        response = scrape_nfl_teams()
        print(f"Found {len(response.teams)} NFL teams:")
        print(response.model_dump_json(indent=2))
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
