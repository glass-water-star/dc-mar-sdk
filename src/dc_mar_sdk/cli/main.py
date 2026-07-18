"""CLI tool for DC MAR SDK - command-line interface for querying and cache management.

Built with Typer and Rich for a modern CLI experience.
"""

import asyncio
import csv
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from dc_mar_sdk import MARClient
from dc_mar_sdk.settings import get_settings

SETTINGS = get_settings()
DEFAULT_SWAGGER_FILE = f"{SETTINGS.swagger_dir}/{SETTINGS.swagger_file_name}"
SWAGGER_DIR = Path(SETTINGS.swagger_dir)
API_BASE_URL = f"{SETTINGS.mar_base_url}{SETTINGS.mar_api_base_path}"

app = typer.Typer(help="DC MAR SDK CLI - Query MAR API and manage cache")
console = Console()


def get_api_key(api_key_option: str | None = None) -> str | None:
    """Get API key from option or environment variable."""
    if api_key_option:
        return api_key_option
    return SETTINGS.mar_api_key or None


@app.command()
def autocomplete(
    address: str = typer.Argument(..., help="Partial address string"),
    *,
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        "-k",
        help="API key (or set env DC_MAR_API_KEY)",
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass cache for this call"),  # noqa: FBT003
) -> None:
    """Get autocomplete suggestions for an address."""

    async def run() -> None:
        key = get_api_key(api_key)
        if not key:
            console.print("[bold red]Error: API key required[/]")
            console.print("  Set DC_MAR_API_KEY environment variable or use --api-key flag")
            return

        client = MARClient(api_key=key)

        try:
            suggestions = await client.autocomplete(address, use_cache=(not no_cache))
            console.print(f'[bold green]Suggestions for "{address}":[/]')
            for i, suggestion in enumerate(suggestions, 1):
                console.print(f"  {i}. {suggestion}")
        except Exception as e:  # noqa: BLE001
            console.print(f"[bold red]Error:[/] {e}")

    asyncio.run(run())


