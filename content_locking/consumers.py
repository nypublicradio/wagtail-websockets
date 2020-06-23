import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.auth import get_user
from django.core.cache import cache
from django.utils.text import slugify

# This module-level variable will store user-presence data. It will contain
# keys that are slugs of a given url, e.g. if a user is on
# /admin/pages/12/edit, the dict will have a key {'adminpages12edit': []}, and
# its corresponding array will list the users currently in that page. The user
# at index [0] will be the first user in the story. Users are added on
# connect() and removed on disconnect().


class PresenceConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room_name = None
        self.room_group_name = None
        self.username = None

    async def user_can_connect(self):
        user = await get_user(self.scope)
        return user.is_authenticated and user.has_perm('wagtail.access_admin')

    async def connect(self):
        """
        Executes when a user connects to the channel (e.g. entering the page)
        """
        self.room_name = slugify(self.scope["url_route"]["kwargs"]["room_name"])
        self.room_group_name = "presence_{}".format(self.room_name)

        if self.user_can_connect():
            user = await get_user(self.scope)
            self.username = user.username

            self.add_user_to_lock_list(self.username)

            await self.channel_layer.group_add(
                self.room_group_name, self.channel_name
            )

            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "send_users", "users": self.get_users_from_lock_list()},
            )

            await self.accept()
        else:
            await self.close()

    async def disconnect(self, code):
        """
        Executes when a user disconnects from a channel (e.g. leaving the page)
        """
        self.remove_user_from_lock_list(self.username)

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "send_users", "users": self.get_users_from_lock_list()},
        )

        await self.channel_layer.group_discard(
            self.room_group_name, self.channel_name
        )

    async def receive(self, text_data=None, bytes_data=None):
        """
        Executes any time the channel receives a message from the client
        """
        data = json.loads(text_data)
        if data["event"] == "form_dirty_true":
            await self.update_dirty_status(True)
        if data["event"] == "form_dirty_false":
            await self.update_dirty_status(False)
        if data["event"] == "force_unlock":
            await self.take_ownership(self.username)

    async def send_users(self, event):
        """
        Sends the user dict (owner, is_dirty, user list, etc.) to the client
        """
        await self.send(
            text_data=json.dumps(
                {"people_here": event["users"], "current_user": self.username}
            )
        )

    def add_user_to_lock_list(self, user, owner=False):
        """
        The 'lock list' is a list of users who currently have a specific
        page open for editing (determined by an active websocket connection).
        This list gets appended as each subsequent user opens the page, which
        means the first user in the list was chronologically the first one to
        open the page, and so on.

        The 'owner' of the article is the user who is considered to have the
        'right" to edit the article, typically either by being chronoloically
        first to open it, or by having kicked out the original owner.

        This method adds the current user to the article's 'lock list', and if
        there is no 'owner' (i.e. if no other user is currently editing that
        article) it sets the current user as the owner.
        """
        users = cache.get(
            self.room_name, {"owner": None, "users_list": [], "is_dirty": False}
        )
        if not users.get("owner"):
            users["owner"] = user
        users["users_list"].append(user)
        cache.set(self.room_name, users, 7200)

    def remove_user_from_lock_list(self, user):
        """
        Removes a user from the 'lock list' by removing the first occurance
        of the user's name from the list (a user can potentially be on the list
        multiple times, if they have the article open in multiple tabs).

        Additionally, if that user was the 'owner' of the article, they are
        removed and the next person in the lock list is assigned ownership.

        If there is no owner, the article is empty, therefore is_dirty is reset
        to False and the users dict is in its blank state.
        """
        users = cache.get(self.room_name)

        if user in users["users_list"]:
            users["users_list"].remove(user)
        if users["owner"] == user:
            users["owner"] = (
                users["users_list"][0] if users["users_list"] else None
            )
        if not users["owner"]:
            users["is_dirty"] = False
        cache.set(self.room_name, users, 7200)

    def get_users_from_lock_list(self):
        """
        Returns the users map, including the owner, list of users and is_dirty
        flag
        """
        users = cache.get(self.room_name)
        return users

    async def update_dirty_status(self, dirty_status):
        """
        Sets the is_dirty flag, and transmits the new is_dirty flag to all
        users in that page (this controls the messaging on the alert box, e.g.
        "unsaved changes will be lost")
        """
        users = cache.get(self.room_name)
        users["is_dirty"] = dirty_status
        cache.set(self.room_name, users, 7200)
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "send_users", "users": self.get_users_from_lock_list()},
        )

    async def take_ownership(self, username):
        """
        Sets the current user as the owner of a given article, and transmits
        that message with the new owner to any user in the same page
        """
        users = cache.get(self.room_name)
        users["owner"] = username
        cache.set(self.room_name, users, 7200)
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "send_users", "users": self.get_users_from_lock_list()},
        )
