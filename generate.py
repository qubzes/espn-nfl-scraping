from pydantic import BaseModel, Field
from scrapegraphai.graphs import ScriptCreatorGraph


# Define the Pydantic schema for the scraped data
class Transaction(BaseModel):
    from_team: str = Field(
        description="The team the player is coming from, if applicable"
    )
    to_team: str = Field(description="The team the player is going to")
    date: str = Field(description="The date of the transaction in YYYY-MM-DD format")
    first_name: str = Field(description="The player's first name")
    last_name: str = Field(description="The player's last name")
    position: str = Field(
        description="The player's position, scraped from their player page"
    )
    transaction: str = Field(
        description="The type of transaction (e.g., Free Agent Signing)"
    )
    player_key: str = Field(
        description="A unique key formed as 'first_name_last_name_to_team'"
    )


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
Create a Python script using Playwright to scrape NFL transactions from the URL 'https://www.nfl.com/transactions/league/signings/YYYY/MM', where YYYY and MM are derived from user-provided dates. The script should handle the following requirements:

1. **Command-Line Arguments**:
   - Accept a single date via `--date YYYY-MM-DD` to scrape transactions for that specific day.
   - Accept a date range via `--start-date YYYY-MM-DD` and `--end-date YYYY-MM-DD` to scrape transactions within that range, even across multiple months.
   - If no date is provided, scrape all transactions for the current month.
   - Use Python's `argparse` to handle these arguments.

2. **Data to Scrape**:
   - From the transactions page, extract:
     - From Team (can be empty)
     - To Team
     - Date (in YYYY-MM-DD format)
     - First Name
     - Last Name
     - Transaction (e.g., Free Agent Signing)
   - For each player, navigate to their player page (linked from their name on the transactions page) to extract:
     - Position (e.g., CB for Cornerback)
   - Generate a Player Key as 'first_name_last_name_to_team' (lowercase, spaces replaced with underscores).

3. **Pagination**:
   - Handle pagination by following the 'Next Page' link until it is no longer available.
   - For each page, extract all transactions that match the user-specified date or date range.

4. **Date Range Handling**:
   - For a single date, scrape the corresponding month's transactions page and filter for the specified day.
   - For a date range, determine all months between the start and end dates (inclusive) and scrape each month's transactions page, filtering transactions within the date range.
   - Ensure dates are validated and converted to YYYY-MM-DD format.

5. **Output**:
   - Return the scraped data as a JSON list of objects, where each object follows the provided schema.
   - Save the output to a file named 'transactions.json'.

6. **Error Handling**:
   - Handle cases where the player page link is missing or inaccessible.
   - Handle network errors or missing data gracefully.
   - Include logging to track progress and errors.

7. **Example**:
   - If the user runs `python3 main.py --date 2024-05-12`, scrape transactions from 'https://www.nfl.com/transactions/league/signings/2024/5' and filter for May 12, 2024.
   - If the user runs `python3 main.py --start-date 2024-03-03 --end-date 2024-06-23`, scrape transactions from March to June 2024, filtering for transactions between March 3 and June 23.

8. **Player Page Navigation**:
   - Player names on the transactions page are links to their player pages (e.g., 'https://www.nfl.com/players/ahkello-witherspoon/').
   - Extract the position from the player page, typically found near the top (e.g., 'CB' for Ahkello Witherspoon).

9. **Performance**:
   - Use Playwright's async API for efficient scraping.
   - Implement a headless browser unless debugging is needed.
   - Close the browser properly after scraping.

Please generate a complete Playwright script that meets these requirements, using the provided schema to structure the output.
"""

# Create the ScriptCreatorGraph instance
script_creator_graph = ScriptCreatorGraph(
    prompt=prompt,
    source="https://www.nfl.com/transactions/league/signings/2023/6",
    config=graph_config,
    schema=Transaction,
)

# Run the graph to generate the Playwright script
result = script_creator_graph.run()

# Print the generated script
print(result)
