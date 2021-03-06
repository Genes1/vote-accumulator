"""
This is a bot meant to serve as a vote accumulator. Votes are defined as reactions.

Features:
	- track the upvotes, downvotes, and cumulative score performed while the bot is up with an sqlite db

	General commands:
		- show any user's scores and ratio
		- display the top x users by score, upvotes, downvotes 

	Admin commands:
		- kill running bot instances
		- display users with lower upvote ratios than one that is chosen
		- force the database to sync with all member info on the server
		- write the database to the console or a specified file
		- clear the database records


Considerations made while building:
	- bot votes are not counted
	- votes of users on their own posts are not counted
	- # of votes cannot go below zero
	- an attachment has to be present in the message for votes to count
	- joining the server adds to db, leaving the server removes from the db
	- namechanges are tracked and update automatically
	- the db is automatically updated when initialized (at the start of a run)

Operation notes:
	- terminate (.kill) and restart the bot if you are seeing multiple messages per command
		- multiple bot instances WILL CAUSE RACE CONDITIONS AND UNWANTED DB MUTATIONS. Restart under suspicion of multiple instances
	- some commands look for administrator privileges, make sure you have them
	- make sure you have your token in a token.txt file in the same directory as the bot.py script
	- you better know what you're doing if you're using the long command
	- the bot is ONLY tracking when it is online -- only changes are detected. messages are not stored
	- *error.log* will be automatically made and remade whenever it is needed to log an error
	- *votes.db* will similarly regenerate when no instance of it is detected

Steps to operate:
	0. Install python 3 (download/install) and discord.py (pip install discord.py). 
		- Ensure you can run python from the commmand line (e.g. 'python --version' at the command prompt gives you a version)
		- If it does not work, add your python directory to your PATH environment variable
	1. Navigate to the folder you will host the bot in
	2. Drop the *bot.py* script in this directory
	2. Generate your bot token, and place it into a new file called *token.txt* in this directory
	3. At this point, you will be ready to start the bot. Open your command prompt (windows + R, 'cmd')
	4. Navigate to the directory with bot.py (via cd [directory/path/here])
	5. Run the bot script with 'python bot.py' in the cmd. The bot should go online and start updating the database
	6. Congrats! You can now run the bot's custom commands. They are prefixed with a period ('.'). Check '.help' for more info
	

"""


import discord, sqlite3, json
from difflib import SequenceMatcher
from discord.ext import commands
from datetime import datetime

with open('token.txt', 'r') as f:
	token = f.read()

with open('config.json', 'r') as f:
	config = json.load(f)

intents = discord.Intents.default()  
intents.members = True 

client = commands.Bot(command_prefix = '.', intents = intents)
client.remove_command('help')




#--------------------------------------- UTILITY FUNCTIONS ---------------------------------------------



async def init_db():

	"""
		Initialize the database.

		Row structure:
		# 0: user id			unique int
		# 1: user				text
		# 2: upvotes earned		int, + (unenforced)
		# 3: downvotes earned 	int, + (unenforced)
		# 4: score 				int

	"""

	connection, cursor = get_db_and_cursor()
	init_command = """CREATE TABLE IF NOT EXISTS users(	
														user_id INTEGER PRIMARY KEY,
	 													user_name TEXT, 
	 													upvotes_earned INTEGER, 
	 													downvotes_earned INTEGER, 
	 													score INTEGER,
	 													times_voted INTEGER
	 												)"""
	 												
	cursor.execute(init_command)


	# RESET DB
	# cursor.execute("DELETE FROM users")
	# cursor.execute("SELECT * FROM users")
	# print("DB cleared.")

	connection.commit()
	result = cursor.fetchall()






def get_db_and_cursor():

	""" Create and return a database connection to votes.db """

	connection = sqlite3.connect('votes.db')
	cursor = connection.cursor()
	return [connection, cursor]







async def add_user(db, cursor, member):

	""" Add a user to the database. """

	if not member.bot:
		cursor.execute("INSERT INTO users (user_id, user_name, upvotes_earned, downvotes_earned, score, times_voted) VALUES (?, ?, 0, 0, 0, 0)", (member.id, member.name))
		db.commit()






async def log(info):

	""" Log an error that occurred while the bot ran. """
	filename = 'error.log' if not config["logging"]["log_file"] else config["logging"]["log_file"]
	with open(filename, 'a') as f:
		f.write(datetime.now().strftime('[%m/%d %H:%M:%S]\n') + info + '\n\n')





