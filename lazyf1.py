#!/usr/bin/env python3

import os
import logging
import fastf1
import pandas as pd
from datetime import datetime
from rich.table import Table
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text
from rich.align import Align
from rich.console import RenderableType
from textual.app import App
from textual.widgets import Header, Footer, Static, Button, LoadingIndicator
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.binding import Binding

# Set up logging to file
log_dir = os.path.join(os.path.expanduser("~"), ".f1dashboard")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "f1dashboard.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=log_file,
    filemode='a'
)

# Redirect FastF1 logs
for logger_name in ["fastf1", "fastf1.core", "fastf1.api", "fastf1.ergast", "fastf1.plotting"]:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    # Add file handler
    handler = logging.FileHandler(log_file)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

# Create cache directory if it doesn't exist
cache_dir = os.path.join(log_dir, "cache")
os.makedirs(cache_dir, exist_ok=True)

# Enable FastF1 cache
fastf1.Cache.enable_cache(cache_dir)

# Define TokyoNight colors
TOKYO_NIGHT = {
    "background": "#1a1b26",
    "foreground": "#c0caf5",
    "black": "#15161e",
    "red": "#f7768e",
    "green": "#9ece6a",
    "yellow": "#e0af68",
    "blue": "#7aa2f7",
    "magenta": "#bb9af7",
    "cyan": "#7dcfff",
    "white": "#a9b1d6",
    "bright_black": "#414868",
    "bright_red": "#f7768e",
    "bright_green": "#9ece6a",
    "bright_yellow": "#e0af68",
    "bright_blue": "#7aa2f7",
    "bright_magenta": "#bb9af7",
    "bright_cyan": "#7dcfff",
    "bright_white": "#c0caf5",
    "accent": "#7aa2f7"
}

class LoadingState:
    """Class to manage loading state for widgets"""
    def __init__(self):
        self.is_loading = False
        self.loading_message = ""
        self.callbacks = []

    def set_loading(self, is_loading, message="Loading data..."):
        self.is_loading = is_loading
        self.loading_message = message
        for callback in self.callbacks:
            callback(is_loading, message)

    def add_callback(self, callback):
        self.callbacks.append(callback)


