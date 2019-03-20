import json

from django.utils.text import slugify

from channels.generic.websocket import AsyncWebsocketConsumer

# This module-level variable will store user-presence data. It will contain
# keys that are slugs of a given url, e.g. if a user is on
# /admin/pages/12/edit, the dict will have a key {'adminpages12edit': []}, and
# its corresponding array will list the users currently in that page. The user
# at index [0] will be the first user in the story. Users are added on
# connect() and removed on disconnect().
people_here = {}


class PresenceConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.people_here = people_here

    async def connect(self):
        self.room_name = slugify(self.scope["url_route"]["kwargs"]["room_name"])
        self.room_group_name = "presence_{}".format(self.room_name)
        self.username = self.scope["user"].username

        try:
            if self.username not in self.people_here[self.room_name]:
                self.people_here[self.room_name] += [self.username]
        except KeyError:
            self.people_here[self.room_name] = [self.username]

        await self.channel_layer.group_add(
            self.room_group_name, self.channel_name
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "send_users", "users": self.people_here[self.room_name]},
        )

        await self.accept()

    async def disconnect(self, code):
        self.people_here[self.room_name].remove(self.username)

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "send_users", "users": self.people_here[self.room_name]},
        )

        await self.channel_layer.group_discard(
            self.room_group_name, self.channel_name
        )

    async def receive(self, text_data=None, bytes_data=None):
        pass

    async def presence(self, event):
        message = event["message"]

        await self.send(text_data=json.dumps({"message": message}))

    async def send_users(self, event):
        await self.send(
            text_data=json.dumps(
                {"people_here": event["users"], "current_user": self.username}
            )
        )
