#!/usr/bin/env python3

import os
import fastf1
import pandas as pd
from datetime import datetime
from rich.table import Table
from rich.panel import Panel
from textual.app import App
from textual.widgets import Header, Footer, Static, Button
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.binding import Binding

# Create cache directory if it doesn't exist
cache_dir = "./cache"
os.makedirs(cache_dir, exist_ok=True)

# Enable FastF1 cache
fastf1.Cache.enable_cache(cache_dir)

class F1Data:
    def __init__(self):
        self.current_year = datetime.now().year
        self.selected_race_index = -1  # -1 means most recent race

    def get_driver_standings(self):
        """Get current driver standings"""
        try:
            # Use ergast API directly through fastf1 since get_driver_standings doesn't exist
            # Load the most recent race to get standings
            # Get all races in the current year
            schedule = fastf1.get_event_schedule(self.current_year)
            completed_races = schedule[schedule['EventDate'] < pd.Timestamp(datetime.now())]

            if completed_races.empty:
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

            return standings
        except Exception as e:
            return [{"position": "Error", "driver": str(e), "team": "", "points": "", "wins": ""}]

    def get_team_standings(self):
        """Get current constructor standings"""
        try:
            # Use the same approach as driver standings
            # Get all races in the current year
            schedule = fastf1.get_event_schedule(self.current_year)
            completed_races = schedule[schedule['EventDate'] < pd.Timestamp(datetime.now())]

            if completed_races.empty:
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

            return standings
        except Exception as e:
            return [{"position": "Error", "team": str(e), "nationality": "", "points": "", "wins": ""}]

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

            return races
        except Exception as e:
            return [{"round": "Error", "name": str(e), "circuit": "", "date": "", "status": ""}]

    def get_completed_races(self):
        """Get list of completed races"""
        try:
            schedule = fastf1.get_event_schedule(self.current_year)
            completed_races = schedule[schedule['EventDate'] < pd.Timestamp(datetime.now())]
            return completed_races
        except Exception as e:
            return pd.DataFrame()

    def get_race_results(self, race_index=None):
        """Get results from a specific race or the last completed race if race_index is None"""
        try:
            completed_races = self.get_completed_races()

            if completed_races.empty:
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

            return race_results
        except Exception as e:
            return [{"position": "Error", "driver": str(e), "team": "", "time": "", "points": "", "race_name": "Error"}]


class DriverStandingsWidget(Static):
    def on_mount(self):
        self.update_timer = self.set_interval(300, self.update_content)
        self.update_content()

    def update_content(self):
        f1_data = F1Data()
        standings = f1_data.get_driver_standings()

        table = Table(title=f"Driver Standings {f1_data.current_year}")
        table.add_column("Pos", justify="right", style="cyan")
        table.add_column("Driver", style="green")
        table.add_column("Team", style="yellow")
        table.add_column("Points", justify="right", style="magenta")
        table.add_column("Wins", justify="right", style="red")

        for driver in standings:
            table.add_row(
                str(driver["position"]),
                driver["driver"],
                driver["team"],
                str(driver["points"]),
                str(driver["wins"])
            )

        self.update(Panel(table, border_style="bright_blue"))


class TeamStandingsWidget(Static):
    def on_mount(self):
        self.update_timer = self.set_interval(300, self.update_content)
        self.update_content()

    def update_content(self):
        f1_data = F1Data()
        standings = f1_data.get_team_standings()

        table = Table(title=f"Constructor Standings {f1_data.current_year}")
        table.add_column("Pos", justify="right", style="cyan")
        table.add_column("Team", style="green")
        table.add_column("Nationality", style="yellow")
        table.add_column("Points", justify="right", style="magenta")
        table.add_column("Wins", justify="right", style="red")

        for team in standings:
            table.add_row(
                str(team["position"]),
                team["team"],
                team["nationality"],
                str(team["points"]),
                str(team["wins"])
            )

        self.update(Panel(table, border_style="bright_green"))


class RaceScheduleWidget(Static):
    def on_mount(self):
        self.update_timer = self.set_interval(300, self.update_content)
        self.update_content()

    def update_content(self):
        f1_data = F1Data()
        races = f1_data.get_race_schedule()

        table = Table(title=f"Race Schedule {f1_data.current_year}")
        table.add_column("Round", justify="right", style="cyan")
        table.add_column("Grand Prix", style="green")
        table.add_column("Circuit", style="yellow")
        table.add_column("Date", style="magenta")
        table.add_column("Status", style="red")

        for race in races:
            status_style = "bright_green" if race["status"] == "Completed" else "bright_yellow" if race["status"] == "In Progress" else "bright_blue"
            table.add_row(
                str(race["round"]),
                race["name"],
                race["circuit"],
                race["date"],
                f"[{status_style}]{race['status']}[/]"
            )

        self.update(Panel(table, border_style="bright_yellow"))


class RaceResultsWidget(Static):
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
        f1_data = F1Data()
        results = f1_data.get_race_results(self.race_index)

        race_name = results[0].get("race_name", "") if results else ""
        title = f"Race Results {race_name} {f1_data.current_year}"

        table = Table(title=title)
        table.add_column("Pos", justify="right", style="cyan")
        table.add_column("Driver", style="green")
        table.add_column("Team", style="yellow")
        table.add_column("Time", style="magenta")
        table.add_column("Points", justify="right", style="red")

        for result in results:
            table.add_row(
                str(result["position"]),
                result["driver"],
                result["team"],
                str(result["time"]),
                str(result["points"])
            )

        self.update(Panel(table, border_style="bright_red"))


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

    CSS = """
    Screen {
        background: #121212;
    }

    #dashboard {
        layout: grid;
        grid-size: 2 2;
        grid-gutter: 1 1;
        height: 95%;
        margin: 1;
    }

    #navigation {
        dock: bottom;
        height: 5;
        align: center middle;
        background: #333;
        padding: 1;
    }

    Button {
        margin: 1 2;
    }

    Static:focus {
        border: heavy $accent;
    }
    """

    def compose(self):
        yield Header(show_clock=True)

        with Container(id="dashboard"):
            yield DriverStandingsWidget(id="drivers_panel")
            yield TeamStandingsWidget(id="teams_panel")
            yield RaceScheduleWidget(id="schedule_panel")
            yield RaceResultsWidget(id="results_panel")

        with Container(id="navigation"):
            yield RaceNavigationBar()

        yield Footer()

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
        for panel in self.query(Static):
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