@app.command()
def analyze(
    addresses_file: str | None = typer.Option(
        None,
        "--file",
        "-f",
        help="CSV or JSON file with addresses",
    ),
    query: str = typer.Option("1600 Pennsylvania", "--query", "-q", help="Single address to query"),
    *,
    api_key: str | None = typer.Option(None, "--api-key", "-k", help="API key (or set env DC_MAR_API_KEY)"),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file (geojson, csv)",
    ),
) -> None:
    """Analyze addresses and export results (Option A: Standalone Analysis)."""

    async def run() -> None:
        key = get_api_key(api_key)
        if not key:
            console.print("[bold red]Error: API key required[/]")
            console.print("  Set DC_MAR_API_KEY environment variable or use --api-key flag")
            return

        client = MARClient(api_key=key)
        results = []

        # Single query or batch from file
        if addresses_file:
            console.print(f"[bold cyan]Reading addresses from {addresses_file}...[/]")
            try:
                if addresses_file.endswith(".csv"):
                    with Path(addresses_file).open() as f:
                        reader = csv.DictReader(f)
                        addresses = [row.get("address") or row.get("Address") for row in reader if row]
                else:
                    with Path(addresses_file).open() as f:
                        data = json.load(f)
                        addresses = data if isinstance(data, list) else [data]
            except (OSError, json.JSONDecodeError) as e:
                console.print(f"[bold red]Error reading file: {e}[/]")
                return
        else:
            addresses = [query]

        console.print(f"[bold cyan]Analyzing {len(addresses)} address(es)...[/]\n")

        with console.status("[bold green]Processing...") as status:
            for i, addr in enumerate(addresses, 1):
                try:
                    matches = await client.autocomplete(addr)
                    results.append({
                        "address": addr,
                        "standardized": matches[0] if matches else None,
                        "alternatives": matches[1:3] if len(matches) > 1 else [],
                        "match_count": len(matches),
                    })
                    status.update(f"[bold green]Processed {i}/{len(addresses)}...")
                except Exception as e:  # noqa: BLE001
                    results.append({
                        "address": addr,
                        "error": str(e),
                    })

                # Rate limiting
                await asyncio.sleep(0.05)

        # Display results
        console.print("\n[bold green]✓ Analysis Complete[/]\n")

        table = Table(title="Address Analysis Results")
        table.add_column("Original Address", style="cyan")
        table.add_column("Standardized", style="green")
        table.add_column("Matches", style="magenta")
        table.add_column("Status", style="yellow")

        for result in results:
            if result.get("standardized"):
                status_str = "✓ Found"
            elif result.get("error"):
                status_str = "✗ Error"
            else:
                status_str = "? No match"
            table.add_row(
                result["address"],
                result.get("standardized", "")[:40],
                str(result.get("match_count", 0)),
                status_str,
            )

        console.print(table)

        # Export results
        if output:
            try:
                if output.endswith(".geojson"):
                    with Path(output).open("w") as f:
                        json.dump(results, f, indent=2)
                    console.print(f"\n✓ GeoJSON exported to {output}")
                elif output.endswith(".csv"):
                    with Path(output).open("w", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=["address", "standardized", "match_count"])
                        writer.writeheader()
                        for r in results:
                            writer.writerow({
                                "address": r["address"],
                                "standardized": r.get("standardized", ""),
                                "match_count": r.get("match_count", 0),
                            })
                    console.print(f"\n✓ CSV exported to {output}")
            except Exception as e:  # noqa: BLE001
                console.print(f"[bold red]Error exporting: {e}[/]")

        # Show telemetry
        stats = await client.get_data_summary()
        console.print("\n[bold cyan]📊 Data Collection Summary:[/]")
        console.print(f"  • Total Requests: {stats['total_api_requests']}")
        console.print(f"  • Data Received: {stats['total_data_received_mb']} MB")
        console.print(f"  • Avg Response: {stats['avg_response_time_ms']:.0f}ms")

    asyncio.run(run())


@app.command()
def cache_status(
    *,
    api_key: str | None = typer.Option(None, "--api-key", "-k", help="API key (or set env DC_MAR_API_KEY)"),
) -> None:
    """Display cache statistics and status."""

    async def run() -> None:
        key = get_api_key(api_key)
        client = MARClient(api_key=key) if key else MARClient()
        stats = await client.get_cache_stats()

        console.print("[bold cyan]Cache Statistics[/]")
        table = Table()
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        for k, v in stats.items():
            display_value = f"{v:.2f}" if isinstance(v, float) else v
            table.add_row(str(k), str(display_value))

        console.print(table)

    asyncio.run(run())


@app.command()
def cache_clear(
    *,
    api_key: str | None = typer.Option(None, "--api-key", "-k", help="API key (or set env DC_MAR_API_KEY)"),
) -> None:
    """Clear all cache entries."""

    async def run() -> None:
        key = get_api_key(api_key)
        client = MARClient(api_key=key) if key else MARClient()
        await client.clear_cache()
        console.print("[bold green]✓ Cache cleared[/]")

    asyncio.run(run())


@app.command()
def api_stats(
    hours: int = typer.Option(24, "--hours", help="Statistics period in hours"),
    *,
    api_key: str | None = typer.Option(None, "--api-key", "-k", help="API key (or set env DC_MAR_API_KEY)"),
) -> None:
    """Display API usage statistics."""

    async def run() -> None:
        key = get_api_key(api_key)
        client = MARClient(api_key=key) if key else MARClient()
        stats = await client.get_api_stats(hours)

        console.print(f"[bold cyan]API Statistics (last {hours} hours)[/]")
        table = Table()
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        for k, v in stats.items():
            display_value = f"{v:.2f}" if isinstance(v, float) else v
            table.add_row(str(k), str(display_value))

        console.print(table)

    asyncio.run(run())


