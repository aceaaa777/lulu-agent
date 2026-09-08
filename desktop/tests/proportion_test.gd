extends SceneTree
var failures=0
func check(ok: bool,message: String):
	if not ok:failures+=1;printerr('PROPORTION_FAIL ',message)
func _initialize():call_deferred('run')
func run():
	var pet=load('res://main.tscn').instantiate();root.add_child(pet);pet.set_process(false);pet.polling=true;pet.lab.open()
	for scale in [.75,1.0,1.25,1.5]:
		pet.set_pet_scale(scale)
		await process_frame;await process_frame
		print("SCALE_ACTUAL ",scale," ",root.size)
		check(root.size==Vector2i(roundi(528*scale),roundi(420*scale)),'both window dimensions use one scale '+str(scale))
		check(root.content_scale_size==Vector2i(528,420),'logical canvas stays fixed')
		check(root.content_scale_aspect==Window.CONTENT_SCALE_ASPECT_KEEP,'window preserves aspect ratio')
	check(pet.lab.reference_preview.stretch_mode==TextureRect.STRETCH_KEEP_ASPECT_CENTERED,'reference comparison keeps aspect')
	check(pet.lab.motion_preview.stretch_mode==TextureRect.STRETCH_KEEP_ASPECT_CENTERED,'animation comparison keeps aspect')
	pet.set_pet_scale(1.0)
	await process_frame;await RenderingServer.frame_post_draw
	print('PROPORTION_RENDER failures=',failures);quit(1 if failures else 0)
