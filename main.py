def main() -> None:
	try:
		from cli.app import SeederCLIApp
	except ModuleNotFoundError as exc:
		raise SystemExit("Missing dependency. Install with: pip install textual") from exc

	SeederCLIApp().run()


if __name__ == "__main__":
	main()