class F1Data:
    def __init__(self):
        self.current_year = datetime.now().year
        self.selected_race_index = -1  # -1 means most recent race
        self.loading_state = LoadingState()

    def get_driver_standings(self):
        """Get current driver standings"""
        self.loading_state.set_loading(True, "Fetching driver standings...")
        try:
            # Use ergast API directly through fastf1 since get_driver_standings doesn't exist
            # Load the most recent race to get standings
            # Get all races in the current year
            schedule = fastf1.get_event_schedule(self.current_year)
            completed_races = schedule[schedule['EventDate'] < pd.Timestamp(datetime.now())]

            if completed_races.empty:
                self.loading_state.set_loading(False)
                return [{"position": "N/A", "driver": "No completed races", "team": "", "points": "", "wins": ""}]

            # Get the most recent race
            last_race = completed_races.iloc[-1]

            # Load the race session
            session = fastf1.get_session(
                self.current_year,
                last_race['RoundNumber'],
                'R'
            )
            session.load(telemetry=False, weather=False)

            # Get driver standings
            results = session.results[['DriverNumber', 'FirstName', 'LastName', 'TeamName', 'Points']]

            # Get all drivers' season points
            drivers_season_points = {}
            for event in completed_races['RoundNumber']:
                try:
                    race = fastf1.get_session(self.current_year, event, 'R')
                    race.load(telemetry=False, weather=False)

                    for _, row in race.results.iterrows():
                        driver = f"{row['FirstName']} {row['LastName']}"
                        if driver not in drivers_season_points:
                            drivers_season_points[driver] = {
                                'points': 0,
                                'wins': 0,
                                'team': row['TeamName']
                            }

                        drivers_season_points[driver]['points'] += row['Points']
                        if row['Position'] == 1:
                            drivers_season_points[driver]['wins'] += 1
                except:
                    continue

            # Sort by points
            sorted_drivers = sorted(drivers_season_points.items(),
                                   key=lambda x: x[1]['points'],
                                   reverse=True)

            # Create standings
            standings = []
            for i, (driver, data) in enumerate(sorted_drivers):
                standings.append({
                    "position": i + 1,
                    "driver": driver,
                    "team": data['team'],
                    "points": data['points'],
                    "wins": data['wins']
                })

            self.loading_state.set_loading(False)
            return standings
        except Exception as e:
            logging.error(f"Error getting driver standings: {e}")
            self.loading_state.set_loading(False)
            return [{"position": "Error", "driver": "Failed to load data", "team": "", "points": "", "wins": ""}]

    def get_team_standings(self):
        """Get current constructor standings"""
        self.loading_state.set_loading(True, "Fetching team standings...")
        try:
            # Use the same approach as driver standings
            # Get all races in the current year
            schedule = fastf1.get_event_schedule(self.current_year)
            completed_races = schedule[schedule['EventDate'] < pd.Timestamp(datetime.now())]

            if completed_races.empty:
                self.loading_state.set_loading(False)
                return [{"position": "N/A", "team": "No completed races", "nationality": "", "points": "", "wins": ""}]

            # Collect team data
            teams_data = {}
            for event in completed_races['RoundNumber']:
                try:
                    race = fastf1.get_session(self.current_year, event, 'R')
                    race.load(telemetry=False, weather=False)

                    for _, row in race.results.iterrows():
                        team = row['TeamName']
                        if team not in teams_data:
                            teams_data[team] = {
                                'points': 0,
                                'wins': 0,
                                'nationality': self._get_team_nationality(team)
                            }

                        teams_data[team]['points'] += row['Points']
                        if row['Position'] == 1:
                            teams_data[team]['wins'] += 1
                except:
                    continue

            # Sort by points
            sorted_teams = sorted(teams_data.items(),
                                 key=lambda x: x[1]['points'],
                                 reverse=True)

            # Create standings
            standings = []
            for i, (team, data) in enumerate(sorted_teams):
                standings.append({
                    "position": i + 1,
                    "team": team,
                    "nationality": data['nationality'],
                    "points": data['points'],
                    "wins": data['wins']
                })

            self.loading_state.set_loading(False)
            return standings
        except Exception as e:
            logging.error(f"Error getting team standings: {e}")
            self.loading_state.set_loading(False)
            return [{"position": "Error", "team": "Failed to load data", "nationality": "", "points": "", "wins": ""}]

    def _get_team_nationality(self, team_name):
        """Map team name to nationality (simplified)"""
        nationalities = {
            "Red Bull Racing": "Austrian",
            "Mercedes": "German",
            "Ferrari": "Italian",
            "McLaren": "British",
            "Aston Martin": "British",
            "Alpine": "French",
            "Williams": "British",
            "AlphaTauri": "Italian",
            "Haas F1 Team": "American",
            "Alfa Romeo": "Swiss",
            "Racing Bulls": "Italian",
            "Kick Sauber": "Swiss"
        }
        return nationalities.get(team_name, "Unknown")

    def get_race_schedule(self):
        """Get race schedule for the current season"""
        self.loading_state.set_loading(True, "Fetching race schedule...")
        try:
            # Get race schedule
            schedule = fastf1.get_event_schedule(self.current_year)

            # Convert to list of dicts for easier handling
            races = []
            for _, row in schedule.iterrows():
                status = "Upcoming"
                if pd.Timestamp(datetime.now()) > row['EventDate']:
                    status = "Completed"
                elif pd.Timestamp(datetime.now()) > row.get('Session5DateUtc', pd.NaT):
                    status = "In Progress"

                # Make sure to use the correct column names from the dataframe
                races.append({
                    "round": row["RoundNumber"],
                    "name": row["EventName"],
                    "circuit": row["Location"],  # Use Location instead of CircuitName
                    "date": row["EventDate"].strftime("%Y-%m-%d"),
                    "status": status
                })

            self.loading_state.set_loading(False)
            return races
        except Exception as e:
            logging.error(f"Error getting race schedule: {e}")
            self.loading_state.set_loading(False)
            return [{"round": "Error", "name": "Failed to load data", "circuit": "", "date": "", "status": ""}]

    def get_completed_races(self):
        """Get list of completed races"""
        try:
            schedule = fastf1.get_event_schedule(self.current_year)
            completed_races = schedule[schedule['EventDate'] < pd.Timestamp(datetime.now())]
            return completed_races
        except Exception as e:
            logging.error(f"Error getting completed races: {e}")
            return pd.DataFrame()

    def get_race_results(self, race_index=None):
        """Get results from a specific race or the last completed race if race_index is None"""
        self.loading_state.set_loading(True, "Fetching race results...")
        try:
            completed_races = self.get_completed_races()

            if completed_races.empty:
                self.loading_state.set_loading(False)
                return [{"position": "N/A", "driver": "No completed races", "team": "", "time": "", "points": ""}]

            # If race_index is None or -1, get the most recent race
            if race_index is None or race_index == -1:
                race = completed_races.iloc[-1]
                race_name = race['EventName']
            else:
                # Otherwise get the specified race (clamp to valid indices)
                idx = max(0, min(race_index, len(completed_races) - 1))
                race = completed_races.iloc[idx]
                race_name = race['EventName']

            # Get results from that race
            session = fastf1.get_session(
                self.current_year,
                race['RoundNumber'],
                'R'
            )
            session.load(telemetry=False, weather=False)

            results = session.results

            # Format results
            race_results = []
            for _, row in results.iterrows():
                race_results.append({
                    "position": row["Position"] if not pd.isna(row["Position"]) else "DNF",
                    "driver": f"{row['FirstName']} {row['LastName']}",
                    "team": row["TeamName"],
                    "time": str(row["Time"]) if not pd.isna(row["Time"]) else "DNF",
                    "points": row["Points"],
                    "race_name": race_name  # Include race name for display
                })

            self.loading_state.set_loading(False)
            return race_results
        except Exception as e:
            logging.error(f"Error getting race results: {e}")
            self.loading_state.set_loading(False)
            return [{"position": "Error", "driver": "Failed to load data", "team": "", "time": "", "points": "", "race_name": "Error"}]