@app.command()
def endpoint_popularity(
    limit: int = typer.Option(10, "--limit", help="Number of endpoints to show"),
    *,
    api_key: str | None = typer.Option(None, "--api-key", "-k", help="API key (or set env DC_MAR_API_KEY)"),
) -> None:
    """Show most frequently called endpoints."""

    async def run() -> None:
        key = get_api_key(api_key)
        client = MARClient(api_key=key) if key else MARClient()
        endpoints = await client.get_endpoint_popularity(limit)

        console.print(f"[bold cyan]Top {limit} Endpoints by Popularity[/]")
        table = Table()
        table.add_column("Endpoint", style="cyan")
        table.add_column("Calls", style="magenta")
        table.add_column("Avg Response (ms)", style="yellow")
        table.add_column("Errors", style="red")

        for ep in endpoints:
            table.add_row(
                ep.get("endpoint", "unknown"),
                str(ep.get("call_count", 0)),
                f"{ep.get('avg_response_time_ms', 0):.2f}",
                str(ep.get("error_count", 0)),
            )

        console.print(table)

    asyncio.run(run())


@app.command()
def data_summary(
    *,
    api_key: str | None = typer.Option(None, "--api-key", "-k", help="API key (or set env DC_MAR_API_KEY)"),
) -> None:
    """Show summary of all data collected from the API."""

    async def run() -> None:
        key = get_api_key(api_key)
        client = MARClient(api_key=key) if key else MARClient()
        summary = await client.get_data_summary()

        console.print("[bold cyan]Data Collection Summary[/]")
        table = Table()
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        for k, v in summary.items():
            display_value = f"{v:.2f}" if isinstance(v, float) else v
            table.add_row(str(k), str(display_value))

        console.print(table)

    asyncio.run(run())


