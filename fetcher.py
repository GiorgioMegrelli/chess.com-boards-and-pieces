from __future__ import annotations

import io
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

import click
import httpx
from PIL import Image
from tqdm import tqdm

DEFAULT_WAIT_MS = 200

STANDARD_MIME_TYPE = "image/png"
SUPPORTED_MIME_TYPES = (STANDARD_MIME_TYPE, "image/jpeg", "image/gif", "image/webp")


class ColEntry(NamedTuple):
    id: str
    readable_name: str
    templated_url: str
    default_size: int
    available_sizes: list[int]


@dataclass(kw_only=True, frozen=True)
class BoardEntry:
    collection_id: str
    readable_name: str
    url_template: str
    default_size: int
    available_sizes: list[int]

    @property
    def get_url_placeholders(self) -> list[str]:
        return list(re.findall(r"{(\w+)}", self.url_template))

    def _get_format_map(self) -> dict[str, str | int]:
        return {"collection": self.collection_id, "size": self.default_size}

    @property
    def default_url(self) -> str:
        d = self._get_format_map()
        return self.url_template.format_map(d)


@dataclass(kw_only=True, frozen=True)
class PieceEntry(BoardEntry):
    name: str

    def _get_format_map(self) -> dict[str, str | int]:
        d = super()._get_format_map()
        d["name"] = self.name
        return d


@dataclass(frozen=True)
class FetcherConfig:
    boards: dict[str, BoardEntry]
    pieces: dict[str, list[PieceEntry]]

    @staticmethod
    def _exec_range(exp: str) -> list[int]:
        if re.match(r"^range\s*\(\s*-?\d+\s*(?:,\s*-?\d+\s*){0,2}\)$", exp):
            return list(eval(exp))
        return json.loads(exp)

    @staticmethod
    def _handle_collections(
        cols: dict, url_templates: dict[str, str]
    ) -> list[ColEntry]:
        entries = []
        for key, col in cols.items():
            templated_url = url_templates[col["url-template"]]
            available_sizes = FetcherConfig._exec_range(col["size"]["available"])
            entries.append(
                ColEntry(
                    id=key,
                    readable_name=col["readable_name"],
                    templated_url=templated_url,
                    default_size=col["size"]["default"],
                    available_sizes=available_sizes,
                )
            )
        return entries

    @staticmethod
    def _handle_boards(d: dict, url_templates: dict[str, str]) -> dict[str, BoardEntry]:
        col_entries = FetcherConfig._handle_collections(d["collections"], url_templates)
        return {
            col_entry.id: BoardEntry(
                collection_id=col_entry.id,
                readable_name=col_entry.readable_name,
                url_template=col_entry.templated_url,
                default_size=col_entry.default_size,
                available_sizes=col_entry.available_sizes,
            )
            for col_entry in col_entries
        }

    @staticmethod
    def _handle_pieces(
        d: dict, url_templates: dict[str, str]
    ) -> dict[str, list[PieceEntry]]:
        col_entries = FetcherConfig._handle_collections(d["collections"], url_templates)
        piece_names = d["names"].split(";")
        return {
            col_entry.id: [
                PieceEntry(
                    collection_id=col_entry.id,
                    readable_name=col_entry.readable_name,
                    name=pn,
                    url_template=col_entry.templated_url,
                    default_size=col_entry.default_size,
                    available_sizes=col_entry.available_sizes,
                )
                for pn in piece_names
            ]
            for col_entry in col_entries
        }

    @staticmethod
    def parse(file_path: Path) -> FetcherConfig:
        with open(file_path, "r") as reader:
            json_data: dict[str | dict[str, dict | Any]] = json.load(reader)
        url_templates = json_data["common"]["url-templates"]
        boards = FetcherConfig._handle_boards(json_data["boards"], url_templates)
        pieces = FetcherConfig._handle_pieces(json_data["pieces"], url_templates)
        return FetcherConfig(boards, pieces)


def save_to_file(file_path: Path, data: bytes) -> None:
    if not isinstance(file_path, Path):
        file_path = Path(file_path)
    if file_path.is_dir():
        raise IsADirectoryError(f"'{file_path}' is a directory!")
    file_path = file_path.resolve().absolute()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(data)


def human_readable_piece(pn: str) -> str:
    color = {"w": "White", "b": "Black"}[pn[0]]
    piece_name = {
        "b": "Bishop",
        "k": "King",
        "n": "Knight",
        "p": "Pawn",
        "q": "Queen",
        "r": "Rock",
    }[pn[1]]
    return f"{color} {piece_name}"


def make_request(url_path: str, *, wait_time_ms: int = 0) -> httpx.Response:
    # Wait, before making request, be kind to server
    if wait_time_ms > 0:
        time.sleep(wait_time_ms / 1000)

    response = httpx.get(url_path)
    response.raise_for_status()
    return response


def request_image_as_png(url_path: str, *, wait_time_ms: int = 0) -> bytes:
    response = make_request(url_path, wait_time_ms=wait_time_ms)
    content_type = response.headers["content-type"].lower()
    if content_type not in SUPPORTED_MIME_TYPES:
        raise ValueError(f"Unsupported MIME type: {content_type}")
    if content_type == STANDARD_MIME_TYPE:
        return response.content
    img_obj = Image.open(io.BytesIO(response.content))
    output_buffer = io.BytesIO()
    img_obj.convert("RGB").save(output_buffer, format="PNG")
    return output_buffer.getvalue()


def start_process(config: FetcherConfig, output_dir: Path):
    with tqdm(total=len(config.boards), desc="Downloading boards") as p_bar:
        for col_name, board in config.boards.items():
            if col_name != "6m5lc":
                continue
            print("Processing 6m5lc")
            p_bar.set_description(f"Downloading '{col_name}'")
            content = request_image_as_png(
                board.default_url, wait_time_ms=DEFAULT_WAIT_MS
            )
            file_path = output_dir / "boards" / f"{col_name}.png"
            save_to_file(file_path, content)
            p_bar.update(1)
            if True:
                return
        p_bar.set_description("Boards are Downloaded!")

    pieces_dir = output_dir / "pieces"
    with tqdm(total=len(config.pieces), desc="Downloading pieces") as p_bar:
        for col_name, pieces in config.pieces.items():
            p_bar.set_description(f"Downloading '{col_name}'")
            with tqdm(pieces, leave=False) as nested_p_bar:
                for piece in nested_p_bar:
                    nested_p_bar.set_description(human_readable_piece(piece.name))
                    content = request_image_as_png(
                        piece.default_url, wait_time_ms=DEFAULT_WAIT_MS
                    )
                    file_path = pieces_dir / col_name / f"{piece.name}.png"
                    save_to_file(file_path, content)
            p_bar.update(1)
        p_bar.set_description("Pieces are Downloaded!")


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-c",
    "--config",
    default=Path("default-config.json"),
    help="Configuration file.",
    type=click.Path(path_type=Path),
)
@click.option(
    "-o",
    "--output",
    default=Path("."),
    help="Output directory.",
    type=click.Path(path_type=Path),
)
def main(config: Path, output: Path) -> None:
    """
    A script for downloading boards and pieces.
    """
    parsed_config = FetcherConfig.parse(config)
    start_process(parsed_config, output)


if __name__ == "__main__":
    main()
