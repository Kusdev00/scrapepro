#!/usr/bin/env python3
"""ScrapePro Lite — Professional Web Scraping CLI Tool."""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.syntax import Syntax
from rich.text import Text

from config import ScrapeConfig
from scraper import Scraper, ScrapeResult
from parsers import auto_detect_parse
from exporters import export_result

console = Console()

# Persistent storage for last scrape result (survives across CLI invocations)
SCRAPE_CACHE_DIR = Path.home() / ".scrapepro"
SCRAPE_CACHE_FILE = SCRAPE_CACHE_DIR / "last_result.json"

BANNER = r"""
  ╔═╗┌─┐┬─┐┌─┐┌─┐┌─┐╔═╗┬─┐┌─┐
  ╚═╗│  ├┬┘├─┤├─┘├─╚╗╠═╝├┬┘│ │
  ╚═╝└─┘┴└─┴ ┴┴  └─╚╝╩  ┴└─└─┘
  Professional Web Scraping Toolkit
"""


def print_banner():
    console.print(
        Panel(
            Text(BANNER, style="bold cyan"),
            border_style="bright_blue",
            title="[bold yellow]ScrapePro Lite v1.0[/]",
            subtitle="[dim]Professional Web Scraping CLI[/]",
        )
    )


def get_scraper(config: ScrapeConfig) -> Scraper:
    return Scraper(config)


def display_result(result: ScrapeResult, verbose: bool = False):
    console.print(f"\n[bold green]✔[/] Scraped: [link={result.url}]{result.url}[/link]")
    console.print(f"[dim]Content hash: {result.content_hash}[/]")

    for key, value in result.data.items():
        if not value:
            continue
        table = Table(
            title=f"[bold]{key.title()}[/]",
            show_header=True,
            header_style="bold magenta",
            border_style="dim",
        )
        if isinstance(value, list) and value and isinstance(value[0], dict):
            headers = list(value[0].keys())
            for h in headers:
                table.add_column(h, style="cyan", max_width=60)
            for item in value[:20]:
                table.add_row(*[str(item.get(h, ""))[:80] for h in headers])
            if len(value) > 20:
                table.add_row(*[f"... +{len(value) - 20} more"] * len(headers))
        elif isinstance(value, list):
            table.add_column("Value", style="cyan", max_width=80)
            for item in value[:20]:
                table.add_row(str(item)[:100])
            if len(value) > 20:
                table.add_row(f"... +{len(value) - 20} more")
        elif isinstance(value, dict):
            table.add_column("Key", style="yellow")
            table.add_column("Value", style="cyan", max_width=80)
            for k, v in list(value.items())[:30]:
                table.add_row(k, str(v)[:100])
        else:
            table.add_column("Content", style="cyan")
            table.add_row(str(value)[:500])
        console.print(table)


@click.group(invoke_without_command=True)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--demo", is_flag=True, help="Run demo mode")
@click.pass_context
def cli(ctx, verbose, demo):
    """ScrapePro Lite — Professional Web Scraping CLI Tool"""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_time=False)],
    )

    if demo:
        print_banner()
        run_demo()
        return

    if ctx.invoked_subcommand is None:
        print_banner()
        console.print(ctx.get_help())


