import json
import os
import time
from typing import Any

import httpx


def load_json(file_path: str) -> dict[str, Any]:
    with open(file_path, "r") as reader:
        return json.loads(reader.read())


def save_file(file_path: str, data: bytes) -> None:
    with open(file_path, "wb") as writer:
        writer.write(data)
    print(f"File '{file_path}' created!")


def check_dirs(directories: list[str]) -> None:
    for d in directories:
        if not os.path.exists(d):
            os.mkdir(d)


def get_request(url_path: str, wait_time: float = 0.2) -> bytes:
    # Wait, before making request, be kind to server
    time.sleep(wait_time)

    response: httpx.Response = httpx.get(url_path)

    if response.status_code == 200:
        return response.content
    else:
        print(f"Something bad with {response}")
        return b""


def start_process(config: dict[str, Any]) -> None:
    boards: dict[str, str] = config["boards"]
    pieces: dict[str, str] = config["pieces"]
    piece_names: list[str] = config["piece-names"]
    def_size: int = config["default-size"]
    files_size: int = len(boards) + len(pieces) * len(piece_names)
    file_index: int = 1

    def print_index(_file_index: int) -> None:
        pre_space = " " * (len(str(files_size)) - len(str(_file_index)))
        print(f"{pre_space}{_file_index}/{files_size}: ", end="")

    boards_dir = "boards/"
    pieces_dir = "pieces/"
    pieces_subdirs = [f"{pieces_dir}{k}/" for k in pieces.keys()]

    check_dirs([boards_dir, pieces_dir, *pieces_subdirs])

    print(f"Downloading {files_size} files...")

    for name, url in boards.items():
        content = get_request(url.format(def_size))
        print_index(file_index)
        save_file(f"boards/{name}.png", content)
        file_index += 1

    for name, url in pieces.items():
        for pn in piece_names:
            content = get_request(url.format(def_size, pn))
            print_index(file_index)
            save_file(f"{pieces_dir}{name}/{pn}.png", content)
            file_index += 1


def main() -> None:
    start_process(load_json("data.json"))


if __name__ == "__main__":
    main()
