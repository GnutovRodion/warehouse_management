from aiohttp import web

from inventory_api.app import create_app


def main() -> None:
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