async def log_guess(info):

	""" Log an error that occurred while the bot ran. """
	filename = 'guess.log' if not config["logging"]["guess_file"] else config["logging"]["guess_file"]
	with open(filename, 'a') as f:
		f.write(datetime.now().strftime('[%m/%d %H:%M:%S]\n') + info + '\n\n')





def result_to_string(row):

	""" Convert a row from the table to a string in printable format. """

	s = "============ " + str(row[1]) + "'s stats ============ \n"
	s += "Total: " + str(row[4]) + '\n'
	s += "Upvotes: " + str(row[2]) + '\n'
	s += "Downvotes: " + str(row[3]) + '\n'
	s += "% Upvotes: " + ('0' if row[2] + row[3] == 0 else str(int(100 * (row[2] / (row[2] + row[3]))))) + '%\n'
	s += "Times voted: " + str(row[5]) + '\n'
	return s



#--------------------------------------------------------------------------------------------------------














# =========================================== EVENTS ========================================



@client.event

async def on_ready():

	game = discord.Game(".help | counting votes")
	await client.change_presence(activity = game)

	await init_db()
	members = client.get_all_members()
	db, cursor = get_db_and_cursor()
	print("Updating DB on startup...")
	#cursor.execute("ALTER TABLE users ADD COLUMN times_voted INTEGER") right here right now

	for member in members:
		try:
			await add_user(db, cursor, member)
		except sqlite3.IntegrityError:
			cursor.execute("UPDATE users SET user_name = ? WHERE user_id = ?", (member.name, member.id))
			#cursor.execute("UPDATE users SET times_voted = ? WHERE user_id = ?", (0, member.id))
			#print("%s's name was updated. (id = %d)" % (member.name, member.id))





	print("DB was automatically updated.\n")
	db.commit()

	print("The count bot is awaiting reactions.")







@client.event

async def on_member_join(member):

	if member.bot:
		return

	db, cursor = get_db_and_cursor()
	await add_user(db, cursor, member)






@client.event

async def on_member_remove(member):

	if member.bot:
		return

	db, cursor = get_db_and_cursor()
	cursor.execute("DELETE FROM users WHERE user_id = ?", (member.id,))
	db.commit()






@client.event

async def on_user_update(before, after):

	if before.bot:
		return

	db, cursor = get_db_and_cursor()
	cursor.execute("UPDATE users SET user_name = ? WHERE user_id = ?", (after.name, before.id,))
	db.commit()






@client.event

async def on_raw_reaction_add(payload):

	voter = payload.member

	if not voter.bot:

		db, cursor = get_db_and_cursor()

		channel = await client.fetch_channel(payload.channel_id)
		category = await client.fetch_channel(payload.channel_id)
		message = await channel.fetch_message(payload.message_id)

		author = message.author

		#print(category.id)
		# or channel not in category.channels

		if client.get_guild(payload.guild_id).get_member(author.id) == None or author.bot or len(message.attachments) == 0 :
			return

		if author.id == voter.id:
			await message.remove_reaction(payload.emoji, voter)
			return

		if payload.emoji.name == '1Upvote':

			# increment score of poster
			cursor.execute("UPDATE users SET upvotes_earned = upvotes_earned + 1 WHERE user_id = ?", (author.id,))
			cursor.execute("UPDATE users SET score = score + 1 WHERE user_id = ?", (author.id,))
			result = cursor.execute("SELECT * FROM users WHERE user_id = ? LIMIT 1", (author.id,))
			info = result.fetchone()
			
			if info == None:
				print("No results were found for the given author (%s). Consider updating the database." % (author.name))
			else:
				db.commit()
		elif payload.emoji.name == '1Downvote':
			
			# decrement score 
			cursor.execute("UPDATE users SET downvotes_earned = downvotes_earned + 1 WHERE user_id = ?", (author.id,))
			cursor.execute("UPDATE users SET score = score - 1 WHERE user_id = ?", (author.id,))
			result = cursor.execute("SELECT * FROM users WHERE user_id = ? LIMIT 1", (author.id,))
			info = result.fetchone()

			if info == None:
				print("No results were found for the given author (%s). Consider updating the database." % (author.name))
			else:
				db.commit()


		# add to voter's vote count
		if payload.emoji.name == '1Upvote' or payload.emoji.name == '1Downvote':
			cursor.execute("UPDATE users SET times_voted = times_voted + 1 WHERE user_id = ?", (voter.id,))
			result = cursor.execute("SELECT * FROM users WHERE user_id = ? LIMIT 1", (voter.id,))
			info = result.fetchone()
			if info == None:
				print("No results were found for the given voter (%s). Consider updating the database." % (voter.name))
			else:
				db.commit()

		# post-wise counting, see if report should be made
		up, down = 0, 0
		for reaction in message.reactions:
			if str(reaction) =='<:1Upvote:722604262571377073>':
				up += reaction.count
			elif str(reaction) == '<:1Downvote:722598932500447265>':
				down += reaction.count

		if down > up + 5:
			log_channel = client.get_channel(int(config["logging"]["log_channel"]))
			await log_channel.send(f'http://discordapp.com/channels/{payload.guild_id}/{payload.channel_id}/{payload.message_id}')





