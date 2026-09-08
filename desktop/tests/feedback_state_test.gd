extends SceneTree
const State=preload('res://src/animation_state.gd')
var failures=0
var checks=0
func check(ok: bool,message: String):
	checks+=1
	if not ok:failures+=1;printerr('FEEDBACK_FAIL ',message)
func tick_to(s,phase: String,limit=20.0):
	for i in range(int(limit*24)):
		if s.phase==phase:return
		s.advance(1.0/24)
func _initialize():
	var m=JSON.parse_string(FileAccess.get_file_as_string('res://assets/clips.json'))
	for name in ['candy','candy_close']:
		var s=State.new(m);s.feedback(name);s.interact();tick_to(s,name+'_hold')
		check(s.phase==name+'_hold','early click does not consume offering '+name)
		var held=s.frame;s.advance(60)
		check(s.phase==name+'_hold' and s.frame==held,'offering freezes until click '+name)
		s.interact();s.advance(1.0/24)
		check(s.phase==name+'_exit' and s.frame==m[name+'_exit'][0],'click starts exact following frame '+name)
		tick_to(s,'idle');check(s.phase=='idle','candy tail completes '+name)
		s=State.new(m);s.set_reading(true);tick_to(s,'read_loop');s.feedback(name);tick_to(s,name+'_hold');s.interact();tick_to(s,'read_loop')
		check(s.phase=='read_loop' and s.reading,'candy click works during deep companionship '+name)
		s=State.new(m);s.feedback(name);tick_to(s,name+'_hold');s.request_quit();tick_to(s,'goodbye');s.advance(3)
		check(s.finished,'quit releases candy '+name)
	var s=State.new(m);s.start_drag();s.advance(15)
	check(s.phase=='pinch_hold' and s.frame==m.pinch_hold[0],'drag freezes while cheek is pinched')
	s.end_drag();tick_to(s,'idle');check(s.phase=='idle','release eventually returns to idle')
	check(m.pinch_hold[0]-m.pinch_enter[0]==70,'hold is last fully pinched frame')
	check(m.pinch_exit[1]-m.pinch_enter[0]==105,'tail stops before ice')
	s=State.new(m);s.start_drag();s.end_drag();tick_to(s,'pinch_hold');check(s.phase=='pinch_hold','short drag still finishes pinch')
	s.advance(1.0/24);check(s.phase=='pinch_exit' and s.frame==m.pinch_exit[0],'release plays exact next frame');tick_to(s,'idle')
	s=State.new(m);s.start_drag();tick_to(s,'pinch_hold');s.end_drag();s.advance(0.2);s.start_drag();s.advance(2)
	check(s.phase=='pinch_hold' and s.frame==m.pinch_hold[0],'regrab during tail holds cheek again');s.end_drag();tick_to(s,'idle')
	for mode in ['thinking','blocked']:
		s=State.new(m);s.set_agent_status(mode);s.advance(30)
		check(s.phase==mode+'_loop','sustained '+mode)
		s.interact();s.advance(5);check(s.phase==mode+'_loop','click cannot fabricate agent resolution '+mode)
		s.set_agent_status('cancelled');tick_to(s,'idle');check(s.phase=='idle','cancel clears '+mode)
		s=State.new(m);s.set_agent_status(mode);tick_to(s,mode+'_loop');s.request_quit();tick_to(s,'goodbye');s.advance(3);check(s.finished,'quit while '+mode)
	s=State.new(m);s.set_agent_status('thinking');tick_to(s,'thinking_loop');s.set_agent_status('completed');tick_to(s,'thinking_done')
	check(s.phase=='thinking_done','completed thought uses first insight slice');tick_to(s,'complete');check(s.phase=='complete','actual completion then shows sign');tick_to(s,'idle')
	s=State.new(m);s.set_agent_status('blocked');tick_to(s,'blocked_loop');s.set_agent_status('thinking');tick_to(s,'thinking_loop')
	check(s.phase=='thinking_loop','supplement resumes thinking, not fake success');s.set_agent_status('completed');tick_to(s,'resolved')
	check(s.phase=='resolved','supplemented success uses second insight slice');tick_to(s,'complete');check(s.phase=='complete','recovered completion sign')
	for name in ['night','thinking_done','resolved','complete','complete_alt']:
		s=State.new(m);s.feedback(name);check(s.phase==name,'one-shot enters '+name);tick_to(s,'idle');check(s.phase=='idle','one-shot finishes '+name)
	for name in ['candy','night','pinch']:
		s=State.new(m);s.preview('sleep');tick_to(s,'sleep_loop');s.feedback(name);tick_to(s,name+'_enter' if name!='night' else name)
		check(s.phase==(name+'_enter' if name!='night' else name),'new feedback exits sleeping '+name)
	print('FEEDBACK_STATE ',checks,' checks, ',failures,' failures');quit(1 if failures else 0)
