import asyncio
import discord
import os
import re
import psutil
import platform
import time
import sys
import fnmatch
import subprocess
import pyspeedtest
import json
from   PIL         import Image
from   discord.ext import commands
from   Cogs import Settings
from   Cogs import DisplayName
from   Cogs import ReadableTime
from   Cogs import GetImage
from   Cogs import Nullify
from   Cogs import ProgressBar
from   Cogs import UserTime
from   Cogs import Message

def setup(bot):
	# Add the bot and deps
	settings = bot.get_cog("Settings")
	bot.add_cog(Bot(bot, settings, sys.argv[0], 'python'))

# This is the Bot module - it contains things like nickname, status, etc

class Bot:

	# Init with the bot reference, and a reference to the settings var
	def __init__(self, bot, settings, path = None, pypath = None):
		self.bot = bot
		self.settings = settings
		self.startTime = int(time.time())
		self.path = path
		self.pypath = pypath
		self.regex = re.compile(r"(http|ftp|https)://([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:/~+#-]*[\w@?^=%&/~+#-])?")
		
	def _is_submodule(self, parent, child):
		return parent == child or child.startswith(parent + ".")

	@asyncio.coroutine
	async def on_loaded_extension(self, ext):
		# See if we were loaded
		if not self._is_submodule(ext.__name__, self.__module__):
			return
		await self._update_status()


	async def onserverjoin(self, server):
		try:
			serverList = self.settings.serverDict['BlockedServers']
		except KeyError:
			self.settings.serverDict['BlockedServers'] = []
			serverList = self.settings.serverDict['BlockedServers']
		for serv in serverList:
			serverName = str(serv).lower()
			try:
				serverID = int(serv)
			except Exception:
				serverID = None
			if serverName == server.name.lower() or serverID == server.id:
				# Found it
				await server.leave()
				return True
			# Check for owner name and id quick
			# Name *MUST* be case-sensitive and have the discriminator for safety
			namecheck = server.owner.name + "#" + str(server.owner.discriminator)
			if serv == namecheck or serverID == server.owner.id:
				# Got the owner
				await server.leave()
				return True
		return False
	
	@commands.command(pass_context=True)
	async def botinfo(self, ctx):
		"""Lists some general stats about the bot."""
		bot_member = ctx.guild.get_member(self.bot.user.id)
		server_embed = discord.Embed(color=bot_member.color)
		server_embed.title = DisplayName.name(bot_member) + " Info"
		
		# Get guild count
		guild_count = "{:,}".format(len(self.bot.guilds))
			
		# Get member count *and* unique member count
		userCount = 0
		counted_users = []
		for server in self.bot.guilds:
			userCount += len(server.members)
			for member in server.members:
				if not member.id in counted_users:
					counted_users.append(member.id)
		if userCount == len(counted_users):
			member_count = "{:,}".format(userCount)
		else:
			member_count = "{:,} ({:,} unique)".format(userCount, len(counted_users))
			
		# Get commands/cogs count
		cog_amnt  = 0
		empty_cog = 0
		for cog in self.bot.cogs:
			if not len(self.bot.get_cog_commands(cog)):
				empty_cog +=1
				# Skip empty cogs
				continue
			cog_amnt += 1
				
		cog_count = "{:,} cog".format(cog_amnt)
		# Easy way to append "s" if needed:
		if not len(self.bot.cogs) == 1:
			cog_count += "s"
		if empty_cog:
			cog_count += " [{:,} without commands]".format(empty_cog)

		command_count = "{:,}".format(len(self.bot.commands))
		
		# Get localized created time
		local_time = UserTime.getUserTime(ctx.author, self.settings, bot_member.created_at)
		created_at = "{} {}".format(local_time['time'], local_time['zone'])
		
		# Get localized joined time
		local_time = UserTime.getUserTime(ctx.author, self.settings, bot_member.joined_at)
		joined_at = "{} {}".format(local_time['time'], local_time['zone'])
		
		# Get the current prefix
		prefix = await self.bot.command_prefix(self.bot, ctx.message)
		prefix = ", ".join(prefix)

		# Get the owners
		ownerList = self.settings.serverDict['Owner']
		owners = "Unclaimed..."
		if len(ownerList):
			userList = []
			for owner in ownerList:
				# Get the owner's name
				user = self.bot.get_user(int(owner))
				if not user:
					userString = "Unknown User ({})".format(owner)
				else:
					userString = "{}#{}".format(user.name, user.discriminator)
				userList.append(userString)
			owners = ', '.join(userList)
			
		# Get bot's avatar url
		avatar = bot_member.avatar_url
		if not len(avatar):
			avatar = bot_member.default_avatar_url
			
		# Get status
		status_text = ":green_heart:"
		if bot_member.status == discord.Status.offline:
			status_text = ":black_heart:"
		elif bot_member.status == discord.Status.dnd:
			status_text = ":heart:"
		elif bot_member.status == discord.Status.idle:
			status_text = ":yellow_heart:"
			
		# Build the embed
		server_embed.add_field(name="Members", value=member_count, inline=True)
		server_embed.add_field(name="Servers", value=guild_count, inline=True)
		server_embed.add_field(name="Commands", value=command_count + " (in {})".format(cog_count), inline=True)
		server_embed.add_field(name="Created", value=created_at, inline=True)
		server_embed.add_field(name="Joined", value=joined_at, inline=True)
		server_embed.add_field(name="Owners", value=owners, inline=True)
		server_embed.add_field(name="Prefixes", value=prefix, inline=True)
		server_embed.add_field(name="Status", value=status_text, inline=True)
		if bot_member.game and bot_member.game.name:
			server_embed.add_field(name="Playing", value=str(bot_member.game.name), inline=True)
		server_embed.set_thumbnail(url=avatar)
		# Send the embed
		await ctx.channel.send(embed=server_embed)
		

	@commands.command(pass_context=True)
	async def ping(self, ctx):
		"""Feeling lonely?"""
		before_typing = time.monotonic()
		await ctx.trigger_typing()
		after_typing = time.monotonic()
		ms = int((after_typing - before_typing) * 1000)
		msg = '*{}*, ***PONG!*** (~{}ms)'.format(ctx.message.author.mention, ms)
		await ctx.channel.send(msg)

		
	@commands.command(pass_context=True)
	async def nickname(self, ctx, *, name : str = None):
		"""Set the bot's nickname (admin-only)."""
		
		isAdmin = ctx.message.author.permissions_in(ctx.message.channel).administrator
		# Only allow admins to change server stats
		if not isAdmin:
			await ctx.channel.send('You do not have sufficient privileges to access this command.')
			return
		
		# Let's get the bot's member in the current server
		botName = "{}#{}".format(self.bot.user.name, self.bot.user.discriminator)
		botMember = ctx.message.guild.get_member_named(botName)
		await botMember.edit(nick=name)

	@commands.command(pass_context=True)
	async def hostinfo(self, ctx):
		"""List info about the bot's host environment."""

		message = await ctx.channel.send('Gathering info...')

		# cpuCores    = psutil.cpu_count(logical=False)
		# cpuThred    = psutil.cpu_count()
		cpuThred      = os.cpu_count()
		cpuUsage      = psutil.cpu_percent(interval=1)
		memStats      = psutil.virtual_memory()
		memPerc       = memStats.percent
		memUsed       = memStats.used
		memTotal      = memStats.total
		memUsedGB     = "{0:.1f}".format(((memUsed / 1024) / 1024) / 1024)
		memTotalGB    = "{0:.1f}".format(((memTotal/1024)/1024)/1024)
		currentOS     = platform.platform()
		system        = platform.system()
		release       = platform.release()
		version       = platform.version()
		processor     = platform.processor()
		botMember     = DisplayName.memberForID(self.bot.user.id, ctx.message.guild)
		botName       = DisplayName.name(botMember)
		currentTime   = int(time.time())
		timeString    = ReadableTime.getReadableTimeBetween(self.startTime, currentTime)
		pythonMajor   = sys.version_info.major
		pythonMinor   = sys.version_info.minor
		pythonMicro   = sys.version_info.micro
		pythonRelease = sys.version_info.releaselevel
		process       = subprocess.Popen(['git', 'rev-parse', '--short', 'HEAD'], shell=False, stdout=subprocess.PIPE)
		git_head_hash = process.communicate()[0].strip()

		threadString = 'thread'
		if not cpuThred == 1:
			threadString += 's'

		msg = '***{}\'s*** **Home:**\n'.format(botName)
		msg += '```\n'
		msg += 'OS       : {}\n'.format(currentOS)
		msg += 'Hostname : {}\n'.format(platform.node())
		msg += 'Language : Python {}.{}.{} {}\n'.format(pythonMajor, pythonMinor, pythonMicro, pythonRelease)
		msg += 'Commit   : {}\n\n'.format(git_head_hash.decode("utf-8"))
		msg += ProgressBar.center('{}% of {} {}'.format(cpuUsage, cpuThred, threadString), 'CPU') + '\n'
		msg += ProgressBar.makeBar(int(round(cpuUsage))) + "\n\n"
		#msg += '{}% of {} {}\n\n'.format(cpuUsage, cpuThred, threadString)
		#msg += '{}% of {} ({} {})\n\n'.format(cpuUsage, processor, cpuThred, threadString)
		msg += ProgressBar.center('{} ({}%) of {}GB used'.format(memUsedGB, memPerc, memTotalGB), 'RAM') + '\n'
		msg += ProgressBar.makeBar(int(round(memPerc))) + "\n\n"
		#msg += '{} ({}%) of {}GB used\n\n'.format(memUsedGB, memPerc, memTotalGB)
		msg += '{} uptime```'.format(timeString)

		await message.edit(content=msg)

	@commands.command(pass_context=True)
	async def embed(self, ctx, embed_type = "field", *, embed):
		"""Builds an embed using json formatting.

		Types:
		
		field
		text

		----------------------------------

		Limits      (All - owner only):

		title_max   (256)
		desc_max    (2048)
		field_max   (25)
		fname_max   (256)
		fval_max    (1024)
		foot_max    (2048)
		auth_max    (256)
		total_max   (6000)

		----------------------------------
		
		Options     (All):

		pm_after    (int - fields, or pages)
		pm_react    (str)
		title       (str)
		page_count  (bool)
		url         (str)
		description (str)
		image       (str)
		footer      (str or dict { text, icon_url })
		thumbnail   (str)
		author      (str, dict, or User/Member)
		color       (user/member)

		----------------------------------

		Options      (field only):

		fields       (list of dicts { name (str), value (str), inline (bool) })

		----------------------------------

		Options      (text only):

		desc_head    (str)
		desc_foot    (str)
		max_pages    (int)
		"""

		channel = ctx.message.channel
		author  = ctx.message.author
		server  = ctx.message.guild

		# Only allow owner to modify the limits
		isOwner = self.settings.isOwner(ctx.author)

		try:
			embed_dict = json.loads(embed)
		except Exception as e:
			await Message.EmbedText(title="Something went wrong...", description=str(e)).send(ctx)
			return
		
		# Only allow owner to modify the limits
		isOwner = self.settings.isOwner(ctx.author)
		if not isOwner:
			embed_dict["title_max"] = 256
			embed_dict["desc_max"] = 2048
			embed_dict["field_max"] = 25
			embed_dict["fname_max"] = 256
			embed_dict["fval_max"] = 1024
			embed_dict["foot_max"] = 2048
			embed_dict["auth_max"] = 256
			embed_dict["total_max"] = 6000

		try:
			if embed_type.lower() == "field":
				await Message.Embed(**embed_dict).send(ctx)
			elif embed_type.lower() == "text":
				await Message.EmbedText(**embed_dict).send(ctx)
			else:
				await Message.EmbedText(title="Something went wrong...", description="\"{}\" is not one of the available embed types...".format(embed_type)).send(ctx)
		except Exception as e:
			try:
				e = str(e)
			except:
				e = "An error occurred :("
			await Message.EmbedText(title="Something went wrong...", description=e).send(ctx)


	@commands.command(pass_context=True)
	async def speedtest(self, ctx):
		"""Run a network speed test (owner only)."""

		channel = ctx.message.channel
		author  = ctx.message.author
		server  = ctx.message.guild

		# Only allow owner
		isOwner = self.settings.isOwner(ctx.author)
		if isOwner == None:
			msg = 'I have not been claimed, *yet*.'
			await ctx.channel.send(msg)
			return
		elif isOwner == False:
			msg = 'You are not the *true* owner of me.  Only the rightful owner can use this command.'
			await ctx.channel.send(msg)
			return

		message = await channel.send('Running speed test...')
		st = pyspeedtest.SpeedTest()
		msg = '**Speed Test Results:**\n'
		msg += '```\n'
		msg += '    Ping: {}\n'.format(round(st.ping(), 2))
		msg += 'Download: {}MB/s\n'.format(round(st.download()/1024/1024, 2))
		msg += '  Upload: {}MB/s```'.format(round(st.upload()/1024/1024, 2))
		await message.edit(content=msg)
		
		
	@commands.command(pass_context=True)
	async def adminunlim(self, ctx, *, unlimited : str = None):
		"""Sets whether or not to allow unlimited xp to admins (owner only)."""

		channel = ctx.message.channel
		author  = ctx.message.author
		server  = ctx.message.guild

		# Check for admin status
		isAdmin = ctx.author.permissions_in(ctx.channel).administrator
		if not isAdmin:
			await ctx.send("You do not have permission to use this command.")
			return
		
		# Get current status
		adminUnlimited = self.settings.getServerStat(ctx.guild, "AdminUnlimited")
		
		if unlimited == None:
			# Output unlimited status
			if adminUnlimited.lower() == "yes":
				await channel.send('Admin unlimited is enabled.')
			else:
				await channel.send('Admin unlimited is disabled.')
			return
		elif unlimited.lower() == "yes" or unlimited.lower() == "on" or unlimited.lower() == "true":
			unlimited = "Yes"
		elif unlimited.lower() == "no" or unlimited.lower() == "off" or unlimited.lower() == "false":
			unlimited = "No"
		else:
			unlimited = "No"

		if unlimited == "Yes":
			if adminUnlimited.lower() == "yes":
				msg = 'Admin unlimited remains enabled.'
			else:
				msg = 'Admin unlimited now enabled.'
		else:
			if adminUnlimited.lower() == "no":
				msg = 'Admin unlimited remains disabled.'
			else:
				msg = 'Admin unlimited now disabled.'
		self.settings.setServerStat(ctx.guild, "AdminUnlimited", unlimited)
		
		await channel.send(msg)
		
	
	@commands.command(pass_context=True)
	async def basadmin(self, ctx, *, asadmin : str = None):
		"""Sets whether or not to treat bot-admins as admins with regards to xp (admin only)."""

		channel = ctx.message.channel
		author  = ctx.message.author
		server  = ctx.message.guild

		# Check for admin status
		isAdmin = ctx.author.permissions_in(ctx.channel).administrator
		if not isAdmin:
			await ctx.send("You do not have permission to use this command.")
			return
		
		# Get current status
		botAdminAsAdmin = self.settings.getServerStat(ctx.guild, "BotAdminAsAdmin")
		
		if asadmin == None:
			# Output unlimited status
			if botAdminAsAdmin.lower() == "yes":
				await channel.send('Bot-admin as admin is enabled.')
			else:
				await channel.send('Bot-admin as admin is disabled.')
			return
		elif asadmin.lower() == "yes" or asadmin.lower() == "on" or asadmin.lower() == "true":
			asadmin = "Yes"
		elif asadmin.lower() == "no" or asadmin.lower() == "off" or asadmin.lower() == "false":
			asadmin = "No"
		else:
			asadmin = "No"

		if asadmin == "Yes":
			if botAdminAsAdmin.lower() == "yes":
				msg = 'Bot-admin as admin remains enabled.'
			else:
				msg = 'Bot-admin as admin now enabled.'
		else:
			if botAdminAsAdmin.lower() == "no":
				msg = 'Bot-admin as admin remains disabled.'
			else:
				msg = 'Bot-admin as admin now disabled.'
		self.settings.setServerStat(ctx.guild, "BotAdminAsAdmin", asadmin)
		
		await channel.send(msg)
		
		
	@commands.command(pass_context=True)
	async def joinpm(self, ctx, *, join_pm : str = None):
		"""Sets whether or not to pm the rules to new users when they join (bot-admin only)."""

		channel = ctx.message.channel
		author  = ctx.message.author
		server  = ctx.message.guild

		# Check for admin status
		isAdmin = ctx.author.permissions_in(ctx.channel).administrator
		if not isAdmin:
			checkAdmin = self.settings.getServerStat(ctx.guild, "AdminArray")
			for role in ctx.author.roles:
				for aRole in checkAdmin:
					# Get the role that corresponds to the id
					if str(aRole['ID']) == str(role.id):
						isAdmin = True
		
		if not isAdmin:
			await ctx.send("You do not have permission to use this command.")
			return
		
		# Get current status
		join_pm_setting = self.settings.getServerStat(ctx.guild, "JoinPM")
		
		if join_pm == None:
			# Output unlimited status
			if join_pm_setting.lower() == "yes":
				await channel.send('New user pm is enabled.')
			else:
				await channel.send('New user pm is disabled.')
			return
		elif join_pm.lower() == "yes" or join_pm.lower() == "on" or join_pm.lower() == "true":
			join_pm = "Yes"
		elif join_pm.lower() == "no" or join_pm.lower() == "off" or join_pm.lower() == "false":
			join_pm = "No"
		else:
			join_pm = "No"

		if join_pm == "Yes":
			if join_pm_setting.lower() == "yes":
				msg = 'New user pm remains enabled.'
			else:
				msg = 'New user pm now enabled.'
		else:
			if join_pm_setting.lower() == "no":
				msg = 'New user pm remains disabled.'
			else:
				msg = 'New user pm now disabled.'
		self.settings.setServerStat(ctx.guild, "JoinPM", join_pm)
		
		await channel.send(msg)


	@commands.command(pass_context=True)
	async def avatar(self, ctx, filename : str = None, sizeLimit : int = 8000000):
		"""Sets the bot's avatar (owner only)."""

		channel = ctx.message.channel
		author  = ctx.message.author
		server  = ctx.message.guild

		# Only allow owner
		isOwner = self.settings.isOwner(ctx.author)
		if isOwner == None:
			msg = 'I have not been claimed, *yet*.'
			await ctx.channel.send(msg)
			return
		elif isOwner == False:
			msg = 'You are not the *true* owner of me.  Only the rightful owner can use this command.'
			await ctx.channel.send(msg)
			return

		if filename is None and len(ctx.message.attachments) == 0:
			await self.bot.user.edit(avatar=None)
			await ctx.channel.send('Avatar removed!')
			# await self.bot.edit_profile(avatar=None)
			return
		
		# Check if attachment
		if filename == None:
			filename = ctx.message.attachments[0].url

		# Check if we created a temp folder for this image
		isTemp = False

		status = await channel.send('Checking if url (and downloading if valid)...')

		# File name is *something* - let's first check it as a url, then a file
		extList = ["jpg", "jpeg", "png", "gif", "tiff", "tif"]
		if GetImage.get_ext(filename) in extList:
			# URL has an image extension
			file = GetImage.download(filename)
			if file:
				# we got a download - let's reset and continue
				filename = file
				isTemp = True

		if not os.path.isfile(filename):
			if not os.path.isfile('./{}'.format(filename)):
				await status.edit(content='*{}* doesn\'t exist absolutely, or in my working directory.'.format(filename))
				# File doesn't exist
				return
			else:
				# Local file name
				filename = './{}'.format(filename)
		
		# File exists - check if image
		img = Image.open(filename)
		ext = img.format

		if not ext:
			# File isn't a valid image
			await status.edit(content='*{}* isn\'t a valid image format.'.format(filename))
			return

		wasConverted = False
		# Is an image PIL understands
		if not ext.lower == "png":
			# Not a PNG - let's convert
			await status.edit(content='Converting to png...')
			filename = '{}.png'.format(filename)
			img.save(filename)
			wasConverted = True

		# We got it - crop and go from there
		w, h = img.size
		dw = dh = 0
		if w > h:
			# Wide
			dw = int((w-h)/2)
		elif h > w:
			# Tall
			dh = int((h-w)/2)
		# Run the crop
		await status.edit(content='Cropping (if needed)...')
		img.crop((dw, dh, w-dw, h-dh)).save(filename)

		# Should be a square png here - let's check size
		# Let's make sure it's less than the passed limit

		imageSize = os.stat(filename)
		await status.edit(content='Resizing (if needed)...')
		while int(imageSize.st_size) > sizeLimit:
			# Image is too big - resize
			myimage = Image.open(filename)
			xsize, ysize = myimage.size
			ratio = sizeLimit/int(imageSize.st_size)
			xsize *= ratio
			ysize *= ratio
			myimage = myimage.resize((int(xsize), int(ysize)), Image.ANTIALIAS)
			myimage.save(filename)
			imageSize = os.stat(filename)
		# Image is resized - let's save it
		img = Image.open(filename)
		ext = img.format
		img.close()

		await status.edit(content='Uploading and applying avatar...')
		with open(filename, 'rb') as f:
			newAvatar = f.read()
			await self.bot.user.edit(avatar=newAvatar)
			# await self.bot.edit_profile(avatar=newAvatar)
		# Cleanup - try removing with shutil.rmtree, then with os.remove()
		await status.edit(content='Cleaning up...')
		if isTemp:
			GetImage.remove(filename)
		else:
			if wasConverted:
				os.remove(filename)
		await status.edit(content='Avatar set!')


	# Needs rewrite!
	@commands.command(pass_context=True)
	async def reboot(self, ctx, force = None):
		"""Reboots the bot (owner only)."""

		channel = ctx.message.channel
		author  = ctx.message.author
		server  = ctx.message.guild

		# Only allow owner
		isOwner = self.settings.isOwner(ctx.author)
		if isOwner == None:
			msg = 'I have not been claimed, *yet*.'
			await ctx.channel.send(msg)
			return
		elif isOwner == False:
			msg = 'You are not the *true* owner of me.  Only the rightful owner can use this command.'
			await ctx.channel.send(msg)
			return
		
		# Save the return channel and flush settings
		self.settings.serverDict["ReturnChannel"] = ctx.channel.id
		self.settings.flushSettings()

		quiet = False
		if force and force.lower() == 'force':
			quiet = True
		if not quiet:
			msg = 'Flushed settings to disk.\nRebooting...'
			await ctx.channel.send(msg)
		# Logout, stop the event loop, close the loop, quit
		for task in asyncio.Task.all_tasks():
			try:
				task.cancel()
			except:
				continue
		try:
			await self.bot.logout()
			self.bot.loop.stop()
			self.bot.loop.close()
		except:
			pass
		# Kill this process
		os._exit(2)


	@commands.command(pass_context=True)
	async def shutdown(self, ctx, force = None):
		"""Shuts down the bot (owner only)."""

		channel = ctx.message.channel
		author  = ctx.message.author
		server  = ctx.message.guild

		# Only allow owner
		isOwner = self.settings.isOwner(ctx.author)
		if isOwner == None:
			msg = 'I have not been claimed, *yet*.'
			await ctx.channel.send(msg)
			return
		elif isOwner == False:
			msg = 'You are not the *true* owner of me.  Only the rightful owner can use this command.'
			await ctx.channel.send(msg)
			return
		
		self.settings.flushSettings()

		quiet = False
		if force and force.lower() == 'force':
			quiet = True
		if not quiet:
			msg = 'Flushed settings to disk.\nShutting down...'
			await ctx.channel.send(msg)
		# Logout, stop the event loop, close the loop, quit
		for task in asyncio.Task.all_tasks():
			try:
				task.cancel()
			except Exception:
				continue
		try:
			await self.bot.logout()
			self.bot.loop.stop()
			self.bot.loop.close()
		except Exception:
			pass
		# Kill this process
		os._exit(3)
			

	@commands.command(pass_context=True)
	async def servers(self, ctx):
		"""Lists the number of servers I'm connected to!"""

		channel = ctx.message.channel
		author  = ctx.message.author
		server  = ctx.message.guild
		
		total = 0
		for server in self.bot.guilds:
			total += 1
		if total == 1:
			msg = 'I am a part of *1* server!'
		else:
			msg = 'I am a part of *{}* servers!'.format(total)
		await channel.send(msg)


	async def _update_status(self):
		# Helper method to update the status based on the server dict
		# Get ready - play game!
		try:
			game = self.settings.serverDict['Game']
		except Exception:
			game = None
		try:
			url = self.settings.serverDict['Stream']
		except Exception:
			url = None
		if url:
			t=1
		else:
			t=0
		# Set status
		try:
			status = self.settings.serverDict["Status"]
		except Exception:
			status = None
		
		if status == "2":
			s = discord.Status.idle
		elif status == "3":
			s = discord.Status.dnd
		elif status == "4":
			s = discord.Status.invisible
		else:
			# Online when in doubt
			s = discord.Status.online
		dgame = discord.Game(name=game, url=url, type=t)
		await self.bot.change_presence(status=s, game=dgame)


	@commands.command(pass_context=True)
	async def status(self, ctx, status = None):
		"""Gets or sets the bot's online status (owner-only).
		Options are:
		1. Online
		2. Idle
		3. DnD
		4. Invisible"""

		# Only allow owner
		isOwner = self.settings.isOwner(ctx.author)
		if isOwner == None:
			msg = 'I have not been claimed, *yet*.'
			await ctx.channel.send(msg)
			return
		elif isOwner == False:
			msg = 'You are not the *true* owner of me.  Only the rightful owner can use this command.'
			await ctx.channel.send(msg)
			return

		if status == None:
			botmem = ctx.guild.get_member(self.bot.user.id)
			await ctx.send("I'm currently set to *{}!*".format(botmem.status))
			return

		stat_string = "1"
		if status == "1" or status.lower() == "online":
			s = discord.Status.online
			stat_name = "online"
		elif status == "2" or status.lower() == "idle" or status.lower() == "away" or status.lower() == "afk":
			stat_string = "2"
			s = discord.Status.idle
			stat_name = "idle"
		elif status == "3" or status.lower() == "dnd" or status.lower() == "do not disturb" or status.lower() == "don't disturb":
			stat_string = "3"
			s = discord.Status.dnd
			stat_name = "dnd"
		elif status == "4" or status.lower() == "offline" or status.lower() == "invisible":
			stat_string = "4"
			s = discord.Status.invisible
			stat_name = "invisible"
		else:
			await ctx.send("That is not a valid status.")
			return

		self.settings.serverDict["Status"] = stat_string
		await self._update_status()
		await ctx.send("Status changed to *{}!*".format(stat_name))
			
		
	@commands.command(pass_context=True)
	async def playgame(self, ctx, *, game : str = None):
		"""Sets the playing status of the bot (owner-only)."""

		channel = ctx.message.channel
		author  = ctx.message.author
		server  = ctx.message.guild

		# Check if we're suppressing @here and @everyone mentions
		if self.settings.getServerStat(ctx.message.guild, "SuppressMentions").lower() == "yes":
			suppress = True
		else:
			suppress = False

		# Only allow owner
		isOwner = self.settings.isOwner(ctx.author)
		if isOwner == None:
			msg = 'I have not been claimed, *yet*.'
			await ctx.channel.send(msg)
			return
		elif isOwner == False:
			msg = 'You are not the *true* owner of me.  Only the rightful owner can use this command.'
			await ctx.channel.send(msg)
			return

		if game == None:
			self.settings.serverDict['Game'] = None
			self.settings.serverDict['Stream'] = None
			msg = 'Removing my playing status...'
			status = await channel.send(msg)

			await self._update_status()
			
			await status.edit(content='Playing status removed!')
			return

		self.settings.serverDict['Game'] = game
		self.settings.serverDict['Stream'] = None
		msg = 'Setting my playing status to *{}*...'.format(game)
		# Check for suppress
		if suppress:
			msg = Nullify.clean(msg)
		status = await channel.send(msg)

		await self._update_status()
		# Check for suppress
		if suppress:
			game = Nullify.clean(game)
		await status.edit(content='Playing status set to *{}!*'.format(game))


	@commands.command(pass_context=True)
	async def streamgame(self, ctx, url = None, *, game : str = None):
		"""Sets the streaming status of the bot, requires the url and the game (owner-only)."""

		channel = ctx.message.channel
		author  = ctx.message.author
		server  = ctx.message.guild

		# Check if we're suppressing @here and @everyone mentions
		if self.settings.getServerStat(ctx.message.guild, "SuppressMentions").lower() == "yes":
			suppress = True
		else:
			suppress = False

		# Only allow owner
		isOwner = self.settings.isOwner(ctx.author)
		if isOwner == None:
			msg = 'I have not been claimed, *yet*.'
			await ctx.channel.send(msg)
			return
		elif isOwner == False:
			msg = 'You are not the *true* owner of me.  Only the rightful owner can use this command.'
			await ctx.channel.send(msg)
			return

		if url == None:
			self.settings.serverDict['Game'] = None
			self.settings.serverDict['Stream'] = None
			msg = 'Removing my streaming status...'
			status = await channel.send(msg)

			await self._update_status()
			
			await status.edit(content='Streaming status removed!')
			return

		if game == None:
			# We're missing parts
			msg = "Usage: `{}streamgame [url] [game]`".format(ctx.prefix)
			await ctx.send(msg)
			return

		# Verify url
		matches = re.finditer(self.regex, url)
		match_url = None
		for match in matches:
			match_url = match.group(0)
		
		if not match_url:
			# No valid url found
			await ctx.send("Url is invalid!")
			return

		self.settings.serverDict['Game'] = game
		self.settings.serverDict['Stream'] = url
		msg = 'Setting my streaming status to *{}*...'.format(game)
		# Check for suppress
		if suppress:
			msg = Nullify.clean(msg)
		status = await channel.send(msg)

		await self._update_status()
		# Check for suppress
		if suppress:
			game = Nullify.clean(game)
		await status.edit(content='Streaming status set to *{}* at `{}`!'.format(game, url))
	

	@commands.command(pass_context=True)
	async def setbotparts(self, ctx, *, parts : str = None):
		"""Set the bot's parts - can be a url, formatted text, or nothing to clear."""
		
		# Check if we're suppressing @here and @everyone mentions
		if self.settings.getServerStat(ctx.message.guild, "SuppressMentions").lower() == "yes":
			suppress = True
		else:
			suppress = False

		# Only allow owner
		isOwner = self.settings.isOwner(ctx.author)
		if isOwner == None:
			msg = 'I have not been claimed, *yet*.'
			await ctx.channel.send(msg)
			return
		elif isOwner == False:
			msg = 'You are not the *true* owner of me.  Only the rightful owner can use this command.'
			await ctx.channel.send(msg)
			return

		channel = ctx.message.channel
		author  = ctx.message.author
		server  = ctx.message.guild

		if not parts:
			parts = ""
			
		self.settings.setGlobalUserStat(self.bot.user, "Parts", parts)
		msg = '*{}\'s* parts have been set to:\n{}'.format(DisplayName.serverNick(self.bot.user, server), parts)
		# Check for suppress
		if suppress:
			msg = Nullify.clean(msg)
		await channel.send(msg)

	@commands.command(pass_context=True)
	async def source(self, ctx):
		"""Link the github source."""
		source = "https://github.com/corpnewt/CorpBot.py"
		msg = '**My insides are located at:**\n\n{}'.format(source)
		await ctx.channel.send(msg)

	@commands.command(pass_context=True)
	async def block(self, ctx, *, server : str = None):
		"""Blocks the bot from joining a server - takes either a name or an id (owner-only).
		Can also take the id or case-sensitive name + descriminator of the owner (eg. Bob#1234)."""
		# Check if we're suppressing @here and @everyone mentions
		if self.settings.getServerStat(ctx.message.guild, "SuppressMentions").lower() == "yes":
			suppress = True
		else:
			suppress = False

		# Only allow owner
		isOwner = self.settings.isOwner(ctx.author)
		if isOwner == None:
			msg = 'I have not been claimed, *yet*.'
			await ctx.channel.send(msg)
			return
		elif isOwner == False:
			msg = 'You are not the *true* owner of me.  Only the rightful owner can use this command.'
			await ctx.channel.send(msg)
			return
		
		if server == None:
			# No server provided
			await ctx.send("Usage: `{}block [server name/id or owner name#desc/id]`".format(ctx.prefix))
			return
		
		try:
			serverList = self.settings.serverDict['BlockedServers']
		except KeyError:
			self.settings.serverDict['BlockedServers'] = []
			serverList = self.settings.serverDict['BlockedServers']

		for serv in serverList:
			if str(serv).lower() == server.lower():
				# Found a match - already blocked.
				msg = "*{}* is already blocked!".format(serv)
				if suppress:
					msg = Nullify.clean(msg)
				await ctx.channel.send(msg)
				return
		
		# Not blocked
		self.settings.serverDict['BlockedServers'].append(server)
		msg = "*{}* now blocked!".format(server)
		# Check for suppress
		if suppress:
			msg = Nullify.clean(msg)
		await ctx.channel.send(msg)


	@commands.command(pass_context=True)
	async def unblock(self, ctx, *, server : str = None):
		"""Unblocks a server or owner (owner-only)."""
		# Check if we're suppressing @here and @everyone mentions
		if self.settings.getServerStat(ctx.message.guild, "SuppressMentions").lower() == "yes":
			suppress = True
		else:
			suppress = False

		# Only allow owner
		isOwner = self.settings.isOwner(ctx.author)
		if isOwner == None:
			msg = 'I have not been claimed, *yet*.'
			await ctx.channel.send(msg)
			return
		elif isOwner == False:
			msg = 'You are not the *true* owner of me.  Only the rightful owner can use this command.'
			await ctx.channel.send(msg)
			return
		
		if server == None:
			# No server provided
			await ctx.send("Usage: `{}unblock [server name/id or owner name#desc/id]`".format(ctx.prefix))
			return
		
		try:
			serverList = self.settings.serverDict['BlockedServers']
		except KeyError:
			self.settings.serverDict['BlockedServers'] = []
			serverList = self.settings.serverDict['BlockedServers']

		for serv in serverList:
			if str(serv).lower() == server.lower():
				# Found a match - already blocked.
				self.settings.serverDict['BlockedServers'].remove(serv)
				msg = "*{}* unblocked!".format(serv)
				if suppress:
					msg = Nullify.clean(msg)
				await ctx.channel.send(msg)
				return
		
		# Not found
		msg = "I couldn't find *{}* in my blocked list.".format(server)
		# Check for suppress
		if suppress:
			msg = Nullify.clean(msg)
		await ctx.channel.send(msg)


	@commands.command(pass_context=True)
	async def unblockall(self, ctx):
		"""Unblocks all blocked servers and owners (owner-only)."""
		# Check if we're suppressing @here and @everyone mentions
		if self.settings.getServerStat(ctx.message.guild, "SuppressMentions").lower() == "yes":
			suppress = True
		else:
			suppress = False

		# Only allow owner
		isOwner = self.settings.isOwner(ctx.author)
		if isOwner == None:
			msg = 'I have not been claimed, *yet*.'
			await ctx.channel.send(msg)
			return
		elif isOwner == False:
			msg = 'You are not the *true* owner of me.  Only the rightful owner can use this command.'
			await ctx.channel.send(msg)
			return
		
		self.settings.serverDict['BlockedServers'] = []

		await ctx.channel.send("*All* servers and owners unblocked!")


	@commands.command(pass_context=True)
	async def blocked(self, ctx):
		"""Lists all blocked servers and owners (owner-only)."""
		# Check if we're suppressing @here and @everyone mentions
		if self.settings.getServerStat(ctx.message.guild, "SuppressMentions").lower() == "yes":
			suppress = True
		else:
			suppress = False

		# Only allow owner
		isOwner = self.settings.isOwner(ctx.author)
		if isOwner == None:
			msg = 'I have not been claimed, *yet*.'
			await ctx.channel.send(msg)
			return
		elif isOwner == False:
			msg = 'You are not the *true* owner of me.  Only the rightful owner can use this command.'
			await ctx.channel.send(msg)
			return

		try:
			serverList = self.settings.serverDict['BlockedServers']
		except KeyError:
			self.settings.serverDict['BlockedServers'] = []
			serverList = self.settings.serverDict['BlockedServers']

		if not len(serverList):
			msg = "There are no blocked servers or owners!"
		else:
			msg = "__Currently Blocked:__\n\n{}".format(', '.join(serverList))

		# Check for suppress
		if suppress:
			msg = Nullify.clean(msg)
		await ctx.channel.send(msg)
			


	@commands.command(pass_context=True)
	async def cloc(self, ctx):
		"""Outputs the total count of lines of code in the currently installed repo."""
		# Script pulled and edited from https://github.com/kyco/python-count-lines-of-code/blob/python3/cloc.py
		
		# Get our current working directory - should be the bot's home
		path = os.getcwd()
		
		# Set up some lists
		extensions = []
		code_count = []
		include = ['py','bat','sh']
		
		# Get the extensions - include our include list
		extensions = self.get_extensions(path, include)
		
		for run in extensions:
			extension = "*."+run
			temp = 0
			for root, dir, files in os.walk(path):
				for items in fnmatch.filter(files, extension):
					value = root + "/" + items
					temp += sum(+1 for line in open(value, 'rb'))
			code_count.append(temp)
			pass
		
		# Set up our output
		msg = 'Some poor soul took the time to sloppily write the following to bring me life:\n```\n'
		padTo = 0
		for idx, val in enumerate(code_count):
			# Find out which has the longest
			tempLen = len(str('{:,}'.format(code_count[idx])))
			if tempLen > padTo:
				padTo = tempLen
		for idx, val in enumerate(code_count):
			lineWord = 'lines'
			if code_count[idx] == 1:
				lineWord = 'line'
			# Setup a right-justified string padded with spaces
			numString = str('{:,}'.format(code_count[idx])).rjust(padTo, ' ')
			msg += numString + " " + lineWord + " of " + extensions[idx] + "\n"
			# msg += extensions[idx] + ": " + str(code_count[idx]) + ' ' + lineWord + '\n'
			# print(extensions[idx] + ": " + str(code_count[idx]))
			pass
		msg += '```'
		await ctx.channel.send(msg)
		
	@cloc.error
	async def cloc_error(self, ctx, error):
		# do stuff
		msg = 'cloc Error: {}'.format(ctx)
		await error.channel.send(msg)

	# Helper function to get extensions
	def get_extensions(self, path, excl):
		extensions = []
		for root, dir, files in os.walk(path):
			for items in fnmatch.filter(files, "*"):
				temp_extensions = items.rfind(".")
				ext = items[temp_extensions+1:]
				if ext not in extensions:
					if ext in excl:
						extensions.append(ext)
						pass
		return extensions
