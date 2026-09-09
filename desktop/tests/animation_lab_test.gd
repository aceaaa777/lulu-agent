extends SceneTree
var pet
var failures=0
var checks=0
func check(ok: bool,message: String):
	checks+=1
	if not ok:failures+=1;printerr('LAB_FAIL ',message)
func _initialize():call_deferred('run')
func run():
	pet=load('res://main.tscn').instantiate();root.add_child(pet);pet.set_process(false);pet.polling=true
	pet.lab.open();pet.lab.speed=2
	for item in pet.lab.ACTIONS:
		var action=str(item[1]);pet.lab.choose(action)
		var entered=false;var released=false;var done=false;var saw_hold=false
		for tick in range(1500):
			pet._process(1.0/24)
			var s=pet.lab.state
			if pet.lab.pending_action.is_empty():entered=true
			if s.phase.ends_with('_loop') or s.phase in ['work','sulk_hold','candy_hold','candy_close_hold','pinch_hold']:
				saw_hold=true
				if pet.lab.held_time>2 and not released:
					var before=s.frame;pet.lab.release_current();check(s.frame==before,'release preserves frame '+action);released=true
			if s.phase=='sleep_loop':check(s.frame>=pet.manifest.sleep_loop[0] and s.frame<=pet.manifest.sleep_loop[1],'sleep loop excludes waking pose')
			if entered and s.phase=='idle' and (action=='idle' or tick>10):done=true;break
			await process_frame
		check(entered and done,'full lifecycle '+action)
		if action in ['sleep','sleep_alt','read','task','sulk']:check(saw_hold,'held stage '+action)
		check(pet.frames.textures.size()<=1253,'bounded resident cache')
		print('LAB_ACTION ',action,' done=',done,' cache=',pet.frames.textures.size())
	pet.lab.start_action('read');pet.lab.state.advance(4);pet.lab.state.interact();pet.lab.state.advance(2)
	check(pet.lab.state.phase=='read_loop','test click preserves deep companionship')
	pet.lab.leave();check(not pet.lab.active and not pet.animation.quitting,'test close preserves real pet')
	pet.lab.start_sequence()
	for tick in range(15000):
		pet._process(1.0/24)
		if not pet.lab.automatic:break
		await process_frame
	check(not pet.lab.automatic and pet.lab.sequence_index==pet.lab.ACTIONS.size(),'automatic sequence finishes all actions')
	pet.lab.choose('sleep')
	for tick in range(1000):
		pet._process(1.0/24)
		if pet.lab.state.phase=='sleep_loop' and not pet.loading:break
		await process_frame
	pet.lab.paused=true;pet._process(1.0/24)
	await process_frame
	if DisplayServer.get_name()!='headless':
		await RenderingServer.frame_post_draw
		pet.lab.get_texture().get_image().save_png('res://../validation/v8/animation-panel.png')
		root.get_texture().get_image().save_png('res://../validation/v8/animation-pet.png')
	print('ANIMATION_LAB ',checks,' checks, ',failures,' failures')
	quit(1 if failures else 0)
