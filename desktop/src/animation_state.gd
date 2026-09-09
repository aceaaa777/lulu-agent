extends RefCounted
var clips: Dictionary
var fps := 24.0
var phase := "idle"
var frame := 0
var busy := false
var loops := 0
var elapsed := 0.0
var transition_id := 0
var previous_frame := 0
var history: Array = []
var idle_seconds := 0.0
var next_wave := 60.0
var blink_seconds := 0.0
var sulk_at := -1.0
var weather := "unknown"
var reading := false
var quitting := false
var finished := false
var released := false
var acknowledgement := false
var looked := false
var rested := false
var variant := 0
var rest_prefix := "sleep"
var agent_mode := ''
var pending_feedback := ''
var recovered := false
var completion_sign := false
var pinch_dragging := false
var pinch_seconds := 0.0
var feedback_prefix := ''
var weather_opened := false
var english := false   # the English build holds up the "done" board (complete_alt) instead of the "搞定" one
# Every task plays the same opening on a fixed clock: thinking for idea_at seconds, then the idea flash once.
# When the idea ends, a task that is already finished goes straight to the sign; one still running gets the keyboard
# until it finishes, then the sign. The backend's thinking/working distinction no longer drives the pet; only
# blocked (waiting for the user) interrupts the clock.
var idea_at := 10.0
var agent_seconds := 0.0
var idea_shown := false
var done_pending := false   # the task finished before the idea played; hold the sign until after it
func play_weather_opening():
	# First time the day's weather is known: open with that scene instead of waiting for an idle rest.
	if weather_opened or quitting or busy or reading or agent_mode!='' or not weather in ['sunny','rainy','cloudy'] or not clips.has(weather):return
	if phase!='idle':return
	weather_opened=true;rested=true;rest_prefix=weather;_switch(weather)
const FEEDBACK = ['pinch','candy','candy_close','night','thinking','thinking_done','blocked','resolved','complete','complete_alt']
func feedback(name: String):
	if quitting or not name in FEEDBACK:return
	pending_feedback=name;released=true
	if phase=='idle':_route()
func sign_clip() -> String:
	return 'complete_alt' if english else 'complete'
func set_agent_status(value: String):
	if quitting:return
	if value in ['thinking','blocked','working']:
		if agent_mode=='':agent_seconds=0.0;idea_shown=false;done_pending=false
		# before the idea the pet always thinks; after it, it always types — the server's word is not what decides
		if value!='blocked':value='working' if idea_shown else 'thinking'
		if agent_mode==value:return
		if value=='thinking' and agent_mode=='blocked':recovered=true
		agent_mode=value;busy=false;released=true
		if phase=='idle':_route()
	elif value=='completed':
		if not idea_shown:
			done_pending=true;return   # keep thinking until the clock says idea; the sign follows the idea
		completion_sign=true
		agent_mode='';busy=false
		if phase in ['thinking_done','resolved']:return   # idea is on screen right now; its end shows the sign
		completion_sign=false;feedback(sign_clip())
	elif value=='cancelled':
		completion_sign=false;recovered=false;idea_shown=false;done_pending=false
		agent_mode='';busy=false;pending_feedback='';released=true
func _play_idea():
	# 10 s in: the idea flashes once; afterwards either the sign (task already done) or the keyboard (still running)
	idea_shown=true
	if done_pending:done_pending=false;completion_sign=true;agent_mode=''
	else:agent_mode='working'
	busy=false;feedback('resolved' if recovered else 'thinking_done');recovered=false
func start_drag():
	pinch_dragging=true;pinch_seconds=0
	if phase=='pinch_exit':_switch('pinch_hold')
	elif not phase.begins_with('pinch'):feedback('pinch')
func end_drag():pinch_dragging=false
func _start_feedback(name: String):
	feedback_prefix=name
	match name:
		'pinch','candy','candy_close':_switch(name+'_enter')
		'thinking':agent_mode='thinking';_switch('thinking_enter')
		'blocked':agent_mode='blocked';_switch('blocked_enter')
		_:_switch(name)
