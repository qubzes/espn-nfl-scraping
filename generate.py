from pydantic import BaseModel, Field
from scrapegraphai.graphs import ScriptCreatorGraph


# Define the Pydantic schema for the scraped roster data
class Player(BaseModel):
   player: str = Field(description="The player's full name")
   jersey_n: str = Field(description="The player's jersey number")
   position: str = Field(description="The player's position")
   team: str = Field(description="The team name")
   height: str = Field(description="The player's height")
   weight: str = Field(description="The player's weight")
   age: str = Field(description="The player's age (scraped from individual player page)")
   experience: str = Field(description="The player's years of experience")
   college: str = Field(description="The college the player attended")
   player_key: str = Field(description="A unique key formed as 'player_name_team' (lowercase, spaces replaced with underscores)")
   date_scraped: str = Field(description="The date when data was scraped in YYYY-MM-DD format")


# Graph configuration
graph_config = {
   "llm": {
      "model": "openai/gpt-4o",
      "api_key": "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",
   },
   "library": "playwright",
}

# Detailed prompt for ScriptCreatorGraph
prompt = """
Create a Python script using Playwright to scrape NFL team rosters. The script should:

1. **Team Collection**:
   - First scrape NFL.com to extract all 32 team URLs from the teams navigation section
   - Each team link follows the pattern: href="/teams/[team-slug]"
   - Extract team names and their corresponding URLs

2. **Roster Scraping**:
   - For each team, visit their roster page: https://www.nfl.com/teams/[team-slug]/roster
   - Extract player data from the roster table including:
    - Player name
    - Jersey number
    - Position
    - Height
    - Weight
    - Experience
    - College

3. **Player Age Extraction**:
   - For each player, navigate to their individual player page (linked from their name on the roster)
   - Extract the player's age from their profile page
   - Handle cases where player links may be missing or inaccessible

4. **Data Structure**:
   - Create a player_key as 'player_name_team' (lowercase, spaces/special chars replaced with underscores)
   - Add current date as date_scraped in YYYY-MM-DD format
   - Structure data according to the provided Player schema

5. **Command Line Options**:
   - Accept --team argument to scrape specific team (e.g. --team "buffalo-bills")
   - If no team specified, scrape all 32 teams
   - Accept --output argument to specify output filename (default: roster_data.json)

6. **Error Handling & Performance**:
   - Use async Playwright for efficient scraping
   - Implement retry logic for failed requests
   - Add logging to track progress
   - Handle missing data gracefully
   - Use headless browser mode
   - Properly close browser after completion

7. **Output**:
   - Save data as JSON array of player objects
   - Include summary of total players scraped per team

The script should be robust, handle edge cases, and provide clear progress feedback during execution.
"""

# Create the ScriptCreatorGraph instance
script_creator_graph = ScriptCreatorGraph(
   prompt=prompt,
   source="https://www.nfl.com/teams",
   config=graph_config,
   schema=Player,
)

# Run the graph to generate the Playwright script
result = script_creator_graph.run()

# Print the generated script
print(result)
