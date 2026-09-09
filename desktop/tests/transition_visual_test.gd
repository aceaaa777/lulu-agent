extends SceneTree
var pet
var failures=0
func check(ok: bool,message: String):
	if not ok:failures+=1;printerr('VISUAL_FAIL ',message)
func _initialize():call_deferred('run')
func run():
	pet=load('res://main.tscn').instantiate();root.add_child(pet);pet.set_process(false);pet.polling=true
	pet.display_frame=int(pet.manifest.idle[0]);pet.blend_from=pet.display_frame
	for progress in [0.0,.25,.5,.75,1.0]:
		pet.blend_time=progress*.16;pet.queue_redraw()
		await process_frame;await RenderingServer.frame_post_draw
		var im=root.get_texture().get_image();var pixel=im.get_pixel(267,160)
		check(pixel.a>.99,'opaque body remains opaque at '+str(progress)+' alpha='+str(pixel.a))
	# Pin the currently visible frame while several rapid selections replace the prefetch target.
	pet.frames.pinned=['2822'];pet.frames.ensure('2822');pet.frames.ensure('7305');pet.frames.ensure('8290')
	check('2822' in pet.frames.recent,'visible scene stays resident on rapid switching')
	print('TRANSITION_VISUAL failures=',failures);quit(1 if failures else 0)