@client.event

async def on_raw_reaction_remove(payload):

	db, cursor = get_db_and_cursor()

	channel = await client.fetch_channel(payload.channel_id)
	message = await channel.fetch_message(payload.message_id)
	author = message.author
	voter = payload.user_id

	if client.get_guild(payload.guild_id).get_member(author.id) == None:
		return

	if author.bot or author.id == payload.user_id or len(message.attachments) == 0:
		return

	if payload.emoji.name == '1Upvote':

		cursor.execute("SELECT upvotes_earned FROM users WHERE user_id = ? LIMIT 1", (author.id,))
		
		if cursor.fetchone()[0] > 0: # don't allow negative upvotes -- score doesn't decrease although -upvote
			cursor.execute("UPDATE users SET upvotes_earned = upvotes_earned - 1 WHERE user_id = ?", (author.id,))
			cursor.execute("UPDATE users SET score = score - 1 WHERE user_id = ?", (author.id,))
			result = cursor.execute("SELECT * FROM users WHERE user_id = ? LIMIT 1", (author.id,))
			info = result.fetchone()

			if info == None:
				print("No results were found for the given author (%s). Consider updating the database." % (author.name))
			else:
				db.commit()

	elif payload.emoji.name == '1Downvote':

		cursor.execute("SELECT downvotes_earned FROM users WHERE user_id = ? LIMIT 1", (author.id,))

		if cursor.fetchone()[0] > 0: # don't allow negative downvotes -- score doesn't increase although -downvote
			cursor.execute("UPDATE users SET downvotes_earned = downvotes_earned - 1 WHERE user_id = ?", (author.id,))
			cursor.execute("UPDATE users SET score = score + 1 WHERE user_id = ?", (author.id,))
			result = cursor.execute("SELECT * FROM users WHERE user_id = ? LIMIT 1", (author.id,))
			info = result.fetchone()

			if info == None:
				print("No results were found for the given author (%s). Consider updating the database." % (author.name))
			else:
				db.commit()

	# decrement voter's votes count
	if payload.emoji.name == '1Upvote' or payload.emoji.name == '1Downvote':
		cursor.execute("UPDATE users SET times_voted = times_voted - 1 WHERE user_id = ?", (voter,))
		result = cursor.execute("SELECT * FROM users WHERE user_id = ? LIMIT 1", (voter,))
		info = result.fetchone()
		if info == None:
			print("No results were found for the given voter id (%s). Consider updating the database." % (voter))
		else:
			db.commit()







@client.event

async def on_message(message):

	# only look in moderated channel
	if message.channel.id == 817630036625588274:

		# make sure it's not the bot
		if message.author != client.user:
			
			user = client.get_user(message.author.id)

			if len(message.content) <= 256:
				print(message.content)
				s = message.author.name + '[' + str(message.author.id) + ']: \n' + message.content
				await log_guess(s)
				await user.send(("Thank you for submitting! Your guess is as follows:\n```%s```" % message.content))

		
		await message.delete()






@client.event

async def on_command_error(ctx, exc):  

	await log("\'%s\' by %s: \n%s => %s" % (ctx.message.content, ctx.message.author, type(exc), str(exc)))
	if type(exc) == discord.ext.commands.errors.MissingRequiredArgument:
		await ctx.channel.send("`Please provide the proper format for this command. Check .help for formatting.`")
	elif type(exc) == discord.ext.commands.errors.CommandNotFound:
		await ctx.channel.send("`No such command exists.  Check .help for a list of commands.`")
	elif type(exc) == discord.ext.commands.errors.MissingPermissions:
		await ctx.channel.send("`You do not have sufficient permissions to run that command.`")
	elif type(exc) == discord.ext.commands.errors.CommandInvokeError: 
		print("An unexpected error occured: " + str(exc))
	else:
		print("OMEGALUL: " + str(exc))



