extends SceneTree
const State=preload('res://src/animation_state.gd')
var failures=0
var checks=0
func check(value: bool,message: String):
	checks+=1
	if not value: failures+=1;printerr('FAIL ',message)
func fresh():return State.new(JSON.parse_string(FileAccess.get_file_as_string('res://assets/clips.json')))
func reach(s,phase: String,seconds: float=15.0):
	for i in range(int(seconds*24)):
		if s.phase==phase:return true
		s.advance(1.0/24)
	return s.phase==phase
func _initialize():
	for name in ['sleep']:
		var s=fresh();s.preview(name)
		check(reach(s,name+'_loop'),'enter '+name)
		s.advance(120);check(s.phase==name+'_loop','held '+name)
		var frame=s.frame;s.interact();check(s.frame==frame,'no jump on click '+name)
		check(reach(s,name+'_exit'),'exit '+name)
		frame=s.frame;s.interact();check(s.frame==frame,'no rewind '+name)
		check(reach(s,'idle'),'idle after '+name)
		for target in ['task','read','ack','quit']:
			s=fresh();s.preview(name);reach(s,name+'_loop')
			match target:
				'task':s.set_busy(true)
				'read':s.set_reading(true)
				'ack':s.acknowledge()
				'quit':s.request_quit()
			check(reach(s,name+'_exit'),'cleanup before '+target)
			check(reach(s,{'task':'work','read':'read_loop','ack':'ok','quit':'goodbye'}[target]),'route '+target)
	for name in ['sunny','rainy','cloudy']:
		var weather_state=fresh();weather_state.preview(name)
		check(weather_state.phase==name,'one click starts complete weather '+name)
		var first=weather_state.frame;var last=int(weather_state.clips[name][1])
		for expected in range(first,last+1):
			check(weather_state.phase==name and weather_state.frame==expected,'weather frame order '+name)
			weather_state.advance(1.0/24)
		check(weather_state.phase=='idle','weather completes without second click '+name)
	var s=fresh();s.set_reading(true);check(reach(s,'read_loop'),'reading enter')
	s.advance(3600);s.interact();s.advance(5);check(s.phase=='read_loop','reading unaffected by idle clock and click')
	s.set_reading(false);check(reach(s,'read_exit'),'reading exits');check(reach(s,'idle'),'reading returns idle')
	s=fresh();s.set_reading(true);reach(s,'read_loop');s.set_busy(true);check(reach(s,'work'),'task interrupts via read exit')
	s.set_busy(false);check(reach(s,'read_loop'),'reading resumes after task')
	s=fresh();s._switch('sulk_enter');reach(s,'sulk_hold');s.advance(100)
	check(s.phase=='sulk_hold','sulk holds until interaction');s.interact();check(reach(s,'sulk_exit'),'sulk recovery');check(reach(s,'idle'),'sulk idle')
	s.advance(5);check(s.phase in ['idle','blink'] and not s.history.any(func(h):return h.phase=='sleep_enter'),'a coaxed sulk does not nap')
	# two idle minutes → nap, even when the pet is sulking at that moment; the sulk finishes first
	s=fresh();s.advance(119);check(s.phase=='sulk_hold','wave then sulk fill the first two idle minutes')
	check(reach(s,'sulk_exit',10),'nap clock ends the sulk (blinks do not count as idle)');check(reach(s,'sleep_enter',3),'nap follows the sulk');check(reach(s,'sleep_loop'),'nap loop')
	check(not s.history.any(func(h):return h.phase in ['sunny','rainy','cloudy']),'idle never shows weather')
	s.advance(1799-s.nap_elapsed);check(s.phase=='sleep_loop','still asleep just under thirty minutes')
	check(reach(s,'sleep_exit',10),'wakes by itself after thirty minutes');check(reach(s,'idle',10),'awake and idle after the nap')
	check(reach(s,'sleep_loop',140),'the next two idle minutes bring the next nap')
	s=fresh();s.weather='sunny';s.play_weather_opening();check(s.phase=='sunny','weather opens the day once')
	check(reach(s,'idle',10),'opening finishes');s.play_weather_opening();check(s.phase=='idle','opening never repeats')
	check(reach(s,'sleep_loop',140),'idle rest is sleep even when the weather is known')
	check(not s.history.filter(func(h):return h.phase=='sunny').size()>1,'weather scene only at the start')
	# a click or drag during the nap still wakes early
	s=fresh();s.advance(130);reach(s,'sleep_loop');s.interact();check(reach(s,'sleep_exit'),'early wake');check(reach(s,'idle'),'early wake idle')
	# reading alternates between the main take and 看书备选, one take per reading session
	s=fresh();s.set_reading(true);check(reach(s,'read_loop'),'first reading uses the main take')
	s.set_busy(true);check(reach(s,'work'),'task during reading');s.set_busy(false);check(reach(s,'read_loop'),'resume keeps the same take')
	s.set_reading(false);check(reach(s,'idle'),'main take exits')
	s.set_reading(true);check(reach(s,'read_alt_loop'),'second reading uses the alternate take')
	s.advance(30);s.interact();check(s.phase=='read_alt_loop','alternate take holds like the main one')
	s.set_reading(false);check(reach(s,'read_alt_exit'),'alternate take exits');check(reach(s,'idle'),'alternate take returns idle')
	s.set_reading(true);check(reach(s,'read_loop'),'third reading is the main take again')
	# candy alternates between the main take and the close-up
	s=fresh();s.feedback('candy');check(reach(s,'candy_hold'),'first candy is the main take');s.interact();check(reach(s,'idle'),'candy done')
	s.feedback('candy');check(reach(s,'candy_close_hold'),'second candy is the close-up');s.interact();check(reach(s,'idle'),'close-up done')
	s.feedback('candy');check(reach(s,'candy_hold'),'third candy is the main take again');s.interact();reach(s,'idle')
	check(reach(s,'idle'),'candy alternation settles')
	s=fresh();s.set_busy(true);s.advance(.1);s.set_busy(false);check(reach(s,'idle'),'short task exits')
	s=fresh();s.set_busy(true);reach(s,'work');s.advance(30);check(s.phase=='work' and s.loops>5,'long task loops')
	s.request_quit();check(reach(s,'goodbye'),'quit after work exit');s.advance(4);check(s.finished,'quit after full wave')
	s=fresh();s.variant=1;s.advance(60.01);check(reach(s,'wave'),'awake wave after idle budget');reach(s,'idle');s.advance(9);check(s.phase in ['idle','blink'],'wait ten idle seconds');check(reach(s,'sulk_enter'),'then sulk')
	print('COMPANION_STATE ',checks,' checks, ',failures,' failures');quit(1 if failures else 0)
