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


import discord, sqlite3
from discord.ext import commands
f = open("token.txt", "r")
token = f.read()
client = commands.Bot(command_prefix = '.')
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
	 													score INTEGER
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

	if member.bot:
		return
	cursor.execute("INSERT INTO users (user_id, user_name, upvotes_earned, downvotes_earned, score) VALUES (?, ?, 0, 0, 0)", (member.id, member.name))
	print("joined: %s %s" % (member.name, member.id))
	db.commit()


	



def get_result_string(info):

	""" 
		Return a string that represents a table row, prettified.
		Takes tuple
		Returns string
	"""

	s = ""
	s += "============ " + str(info[1]) + " ============ \n"
	s += "Total: " + str(info[4]) + '\n'
	s += "Upvotes: " + str(info[2]) + '\n'
	s += "Downvotes: " + str(info[3]) + '\n'
	return s






def log(info):

	""" 
		Log an error that occurred while the bot ran.
	"""

	f = open('error.log', 'a')
	f.write(info + '\n')
	f.close()



#--------------------------------------------------------------------------------------------------------














# =========================================== EVENTS ========================================



@client.event

async def on_ready():

	await init_db()
	members = client.get_all_members()
	db, cursor = get_db_and_cursor()
	print("Updating DB on startup...")

	for member in members:
		try:
			await add_user(db, cursor, member)
		except sqlite3.IntegrityError:
			cursor.execute("UPDATE users SET user_name = ? WHERE user_id = ?", (member.name, member.id))
			print("%s's name was updated. (id = %d)" % (member.name, member.id))
			pass

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
	print("\n%s has left and was removed from the db.\n" % (member.name))






@client.event

async def on_user_update(before, after):

	if before.bot:
		return

	db, cursor = get_db_and_cursor()
	cursor.execute("UPDATE users SET user_name = ? WHERE user_id = ?", (after.name, before.id,))






@client.event

async def on_raw_reaction_add(payload):

	member = payload.member

	if not member.bot:

		db, cursor = get_db_and_cursor()

		channel = await client.fetch_channel(payload.channel_id)
		message = await channel.fetch_message(payload.message_id)
		author = message.author

		if author.id == member.id:
			await message.remove_reaction(payload.emoji, member)
			return

		if author.bot or len(message.attachments) == 0:
			return


		if payload.emoji.name == '1Upvote':

			cursor.execute("UPDATE users SET upvotes_earned = upvotes_earned + 1 WHERE user_id = ?", (author.id,))
			cursor.execute("UPDATE users SET score = score + 1 WHERE user_id = ?", (author.id,))
			result = cursor.execute("SELECT * FROM users WHERE user_id = ? LIMIT 1", (author.id,))
			info = result.fetchone()
			
			if info == None:
				print("No results were found for the given author (%s). Consider updating the database." % (author.name))
			else:
				db.commit()

		elif payload.emoji.name == '1Downvote':
			
			cursor.execute("UPDATE users SET downvotes_earned = downvotes_earned + 1 WHERE user_id = ?", (author.id,))
			cursor.execute("UPDATE users SET score = score - 1 WHERE user_id = ?", (author.id,))
			result = cursor.execute("SELECT * FROM users WHERE user_id = ? LIMIT 1", (author.id,))
			info = result.fetchone()

			if info == None:
				print("No results were found for the given author (%s). Consider updating the database." % (author.name))
			else:
				db.commit()






@client.event

async def on_raw_reaction_remove(payload):

	db, cursor = get_db_and_cursor()

	channel = await client.fetch_channel(payload.channel_id)
	message = await channel.fetch_message(payload.message_id)
	author = message.author

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






@client.event

async def on_command_error(ctx, exc):  

	log("\'%s\' by %s : %s" % (ctx.message.content, ctx.message.author, type(exc)))
	if type(exc) == discord.ext.commands.errors.MissingRequiredArgument:
		await ctx.channel.send("`Please provide the proper format for this command. Check .help for formatting.`")
	elif type(exc) == discord.ext.commands.errors.CommandNotFound:
		await ctx.channel.send("`No such command exists.`")
	elif type(exc) == discord.ext.commands.errors.MissingPermissions:
		await ctx.channel.send("`You do not have sufficient permissions to run that command.`")
	elif type(exc) == discord.ext.commands.errors.CommandInvokeError: #todo what is happening here???
		print(exc)




# ==================================================================================================









# ////////////////////////////////////// USER COMMANDS \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\