# ==================================================================================================









# ////////////////////////////////////// USER COMMANDS \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\



@client.command(aliases = ['score', 'show', 'votes'])

async def stats(ctx, *args):

	"""
		Display the upvotes, downvotes, and stats of an individual.
		Usage: .stats [user id] | .stats me
	"""

	db, cursor = get_db_and_cursor()
	s = ''

	if args[0] == "me":

		arg = ctx.message.author.id
		cursor.execute("SELECT * FROM users WHERE user_id = ? LIMIT 1", (arg,))
		result = cursor.fetchone()
		s = result_to_string(result) if result != None else "No such user found."

	elif args[0] == "id":

		if len(args) > 1:

			cursor.execute("SELECT * FROM users WHERE user_id = ? LIMIT 1", (args[1],))
			result = cursor.fetchone()
			s = result_to_string(result) if result != None else "No such user found."

		else:
			await ctx.channel.send("`Please enter the approriate number of arguments for id usage.`")
			return

	else:

		cursor.execute("SELECT * FROM users")
		matches = []

		for result in cursor.fetchall():
			if SequenceMatcher(None, args[0].lower(), result[1].lower()).ratio() >= 0.75:
				matches.append(list(result))
			#print("%s is similar to %s: %s" % (result[1].lower(), args[0].lower(), SequenceMatcher(None, args[0].lower(), result[1].lower()).ratio()))

		for match in matches:
			user = client.get_user(match[0])
			if user == None:
				continue
			match[1] = "%s#%s" % (user.name, user.discriminator)
			s += result_to_string(match)

		if s == '':
			s += "No results found."


	await ctx.channel.send('```' + s + '```')






@client.command(pass_context = True, aliases = ['sort'])

async def top(ctx, *args):

	"""
		Display the upvotes, downvotes, and stats of an individual.
		Usage: .top [places](1-10) [criteria](up/down/ratio/score)
	"""

	if len(args) == 0 or len(args) > 2:
		await ctx.channel.send("`Please use the approriate amount of arguments for this command. .help for more info.`")
		return 		

	try:
		num = int(args[0])
	except ValueError:
		await ctx.channel.send("`Enter an integer as the first argument for this command.`")
		return 

	if num < 1 or num > 10:
		await ctx.channel.send("`Enter a number 1-10 as the argument.`")
		return


	k = 'score'

	if len(args) == 2:
		if args[1] == 'up':
			k = "upvotes_earned"
		elif args[1] == 'down':	
			k = "downvotes_earned"
		elif args[1] == 'votes':	
			k = "times_voted"
		else:
			await ctx.channel.send("`The second argument was not one of ['', 'score', 'up', 'down', 'votes']. Try again.`")
			return

	q = "SELECT * FROM users ORDER BY %s DESC LIMIT ?" % k

	db, cursor = get_db_and_cursor()


	cursor.execute(q, (num,))
	s = "{:^63}\n".format("Top %s curator%s ordered by %s" % ('' if (num == 1) else num, 's' if (num > 1) else '', k.replace('_', ' ')))
	s += ' ' + '_' * 71 + ' \n'
	s +=  "|{:^38}|{:^5}|{:^5}|{:^5}|{:^5}|{:^8}|\n".format("Name", "Score", "Up", "Down", "% Up", "Votes")
	s += '·' + '-' * 38 + '+' + '-' * 5 + '+' + '-' * 5 + '+' + '-' * 5 + '+' + '-' * 5 + '+' + '-' * 8 + '·\n'
	i = 1

	for row in cursor.fetchall():
		if (row[3] != 0 or row[4] != 0) or k == 'times_voted': 
			s += "|{:<5}{:<32} |{:<5}|{:<5}|{:<5}|{:<5}|{:<8}|\n".format(str(i) + '.', row[1], row[4], row[2], row[3], 
				str(int(100 * (row[2] / (row[2] + row[3]) if (row[2] + row[3]) != 0 else 0))) + '%', row[5])
			s += '·' + '-' * 38 + '+' + '-' * 5 + '+' + '-' * 5 + '+' + '-' * 5 + '+' + '-' * 5 + '+' + '-' * 8 + '·\n'
			i += 1

	await ctx.channel.send('```' + s + '```')






