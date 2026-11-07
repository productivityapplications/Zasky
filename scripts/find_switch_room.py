"""Map a Discord channel ID to its assigned Switch room ID."""

from __future__ import annotations

import argparse
import asyncio

from zasky.config import load_settings
from zasky.switch.operations import SwitchOperations


async def find(settings, channel_id: str) -> None:
    ops = SwitchOperations(settings)
    try:
        rooms = await ops.list_rooms()
        for room in rooms:
            room_id = str(room.get("room_id") or room.get("id") or "")
            if not room_id:
                continue
            detail = await ops.get_room_detail(room_id)
            if str(detail.get("external_channel_id") or "") == channel_id:
                print(f"room_id={room_id}")
                print(f"name={detail.get('name') or room.get('name') or 'unknown'}")
                return
        print("No assigned Switch room maps to that Discord channel ID.")
        print("Create/attach the room to Zasky in Switch, then rerun.")
    finally:
        await ops.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default="/root/Zasky-secrets/zasky.env")
    parser.add_argument("--channel-id", required=True)
    args = parser.parse_args()
    settings = load_settings(args.env_file)
    asyncio.run(find(settings, args.channel_id))


if __name__ == "__main__":
    main()