func _feedback_end() -> bool:
	if phase in ['thinking_enter','blocked_enter']:
		if quitting or pending_feedback!='' or agent_mode!=phase.trim_suffix('_enter'):_route()
		else:_switch(agent_mode+'_loop')
	elif phase in ['thinking_loop','blocked_loop']:
		if quitting or pending_feedback!='' or agent_mode!=phase.trim_suffix('_loop'):_route()
		else:frame=int(clips[phase][0]);loops+=1
	elif phase in ['candy_enter','candy_close_enter']:
		released=quitting or busy or agent_mode!='';_switch(feedback_prefix+'_hold')
	elif phase in ['candy_hold','candy_close_hold']:
		if released or quitting or pending_feedback!='':_switch(feedback_prefix+'_exit')
		else:frame=int(clips[phase][0])
	elif phase=='pinch_enter':pinch_seconds=0;_switch('pinch_hold')
	elif phase=='pinch_hold':
		pinch_seconds+=1.0/fps
		if quitting or not pinch_dragging:_switch('pinch_exit')
		else:frame=int(clips.pinch_hold[0])
	elif phase in ['thinking_done','resolved']:
		if completion_sign and not quitting:pending_feedback=sign_clip();completion_sign=false
		_route()
	elif phase in ['pinch_exit','candy_exit','candy_close_exit','night','complete','complete_alt']:_route()
	else:return false
	return true
func _init(manifest: Dictionary):
	clips = manifest
	fps = float(clips.fps)
	frame = int(clips.idle[0])
func _switch(next: String):
	previous_frame = frame
	phase = next
	frame = int(clips[phase][0])
	transition_id += 1
	history.append({'phase': phase, 'busy': busy, 'ms': Time.get_ticks_msec()})
	if history.size() > 40: history.pop_front()
func _reset_idle_clock():
	idle_seconds = 0.0
	blink_seconds = 0.0
	next_wave = 60.0
	sulk_at = -1.0
	looked = false
	rested = false
func interact():
	_reset_idle_clock()
	if (not reading or phase in ['candy_hold','candy_close_hold']) and not phase.begins_with('thinking') and not phase.begins_with('blocked'):
		released = true
	# Never rewind an exit or interrupt its remaining frames.
func set_busy(value: bool):
	if busy == value: return
	busy = value
	if busy:
		released = true
		if phase == 'idle': _route()
func set_reading(value: bool):
	if quitting: return
	reading = value
	if phase == 'idle': _route()
	elif not value or not phase.begins_with('read_'): released = true
func acknowledge():
	if quitting: return
	acknowledgement = true
	released = true
	if phase == 'idle': _route()
func request_quit():
	quitting = true
	reading = false
	released = true
	if phase == 'idle': _route()
func preview(name: String):
	if busy or quitting or reading: return
	if phase != 'idle': return
	if name in ['sunny','rainy','cloudy']:
		_switch(name)
	elif name in ['sleep','sleep_alt']:
		rest_prefix = name
		released = false
		_switch(rest_prefix + '_enter')
	elif name in ['look_a','look_b']: _switch(name)
func _route():
	released = false
	if quitting:
		_switch('goodbye')
	elif pending_feedback!='':
		var next=pending_feedback;pending_feedback='';_start_feedback(next)
	elif agent_mode!='':
		if agent_mode=='working':_switch('enter')
		else:_switch(agent_mode+'_enter')
	elif acknowledgement:
		acknowledgement = false
		_switch('ok')
	elif busy:
		_switch('enter')
	elif reading:
		_switch('read_enter')
	else:
		_reset_idle_clock()
		_switch('idle')
