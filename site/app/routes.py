from app import app, db, mqtt, photos
from flask import render_template, redirect, url_for, flash, request
from app.forms import RegisterRunnerForm, AddCheckpointForm, LoginForm, RegisterRaceForm, EditRaceForm, EditCheckpointForm
from app.models import User, Event, Race, Runner, Checkpoint
from flask_login import current_user, login_user, logout_user
from bson.objectid import ObjectId

events_col = db.events
races_col = db.races
runners_col = db.runners
checkpoints_col = db.checkpoints

@app.route('/')
def index():
	return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
	if (current_user.is_authenticated):
		return redirect(url_for('index'))
	form = LoginForm()
	if form.validate_on_submit():
		if form.username.data == 'admin' and form.password.data == 'admin':
			user = User()
			user.username = 'admin'
			user.password = 'admin'
			user.role = 'admin'
			user.id = 1
			login_user(user)
			flash('{}  authorized! Welcome!'.format(user.username))
			return redirect(url_for('index'))
		elif form.username.data == 'organizer' and form.password.data == 'organizer':
			user = User()
			user.username = 'organizer'
			user.password = 'organizer'
			user.role = 'organizer'
			user.id = 2
			login_user(user)
			flash('{} authorized! Welcome!'.format(user.username))
			return redirect(url_for('index'))
		else:
			flash('Invalid username or password')
			return redirect(url_for('login'))
	return render_template('login.html', form=form)


@mqtt.on_connect()
def handle_connect(client, userdata, flags, rc):
	mqtt.subscribe('myTopic')


@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
	payload=message.payload.decode().split(' ')
	payload[0]=payload[0].strip()
	payload[2]+=(' ' + payload[3])
	payload.pop()
	print(payload)
	event = Event(payload[0], payload[1], payload[2])
	events_col.insert_one({"checkpoint_id":event.checkpoint_id, "tag":event.tag, "time":event.time})


@app.route("/clear")
def clear():
	events_col.remove()
	return redirect(url_for('table'))

@app.route("/clear/<race_id>")
def clear_checkpoints(race_id):
	race = races_col.find({"_id":ObjectId(race_id)})[0]
	for checkpoint in race['checkpoints']:
		checkpoints_col.delete_one({"_id":checkpoint})
	races_col.update_one({"_id":ObjectId(race_id)}, {"$set":{"checkpoints":[]}})
	return redirect(url_for('race_checkpoints', race_id=race_id))

@app.route("/results")
def table():
	list = []
	for events in events_col.find() :
	   list.append(events)
	list.reverse()
	return render_template("table.html", events=list)


@app.route('/register_runner', methods=['GET', 'POST'])
def register_runner():
	if (current_user.is_anonymous):
		return redirect(url_for('index'))
	form = RegisterRunnerForm()
	if form.validate_on_submit():
		flash('Runner {} {} is successfully registered.'.format(form.first_name.data, form.last_name.data))
		runner = Runner(form.first_name.data, form.last_name.data, form.id.data)
		runners_col.insert_one({"first_name":runner.first_name, "last_name":runner.last_name, "id":runner.id})
		return redirect(url_for('runners_table'))
	return render_template('register_runner.html', form=form)

@app.route('/runners')
def runners_table():
	list = []
	for runners in runners_col.find():
		list.append(runners)
	return render_template('runners_table.html', runners=list)

@app.route('/register_race', methods=['GET', 'POST'])
def register_race():
	if (current_user.is_anonymous):
		return redirect(url_for('index'))
	form = RegisterRaceForm()
	form.laps_number.choices = [(i, i) for i in range(1,11)]
	if form.validate_on_submit():
		filename = photos.save(form.logo.data)
		url = photos.url(filename)
		race = Race(form.name.data, url, form.admin.data, form.laps_number.data, form.distance.data, form.date_and_time_of_race.data, form.description.data)
		races_col.insert_one({"name":race.name, "logo":race.logo, "admin":race.admin, "laps_number":race.laps_number,
			"distance":race.distance, "date_and_time_of_race":race.date_and_time_of_race, "description":race.description, "checkpoints":[]})
		flash('Race {} is successfully registered.'.format(form.name.data))
		return redirect(url_for('races'))
	return render_template('register_race.html', form=form)

@app.route("/races")
def races():
	list = []
	for race in races_col.find():
	   list.append(race)
	return render_template("races.html", races=list)

@app.route("/race/<race_id>")
def race(race_id):
	race = races_col.find({"_id":ObjectId(race_id)})[0]
	return render_template("race.html", race=race)

