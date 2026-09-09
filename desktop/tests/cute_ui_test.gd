extends SceneTree
var pet
var failures=0
func check(ok,message):
	if not ok:failures+=1;printerr('CUTE_UI_FAIL ',message)
func _initialize():call_deferred('run')
func run():
	pet=load('res://main.tscn').instantiate();root.add_child(pet);pet.set_process(false);pet.polling=true;pet.refreshing=true;pet.prompt.set_block_signals(true)
	await process_frame;await process_frame
	for size in [Vector2i(900,740),Vector2i(700,640)]:
		pet.panel.size=size
		for tab in range(pet.tabs.get_tab_count()):
			pet.tabs.current_tab=tab
			await process_frame;await process_frame
			var rect=pet.prompt.get_global_rect()
			check(pet.prompt.is_visible_in_tree(),'input visible on tab '+str(tab))
			check(rect.position.y>=0 and rect.end.y<pet.panel.size.y,'input fits '+str(size)+' tab '+str(tab)+' '+str(rect))
			check(pet.run_button.get_global_rect().end.y<pet.panel.size.y,'send button fits '+str(size)+' tab '+str(tab))
		pet.tabs.current_tab=0;pet.prompt.grab_focus();pet.prompt.text=''
		var key=InputEventKey.new();key.pressed=true;key.keycode=KEY_A;key.unicode=97;pet.panel.push_input(key)
		await process_frame
		check(pet.prompt.text=='a','keyboard input reaches composer '+str(size))
		pet.prompt.text='帮我整理一份明天的学习计划。'
		await process_frame;await RenderingServer.frame_post_draw
		pet.panel.get_texture().get_image().save_png('res://../validation/cute-ui/panel-'+str(size.x)+'.png')
	pet.pet_status.text='我在这里，随时叫我';pet.display_frame=int(pet.manifest.idle[0]);pet.blend_from=pet.display_frame;pet.blend_time=1;pet.queue_redraw()
	await process_frame;await RenderingServer.frame_post_draw
	var im=root.get_texture().get_image();im.save_png('res://../validation/cute-ui/pet.png')
	check(im.get_pixel(10,10).a<.01,'desktop remains transparent')
	check(im.get_pixel(264,344).a>.95,'generated frame is displayed')
	var s=pet.AnimationState.new(pet.manifest);s.start_drag();s.advance(1.0)
	check(s.phase=='pinch_hold','pinch reaches hold within one second')
	s.advance(5);check(s.phase=='pinch_hold','drag remains held')
	s.end_drag();s.advance(.05);check(s.phase=='pinch_exit','release begins tail')
	s.advance(1.0);check(s.phase=='pinch_exit','tail is not accelerated');s.advance(.6);check(s.phase=='idle','tail finishes without ice')
	print('CUTE_UI failures=',failures);quit(1 if failures else 0)
