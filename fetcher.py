import json
import time
from argparse import ArgumentParser
from dataclasses import dataclass, field, fields
from pathlib import Path

import httpx

BOARDS_DIR = Path("boards")
PIECES_DIR = Path("pieces")

DEFAULT_CONFIG_FILE = "default-config.json"


@dataclass(kw_only=True, frozen=True)
class FetcherConfig:
    default_size: int
    piece_names: list[str] = field(default_factory=list)
    pieces: dict[str, str] = field(default_factory=dict)
    boards: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        for p in fields(self):
            if getattr(self, p.name) is None:
                raise AttributeError(f"'{p.name}' is None!")


class LimitedProgressPrinter:
    def __init__(self, limit: int):
        if limit <= 0:
            raise ValueError(f"Non-positive limit")
        self._curr = 1
        self._limit = limit
        self._progress_val_len = 2 * len(str(self._limit)) + 4

    def print_progress(self, s: str, *, end: str = "\n"):
        if self._curr > self._limit:
            raise RuntimeError(f"Limit of {self._limit} is reached!")
        progress_val = f"{self._curr}/{self._limit}: ".rjust(self._progress_val_len)
        self._curr += 1
        print(progress_val + s, end=end)


@dataclass(kw_only=True, frozen=True)
class ParsedArgs:
    config: str


def bold(s: str) -> str:
    return f"\033[1m{s}\033[0m"


def parse_cmd_args() -> ParsedArgs:
    parser = ArgumentParser(description="A script for downloading boards and pieces.")
    parser.add_argument(
        "-c",
        "--config",
        required=False,
        default=DEFAULT_CONFIG_FILE,
        help="Configuration file",
    )
    args = parser.parse_args()
    return ParsedArgs(config=args.config)


def load_config_from_json(file_path: str) -> FetcherConfig:
    with open(file_path, "r") as reader:
        json_data = json.load(reader)
        return FetcherConfig(
            default_size=json_data["default-size"],
            piece_names=json_data["piece-names"],
            pieces=json_data["pieces"],
            boards=json_data["boards"],
        )


def save_to_file(file_path: Path, data: bytes) -> None:
    if file_path.is_dir():
        raise IsADirectoryError(f"'{file_path}' is a directory!")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "wb") as writer:
        writer.write(data)


def make_request(url_path: str, *, wait_time_ms: int = 0) -> bytes:
    # Wait, before making request, be kind to server
    if wait_time_ms > 0:
        time.sleep(wait_time_ms / 1000)

    response: httpx.Response = httpx.get(url_path)
    response.raise_for_status()

    return response.content


def start_process(config: FetcherConfig):
    boards = config.boards
    pieces = config.pieces
    piece_names = config.piece_names
    def_size = config.default_size
    total_size = len(boards) + len(pieces) * len(piece_names)

    index_printer = LimitedProgressPrinter(total_size)

    print(bold(f"Downloading {total_size} file(s)..."))

    for name, url in boards.items():
        content = make_request(url.format(def_size), wait_time_ms=200)
        file_path = BOARDS_DIR / f"{name}.png"
        save_to_file(file_path, content)
        index_printer.print_progress(f"Board is stored at: {file_path}")

    for name, url in pieces.items():
        print(f"Download pieces of '{name}':")
        for pn in piece_names:
            content = make_request(url.format(def_size, pn), wait_time_ms=200)
            file_path = PIECES_DIR / name / f"{pn}.png"
            save_to_file(file_path, content)
            index_printer.print_progress(f"Piece of '{name}' is stored at: {file_path}")


def main() -> None:
    args = parse_cmd_args()
    config_file = load_config_from_json(args.config)
    start_process(config_file)


if __name__ == "__main__":
    main()