@app.route("/race/<race_id>/delete")
def delete_race(race_id):
	race = races_col.find({"_id":ObjectId(race_id)})[0]
	races_col.delete_one(race)
	return redirect(url_for('races'))

@app.route("/race/<race_id>/edit", methods=['GET', 'POST'])
def edit_race(race_id):
	race = races_col.find({"_id":ObjectId(race_id)})[0]
	checkpoints = race['checkpoints']
	form = EditRaceForm()
	form.laps_number.choices = [(i, i) for i in range(1,11)]
	if form.validate_on_submit():
		if form.logo.data == None:
			url = race['logo']
		else:
			filename = photos.save(form.logo.data)
			url = photos.url(filename)
		race = Race(form.name.data, url, form.admin.data, form.laps_number.data, form.distance.data, form.date_and_time_of_race.data, form.description.data)
		races_col.replace_one({"_id":ObjectId(race_id)}, {"name":race.name, "logo":race.logo, "admin":race.admin, "laps_number":race.laps_number,
			"distance":race.distance, "date_and_time_of_race":race.date_and_time_of_race, "description":race.description, "checkpoints":checkpoints})
		flash('Race {} is successfully edited.'.format(form.name.data))
		return redirect(url_for('race', race_id=race_id))
	elif request.method == 'GET':
		form.add_data(race)

	return render_template('race.html', form=form, race_name=race['name'], race_id=race_id)

@app.route("/race/<race_id>/checkpoints")
def race_checkpoints(race_id):
	race = races_col.find({"_id":ObjectId(race_id)})[0]
	list = []
	for checkpoint in race['checkpoints']:
	   list.append(checkpoints_col.find({"_id":checkpoint})[0])
	return render_template('race_checkpoints.html', race_name=race['name'], checkpoints=list, race_id=race_id)

@app.route('/race/<race_id>/add_checkpoint', methods=['GET', 'POST'])
def register_checkpoint(race_id):
	if (current_user.is_anonymous):
		return redirect(url_for('index'))
	form = AddCheckpointForm()
	form.id.data = ObjectId(race_id)
	if form.validate_on_submit():
		checkpoint = Checkpoint(form.name.data, form.operator.data, ObjectId(race_id))
		checkpoints_col.insert_one({"name":checkpoint.name, "operator":checkpoint.operator, "race":checkpoint.race})
		checkpoint_in_db = checkpoints_col.find({"name":checkpoint.name, "operator":checkpoint.operator, "race":checkpoint.race})[0]
		races_col.update_one({"_id":ObjectId(race_id)}, {"$addToSet":{"checkpoints":checkpoint_in_db['_id']}})
		flash('Checkpoint {} is successfully registered.'.format(form.name.data))
		return redirect(url_for('race_checkpoints', race_id=race_id))
	return render_template('register_checkpoint.html', form=form)

@app.route("/race/<race_id>/checkpoint/<checkpoint_id>/edit", methods=['GET', 'POST'])
def edit_checkpoint(race_id, checkpoint_id):
	checkpoint = checkpoints_col.find({"_id":ObjectId(checkpoint_id)})[0]
	form = EditCheckpointForm()
	if form.validate_on_submit():
		checkpoint = Checkpoint(form.name.data, form.operator.data, ObjectId(race_id))
		checkpoints_col.replace_one({"_id":ObjectId(checkpoint_id)}, {"name":checkpoint.name, "operator":checkpoint.operator, "race":checkpoint.race})
		flash('Checkpoint {} is successfully edited.'.format(form.name.data))
		return redirect(url_for('race_checkpoints', race_id=race_id))
	elif request.method == 'GET':
		form.add_data(checkpoint)

	return render_template('edit_checkpoint.html', form=form, checkpoint_name=checkpoint['name'], race_id=race_id, checkpoint_id=checkpoint_id)

@app.route("/race/<race_id>/checkpoint/<checkpoint_id>/delete")
def delete_checkpoint(race_id, checkpoint_id):
	checkpoint = checkpoints_col.find({"_id":ObjectId(checkpoint_id)})[0]
	races_col.update_one({"_id":ObjectId(race_id)}, {"$pullAll":{"checkpoints":[ObjectId(checkpoint_id)]}})
	checkpoints_col.delete_one(checkpoint)
	return redirect(url_for('race_checkpoints', race_id=race_id))


@app.route('/logout')
def logout():
	logout_user()
	return redirect(url_for('index'))