@app.command()
def drift_check(
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="DC MAR API Key (or use DC_MAR_API_KEY env var)",
    ),
    swagger_file: str = typer.Option(
        DEFAULT_SWAGGER_FILE,
        "--swagger-file",
        help="Path to Swagger/OpenAPI JSON file",
    ),
    respect_robots: bool = typer.Option(
        True,
        "--respect-robots/--ignore-robots",
        help="Respect robots.txt rules before probing API endpoints",
    ),
    user_agent: str = typer.Option(
        SETTINGS.drift_user_agent,
        "--user-agent",
        help="User-Agent used for robots.txt and API requests",
    ),
    safe_read_only: bool = typer.Option(
        True,
        "--safe-read-only/--no-safe-read-only",
        help="Only probe GET operations; use --no-safe-read-only to allow unsafe methods",
    ),
    operation: list[str] | None = typer.Option(
        None,
        "--operation",
        help="Optional allowlist entry like \"GET /api/v2.2/units\" (repeatable)",
    ),
):
    """Check for API drift between Swagger spec and actual responses"""

    key = get_api_key(api_key)
    if not key:
        console.print("[red]Error: API key required[/]")
        raise typer.Exit(1)

    swagger_path = Path(swagger_file)
    if not swagger_path.exists():
        console.print(f"[red]Error: Swagger spec not found at {swagger_path}[/]")
        raise typer.Exit(1)

    async def run() -> int:
        from dc_mar_sdk.tools.drift_detector import SwaggerValidator

        console.print("\n[bold cyan]🔍 Swagger Drift Detection[/]")
        console.print(f"Spec: {swagger_path}")
        console.print(f"API: {API_BASE_URL}\n")

        validator = SwaggerValidator(str(swagger_path), key)
        include_unsafe_methods = not safe_read_only
        if respect_robots:
            allowed, disallowed, robots_error = await validator.check_robots_txt(
                user_agent=user_agent,
                include_unsafe_methods=include_unsafe_methods,
                operation_allowlist=operation,
            )
            if robots_error:
                console.print(f"[yellow]robots.txt note:[/] {robots_error}")
            if not allowed:
                console.print("[red]robots.txt disallows one or more operations:[/]")
                for op in disallowed[:10]:
                    console.print(f"  - {op}")
                if len(disallowed) > 10:
                    console.print(f"  ... and {len(disallowed) - 10} more")
                return 1
            console.print("[green]✓ robots.txt check passed[/]\n")
        results = await validator.test_all(
            user_agent=user_agent,
            include_unsafe_methods=include_unsafe_methods,
            operation_allowlist=operation,
        )

        # Display results
        console.print("[bold]Test Results[/]")
        console.print("=" * 80)

        table = Table(title="Drift Detection Results")
        table.add_column("Method", style="green")
        table.add_column("Endpoint", style="cyan")
        table.add_column("Status", style="magenta")
        table.add_column("Issues", style="yellow")
        table.add_column("Severity", style="red")

        total_errors = 0
        for result in results:
            status = "✅ Pass" if result.success else "❌ Fail"
            error_count = sum(1 for i in result.issues if i.severity == "error")
            warn_count = sum(1 for i in result.issues if i.severity == "warning")

            severity = ""
            if error_count > 0:
                severity = f"🔴 {error_count} error(s)"
                total_errors += error_count
            if warn_count > 0:
                if severity:
                    severity += f", 🟡 {warn_count} warning(s)"
                else:
                    severity = f"🟡 {warn_count} warning(s)"

            table.add_row(
                result.method.upper(),
                result.endpoint,
                status,
                f"{len(result.issues)} issue(s)",
                severity or "✓"
            )

        console.print(table)

        # Show detailed issues
        if any(r.issues for r in results):
            console.print("\n[bold]Issue Details[/]")
            for result in results:
                if result.issues:
                    console.print(f"\n[bold cyan]{result.method.upper()} {result.endpoint}[/]")
                    for issue in result.issues:
                        icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(issue.severity)
                        console.print(f"  {icon} [{issue.severity.upper()}] {issue.issue_type}")
                        console.print(f"     Location: {issue.location}")
                        console.print(f"     Spec: {issue.spec_format}")
                        console.print(f"     Actual: {issue.actual_format}")

        # Summary
        console.print("\n[bold]Summary[/]")
        passed = sum(1 for r in results if r.success)
        total = len(results)
        console.print(f"  Tests: {passed}/{total} passed")
        console.print(f"  Total Issues: {sum(len(r.issues) for r in results)}")
        console.print(f"  Critical Errors: {total_errors}")

        if total_errors > 0:
            console.print("\n[red]⚠️  Drift detected![/]")
            console.print(f"[red]  {total_errors} critical error(s) require attention[/]")
            return 1
        else:
            console.print("\n[green]✅ No critical drift detected[/]")
            return 0

    result_code = asyncio.run(run())
    raise typer.Exit(result_code)


@app.command()
def drift_smoke(
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="DC MAR API Key (or use DC_MAR_API_KEY env var)",
    ),
    swagger_file: str = typer.Option(
        DEFAULT_SWAGGER_FILE,
        "--swagger-file",
        help="Path to Swagger/OpenAPI JSON file",
    ),
    include_unsafe_methods: bool = typer.Option(
        False,
        "--include-unsafe-methods",
        help="Also probe POST/PUT/PATCH/DELETE operations in smoke test",
    ),
):
    """Run a lightweight live smoke test for drift + robots compliance."""

    key = get_api_key(api_key)
    if not key:
        console.print("[red]Error: API key required[/]")
        raise typer.Exit(1)

    swagger_path = Path(swagger_file)
    if not swagger_path.exists():
        console.print(f"[red]Error: Swagger spec not found at {swagger_path}[/]")
        raise typer.Exit(1)

    async def run() -> int:
        from dc_mar_sdk.tools.drift_detector import SwaggerValidator

        validator = SwaggerValidator(str(swagger_path), key)
        console.print("\n[bold cyan]🧪 Drift Smoke Test[/]")
        console.print(f"Spec: {swagger_path}")

        allowed, disallowed, robots_error = await validator.check_robots_txt(
            user_agent=f"{SETTINGS.drift_user_agent}-smoke",
            include_unsafe_methods=include_unsafe_methods,
        )
        if robots_error:
            console.print(f"[yellow]robots.txt note:[/] {robots_error}")
        if not allowed:
            console.print("[red]robots.txt disallows one or more operations:[/]")
            for op in disallowed[:10]:
                console.print(f"  - {op}")
            return 1
        console.print("[green]✓ robots.txt check passed[/]")

        results = await validator.test_all(
            user_agent=f"{SETTINGS.drift_user_agent}-smoke",
            include_unsafe_methods=include_unsafe_methods,
        )
        critical = sum(1 for r in results for i in r.issues if i.severity == "error")
        console.print(f"Operations tested: {len(results)}")
        console.print(f"Critical drift issues: {critical}")

        if critical > 0:
            console.print("[red]✗ Smoke test failed[/]")
            return 1

        console.print("[green]✓ Smoke test passed[/]")
        return 0

    result_code = asyncio.run(run())
    raise typer.Exit(result_code)


