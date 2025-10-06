#!/usr/bin/env python3
"""
Chess Position Renderer

Generates chess position images by combining board and piece PNGs based on a FEN string.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from PIL import Image


# Default starting position FEN
DEFAULT_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
DEFAULT_SIZE = 80
DEFAULT_OUTPUT = "chess_position.png"

# Mapping FEN characters to piece filenames
PIECE_MAP = {
    'r': 'br.png',  # black rook
    'n': 'bn.png',  # black knight
    'b': 'bb.png',  # black bishop
    'q': 'bq.png',  # black queen
    'k': 'bk.png',  # black king
    'p': 'bp.png',  # black pawn
    'R': 'wr.png',  # white rook
    'N': 'wn.png',  # white knight
    'B': 'wb.png',  # white bishop
    'Q': 'wq.png',  # white queen
    'K': 'wk.png',  # white king
    'P': 'wp.png',  # white pawn
}


def parse_fen(fen: str) -> list[list[Optional[str]]]:
    """
    Parse FEN string and return 8x8 board representation.

    Returns a 2D list where board[rank][file] contains the FEN character
    for the piece at that position, or None for empty squares.
    Rank 0 = visual top (rank 8), Rank 7 = visual bottom (rank 1).
    """
    # Extract just the board layout part (before first space)
    board_layout = fen.split()[0]

    # Split into ranks (8 to 1, top to bottom)
    ranks = board_layout.split('/')

    if len(ranks) != 8:
        raise ValueError(f"Invalid FEN: expected 8 ranks, got {len(ranks)}")

    board: list[list[Optional[str]]] = []

    for rank in ranks:
        row: list[Optional[str]] = []
        for char in rank:
            if char.isdigit():
                # Empty squares
                row.extend([None] * int(char))
            elif char in PIECE_MAP:
                row.append(char)
            else:
                raise ValueError(f"Invalid FEN character: {char}")

        if len(row) != 8:
            raise ValueError(f"Invalid FEN: rank has {len(row)} squares instead of 8")

        board.append(row)

    return board


def load_fen_by_id(position_id: int, fen_file: str = "fen.json") -> str:
    """
    Load a FEN string from the JSON file by ID.

    Args:
        position_id: The ID of the position to load
        fen_file: Path to the JSON file containing positions (default: fen.json)

    Returns:
        The FEN string for the specified position

    Raises:
        FileNotFoundError: If the JSON file doesn't exist
        ValueError: If the ID is not found in the file
    """
    fen_path = Path(fen_file)

    if not fen_path.exists():
        raise FileNotFoundError(f"FEN file not found: {fen_path}")

    with open(fen_path, 'r') as f:
        positions = json.load(f)

    for position in positions:
        if position.get('id') == position_id:
            return position['fen']

    raise ValueError(f"Position with ID {position_id} not found in {fen_file}")


def render_position(
    fen: str,
    board_name: str,
    pieces_name: str,
    size: int,
    output: str,
    side: str = 'white'
) -> None:
    """
    Render a chess position to an image file.

    Args:
        fen: FEN string representing the position
        board_name: Name of the board style (without .png)
        pieces_name: Name of the pieces directory
        size: Size of each square in pixels
        output: Output filename
        side: Perspective to render from ('white' or 'black', default 'white')
    """
    # Validate paths
    board_path = Path(f"boards/{board_name}.png")
    pieces_dir = Path(f"pieces/{pieces_name}")

    if not board_path.exists():
        raise FileNotFoundError(f"Board not found: {board_path}")

    if not pieces_dir.exists():
        raise FileNotFoundError(f"Pieces directory not found: {pieces_dir}")

    # Parse FEN
    board = parse_fen(fen)

    # Load and resize board
    board_img = Image.open(board_path)
    board_size = size * 8
    board_img = board_img.resize((board_size, board_size), Image.Resampling.LANCZOS)

    # Convert to RGBA to handle transparency
    if board_img.mode != 'RGBA':
        board_img = board_img.convert('RGBA')

    # Rotate board 180° if viewing from black's perspective
    if side == 'black':
        board_img = board_img.rotate(180)

    # Create a new image for compositing
    final_img = board_img.copy()

    # Place pieces on the board
    for rank_idx, rank in enumerate(board):
        for file_idx, piece_char in enumerate(rank):
            if piece_char is not None:
                # Get piece filename
                piece_filename = PIECE_MAP[piece_char]
                piece_path = pieces_dir / piece_filename

                if not piece_path.exists():
                    print(f"Warning: Piece file not found: {piece_path}", file=sys.stderr)
                    continue

                # Load and resize piece
                piece_img = Image.open(piece_path)
                piece_img = piece_img.resize((size, size), Image.Resampling.LANCZOS)

                # Convert to RGBA
                if piece_img.mode != 'RGBA':
                    piece_img = piece_img.convert('RGBA')

                # Calculate position on board
                if side == 'black':
                    # Flip coordinates for black's perspective
                    x = (7 - file_idx) * size
                    y = (7 - rank_idx) * size
                else:
                    x = file_idx * size
                    y = rank_idx * size

                # Paste piece onto board with transparency
                final_img.paste(piece_img, (x, y), piece_img)

    # Save the final image
    final_img.save(output)
    print(f"Chess position rendered to: {output}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Render chess positions from FEN notation using chess.com board and piece images.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Starting position with brown board and alpha pieces
  %(prog)s --board brown --pieces alpha --size 80

  # Custom position
  %(prog)s --fen "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4" --board marble --pieces 3d_wood --size 100
        """
    )

    # Create mutually exclusive group for FEN input methods
    fen_group = parser.add_mutually_exclusive_group()

    fen_group.add_argument(
        '--fen',
        type=str,
        help=f'FEN string representing the chess position (default: starting position if neither --fen nor --id provided)'
    )

    fen_group.add_argument(
        '--id',
        type=int,
        help='Load FEN from fen.json by position ID'
    )

    parser.add_argument(
        '--board',
        type=str,
        required=True,
        help='Board style name without .png extension (e.g., "brown", "marble")'
    )

    parser.add_argument(
        '--pieces',
        type=str,
        required=True,
        help='Pieces directory name (e.g., "alpha", "3d_wood")'
    )

    parser.add_argument(
        '--size',
        type=int,
        default=DEFAULT_SIZE,
        help=f'Size of each square in pixels (default: {DEFAULT_SIZE})'
    )

    parser.add_argument(
        '--side',
        type=str,
        choices=['white', 'black'],
        default='white',
        help='Perspective to render from: white (bottom) or black (top). Default: white'
    )

    parser.add_argument(
        '--output',
        type=str,
        default=DEFAULT_OUTPUT,
        help=f'Output filename (default: {DEFAULT_OUTPUT})'
    )

    args = parser.parse_args()

    try:
        # Determine which FEN to use
        if args.id is not None:
            fen = load_fen_by_id(args.id)
        elif args.fen is not None:
            fen = args.fen
        else:
            fen = DEFAULT_FEN

        render_position(
            fen=fen,
            board_name=args.board,
            pieces_name=args.pieces,
            size=args.size,
            output=args.output,
            side=args.side
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
