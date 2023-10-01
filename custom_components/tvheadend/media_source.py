from __future__ import annotations

import json
import logging

from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

from .const import DOMAIN

DEFAULT_ICON_PATH = "/static/img/logomid.png"
TAG_IDENTIFIER_PREFIX = "tag:"


async def async_get_media_source(hass: HomeAssistant) -> TVHeadendMediaSource:
    entries = hass.config_entries.async_entries(DOMAIN)
    entry = entries[0]
    return TVHeadendMediaSource(hass, entry)


class TVHeadendMediaSource(MediaSource):
    name = "TVH"

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        super().__init__(DOMAIN)
        self.hass = hass
        self.config = config

    async def _async_read_response(self, response):
        """Reads the response, logging any json errors"""

        text = await response.text()

        if response.status >= 400:
            _LOGGER.error(f"Request failed: {response.status}: {text}")
            return None

        try:
            return json.loads(text)
        except:
            raise Exception(f"Failed to extract response json: {text}")

    async def _async_get_entries(self, url):
        async with aiohttp.ClientSession() as client:
            async with client.get(url) as channel_grid_response:
                channel_grid_json = await self._async_read_response(
                    channel_grid_response
                )
                return channel_grid_json["entries"]

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.CHANNEL,
            media_content_type=MediaType.VIDEO,
            title=self.name,
            can_play=False,
            can_expand=True,
            thumbnail=self.config.data["tvheadend_url"] + DEFAULT_ICON_PATH,
            children_media_class=MediaClass.DIRECTORY,
            children=[*await self._async_build_children(item)],
        )

    async def _async_build_children(
        self, item: MediaSourceItem
    ) -> list[BrowseMediaSource]:
        if item.identifier is None:
            return await self._async_build_channel_tags(item)
        return await self._async_build_channels(item)

    async def _async_build_channels(
        self, item: MediaSourceItem
    ) -> list[BrowseMediaSource]:
        channels = await self._async_get_entries(
            self.config.data["tvheadend_url"]
            + "/api/channel/grid?limit=999999999&sort=number&dir=asc"
        )

        sources = []

        for channel in channels:
            if (
                not item.identifier.replace(TAG_IDENTIFIER_PREFIX, "")
                in channel["tags"]
            ):
                continue

            sources.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=channel["uuid"],
                    media_class=MediaClass.CHANNEL,
                    media_content_type=MediaType.VIDEO,
                    title=str(channel["number"]) + " " + channel["name"],
                    thumbnail=self.config.data["tvheadend_url"]
                    + (channel["icon_public_url"] or DEFAULT_ICON_PATH),
                    can_play=True,
                    can_expand=False,
                )
            )

        return sources

    async def _async_build_channel_tags(
        self, item: MediaSourceItem
    ) -> list[BrowseMediaSource]:
        channel_tags = await self._async_get_entries(
            self.config.data["tvheadend_url"] + "/api/channeltag/grid?limit=999999999"
        )

        tag_sources = []

        for channel_tag in channel_tags:
            tag_sources.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=TAG_IDENTIFIER_PREFIX + channel_tag["uuid"],
                    media_class=MediaClass.CHANNEL,
                    media_content_type=MediaType.VIDEO,
                    title=channel_tag["name"],
                    thumbnail=self.config.data["tvheadend_url"]
                    + (channel_tag["icon_public_url"] or DEFAULT_ICON_PATH),
                    can_play=False,
                    can_expand=True,
                )
            )

        return tag_sources

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        return PlayMedia(
            self.config.data["tvheadend_url"]
            + "/stream/channel/"
            + item.identifier
            + "?profile=pass",
            "video/mp4",
        )