@app.command()
def swagger_list(
):
    """List all available Swagger spec versions"""
    swagger_dir = SWAGGER_DIR

    try:
        from dc_mar_sdk.tools.swagger_manager import SwaggerManager
        manager = SwaggerManager(swagger_dir, "")  # Don't need API key to list

        versions = manager.list_versions()

        if not versions:
            console.print("[yellow]No Swagger versions found[/]")
            return

        console.print("[bold cyan]Available Swagger Versions[/]\n")

        table = Table()
        table.add_column("Version", style="cyan")
        table.add_column("Path", style="magenta")
        table.add_column("Size", style="yellow")
        table.add_column("Modified", style="green")

        for v in versions:
            table.add_row(str(v["version"]), v["path"], v["size"], v["modified"])

        console.print(table)
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)


@app.command()
def swagger_fix(
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="DC MAR API Key (or use DC_MAR_API_KEY env var)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Automatically fix Swagger spec drift by introspecting actual API responses"""

    key = get_api_key(api_key)
    if not key:
        console.print("[red]Error: API key required[/]")
        raise typer.Exit(1)

    swagger_dir = SWAGGER_DIR

    async def run():
        try:
            from dc_mar_sdk.tools.swagger_manager import SwaggerManager

            console.print("\n[bold cyan]🔧 Swagger Drift Auto-Fix[/]")
            console.print(f"Swagger Directory: {swagger_dir}")
            console.print(f"Base API: {API_BASE_URL}\n")

            manager = SwaggerManager(swagger_dir, key)

            # Show current versions
            console.print("[bold]Current Versions:[/]")
            versions = manager.list_versions()
            for v in versions:
                icon = "📄" if v["version"] == "current" else "📋"
                console.print(f"  {icon} {v['version']}: {v['size']}")

            console.print("\n[bold]Starting drift fix workflow...[/]\n")

            # Run the fix workflow
            summary = await manager.run_fix_workflow(verbose=verbose)

            # Show new versions
            console.print("\n[bold cyan]Updated Versions:[/]")
            versions = manager.list_versions()
            for v in versions:
                icon = "📄" if v["version"] == "current" else "📋"
                console.print(f"  {icon} {v['version']}: {v['size']}")

            console.print("\n[green]✅ Swagger drift fix complete![/]")
            console.print(
                f"  Tested: {summary['tested']} | Successful: {summary['successful']} | ",
                f"Schemas Updated: {summary['updated']}",
            )
            console.print(f"  Backup Version: swagger.v{summary['backup_version']}.json")
            console.print("  Validation: ✓ Passed")
            console.print("\n[bold]Next steps:[/]")
            console.print("  1. Review the updated swagger.json")
            console.print("  2. Test with: uv run dc-mar-sdk-cli drift-check")
            console.print("  3. Commit changes if satisfied")

            return 0
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]Error: {e}[/]")
            import traceback
            if verbose:
                traceback.print_exc()
            return 1

    result_code = asyncio.run(run())
    raise typer.Exit(result_code)


