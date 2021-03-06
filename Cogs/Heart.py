import asyncio
import discord
import re
from   discord.ext import commands
from   Cogs import DisplayName

def setup(bot):
	# Add the bot
	bot.add_cog(Heart(bot))

class Heart:

	# Init with the bot reference, and a reference to the settings var
	def __init__(self, bot):
		self.bot = bot
		# compile regex to look for i + hug or hug + me
		self.regex = re.compile(r"((.*?)\bi\b(.*?)\bhug\b(.*?))|((.*?)\bhug\b(.*?)\bme\b(.*?))")

	async def message(self, message):
		# Check the message - and append a heart if a ping exists, but no command
		context = await self.bot.get_context(message)
		if context.command:
			return {}
		# Check for a mention
		try:
			botMember = discord.utils.get(message.guild.members, id=self.bot.user.id)
		except Exception:
			# Couldn't get a member - just get the user
			botMember = self.bot.user
		react_list = []
		# Get our hug phrases
		'''hugs = [ "i need a hug", "i wish i had a hug", "i could use a hug", "hug me" ]
		for hug in hugs:
			if hug in message.content.lower():
				# We need a hug, stat!
				react_list.append("🤗")
				break'''
		matches = re.finditer(self.regex, message.content.lower())
		if len(list(matches)):
			# We need a hug, stat!
			react_list.append("🤗")
		if botMember.mention in message.content:
			# We got a mention!
			react_list.append("❤")
		# Return our reactions - if any
		if len(react_list):
			return { "Reaction" : react_list }
