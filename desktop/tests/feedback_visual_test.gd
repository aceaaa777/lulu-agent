extends SceneTree
var failures=0
var checks=0
func check(ok: bool,message: String):
	checks+=1
	if not ok:failures+=1;printerr('FEEDBACK_VISUAL_FAIL ',message)
func _initialize():call_deferred('run')
func run():
	var pet=load('res://main.tscn').instantiate();root.add_child(pet);pet.set_process(false);pet.polling=true;pet.lab.open()
	var m=pet.manifest;var reference=int(m.idle[0])
	var targets=[['pinch',m.pinch_hold[0]],['candy',m.candy_hold[0]],['candy_close',m.candy_close_hold[0]],['night',m.night[0]+80],['thinking',m.thinking_loop[0]],['thinking_done',m.thinking_done[0]+40],['blocked',m.blocked_loop[0]],['resolved',m.resolved[0]+35],['complete',m.complete[0]+55],['complete_alt',m.complete_alt[0]+55],['sign_edge_cn',m.complete[0]+96],['sign_edge_en',m.complete_alt[0]+28]]
	for item in targets:
		var frame=int(item[1]);var group=str(pet.frames.groups[frame]);pet.frames.pinned=[group,str(pet.frames.groups[reference])];pet.frames.ensure(group)
		while not pet.frames.ready(group):pet.frames.pump();await process_frame
		var rect=pet.frames.display_rect(frame)
		check(absf(rect.z/rect.w-16.0/9.0)<0.001,'native ratio '+item[0])
		pet.display_frame=frame;pet.blend_from=reference
		for progress in [0.0,.25,.5,.75,1.0]:
			pet.blend_time=progress*.16;pet.queue_redraw();pet.lab.update(0)
			await process_frame;await RenderingServer.frame_post_draw
			var im=root.get_texture().get_image()
			check(im.get_pixel(264,170).a>.98,'opaque body '+item[0]+' '+str(progress))
			check(im.get_pixel(10,10).a<.02,'transparent surroundings '+item[0])
		root.get_texture().get_image().save_png('res://../validation/v8/feedback-'+item[0]+'.png')
		if item[0]=='candy':pet.lab.get_texture().get_image().save_png('res://../validation/v8/feedback-panel.png')
	print('FEEDBACK_VISUAL ',checks,' checks, ',failures,' failures');quit(1 if failures else 0)