@app.command()
def swagger_reset(
    version: str | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Version to reset to, or \"list\" to show available versions",
    ),
):
    """Reset Swagger spec to a previous version"""

    swagger_dir = SWAGGER_DIR

    try:
        from dc_mar_sdk.tools.swagger_manager import SwaggerManager
        manager = SwaggerManager(swagger_dir, "")

        console.print("\n[bold cyan]🔄 Swagger Version Reset[/]\n")

        if version is None or version.lower() == "list":
            # Show available versions
            versions = manager.list_versions()

            if not versions:
                console.print("[yellow]No versions available[/]")
                return

            console.print("[bold]Available versions:[/]")
            table = Table()
            table.add_column("Version", style="cyan")
            table.add_column("Size", style="yellow")
            table.add_column("Modified", style="green")

            for v in versions:
                version_str = str(v["version"])
                table.add_row(version_str, v["size"], v["modified"])

            console.print(table)
            console.print()
            console.print("[bold]To reset to a version, run:[/]")
            console.print("  uv run dc-mar-sdk-cli swagger-reset --version VERSION")
            return

        try:
            target_version = int(version)
        except ValueError:
            console.print("[red]Error: --version must be an integer or 'list'[/]")
            raise typer.Exit(1)

        # Reset to specified version
        console.print(f"[bold]Resetting to version {target_version}...[/]\n")
        manager.reset_to_version(target_version)
        valid, issues = manager.validate_swagger_file()
        if not valid:
            console.print("[red]Reset completed but swagger validation failed:[/]")
            for issue in issues:
                console.print(f"  - {issue}")
            raise typer.Exit(1)

        console.print("\n[green]✅ Reset complete![/]")
        console.print("  Validation: ✓ Passed")
        console.print("[bold]Next steps:[/]")
        console.print("  1. Test with: uv run dc-mar-sdk-cli drift-check")
        console.print("  2. Review changes")
        console.print("  3. Commit if satisfied")

    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)


@app.command()
def swagger_heal(
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="DC MAR API Key (or use DC_MAR_API_KEY env var)",
    ),
    swagger_file: str = typer.Option(
        DEFAULT_SWAGGER_FILE,
        "--swagger-file",
        help="Path to Swagger/OpenAPI JSON file",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Self-healing flow: detect drift, fix swagger, and verify."""

    key = get_api_key(api_key)
    if not key:
        console.print("[red]Error: API key required[/]")
        raise typer.Exit(1)

    swagger_path = Path(swagger_file)
    if not swagger_path.exists():
        console.print(f"[red]Error: Swagger spec not found at {swagger_path}[/]")
        raise typer.Exit(1)

    async def run() -> int:
        from dc_mar_sdk.tools.drift_detector import SwaggerValidator
        from dc_mar_sdk.tools.swagger_manager import SwaggerManager

        console.print("\n[bold cyan]🩺 Swagger Self-Heal[/]")
        validator = SwaggerValidator(str(swagger_path), key)
        pre_results = await validator.test_all()
        pre_critical = sum(1 for r in pre_results for i in r.issues if i.severity == "error")
        console.print(f"Before fix: {pre_critical} critical drift issue(s)")

        manager = SwaggerManager(SWAGGER_DIR, key)
        summary = await manager.run_fix_workflow(verbose=verbose)
        console.print(
            f"Fix summary: tested={summary['tested']} successful={summary['successful']} updated={summary['updated']}"
        )

        post_validator = SwaggerValidator(str(swagger_path), key)
        post_results = await post_validator.test_all()
        post_critical = sum(1 for r in post_results for i in r.issues if i.severity == "error")
        console.print(f"After fix: {post_critical} critical drift issue(s)")

        if post_critical > 0:
            console.print("[yellow]Self-heal completed, but drift remains[/]")
            return 1

        console.print("[green]✅ Self-heal completed with no critical drift[/]")
        return 0

    result_code = asyncio.run(run())
    raise typer.Exit(result_code)


if __name__ == "__main__":
    app()