func _end_clip():
	if _feedback_end():return
	if phase == 'goodbye':
		finished = true
	elif phase == 'work':
		if (busy or agent_mode=='working') and not quitting and not acknowledgement and pending_feedback=='':
			frame = int(clips.work[0]); loops += 1
		else: _switch('exit')
	elif phase == 'enter':
		_switch('work' if (busy or agent_mode=='working') and not quitting else 'exit')
	elif phase == 'exit' or phase == 'ok': _route()
	elif phase == 'read_enter':
		_switch('read_exit' if released or not reading or busy or quitting else 'read_loop')
	elif phase == 'read_loop':
		if released or not reading or busy or quitting: _switch('read_exit')
		else: frame = int(clips.read_loop[0]); loops += 1
	elif phase == 'read_exit': _route()
	elif phase in ['sleep_enter','sleep_alt_enter','sunny_enter','rainy_enter','cloudy_enter']:
		_switch(rest_prefix + ('_exit' if released else '_loop'))
	elif phase in ['sleep_loop','sleep_alt_loop','sunny_loop','rainy_loop','cloudy_loop']:
		if released: _switch(rest_prefix + '_exit')
		else: frame = int(clips[phase][0]); loops += 1
	elif phase in ['sleep_exit','sleep_alt_exit','sunny_exit','rainy_exit','cloudy_exit']: _route()
	elif phase == 'sulk_enter': _switch('sulk_exit' if released else 'sulk_hold')
	elif phase == 'sulk_hold':
		if released: _switch('sulk_exit')
		else: frame = int(clips.sulk_hold[0])
	elif phase == 'sulk_exit': _route()
	elif phase == 'wave':
		if released or busy or quitting or reading or acknowledgement or pending_feedback!='' or agent_mode!='': _route()
		else:
			sulk_at = idle_seconds + 10.0
			_switch('idle')
	elif phase in ['blink','look_a','look_b','read_alt','sunny','rainy','cloudy']:
		if released or busy or quitting or reading or acknowledgement or pending_feedback!='' or agent_mode!='': _route()
		else: _switch('idle')
	elif phase == 'idle':
		if released or busy or quitting or reading or acknowledgement or pending_feedback!='' or agent_mode!='': _route()
		else: frame = int(clips.idle[0])
func advance(delta: float):
	if finished: return
	elapsed += delta
	while not finished:
		var step=1.0/(fps*(3.0 if phase=='pinch_enter' else 1.0))
		if elapsed+0.000001<step:break
		elapsed -= step
		if agent_mode in ['thinking','working']:
			agent_seconds += 1.0 / fps
			if not idea_shown and agent_seconds>=idea_at:_play_idea()
		if phase in ['idle','look_a','look_b','wave'] and not busy and not reading and not quitting:
			idle_seconds += 1.0 / fps
		if phase in ['idle','blink'] and not busy and not reading and not quitting:
			blink_seconds += 1.0 / fps
		if phase == 'idle' and not released and not busy and not reading and not quitting:
			if clips.has('blink') and blink_seconds + 0.000001 >= float(clips.get('blink_interval_seconds',10)):
				blink_seconds=0.0; _switch('blink'); continue
			if sulk_at >= 0 and idle_seconds + 0.000001 >= sulk_at:
				sulk_at = -1; _switch('sulk_enter'); continue
			if idle_seconds + 0.000001 >= next_wave:
				next_wave += 60; _switch('wave'); continue
			if idle_seconds >= 12 and not looked:
				looked = true; _switch('look_a' if variant % 2 == 0 else 'look_b'); continue
			# Alternate awake wave cycles and sleep cycles; held states require interaction.
			if idle_seconds >= 35 and not rested and variant % 2 == 0 and sulk_at < 0:
				rested = true; variant += 1
				rest_prefix = weather if weather in ['sunny','rainy','cloudy'] else 'sleep'
				_switch('sleep_enter' if rest_prefix=='sleep' else rest_prefix); continue
		if frame < int(clips[phase][1]): frame += 1
		else:
			var was_sulk = phase == 'sulk_exit'
			_end_clip()
			if was_sulk: variant += 1