@client.command(aliases = ['score', 'show', 'votes'])

async def stats(ctx, arg):

	"""
		Display the upvotes, downvotes, and stats of an individual.
		Usage: .stats [user id] | .stats me
	"""

	db, cursor = get_db_and_cursor()
	if arg == "me":
		arg = ctx.message.author.id

	cursor.execute("SELECT * FROM users WHERE user_id = ? LIMIT 1", (arg,))
	result = cursor.fetchone()

	if result == None:
		s = "No such user found."
	else:	
		s = ""
		s += "============ " + str(result[1]) + " ============ \n"
		s += "Total: " + str(result[4]) + '\n'
		s += "Upvotes: " + str(result[2]) + '\n'
		s += "Downvotes: " + str(result[3]) + '\n'



	await ctx.channel.send('```' + s + '```')






@client.command(pass_context = True, aliases = ['sort'])

async def top(ctx, *args):

	"""
		Display the upvotes, downvotes, and stats of an individual.
		Usage: .top [places](1-20) [criteria](up/down/ratio/score)
	"""

	if len(args) == 0 or len(args) > 2:
		await ctx.channel.send("`Please use the approriate amount of arguments for this command. .help for more info.`")
		return 		

	try:
		num = int(args[0])
	except ValueError:
		await ctx.channel.send("`Enter an integer as the first argument for this command.`")
		return 

	if num < 1 or num > 20:
		await ctx.channel.send("`Enter a number 1-20 as the argument.`")
		return


	k = "score"

	if len(args) == 2:
		if args[1] == '' or args[1] == 'score':
			pass
		elif args[1] == 'up':
			k = "upvotes_earned"
		elif args[1] == 'down':	
			k = "downvotes_earned"
		else:
			await ctx.channel.send("`The second argument was not one of ['', 'score', 'up', 'down']. Try again.`")
			return

	q = "SELECT * FROM users ORDER BY %s DESC LIMIT ?" % k

	db, cursor = get_db_and_cursor()


	cursor.execute(q, (num,))
	s = "{:^58}\n".format("top %s curator%s ordered by %s" % ('' if (num == 1) else num, 's' if (num > 1) else '', k))
	s += ' ' + '_' * 56 + ' \n'
	s +=  "|{:^32}|{:^5}|{:^5}|{:^5}|{:^5}|\n".format("Name", "Score", "Up", "Down", "Ratio")
	s += '·' + '-' * 32 + '+' + '-' * 5 + '+' + '-' * 5 + '+' + '-' * 5 + '+' + '-' * 5 + '·\n'

	for row in cursor.fetchall():
		if (row[3] != 0 or row[4] != 0): 
			s += "|{:<32}|{:<5}|{:<5}|{:<5}|{:<5.3f}|\n".format(row[1], row[4], row[2], row[3], 
				(row[2] / (row[2] + row[3])))
			s += '·' + '-' * 32 + '+' + '-' * 5 + '+' + '-' * 5 + '+' + '-' * 5 + '+' + '-' * 5 + '·\n'

	await ctx.channel.send('```' + s + '```')





@client.command(pass_context = True, aliases = ['helpme'])

async def help(ctx):

	""" 
		List the available commands to general users. 
	"""

	embed = discord.Embed(
		colour = discord.Colour.blue()
	)

	embed.set_author(name = "Museum Help Service", icon_url = "https://cdn.discordapp.com/attachments/732933150828658689/736083821144965180/imageedit_153_3067097904.png") 				# top left small circle
	#embed.set_image(url = "https://cdn.discordapp.com/attachments/735961470398890084/736071911561363507/yande.re_621327_sample_ikomochi_megane_seifuku_shirt_lift_skirt_lift.jpg") 	# bottom large rect
	#embed.set_thumbnail(url = "https://cdn.discordapp.com/attachments/722537044353482862/722698539771363328/original_drawn_by_laru__sample-4bbee8bbb28f24ea258c2a257efc3f9e.jpg")		# top right small rect

	embed.add_field(name = ".score\nalias: [.show, .votes]", value = "`.score [user id]`\n`.score me`\n\nShow the score, upvotes, and downvotes for the given user.")
	embed.add_field(name = ".top\nalias: [.sort]\n", value = "`.top (1-20) (score/up/down)`\n`.top (1-20)` \n\nShow the stats, in order, of the top X users. Is ordered by a criteria, which may be specified as 'score', 'up, or 'down'. Takes on 'score' by default, if left empty.")
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






