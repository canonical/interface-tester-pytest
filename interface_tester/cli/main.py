import typer

from interface_tester.cli.discover import pprint_tests


def main():
    app = typer.Typer(help="Interface tester CLI utilities.")
    app.command("discover")(pprint_tests)
    app.command("_", hidden=True)(
        lambda: None
    )  # without this, 'discover' will be the only toplevel command.

    app()


if __name__ == "__main__":
    typer.run(main)
