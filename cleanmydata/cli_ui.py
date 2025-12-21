"""CLI UI utilities for cleanmydata."""

import itertools
import sys
import threading
import time

from rich.console import Console

console = Console()


def print_section(title, level="sub", verbose=True):
    """Print formatted Rich section headers only if verbose=True."""
    if not verbose:
        return

    if level == "main":
        console.rule(f"[bold white]{title}[/bold white]", style="bright_green")
        console.print()
    elif level == "sub":
        console.rule(f"[bold cyan]{title}[/bold cyan]", style="dim cyan")


class Spinner:
    """Terminal spinner for indicating progress."""

    def __init__(self, message="Processing...", delay=0.1):
        self.spinner = itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
        self.delay = delay
        self.message = message
        self.stop_running = False
        self.thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        while not self.stop_running:
            sys.stdout.write(f"\r{self.message} {next(self.spinner)}")
            sys.stdout.flush()
            time.sleep(self.delay)
        sys.stdout.write(f"\r{self.message} \n")
        sys.stdout.flush()

    def start(self):
        self.stop_running = False
        self.thread.start()

    def stop(self):
        self.stop_running = True
        self.thread.join()
