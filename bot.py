"""
This is a bot meant to serve as a vote accumulator. Votes are defined as reactions.

Features:
	- track the upvotes, downvotes, and cumulative score performed while the bot is up with an sqlite db
	- show your score and ratio
	- TODO display the top x scores 

Considerations:
	- bot votes are not counted
	- votes of users on their own posts are not counted
	- downvotes cannot go below zero

Operation notes:
	- terminate (.kill) and restart the bot if you are seeing multiple messages per command
	- .help for help
	- some commands look for administrator privileges, make sure you have them

"""


import discord, sqlite3
from discord.ext import commands
f = open("token.txt", "r")
token = f.read()
client = commands.Bot(command_prefix = '.')
client.remove_command('help')



#--------------------------------------- UTILITY FUNCTIONS ---------------------------------------------



async def add_user(db, cursor, member):
	""" Add a user to the database. """
	if member.bot:
		return
	cursor.execute("INSERT INTO users (user_id, user_name, upvotes_earned, downvotes_earned, score) VALUES (?, ?, 0, 0, 0)", (member.id, member.name))
	print("joined: %s %s" % (member.name, member.id))
	db.commit()
	#db.close()


	


def get_db_and_cursor():
	""" Create and return a database connection to votes.db """
	connection = sqlite3.connect('votes.db')
	cursor = connection.cursor()
	return [connection, cursor]





def init_db():
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
	 													pvotes_earned INTEGER, 
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




#--------------------------------------------------------------------------------------------------------







init_db()






# =========================================== EVENTS ========================================



@client.event

async def on_ready():

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
			#
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
	#print("Username change detected: %s -> %s" % (before.name, after.name))





@client.event

async def on_raw_reaction_add(payload):

	member = payload.member

	if not member.bot:

		db, cursor = get_db_and_cursor()

		channel = await client.fetch_channel(payload.channel_id)
		message = await channel.fetch_message(payload.message_id)
		author = message.author

		if author.bot or author.id == member.id or len(message.attachments) == 0:
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
			#print("Score decreased (up removed)")
			if info == None:
				print("No results were found for the given author (%s). Consider updating the database." % (author.name))
			else:
				db.commit()
				#print(get_result_string(info))

	elif payload.emoji.name == '1Downvote':

		cursor.execute("SELECT downvotes_earned FROM users WHERE user_id = ? LIMIT 1", (author.id,))

		if cursor.fetchone()[0] > 0: # don't allow negative downvotes -- score doesn't increase although -downvote
			cursor.execute("UPDATE users SET downvotes_earned = downvotes_earned - 1 WHERE user_id = ?", (author.id,))
			cursor.execute("UPDATE users SET score = score + 1 WHERE user_id = ?", (author.id,))
			result = cursor.execute("SELECT * FROM users WHERE user_id = ? LIMIT 1", (author.id,))
			info = result.fetchone()
			#print("Score increased (down removed)")
			if info == None:
				print("No results were found for the given author (%s). Consider updating the database." % (author.name))
			else:
				db.commit()
				#print(get_result_string(info))





@client.event

async def on_command_error(ctx, exc):  

	print("\'%s\' by %s : %s" % (ctx.message.content, ctx.message.author, type(exc)))
	if type(exc) == discord.ext.commands.errors.MissingRequiredArgument:
		await ctx.channel.send("`Please provide the proper format for this command. Check .helpme for formatting.`")
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
	#print(result)

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
			k = "score"
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
	#s += '_' * 64 + '\n'
	s += ' ' + '_' * 56 + ' \n'
	s +=  "|{:^32}|{:^5}|{:^5}|{:^5}|{:^5}|\n".format("Name", "Score", "Up", "Down", "Ratio")
	s += '·' + '-' * 32 + '+' + '-' * 5 + '+' + '-' * 5 + '+' + '-' * 5 + '+' + '-' * 5 + '·\n'

	# {:<8}
	for row in cursor.fetchall():
		if (row[3] != 0 or row[4] != 0): 
			s += "|{:<32}|{:<5}|{:<5}|{:<5}|{:<5}|\n".format(row[1], row[4], row[2], row[3], 
				(row[3] / (row[3] + row[4])))
			s += '·' + '-' * 32 + '+' + '-' * 5 + '+' + '-' * 5 + '+' + '-' * 5 + '+' + '-' * 5 + '·\n'

	await ctx.channel.send('```' + s + '```')





