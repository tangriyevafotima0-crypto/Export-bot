"""Contact analysis module for social graph building and contact detection.

Provides mutual contact discovery, social graph construction for D3.js
visualization, and contact status checking functionality.
"""

import asyncio
from typing import Optional

from sqlalchemy import select
from telethon.errors import FloodWaitError
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.tl.functions.users import GetFullUserRequest

from core.config import get_settings
from core.database import get_session
from core.logger import get_logger
from core.models import TrackedUser

logger = get_logger(__name__)


class ContactAnalyzer:
    """Analyzes contacts and builds social graphs for stalking detection.

    Discovers mutual contacts, builds JSON social graph data suitable
    for D3.js visualization, and checks whether users have saved
    the owner's number in their contacts.
    """

    def __init__(self) -> None:
        """Initialize the ContactAnalyzer with the userbot client."""
        from userbot.client import TelethonClient

        self._telethon = TelethonClient()
        self._settings = get_settings()

    async def find_all_mutual_contacts(self) -> list[dict]:
        """Find all mutual contacts between the owner and tracked users.

        Compares the owner's contact list with tracked users to identify
        mutual contacts (users who appear in both contact lists).

        Returns:
            list[dict]: List of mutual contact info with user_id, username,
                first_name, last_name, and is_tracked fields.
        """
        await self._telethon.ensure_connected()
        client = self._telethon.client
        mutual_contacts = []

        try:
            contacts_result = await self._telethon.safe_request(
                client(GetContactsRequest(hash=0))
            )

            if not contacts_result or not hasattr(contacts_result, "users"):
                return []

            my_contact_ids = {u.id for u in contacts_result.users}

            async for session in get_session():
                tracked_result = await session.execute(
                    select(TrackedUser).where(TrackedUser.is_active.is_(True))
                )
                tracked_users = tracked_result.scalars().all()
                tracked_ids = {u.telegram_id for u in tracked_users}

            for user in contacts_result.users:
                is_mutual = getattr(user, "mutual_contact", False)
                if is_mutual or user.id in tracked_ids:
                    mutual_contacts.append({
                        "user_id": user.id,
                        "username": getattr(user, "username", None),
                        "first_name": getattr(user, "first_name", None),
                        "last_name": getattr(user, "last_name", None),
                        "phone": getattr(user, "phone", None),
                        "is_tracked": user.id in tracked_ids,
                        "is_mutual": is_mutual,
                    })

        except FloodWaitError as e:
            logger.warning(f"FloodWaitError: sleeping {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Error finding mutual contacts: {e}")

        return mutual_contacts

    async def build_social_graph(self, user_id: int) -> dict:
        """Build a social graph centered on a specific user for D3.js visualization.

        Creates a node-link graph structure showing relationships between
        the target user, the owner, and mutual contacts/groups.

        Args:
            user_id: The Telegram user ID to build the graph around.

        Returns:
            dict: D3.js compatible graph with 'nodes' and 'links' arrays.
                Nodes have id, label, type, and group fields.
                Links have source, target, and type fields.
        """
        await self._telethon.ensure_connected()
        client = self._telethon.client
        nodes = []
        links = []
        node_ids = set()

        my_id = self._telethon.my_id
        nodes.append({
            "id": str(my_id),
            "label": "Me",
            "type": "owner",
            "group": 0,
        })
        node_ids.add(str(my_id))

        try:
            full_user = await self._telethon.safe_request(
                client(GetFullUserRequest(user_id))
            )
            target_user = full_user.users[0] if full_user.users else None

            target_label = "Unknown"
            if target_user:
                target_label = (
                    getattr(target_user, "username", None)
                    or getattr(target_user, "first_name", None)
                    or str(user_id)
                )

            nodes.append({
                "id": str(user_id),
                "label": target_label,
                "type": "target",
                "group": 1,
            })
            node_ids.add(str(user_id))

            links.append({
                "source": str(my_id),
                "target": str(user_id),
                "type": "tracked",
            })

        except FloodWaitError as e:
            logger.warning(f"FloodWaitError: sleeping {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Error getting user {user_id} info: {e}")
            nodes.append({
                "id": str(user_id),
                "label": str(user_id),
                "type": "target",
                "group": 1,
            })
            node_ids.add(str(user_id))

        try:
            from userbot.group_monitor import GroupMonitor

            group_monitor = GroupMonitor()
            mutual_groups = await group_monitor.scan_mutual_groups(user_id)

            for group in mutual_groups[:10]:
                group_node_id = f"group_{group['id']}"
                if group_node_id not in node_ids:
                    nodes.append({
                        "id": group_node_id,
                        "label": group["title"],
                        "type": "group",
                        "group": 2,
                    })
                    node_ids.add(group_node_id)

                links.append({
                    "source": str(my_id),
                    "target": group_node_id,
                    "type": "member",
                })
                links.append({
                    "source": str(user_id),
                    "target": group_node_id,
                    "type": "member",
                })

        except Exception as e:
            logger.debug(f"Cannot build group graph for {user_id}: {e}")

        mutual_contacts = await self.find_all_mutual_contacts()
        for contact in mutual_contacts[:15]:
            contact_id = str(contact["user_id"])
            if contact_id not in node_ids and contact_id != str(user_id):
                nodes.append({
                    "id": contact_id,
                    "label": contact.get("username") or contact.get("first_name") or contact_id,
                    "type": "contact",
                    "group": 3,
                })
                node_ids.add(contact_id)
                links.append({
                    "source": str(my_id),
                    "target": contact_id,
                    "type": "contact",
                })

        return {"nodes": nodes, "links": links}

    async def check_if_saved_my_number(self, user_id: int) -> bool:
        """Check if a user has saved the owner's phone number in their contacts.

        Uses Telethon to determine the contact mutual status, which indicates
        whether the other user has the owner in their contacts.

        Args:
            user_id: The Telegram user ID to check.

        Returns:
            bool: True if the user has saved the owner's number.
        """
        await self._telethon.ensure_connected()
        client = self._telethon.client

        try:
            full_user = await self._telethon.safe_request(
                client(GetFullUserRequest(user_id))
            )

            if full_user.users:
                user = full_user.users[0]
                return getattr(user, "mutual_contact", False)

        except FloodWaitError as e:
            logger.warning(f"FloodWaitError: sleeping {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Error checking contact status for {user_id}: {e}")

        return False
