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
	s=fresh();s._switch('sulk_enter');reach(s,'sulk_hold');s.advance(180)
	check(s.phase=='sulk_hold','sulk holds until interaction');s.interact();check(reach(s,'sulk_exit'),'sulk recovery');check(reach(s,'idle'),'sulk idle')
	s=fresh();s.set_busy(true);s.advance(.1);s.set_busy(false);check(reach(s,'idle'),'short task exits')
	s=fresh();s.set_busy(true);reach(s,'work');s.advance(30);check(s.phase=='work' and s.loops>5,'long task loops')
	s.request_quit();check(reach(s,'goodbye'),'quit after work exit');s.advance(4);check(s.finished,'quit after full wave')
	s=fresh();s.variant=1;s.advance(60.01);check(reach(s,'wave'),'awake wave after idle budget');reach(s,'idle');s.advance(9);check(s.phase in ['idle','blink'],'wait ten idle seconds');check(reach(s,'sulk_enter'),'then sulk')
	print('COMPANION_STATE ',checks,' checks, ',failures,' failures');quit(1 if failures else 0)
