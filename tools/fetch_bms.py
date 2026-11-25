"""Download and validate one original CN chart from Bestdori."""

import argparse
from pathlib import Path

from requests.exceptions import RequestException

from agent.custom.utils.api import BestdoriAPI


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("song_id", type=int, help="Bestdori song ID")
    parser.add_argument("difficulty", type=str.lower, choices=("easy", "normal", "hard", "expert", "special"))
    parser.add_argument("--output-dir", type=Path, default=Path("charts"))
    args = parser.parse_args()
    if args.song_id < 1:
        parser.error("song ID must be positive")

    target = args.output_dir / f"{args.song_id}-{args.difficulty}.bms"
    if target.exists() or target.with_suffix(".txt").exists():
        parser.exit(1, f"A local chart already exists for {target.stem}.\n")
    try:
        raw, _ = BestdoriAPI.get_bms(args.song_id, args.difficulty)
        target.parent.mkdir(parents=True, exist_ok=True)
        output = target.open("xb")
        try:
            with output:
                output.write(raw)
        except (OSError, KeyboardInterrupt):
            target.unlink(missing_ok=True)
            raise
    except (RequestException, ValueError, OSError) as error:
        parser.exit(1, f"Could not save {target}: {error}\n")
    print(target.resolve())


if __name__ == "__main__":
    main()