@client.command(pass_context = True)

async def help(ctx):
	""" List the available commands to general users. """
	embed = discord.Embed(
		colour = discord.Colour.blue()
	)

	embed.set_author(name = "Museum Help Service", icon_url = "https://cdn.discordapp.com/attachments/732933150828658689/736083821144965180/imageedit_153_3067097904.png") 						# top left small circle
	#embed.set_image(url = "https://cdn.discordapp.com/attachments/735961470398890084/736071911561363507/yande.re_621327_sample_ikomochi_megane_seifuku_shirt_lift_skirt_lift.jpg") 	# bottom large rect
	#embed.set_thumbnail(url = "https://cdn.discordapp.com/attachments/722537044353482862/722698539771363328/original_drawn_by_laru__sample-4bbee8bbb28f24ea258c2a257efc3f9e.jpg")		# top right small rect

	embed.add_field(name = ".score\nalias: [.show, .votes]", value = "*.score me* \n*.score [user id]* \n\nShow the stats for the mentioned user.\nEx: `.score 736025037462831256`")
	embed.add_field(name = ".top", value = "\nalias: [.sort]\n*.top [places]\(1-20)\n[criteria]\(up/down/ratio/score)* \n\nShow the stats, in order, of the top X users. Is ordered by a criteria, which may be specified as 'score', 'up, 'down'. Takes on 'score' by default, if left empty.\nEx: `.top 10`\n`.top 5 down`")

	await ctx.channel.send(embed = embed)





# ///////////////////////////////////////////////\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\





# +++++++++++++++++++++++++++++++++++++ ADMIN COMMANDS +++++++++++++++++++++++++++++++++++++++++++++++



@client.command(pass_context = True, aliases = ['end', 'terminate'])
@commands.has_permissions(administrator = True)

async def kill(ctx):
	""" Kill all bot instances. 

		If you are experiencing multiple messages or other hiccups, use this command 
		and then restart the bot. 
	"""
	await ctx.channel.send("`Bot is being terminated...`")
	await client.logout()
	print("Bot was terminated.")





@client.command(aliases = ['sync'])
@commands.has_permissions(administrator = True)

async def update(ctx):

	""" Update the database on call. """
	members = ctx.guild.members
	db, cursor = get_db_and_cursor()
	for member in members:
		try:
			await add_user(db, cursor, member)
		except sqlite3.IntegrityError:
			cursor.execute("UPDATE users SET user_name = ? WHERE user_id = ? LIMIT 1", (member.name, member.id))
			print("%'s name was updated. (id = %d)" % (member.name, member.id))
			pass

	db.commit()







@client.command(aliases = ['db'])
@commands.has_permissions(administrator = True)

async def show_db(ctx):
	"""
		Show the contents of the entire database.

	"""
	connection, cursor = get_db_and_cursor()

	cursor.execute("SELECT * FROM users")

	print('-' * 32)
	for t in cursor.fetchall():
		print(get_result_string(t))
	print('-' * 32)






@client.command(aliases = ['admin'], pass_context = True)
@commands.has_permissions(administrator = True)

async def adminhelp(ctx):
	""" List the available commands to admins. """
	embed = discord.Embed(
		colour = discord.Colour.blue()
	)

	embed.set_author(name = "Museum Help Service [Admin]", icon_url = "https://cdn.discordapp.com/attachments/732933150828658689/736083821144965180/imageedit_153_3067097904.png") 

	embed.add_field(name = ".kill\nalias: [.end, .terminate]", value = "Kill all instances of the bot currently running. Use this before restarting, or if you get multiple bot messages per command.")
	embed.add_field(name = ".update\nalias: [.update, .sync]", value = "Update the database to have all currently visible users and their usernames.")
	embed.add_field(name = ".db", value = "Show the full database in the python console.")

	await ctx.channel.send(embed = embed)



# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++




client.run(token)