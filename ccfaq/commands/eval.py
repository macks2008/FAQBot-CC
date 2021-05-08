"""Runs code in an emulator and displays the result."""

import aiohttp
import asyncio
import io
import json
import logging
import re
from typing import Optional, List, Tuple

import discord
import discord.ext.commands as commands
from discord_slash.cog_ext import cog_slash
from discord_slash import SlashContext, SlashCommand
import discord_slash.utils.manage_commands as manage_commands

from ccfaq.commands import COMMAND_TIME
from ccfaq.config import guild_ids, eval_server
from ccfaq.timing import with_async_timer

LOG = logging.getLogger(__name__)

CODE_BLOCKS = re.compile(r'```(?:lua)?\n(.*?)```|(`+)(.*?)\2', flags=re.DOTALL | re.IGNORECASE)

DROP_COMMAND = re.compile(r'^%([a-z]+)')

class EvalCog(commands.Cog):

    def __init__(self):
        self.session = aiohttp.ClientSession()

    def _get_code_blocks(self, message: discord.Message) -> List[str]:
        contents = message.content
        code_blocks = [
            group[0] or group[2] for group in CODE_BLOCKS.findall(contents)
        ]

        if code_blocks:
            return code_blocks

        contents = DROP_COMMAND.sub('', contents).strip()
        print(contents)
        if contents:
            return [contents]

        return []

    @commands.command(name="eval", aliases=["exec", "code"])
    @with_async_timer(COMMAND_TIME.labels('eval', 'message'))
    async def eval(self, ctx: commands.Context) -> None:
        """Execute some code."""

        code_blocks = self._get_code_blocks(ctx.message)

        if not code_blocks and ctx.message.reference:
            try:
                reply_to = await ctx.fetch_message(ctx.message.reference.message_id)
            except:
                LOG.exception("Cannot find message we're replying to.")
            else:
                code_blocks = self._get_code_blocks(reply_to)
                if code_blocks:
                    message = reply_to

        if not code_blocks:
            await message.reply(":bangbang: No code found in message!", mention_author=False)
            return

        warnings = []
        if len(code_blocks) == 1:
            code = code_blocks[0]
        else:
            warnings.append(":warning: Multiple code blocks, choosing the first.")
            code = code_blocks[0]

        LOG.info("Running: %s", json.dumps(code))

        try:
            response : aiohttp.ClientResponse
            async with self.session.post(eval_server(), data=code, timeout=aiohttp.ClientTimeout(total=20)) as response:
                if response.status == 200:
                    if response.headers.get("X-Clean-Exit") != "True":
                        warnings.append(":warning: Computer ran for too long.")

                    image = await response.read()
                else:
                    image = None
        except:
            LOG.exception("Error contacting eval.tweaked.cc")
            await ctx.reply(":bangbang: Unknown error when running code", mention_author=False)
            return

        if not image:
            await ctx.reply(":bangbang: No screnshot returned. Sorry!", mention_author=False)
        else:
            await ctx.reply(
                "\n".join(warnings),
                mention_author=False,
                file=discord.File(io.BytesIO(image), 'image.png')
            )


    def cog_unload(self) -> None:
        asyncio.ensure_future(self.session.close())