@client.command(pass_context = True, aliases = ['helpme'])

async def help(ctx):

	""" List the available commands to general users. """

	embed = discord.Embed(
		colour = discord.Colour.blue()
	)

	embed.set_author(name = config["embed"]["author"], icon_url = config["embed"]["author_image"])
	embed.set_image(url = config["embed"]["bottom_image"])
	embed.set_thumbnail(url = config["embed"]["thumbnail_image"])


	embed.add_field(name = ".score\nalias: [.show, .votes]", value = "`.score [username]`\n`.score id [user id]`\n`.score me`\n\nShow the score, upvotes, and downvotes for the given user.")
	embed.add_field(name = ".top\nalias: [.sort]\n", value = "`.top (1-10) (score/up/down/votes)`\n`.top (1-10)` \n\nShow the stats, in order, of the top X users. Is ordered by a criteria, which may be specified as 'score', 'up', 'down', or 'votes'. Takes on 'score' by default, if left empty.")
	embed.add_field(name = "\nLeaving", value = "Leaving the server and rejoining ***WILL WIPE YOUR SCORE.*** For this reason, we can *not* recover voting records of previous visits. This lets us keep the database small and efficient.", inline = False)

	await ctx.channel.send(embed = embed)




# ///////////////////////////////////////////////\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\





# +++++++++++++++++++++++++++++++++++++ ADMIN COMMANDS +++++++++++++++++++++++++++++++++++++++++++++++



@client.command(pass_context = True, aliases = ['end', 'terminate'])
@commands.has_permissions(administrator = True)

async def kill(ctx):

	""" 
		Kill all bot instances. 

		If you are experiencing multiple messages or other hiccups, use this command 
		and then restart the bot. 
	"""

	await ctx.channel.send("`Bot is being terminated...`")
	await client.logout()
	print("Bot was terminated.")






@client.command(pass_context = True, aliases = ['cu'])
@commands.has_permissions(administrator = True)

async def change_up(ctx, *args):

	"""
		Add a certain amount to a user's score.
	"""

	db, cursor = get_db_and_cursor()
	s = ''


	cursor.execute("SELECT * FROM users WHERE user_id = ? LIMIT 1", (args[0],))
	result = cursor.fetchone()
	s = result_to_string(result) if result != None else "No such user found."

	try:
		num = int(args[1])
	except ValueError:
		await ctx.channel.send("`Enter an integer as the first argument for this command.`")
		return 

	if s != "No such user found.":
		cursor.execute("UPDATE users SET upvotes_earned = upvotes_earned + ? WHERE user_id = ?", (num, args[0],))
		await ctx.channel.send("`Update was run.`")
	else:
		await ctx.channel.send("`User was not found.`")

	db.commit()






@client.command(pass_context = True, aliases = ['cd'])
@commands.has_permissions(administrator = True)

async def change_down(ctx, *args):

	"""
		Add a certain amount to a user's score.
	"""

	db, cursor = get_db_and_cursor()
	s = ''


	cursor.execute("SELECT * FROM users WHERE user_id = ? LIMIT 1", (args[0],))
	result = cursor.fetchone()
	s = result_to_string(result) if result != None else "No such user found."

	try:
		num = int(args[1])
	except ValueError:
		await ctx.channel.send("`Enter an integer as the first argument for this command.`")
		return 

	if s != "No such user found.":
		cursor.execute("UPDATE users SET downvotes_earned = downvotes_earned + ? WHERE user_id = ?", (num, args[0],))
		await ctx.channel.send("`Update was run.`")
	else:
		await ctx.channel.send("`User was not found.`")

	db.commit()






@client.command(aliases = ['sync'])
@commands.has_permissions(administrator = True)

async def update(ctx):

	""" Update the database on call. """

	print("Manual database update started...")
	members = ctx.guild.members
	db, cursor = get_db_and_cursor()
	for member in members:
		try:
			await add_user(db, cursor, member)
		except sqlite3.IntegrityError:
			cursor.execute("UPDATE users SET user_name = ? WHERE user_id = ?", (member.name, member.id))
			pass
	print("Database was updated.")
	db.commit()






@client.command(aliases = ['db'])
@commands.has_permissions(administrator = True)