@client.command(aliases = ['sync'])
@commands.has_permissions(administrator = True)

async def update(ctx):

	""" 
		Update the database on call. 
	"""

	members = ctx.guild.members
	db, cursor = get_db_and_cursor()
	for member in members:
		try:
			await add_user(db, cursor, member)
		except sqlite3.IntegrityError:
			cursor.execute("UPDATE users SET user_name = ? WHERE user_id = ?", (member.name, member.id))
			print("%s's name was updated. (id = %d)" % (member.name, member.id))
			pass

	db.commit()






@client.command(aliases = ['db'])
@commands.has_permissions(administrator = True)

async def show_db(ctx, *args):

	"""
		Show the contents of the entire database.
		If no arguments are provided, print the db in the python console.
		Otherwise, create/overwrite the file specified by the first argument.
	"""

	if len(args) > 0:
		f = open(args[0], "w")

	connection, cursor = get_db_and_cursor()

	cursor.execute("SELECT * FROM users")

	if len(args) == 0:
		print('\n' + '-' * 32 + '\n')
		for t in cursor.fetchall():
			print(get_result_string(t))
		print('-' * 32 + '\n')
	else:
		f.write('\n' + '-' * 32 + '\n')
		for t in cursor.fetchall():
			f.write(get_result_string(t))
		f.write('-' * 32 + '\n')
		f.close()






@client.command(aliases = ['lim'])
@commands.has_permissions(administrator = True)

async def limit(ctx, arg):

	"""
		Show the contents of the entire database.
	"""

	try:
		limit = float(arg)
	except ValueError:
		await ctx.channel.send("`Enter a decimal between as the argument for this command.`")
		return 

	if limit <= 0.0 and limit >= 1.0:
		await ctx.channel.send("`Enter a decimal between as the argument for this command.`")
		return 	

	connection, cursor = get_db_and_cursor()
	cursor.execute("SELECT * FROM users")

	s = "```The following users have below a %s like ratio:\n" % (limit)
	s += '=' * 59 + '\n'
	flag = False

	for row in cursor.fetchall():
		if row[3] != 0 or row[4] != 0:
			ratio = (row[2] / (row[2] + row[3]))
			#print("ratio: %s\nlimit: %s\n" % (ratio, limit))
			if ratio <= limit:
				flag = True
				s += "{:<32} | {:>3}% upvoted, {:>4} posted\n".format(row[1], int(round(ratio * 100)), row[2] + row[3])

	if not flag:
		s += "There were no users with ratios found below this threshold.\n"

	s += '=' * 59 + "```"

	await ctx.channel.send(s)







@client.command()
@commands.has_permissions(administrator = True)

async def destroy_the_database_yes_i_know_what_this_meansdestroy_the_database_yes_i_know_what_this_means(ctx, arg):

	"""
		If you have any data, PLEASE BACK IT UP!!!!
	"""

	connection, cursor = get_db_and_cursor()
	cursor.execute("DELETE FROM users")
	cursor.execute("SELECT * FROM users")







@client.command(aliases = ['admin'], pass_context = True)
@commands.has_permissions(administrator = True)

async def adminhelp(ctx):

	""" 
		List the commands available to admins. 
	"""

	embed = discord.Embed(
		colour = discord.Colour.blue()
	)

	embed.set_author(name = "Museum Help Service [Admin]", icon_url = "https://cdn.discordapp.com/attachments/732933150828658689/736083821144965180/imageedit_153_3067097904.png") 

	embed.add_field(name = ".kill\nalias: [.end, .terminate]\n\n", value = "`.kill`\n\nKill all instances of the bot currently running. Use this before restarting, or if you get multiple bot messages per command.")
	embed.add_field(name = ".limit\nalias: [.lim]", value = "`.limit (0.0 - 1.0)`\n\nDisplay all users with an upvote ratio (up / [up + down]) lower than the one specified.")
	embed.add_field(name = ".update\nalias: [.sync]", value = "`.update`\n\nUpdate the database to have all currently visible users and their usernames.")
	embed.add_field(name = ".db", value = "`.db`\n`.db [filename]`\n\nWrite the contents of the entire database. If no arguments are provided, print the db in the python console. Otherwise, create/overwrite the file specified by the first argument.")
	embed.add_field(name = ".destroy_the_database_yes_i_know_what_this_means", value = "`.destroy_the_database_yes_i_know_what_this_means`\n\nDon't do this unless you have a backup.")

	await ctx.channel.send(embed = embed)






# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++




client.run(token)