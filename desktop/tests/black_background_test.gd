extends SceneTree
var failures=0
func check(ok: bool, message: String):
	if not ok:failures+=1;printerr('BLACK_BACKGROUND_FAIL ',message)
func _initialize():call_deferred('run')
func run():
	var pet=load('res://main.tscn').instantiate();root.add_child(pet);pet.set_process(false);pet.polling=true;pet.lab.open()
	pet.display_frame=int(pet.manifest.idle[0]);pet.blend_from=pet.display_frame;pet.blend_time=1;pet.lab.update(0);pet.queue_redraw()
	for color in [Color.BLACK,Color.WHITE,Color('#f3ece1')]:
		pet.lab.set_inspection_background(color)
		await process_frame;await RenderingServer.frame_post_draw
		var actual=root.get_texture().get_image().get_pixel(5,5)
		check(actual.is_equal_approx(color),'desktop canvas uses requested opaque inspection background')
		check(pet.lab.reference_preview.stretch_mode==TextureRect.STRETCH_KEEP_ASPECT_CENTERED,'reference keeps aspect')
		check(pet.lab.motion_preview.stretch_mode==TextureRect.STRETCH_KEEP_ASPECT_CENTERED,'motion keeps aspect')
	pet.lab.set_inspection_background(Color.BLACK)
	await process_frame;await RenderingServer.frame_post_draw
	pet.lab.get_texture().get_image().save_png('res://.local/black-panel.png')
	pet.lab.leave();pet.queue_redraw()
	await process_frame;await RenderingServer.frame_post_draw
	check(root.get_texture().get_image().get_pixel(5,5).a<.01,'normal companion restores transparency')
	print('BLACK_BACKGROUND failures=',failures);quit(1 if failures else 0)