async def show_db(ctx, *args):

	"""
		Show the contents of the entire database.
		If no arguments are provided, print the db in the python console.
		Otherwise, create/overwrite the file specified by the first argument.
	"""

	connection, cursor = get_db_and_cursor()
	cursor.execute("SELECT * FROM users")

	if len(args) == 0:
		print('\n' + '-' * 32 + '\n')
		for t in cursor.fetchall():
			print(result_to_string(t))
		print('-' * 32 + '\n')
	else:
		with open(args[0], "w") as f:
			f.write('\n' + '-' * 32 + '\n')
			for t in cursor.fetchall():
				f.write(result_to_string(t))
			f.write('-' * 32 + '\n')






@client.command(aliases = ['lim'])
@commands.has_permissions(administrator = True)

async def limit(ctx, *args):

	"""
		Display users with an upvote ratio lower than the first argument (ratio).
		Upvote ratio is calculated as up / (up + down).
		Takes an optional secondary argument, a minimum number of votes for consideration.
	"""

	try:
		limit = float(args[0])
		second_arg = False
		if len(args) > 1:
			specified_votes = int(args[1])
			second_arg = True
	except ValueError:
		await ctx.channel.send("`Please ensure that you have the proper argument types for this command.`")
		return 

	if limit <= 0.0 and limit >= 1.0:
		await ctx.channel.send("`Enter a decimal 0 <= x <= 1 as the first argument for this command.`")
		return 	

	connection, cursor = get_db_and_cursor()
	cursor.execute("SELECT * FROM users")


	s = "```The following users have below a %s like ratio%s:\n" % (limit, '' if not second_arg else " with at least %s votes" % (specified_votes))
	s += '=' * 59 + '\n'
	found = False

	for row in cursor.fetchall():
		if row[3] != 0 or row[4] != 0:
			total = row[2] + row[3]
			ratio = row[2] / total
			if ratio <= limit:
				if second_arg and total < specified_votes:
					continue
				found = True
				s += "{:<32} | {:>3}% upvotes, {:>4} votes\n".format(row[1], int(round(ratio * 100)), row[2] + row[3])

	if not found:
		s += "There were no users with ratios found below this threshold.\n"

	s += '=' * 59 + "```"

	await ctx.channel.send(s)







@client.command()
@commands.has_permissions(administrator = True)

async def destroy_the_database_yes_i_know_what_this_means(ctx, arg):

	""" If you have any data, PLEASE BACK IT UP!!!! """

	connection, cursor = get_db_and_cursor()
	cursor.execute("DELETE FROM users")
	cursor.execute("SELECT * FROM users")
	connection.commit()







@client.command(aliases = ['admin'], pass_context = True)
@commands.has_permissions(administrator = True)

async def admin_help(ctx):

	""" List the commands available to admins. """

	embed = discord.Embed(
		colour = discord.Colour.blue()
	)
	
	embed.set_author(name = config["embed"]["author"] + " [Admin]", icon_url = config["embed"]["author_image"])
	embed.set_image(url = config["embed"]["bottom_image"])
	embed.set_thumbnail(url = config["embed"]["thumbnail_image"])

	embed.add_field(name = ".kill\nalias: [.end, .terminate]\n\n", value = "`.kill`\n\nKill all instances of the bot currently running. Use this before restarting, or if you get multiple bot messages per command.")
	embed.add_field(name = ".limit\nalias: [.lim]", value = "`.limit (0.0 - 1.0)`\n`.limit (0.0 - 1.0) [X>0]`\n\nDisplay all users with an upvote ratio (up / [up + down]) lower than the one specified. An additional argument qualifies the search for the user to have at least X amount of votes recorded.")
	embed.add_field(name = ".update\nalias: [.sync]", value = "`.update`\n\nUpdate the database to have all currently visible users and their usernames.")
	embed.add_field(name = ".change_down\nalias: [.cd]", value = "`.change_down [user_id] [int X]`\n\nChange a user's downvotes by a given amount. Can be positive or negative.")
	embed.add_field(name = ".change_up\nalias: [.cu]", value = "`.change_up [user_id] [int X]`\n\nChange a user's upvotes by a given amount. Can be positive or negative.")
	embed.add_field(name = ".db", value = "`.db`\n`.db [filename]`\n\nWrite the contents of the entire database. If no arguments are provided, print the db in the python console. Otherwise, create/overwrite the file specified by the first argument.")
	embed.add_field(name = ".destroy_the_database_yes_i_know_what_this_means", value = "`.destroy_the_database_yes_i_know_what_this_means`\n\nDon't do this unless you have a backup.")

	await ctx.channel.send(embed = embed)






# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++




client.run(token)