@cli.command()
@click.argument("url")
@click.option("--css", "css_selector", default=None, help="CSS selector to extract")
@click.option("--xpath", "xpath_expr", default=None, help="XPath expression to extract")
@click.option("--tables", "extract_tables", is_flag=True, help="Extract all tables")
@click.option("--links", "extract_links", is_flag=True, help="Extract all links")
@click.option("--images", "extract_images", is_flag=True, help="Extract all images")
@click.option("--metadata", "extract_metadata", is_flag=True, help="Extract metadata")
@click.option("--text", "extract_text", is_flag=True, help="Extract clean text")
@click.option("--all", "extract_all", is_flag=True, help="Smart scrape everything")
@click.pass_context
def scrape(ctx, url, css_selector, xpath_expr, extract_tables, extract_links,
           extract_images, extract_metadata, extract_text, extract_all):
    """Scrape a URL and extract data."""
    verbose = ctx.obj.get("verbose", False)
    config = ScrapeConfig(verbose=verbose)
    scraper = get_scraper(config)

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(description=f"Scraping {url}...", total=None)
        result = scraper.scrape(url)

    if result is None:
        console.print(f"[bold red]✘[/] Failed to scrape {url}")
        sys.exit(1)

    # Determine what to show
    specific = any([css_selector, xpath_expr, extract_tables, extract_links,
                    extract_images, extract_metadata, extract_text])

    if css_selector:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(result.raw_html, "lxml")
        elements = soup.select(css_selector)
        console.print(f"\n[bold]CSS Selector:[/] [cyan]{css_selector}[/]")
        console.print(f"[bold]Matches:[/] {len(elements)}")
        for i, el in enumerate(elements[:30]):
            text = el.get_text(strip=True)[:200]
            console.print(f"  [dim]{i + 1}.[/] {text}")
        return

    if xpath_expr:
        from bs4 import BeautifulSoup
        from lxml import etree
        soup = BeautifulSoup(result.raw_html, "lxml")
        tree = etree.HTML(str(soup))
        elements = tree.xpath(xpath_expr)
        console.print(f"\n[bold]XPath:[/] {xpath_expr}")
        console.print(f"[bold]Matches:[/] {len(elements)}")
        for i, el in enumerate(elements[:30]):
            text = str(el)[:200] if not hasattr(el, 'text') else el.text[:200]
            console.print(f"  [dim]{i + 1}.[/] {text}")
        return

    if specific:
        if extract_tables:
            display_section("Tables", result.data.get("tables", []))
        if extract_links:
            display_section("Links", result.data.get("links", []))
        if extract_images:
            display_section("Images", result.data.get("images", []))
        if extract_metadata:
            display_section("Metadata", result.data.get("metadata", {}))
        if extract_text:
            console.print(f"\n[bold]Article Text:[/]\n")
            console.print(result.data.get("text", "")[:2000])
    else:
        display_result(result, verbose)

    # Auto-detect and show specialized parsing
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(result.raw_html, "lxml")
    auto_data = auto_detect_parse(soup, url)
    if auto_data.get("type"):
        console.print(f"\n[bold yellow]⚡ Auto-detected:[/] [cyan]{auto_data['type']}[/]")
        for k, v in auto_data.items():
            if k != "type" and v:
                console.print(f"  [bold]{k}:[/] {str(v)[:150]}")

    ctx.obj["last_result"] = result

    # Persist to disk so `export` works across separate CLI invocations
    try:
        SCRAPE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        SCRAPE_CACHE_FILE.write_text(
            json.dumps(result.to_dict(), indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


@cli.command()
@click.argument("url")
@click.option("--depth", "-d", default=2, type=int, help="Crawl depth")
@click.pass_context
def crawl(ctx, url, depth):
    """Crawl a site to specified depth."""
    verbose = ctx.obj.get("verbose", False)
    config = ScrapeConfig(verbose=verbose, max_depth=depth)
    scraper = get_scraper(config)

    console.print(f"[bold]Crawling[/] [link={url}]{url}[/link] [dim]depth={depth}[/]")

    results = scraper.crawl(url, depth)
    console.print(f"\n[bold green]✔[/] Crawled [bold]{len(results)}[/] pages")
    for r in results:
        title = r.data.get("title", "No title")[:60]
        console.print(f"  • [link={r.url}]{title}[/link]")

    ctx.obj["last_result"] = results[-1] if results else None

    if results:
        try:
            SCRAPE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            SCRAPE_CACHE_FILE.write_text(
                json.dumps(results[-1].to_dict(), indent=2, default=str, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass


@cli.command()
@click.argument("format", type=click.Choice(["json", "csv", "xlsx", "md", "sqlite"]))
@click.option("--output", "-o", default=None, help="Output file path")
@click.option("--input", "input_file", default=None, help="Input JSON file (instead of last result)")
@click.pass_context
def export(ctx, format, output, input_file):
    """Export last scrape result to a format."""
    result = None
    if input_file:
        data = json.loads(Path(input_file).read_text())
        result = ScrapeResult(data["url"], data["data"], "")
        result.timestamp = data.get("timestamp", time.time())
        result._hash = data.get("content_hash", "")
    else:
        result = ctx.obj.get("last_result")

    # Fall back to on-disk cache from a previous `scrape` invocation
    if result is None and SCRAPE_CACHE_FILE.exists():
        try:
            data = json.loads(SCRAPE_CACHE_FILE.read_text(encoding="utf-8"))
            result = ScrapeResult(data["url"], data["data"], "")
            result.timestamp = data.get("timestamp", time.time())
            result._hash = data.get("content_hash", "")
        except Exception:
            pass

    if result is None:
        console.print("[bold red]✘[/] No scrape result available. Run 'scrape' first.")
        sys.exit(1)

    try:
        # Default to current working directory if no output path given
        if output is None:
            ext_map = {"json": ".json", "csv": ".csv", "xlsx": ".xlsx", "md": ".md", "sqlite": ".db"}
            ext = ext_map.get(format, f".{format}")
            output = str(Path.cwd() / f"scrape_export{ext}")
        out_path = export_result(result, format, output)
        console.print(f"[bold green]✔[/] Exported to [cyan]{out_path}[/]")
    except Exception as e:
        console.print(f"[bold red]✘[/] Export failed: {e}")
        sys.exit(1)


@cli.command()
@click.argument("url")
@click.option("--interval", "-i", default=60, type=int, help="Interval in minutes")
@click.pass_context
def schedule(ctx, url, interval):
    """Set up recurring scrape with change detection."""
    verbose = ctx.obj.get("verbose", False)
    config = ScrapeConfig(verbose=verbose)
    scraper = get_scraper(config)

    console.print(f"[bold]Scheduling[/] [link={url}]{url}[/link] every [cyan]{interval}m[/]")
    console.print("[dim]Press Ctrl+C to stop[/]\n")

    prev_result = None
    try:
        while True:
            result = scraper.scrape(url)
            if result:
                if prev_result:
                    changes = Scraper.compare_results(prev_result, result)
                    if changes["hash_changed"]:
                        console.print(f"[bold yellow]⚡ Change detected![/] {time.strftime('%H:%M:%S')}")
                        for field, diff in changes.get("field_changes", {}).items():
                            console.print(f"  [bold]{field}:[/]")
                            console.print(f"    [red]- {str(diff['old'])[:100]}[/]")
                            console.print(f"    [green]+ {str(diff['new'])[:100]}[/]")
                    else:
                        console.print(f"[dim]No changes. {time.strftime('%H:%M:%S')}[/]")
                else:
                    console.print(f"[green]Initial scrape complete.[/] Hash: {result.content_hash}")
                prev_result = result
            time.sleep(interval * 60)
    except KeyboardInterrupt:
        console.print("\n[dim]Scheduler stopped.[/]")


@cli.command()
@click.argument("file1")
@click.argument("file2")
def compare(file1, file2):
    """Compare two scrape results and show changes."""
    data1 = json.loads(Path(file1).read_text())
    data2 = json.loads(Path(file2).read_text())

    r1 = ScrapeResult(data1["url"], data1["data"], "")
    r2 = ScrapeResult(data2["url"], data2["data"], "")

    changes = Scraper.compare_results(r1, r2)

    if not changes["hash_changed"]:
        console.print("[green]No changes detected.[/]")
        return

    console.print("[bold yellow]⚡ Changes Detected![/]\n")
    table = Table(title="Field Changes", border_style="yellow")
    table.add_column("Field", style="bold")
    table.add_column("Old Value", style="red", max_width=50)
    table.add_column("New Value", style="green", max_width=50)

    for field, diff in changes.get("field_changes", {}).items():
        table.add_row(field, str(diff["old"])[:200], str(diff["new"])[:200])
    console.print(table)


def display_section(title: str, data):
    """Display a single section of scrape data."""
    if not data:
        return
    table = Table(title=f"[bold]{title}[/]", border_style="dim")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        for h in data[0].keys():
            table.add_column(h, style="cyan", max_width=60)
        for item in data[:15]:
            table.add_row(*[str(item.get(h, ""))[:80] for h in data[0].keys()])
    elif isinstance(data, list):
        table.add_column("Value", style="cyan")
        for item in data[:15]:
            table.add_row(str(item)[:100])
    elif isinstance(data, dict):
        table.add_column("Key", style="yellow")
        table.add_column("Value", style="cyan")
        for k, v in list(data.items())[:20]:
            table.add_row(k, str(v)[:100])
    console.print(table)


def run_demo():
    """Run demo mode scraping a sample site."""
    console.print("\n[bold yellow]⚡ Demo Mode — Scraping example.com[/]\n")
    config = ScrapeConfig(verbose=True)
    scraper = Scraper(config)
    result = scraper.scrape("https://example.com")

    if result:
        display_result(result, verbose=True)
        console.print("\n[bold]Exporting demo results...[/]")
        for fmt in ["json", "csv", "md"]:
            try:
                out = export_result(result, fmt, f"demo_output.{fmt}")
                console.print(f"  [green]✔[/] {fmt.upper()}: {out}")
            except Exception as e:
                console.print(f"  [red]✘[/] {fmt.upper()}: {e}")
    else:
        console.print("[red]Demo scrape failed.[/]")


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