class EnhancedLoadingIndicator(Static):
    """A more visible loading indicator"""
    def __init__(self, message: str = "Loading...", spinner_type: str = "dots12", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message
        self.spinner_type = spinner_type

    def on_mount(self):
        self.update_timer = self.set_interval(0.1, self.refresh)
        self.refresh()

    def refresh(self):
        spinner = Spinner(self.spinner_type, text=self.message)
        self.update(Align.center(spinner))


class LoadableWidget(Static):
    """Base class for widgets that can show loading state"""
    def __init__(self, *args, loading_state=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.loading_state = loading_state
        self.is_loading = False
        self.loading_message = "Loading..."
        if loading_state:
            loading_state.add_callback(self.on_loading_changed)

    def on_loading_changed(self, is_loading, message):
        self.is_loading = is_loading
        self.loading_message = message
        self.update_content()


class DriverStandingsWidget(LoadableWidget):
    def on_mount(self):
        self.update_timer = self.set_interval(300, self.update_content)
        self.update_content()

    def update_content(self):
        if self.is_loading:
            content = Vertical(
                EnhancedLoadingIndicator(self.loading_message, spinner_type="point"),
                Text("Please wait...", style=TOKYO_NIGHT["white"]),
                classes="loading-container"
            )
            self.update(Panel(content,
                              title="Driver Standings",
                              border_style=TOKYO_NIGHT["blue"]))
            return

        f1_data = F1Data()
        standings = f1_data.get_driver_standings()

        table = Table(title=f"Driver Standings {f1_data.current_year}")
        table.add_column("Pos", justify="right", style=TOKYO_NIGHT["cyan"])
        table.add_column("Driver", style=TOKYO_NIGHT["green"])
        table.add_column("Team", style=TOKYO_NIGHT["yellow"])
        table.add_column("Points", justify="right", style=TOKYO_NIGHT["magenta"])
        table.add_column("Wins", justify="right", style=TOKYO_NIGHT["red"])

        for driver in standings:
            table.add_row(
                str(driver["position"]),
                driver["driver"],
                driver["team"],
                str(driver["points"]),
                str(driver["wins"])
            )

        self.update(Panel(table, border_style=TOKYO_NIGHT["blue"]))


class TeamStandingsWidget(LoadableWidget):
    def on_mount(self):
        self.update_timer = self.set_interval(300, self.update_content)
        self.update_content()

    def update_content(self):
        if self.is_loading:
            content = Vertical(
                EnhancedLoadingIndicator(self.loading_message, spinner_type="point"),
                Text("Please wait...", style=TOKYO_NIGHT["white"]),
                classes="loading-container"
            )
            self.update(Panel(content,
                              title="Constructor Standings",
                              border_style=TOKYO_NIGHT["green"]))
            return

        f1_data = F1Data()
        standings = f1_data.get_team_standings()

        table = Table(title=f"Constructor Standings {f1_data.current_year}")
        table.add_column("Pos", justify="right", style=TOKYO_NIGHT["cyan"])
        table.add_column("Team", style=TOKYO_NIGHT["green"])
        table.add_column("Nationality", style=TOKYO_NIGHT["yellow"])
        table.add_column("Points", justify="right", style=TOKYO_NIGHT["magenta"])
        table.add_column("Wins", justify="right", style=TOKYO_NIGHT["red"])

        for team in standings:
            table.add_row(
                str(team["position"]),
                team["team"],
                team["nationality"],
                str(team["points"]),
                str(team["wins"])
            )

        self.update(Panel(table, border_style=TOKYO_NIGHT["green"]))


class RaceScheduleWidget(LoadableWidget):
    def on_mount(self):
        self.update_timer = self.set_interval(300, self.update_content)
        self.update_content()

    def update_content(self):
        if self.is_loading:
            content = Vertical(
                EnhancedLoadingIndicator(self.loading_message, spinner_type="point"),
                Text("Please wait...", style=TOKYO_NIGHT["white"]),
                classes="loading-container"
            )
            self.update(Panel(content,
                              title="Race Schedule",
                              border_style=TOKYO_NIGHT["yellow"]))
            return

        f1_data = F1Data()
        races = f1_data.get_race_schedule()

        table = Table(title=f"Race Schedule {f1_data.current_year}")
        table.add_column("Round", justify="right", style=TOKYO_NIGHT["cyan"])
        table.add_column("Grand Prix", style=TOKYO_NIGHT["green"])
        table.add_column("Circuit", style=TOKYO_NIGHT["yellow"])
        table.add_column("Date", style=TOKYO_NIGHT["magenta"])
        table.add_column("Status", style=TOKYO_NIGHT["red"])

        for race in races:
            status_style = TOKYO_NIGHT["green"] if race["status"] == "Completed" else TOKYO_NIGHT["yellow"] if race["status"] == "In Progress" else TOKYO_NIGHT["blue"]
            table.add_row(
                str(race["round"]),
                race["name"],
                race["circuit"],
                race["date"],
                f"[{status_style}]{race['status']}[/]"
            )

        self.update(Panel(table, border_style=TOKYO_NIGHT["yellow"]))


class RaceResultsWidget(LoadableWidget):
    race_index = reactive(-1)  # -1 means most recent race

    def on_mount(self):
        self.update_timer = self.set_interval(300, self.update_content)
        self.update_content()

    def watch_race_index(self, race_index):
        """React when race_index changes"""
        self.update_content()

    def previous_race(self):
        """Navigate to previous race"""
        f1_data = F1Data()
        completed_races = f1_data.get_completed_races()

        # If we're already showing the first race, don't go further back
        if self.race_index == 0:
            return

        # If we're showing the most recent race, set to second-to-last race
        if self.race_index == -1:
            self.race_index = len(completed_races) - 2
        else:
            # Otherwise just move back one race
            self.race_index = max(0, self.race_index - 1)

    def next_race(self):
        """Navigate to next race"""
        f1_data = F1Data()
        completed_races = f1_data.get_completed_races()

        # If already at most recent race, don't change
        if self.race_index == -1:
            return

        # Move to next race
        if self.race_index < len(completed_races) - 1:
            self.race_index += 1

        # If we reached the last race, set to -1 to indicate most recent
        if self.race_index == len(completed_races) - 1:
            self.race_index = -1

    def update_content(self):
        if self.is_loading:
            content = Vertical(
                EnhancedLoadingIndicator(self.loading_message, spinner_type="point"),
                Text("Please wait...", style=TOKYO_NIGHT["white"]),
                classes="loading-container"
            )
            self.update(Panel(content,
                              title="Race Results",
                              border_style=TOKYO_NIGHT["red"]))
            return

        f1_data = F1Data()
        results = f1_data.get_race_results(self.race_index)

        race_name = results[0].get("race_name", "") if results else ""
        title = f"Race Results {race_name} {f1_data.current_year}"

        table = Table(title=title)
        table.add_column("Pos", justify="right", style=TOKYO_NIGHT["cyan"])
        table.add_column("Driver", style=TOKYO_NIGHT["green"])
        table.add_column("Team", style=TOKYO_NIGHT["yellow"])
        table.add_column("Time", style=TOKYO_NIGHT["magenta"])
        table.add_column("Points", justify="right", style=TOKYO_NIGHT["red"])

        for result in results:
            table.add_row(
                str(result["position"]),
                result["driver"],
                result["team"],
                str(result["time"]),
                str(result["points"])
            )

        self.update(Panel(table, border_style=TOKYO_NIGHT["red"]))


class GlobalLoadingOverlay(Static):
    """A global overlay for loading state"""
    DEFAULT_CSS = """
    GlobalLoadingOverlay {
        background: rgba(26, 27, 38, 0.8);
        align: center middle;
    }

    .spinner-container {
        background: #1a1b26;
        border: solid #7aa2f7;
        width: 50%;
        height: 15;
        align: center middle;
        padding: 1;
    }
    """

    def __init__(self, loading_state, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loading_state = loading_state
        self.loading_state.add_callback(self.on_loading_changed)
        self.visible = False

    def on_mount(self):
        self.update_loading(False, "")

    def on_loading_changed(self, is_loading, message):
        self.update_loading(is_loading, message)

    def update_loading(self, is_loading, message):
        if is_loading:
            content = Vertical(
                EnhancedLoadingIndicator(message, spinner_type="dots12"),
                Text("Processing data...", style=TOKYO_NIGHT["bright_white"]),
                Text("This may take a moment", style=TOKYO_NIGHT["white"]),
                classes="spinner-container"
            )
            self.update(content)
            self.visible = True
            self.styles.display = "block"
        else:
            self.visible = False
            self.styles.display = "none"


class StatusBar(Static):
    """Status bar to show application state"""
    def __init__(self, loading_state, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loading_state = loading_state
        self.loading_state.add_callback(self.on_loading_changed)

    def on_mount(self):
        self.update_status(False, "")

    def on_loading_changed(self, is_loading, message):
        self.update_status(is_loading, message)

    def update_status(self, is_loading, message):
        if is_loading:
            status = Text.assemble(
                ("⟳ ", TOKYO_NIGHT["yellow"]),
                (message, TOKYO_NIGHT["bright_white"]),
                (" | Logs: ", TOKYO_NIGHT["white"]),
                (log_file, TOKYO_NIGHT["cyan"])
            )
        else:
            status = Text.assemble(
                ("✓ ", TOKYO_NIGHT["green"]),
                ("Ready", TOKYO_NIGHT["bright_white"]),
                (" | Logs: ", TOKYO_NIGHT["white"]),
                (log_file, TOKYO_NIGHT["cyan"])
            )

        self.update(status)


class RaceNavigationBar(Horizontal):
    def compose(self):
        yield Button("← Previous Race (P)", id="prev_race", variant="primary")
        yield Button("Next Race (N) →", id="next_race", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "prev_race":
            self.app.query_one(RaceResultsWidget).previous_race()
        elif event.button.id == "next_race":
            self.app.query_one(RaceResultsWidget).next_race()


class F1DashboardApp(App):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "previous_race", "Previous Race"),
        Binding("n", "next_race", "Next Race"),
        Binding("r", "refresh", "Refresh Data"),
        Binding("1", "focus_drivers", "Driver Standings"),
        Binding("2", "focus_teams", "Team Standings"),
        Binding("3", "focus_schedule", "Race Schedule"),
        Binding("4", "focus_results", "Race Results"),
        Binding("tab", "focus_next", "Next Panel", show=False),
        Binding("shift+tab", "focus_previous", "Previous Panel", show=False),
    ]

    CSS = f"""
    Screen {{
        background: {TOKYO_NIGHT["background"]};
        color: {TOKYO_NIGHT["foreground"]};
    }}

    #dashboard {{
        layout: grid;
        grid-size: 2 2;
        grid-gutter: 1 1;
        height: 90%;
        margin: 1;
    }}

    #navigation {{
        dock: bottom;
        height: 3;
        align: center middle;
        background: {TOKYO_NIGHT["black"]};
        padding: 1;
    }}

    #status_bar {{
        dock: bottom;
        height: 1;
        background: {TOKYO_NIGHT["black"]};
        color: {TOKYO_NIGHT["bright_white"]};
        padding: 0 1;
    }}

    Button {{
        margin: 0 2;
        background: {TOKYO_NIGHT["bright_black"]};
        color: {TOKYO_NIGHT["foreground"]};
    }}

    Button:hover {{
        background: {TOKYO_NIGHT["blue"]};
    }}

    LoadingIndicator {{
        color: {TOKYO_NIGHT["yellow"]};
    }}

    .loading-container {{
        width: 100%;
        height: 100%;
        align: center middle;
        padding: 1;
    }}

    Static:focus {{
        border: heavy {TOKYO_NIGHT["accent"]};
    }}

    Footer {{
        background: {TOKYO_NIGHT["black"]};
        color: {TOKYO_NIGHT["foreground"]};
    }}

    Header {{
        background: {TOKYO_NIGHT["black"]};
        color: {TOKYO_NIGHT["foreground"]};
    }}
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loading_state = LoadingState()
        self.f1_data = F1Data()
        self.f1_data.loading_state = self.loading_state

    def compose(self):
        yield Header(show_clock=True)

        with Container(id="dashboard"):
            yield DriverStandingsWidget(id="drivers_panel", loading_state=self.loading_state)
            yield TeamStandingsWidget(id="teams_panel", loading_state=self.loading_state)
            yield RaceScheduleWidget(id="schedule_panel", loading_state=self.loading_state)
            yield RaceResultsWidget(id="results_panel", loading_state=self.loading_state)

        yield StatusBar(self.loading_state, id="status_bar")

        with Container(id="navigation"):
            yield RaceNavigationBar()

        yield Footer()

        # Global loading overlay
        yield GlobalLoadingOverlay(self.loading_state, id="global_loading")

    def on_mount(self):
        # Set initial focus
        self.query_one("#drivers_panel").focus()

    def action_previous_race(self):
        """Handle keyboard shortcut for previous race"""
        self.query_one(RaceResultsWidget).previous_race()

    def action_next_race(self):
        """Handle keyboard shortcut for next race"""
        self.query_one(RaceResultsWidget).next_race()

    def action_refresh(self):
        """Refresh all data"""
        for panel in self.query(LoadableWidget):
            if hasattr(panel, "update_content"):
                panel.update_content()

    def action_focus_drivers(self):
        """Focus driver standings panel"""
        self.query_one("#drivers_panel").focus()

    def action_focus_teams(self):
        """Focus team standings panel"""
        self.query_one("#teams_panel").focus()

    def action_focus_schedule(self):
        """Focus race schedule panel"""
        self.query_one("#schedule_panel").focus()

    def action_focus_results(self):
        """Focus race results panel"""
        self.query_one("#results_panel").focus()

    def action_focus_next(self):
        """Focus next panel in sequence"""
        panels = ["#drivers_panel", "#teams_panel", "#schedule_panel", "#results_panel"]
        focused = self.focused

        if focused and focused.id in panels:
            current_index = panels.index(focused.id)
            next_index = (current_index + 1) % len(panels)
            self.query_one(panels[next_index]).focus()

    def action_focus_previous(self):
        """Focus previous panel in sequence"""
        panels = ["#drivers_panel", "#teams_panel", "#schedule_panel", "#results_panel"]
        focused = self.focused

        if focused and focused.id in panels:
            current_index = panels.index(focused.id)
            prev_index = (current_index - 1) % len(panels)
            self.query_one(panels[prev_index]).focus()


if __name__ == "__main__":
    app = F1DashboardApp()
    app.run()
